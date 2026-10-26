"""Build the three fictional example sites in docs/, ready for GitHub Pages.

python generer_exemples.py            # sites + demo page
python generer_exemples.py --captures # also screenshots in captures/ (Playwright)
python generer_exemples.py --verifier # also the full browser quality check
"""
import argparse
from html import escape
import json
from pathlib import Path
import shutil

from generation.essential import prepare_essential
from generation.exporter import export_essential
from generation.profile import BusinessProfile

ROOT=Path(__file__).resolve().parent
EXAMPLES=[('plombier','Plomberie','Marseille'),('garage','Garage automobile','Lyon'),('nettoyage','Nettoyage professionnel','Montpellier')]
# Fictional numbers: ARCEP range reserved for works of fiction.
PHONES={'plombier':'04 65 71 00 01','garage':'04 65 71 00 02','nettoyage':'04 65 71 00 03'}


REPOSITORY='https://github.com/lesuperf/localexpand-generateur'


def build(output):
    if output.exists():shutil.rmtree(output)
    output.mkdir(parents=True)
    sites=[]
    for key,label,city in EXAMPLES:
        data=json.loads((ROOT/'generation/fixtures'/f'{key}.json').read_text(encoding='utf-8'))
        data['phone']=PHONES[key]
        draft=prepare_essential(BusinessProfile.from_dict(data),demo=True)
        report=export_essential(draft,output/key,assets_root=ROOT/'exemples')
        (output/key/'qualite.json').unlink()
        sites.append({'key':key,'name':data['name'],'trade':f'{label} · {city}','accent':draft.profile.visuals.primary,
                      'passed':report['structure']['passed']})
    return sites


def thumbnails(output):
    """Small JPEG previews for the showcase cards; skipped without Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    (output/'apercus').mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        page=browser.new_page(viewport={'width':1280,'height':800})
        for key,_,_ in EXAMPLES:
            page.goto((output/key/'index.html').as_uri(),wait_until='load')
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(output/'apercus'/f'{key}.jpg'),type='jpeg',quality=78)
        browser.close()
    return True


def showcase(output,sites):
    shutil.copy2(ROOT/'exemples/vitrine.css',output/'vitrine.css')
    cards=[]
    for site in sites:
        shot=output/'apercus'/f'{site["key"]}.jpg'
        image=f'<div class="shot"><img src="apercus/{site["key"]}.jpg" alt="" width="1280" height="800" loading="lazy"></div>' if shot.exists() else ''
        status='Contrôles qualité réussis' if site['passed'] else 'À vérifier'
        cards.append(f'<a class="card" style="--accent:{site["accent"]}" href="{site["key"]}/index.html">{image}<div class="body"><strong>{escape(site["name"])}</strong><span class="trade">{escape(site["trade"])}</span><small>{status}</small></div></a>')
    (output/'index.html').write_text(f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LocalExpand — exemples de sites générés</title><meta name="description" content="Trois sites vitrines générés automatiquement par LocalExpand à partir d’une simple fiche entreprise."><link rel="stylesheet" href="vitrine.css"></head>
<body><main><p class="eyebrow">Générateur de sites · Exemples</p><h1>Sites générés par <em>LocalExpand</em></h1>
<p class="intro">Trois entreprises fictives, une seule fiche par entreprise. Le moteur choisit la mise en page, les icônes et les couleurs, puis vérifie chaque site dans un vrai navigateur. Aucun site n’a été retouché à la main.</p>
<div class="actions"><a class="btn" href="#exemples">Voir les exemples <span aria-hidden="true">↓</span></a><a class="btn ghost" href="{REPOSITORY}">Voir le code sur GitHub <span aria-hidden="true">↗</span></a></div>
<ul class="stats"><li><strong>3</strong>métiers différents</li><li><strong>0</strong>retouche manuelle</li><li><strong>5</strong>largeurs d’écran contrôlées</li><li><strong>0</strong>ligne de JavaScript dans les sites</li></ul>
<nav class="grid" id="exemples" aria-label="Exemples de sites">{"".join(cards)}</nav></main>
<footer>Entreprises, coordonnées et illustrations fictives · © 2026 Florian Husaj</footer></body></html>''',encoding='utf-8')


def captures(output,folder):
    from playwright.sync_api import sync_playwright
    folder.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        for key,_,_ in EXAMPLES:
            for name,size in [('ordinateur',{'width':1440,'height':900}),('mobile',{'width':390,'height':844})]:
                page=browser.new_page(viewport=size,device_scale_factor=1 if name=='ordinateur' else 2)
                page.goto((output/key/'index.html').as_uri(),wait_until='load')
                page.evaluate('document.fonts.ready')
                page.screenshot(path=str(folder/f'{key}-{name}.png'))
                page.close()
        browser.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--captures',action='store_true')
    parser.add_argument('--verifier',action='store_true')
    args=parser.parse_args()
    output=ROOT/'docs'
    sites=build(output)
    if not thumbnails(output):print('Playwright absent : page d’accueil sans aperçus.')
    showcase(output,sites)
    print('Sites générés dans docs/')
    if args.captures:
        captures(output,ROOT/'captures');print('Captures dans captures/')
    if args.verifier:
        from generation.browser_quality import inspect_site
        for key,_,_ in EXAMPLES:
            result=inspect_site(output/key)
            print(key,'contrôle navigateur réussi' if result['completed'] and result['passed'] else 'contrôle navigateur à revoir')


if __name__=='__main__':main()
