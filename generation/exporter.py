"""Self-contained, immutable Essentiel packages. No fetches or publication."""
import base64
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import zipfile
import re

from bs4 import BeautifulSoup

from .essential import render_essential
from .profile import ProfileError, image_source
from .quality import check_document


def write_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def export_essential(draft, destination, *, assets_root=None):
    """Resolve every image before creating a new destination; never overwrite."""
    result=render_essential(draft)
    if not result.document:
        raise ProfileError('render','; '.join(issue.message for issue in result.issues))
    soup=BeautifulSoup(result.document,'html.parser')
    resources={}
    for image in soup.select('img'):
        src=image_source(image['src'],'image')
        if src.startswith('data:'):
            header,encoded=src.split(',',1)
            extension=header.split('/')[1].split(';')[0]
            raw=base64.b64decode(encoded,validate=True)
        else:
            if assets_root is None:raise ProfileError('image','Le dossier des ressources locales est absent.')
            root=Path(assets_root).resolve()
            source=(root/src).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                raise ProfileError('image','Une ressource locale est absente ou sort du dossier autorisé.')
            if source.stat().st_size>8*1024*1024:raise ProfileError('image','Image supérieure à 8 Mo.')
            raw=source.read_bytes()
            extension=source.suffix.lower()[1:].replace('jpg','jpeg')
            image_source(f'data:image/{extension};base64,'+base64.b64encode(raw).decode(),'image')
        name='assets/'+hashlib.sha256(raw).hexdigest()[:24]+'.'+extension.replace('jpeg','jpg')
        resources[name]=raw
        image['src']=name
    css='\n'.join(node.get_text() for node in soup.select('style'))
    for node in soup.select('style'):node.decompose()
    soup.head.append(soup.new_tag('link',rel='stylesheet',href='styles.css'))
    csp=soup.select_one('meta[http-equiv="Content-Security-Policy"]')
    csp['content']=csp['content'].replace("style-src 'unsafe-inline'","style-src 'self' 'unsafe-inline'")
    html=str(soup)
    quality=check_document(html,{'styles.css':css})
    if not quality.passed:raise ProfileError('quality','Le contrôle structurel de l’export a échoué.')
    # No delivery claim: software checks cannot certify business/legal facts.
    report={'version':1,'engine':'essentiel-v1','design_version':'essentiel-phase-d-v1','demo':draft.demo,'theme':draft.theme,
        'status':'generated','delivery_ready':False,'internal_preview':draft.internal_preview,
        'structure':{'passed':quality.passed,'checks':[asdict(item) for item in quality.checks]},
        'resources':{'passed':True,'images':len(resources),'external_dependencies':0},
        'browser':{'completed':False,'passed':False,'reason':'Contrôle navigateur non exécuté.'},
        'sections':[asdict(item) for item in draft.plan.sections],
        'decisions':list(draft.decisions),'copy_sources':dict(draft.copy_sources),
        'warnings':[asdict(item) for item in result.issues if item.severity=='warning'],
        'remaining':['Valider les contenus et les droits sur les images avec l’entreprise.',
                     'Vérifier la propriété et la réception des coordonnées de contact.',
                     'Renseigner et valider les mentions légales avant toute publication.',
                     'Choisir le domaine et contrôler l’hébergement HTTPS.']}
    if draft.demo:report['remaining'].insert(0,'Entreprise fictive : démonstration uniquement, contacts .test non distribuables.')
    if draft.internal_preview:
        report['remaining'][:0]=['Maquette interne non officielle : cette entreprise n’est pas cliente de LocalExpand.',
            'Illustrations temporaires : elles ne représentent pas l’entreprise. Usage de test privé uniquement ; droits commerciaux à établir ou photos à remplacer.']
    folder=Path(destination)
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'index.html').write_text(html,encoding='utf-8')
    (folder/'styles.css').write_text(css,encoding='utf-8')
    if resources:(folder/'assets').mkdir()
    for name,raw in resources.items():(folder/name).write_bytes(raw)
    write_json(folder/'qualite.json',report)
    return report


def zip_export(folder, destination):
    """Whitelist only generated public resources; no profiles, accounts or DB."""
    folder=Path(folder)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in ['index.html','styles.css','qualite.json']:
            archive.write(folder/name,name)
        for source in sorted((folder/'assets').glob('*')):
            if source.is_file():archive.write(source,'assets/'+source.name)


def check_archive(source):
    """Verify whitelist, referenced assets, embedded fonts and offline structure."""
    with zipfile.ZipFile(source) as archive:
        names=archive.namelist()
        allowed=all(name in {'index.html','styles.css','qualite.json'} or
                    re.fullmatch(r'assets/[a-f0-9]{24}\.(?:png|jpg|webp)',name) for name in names)
        required={'index.html','styles.css','qualite.json'}<=set(names)
        checks={'whitelist':allowed,'required_files':required,'unique_entries':len(names)==len(set(names)),
                'crc':archive.testzip() is None}
        if not required:return {'passed':False,'checks':checks}
        html=archive.read('index.html').decode('utf-8');css=archive.read('styles.css').decode('utf-8')
        soup=BeautifulSoup(html,'html.parser')
        used={img['src'] for img in soup.select('img')}
        checks['all_images_packaged']=used<=set(names)
        checks['no_unused_images']={name for name in names if name.startswith('assets/')}==used
        checks['embedded_fonts']=bool(re.search(r'url\(data:font/woff2;base64,',css))
        checks['font_licenses']='SIL' in css or 'OFL' in css
        checks['offline_structure']=check_document(html,{'styles.css':css},preview=False).passed
        return {'passed':all(checks.values()),'checks':checks,'files':names}
