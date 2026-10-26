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


def build(output):
    if output.exists():shutil.rmtree(output)
    output.mkdir(parents=True)
    cards=[]
    for key,label,city in EXAMPLES:
        data=json.loads((ROOT/'generation/fixtures'/f'{key}.json').read_text(encoding='utf-8'))
        data['phone']=PHONES[key]
        draft=prepare_essential(BusinessProfile.from_dict(data),demo=True)
        report=export_essential(draft,output/key,assets_root=ROOT/'exemples')
        (output/key/'qualite.json').unlink()
        cards.append(f'<a href="{key}/index.html"><strong>{escape(data["name"])}</strong><span>{escape(label)} · {escape(city)}</span><small>{report["structure"]["passed"] and "Contrôles structurels réussis" or "À vérifier"}</small></a>')
    (output/'index.html').write_text(f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LocalExpand — exemples de sites générés</title>
<style>body{{margin:0;font:16px/1.6 system-ui,sans-serif;background:#141c21;color:#f4f5ef}}main{{max-width:880px;margin:auto;padding:72px 24px}}h1{{font-size:clamp(36px,6vw,64px);line-height:1.05;letter-spacing:-.04em;margin:0 0 16px}}p{{color:#bcc8cb;max-width:60ch}}nav{{display:grid;gap:14px;margin-top:40px}}a{{display:grid;gap:4px;padding:22px 26px;border:1px solid #ffffff26;border-radius:14px;color:inherit;text-decoration:none;background:#202a30}}a:hover{{border-color:#f2ca55}}strong{{font-size:22px}}span{{color:#f2ca55}}small{{color:#bcc8cb}}</style></head>
<body><main><h1>Sites générés par LocalExpand</h1><p>Trois entreprises fictives, une seule fiche par entreprise : le moteur choisit la mise en page, les icônes et les couleurs. Aucun site n’a été retouché à la main.</p><nav>{"".join(cards)}</nav></main></body></html>''',encoding='utf-8')


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
    build(output)
    print('Sites générés dans docs/')
    if args.captures:
        captures(output,ROOT/'captures');print('Captures dans captures/')
    if args.verifier:
        from generation.browser_quality import inspect_site
        for key,_,_ in EXAMPLES:
            result=inspect_site(output/key)
            print(key,'contrôle navigateur réussi' if result['completed'] and result['passed'] else 'contrôle navigateur à revoir')


if __name__=='__main__':main()
