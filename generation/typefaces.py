"""Local, licensed typefaces embedded into exported CSS. No network dependency."""
import base64
from functools import lru_cache
from pathlib import Path

ASSETS=Path(__file__).resolve().parents[1]/'design-assets'
CATALOGUE={
    'geist':('LE Geist','geist-latin.woff2','geist-OFL.txt','normal','100 900'),
    'bricolage':('LE Bricolage','bricolage-grotesque-latin.woff2','bricolage-OFL.txt','normal','200 800'),
    'instrument':('LE Instrument','instrument-serif-latin.woff2','instrument-serif-OFL.txt','normal','400'),
    'instrument-italic':('LE Instrument','instrument-serif-italic-latin.woff2','instrument-serif-OFL.txt','italic','400'),
}


@lru_cache(maxsize=3)
def embedded_typefaces(theme):
    choices={'clair':('geist',),'contraste':('geist','bricolage'),
             'editorial':('geist','instrument','instrument-italic')}
    if theme not in choices:raise ValueError('Thème typographique inconnu.')
    rules=[];licenses=set()
    for key in choices[theme]:
        family,filename,license_file,style,weight=CATALOGUE[key]
        raw=(ASSETS/filename).read_bytes()
        if not raw.startswith(b'wOF2'):raise OSError('La police locale est invalide.')
        if license_file not in licenses:
            # The complete redistributable license travels inside styles.css.
            license_text=(ASSETS/license_file).read_text(encoding='utf-8').replace('*/','* /')
            rules.append('/* LocalExpand typeface license: '+filename+'\n'+license_text+'\n*/')
            licenses.add(license_file)
        encoded=base64.b64encode(raw).decode('ascii')
        rules.append(f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{encoded}) format('woff2');font-style:{style};font-weight:{weight};font-display:swap}}")
    display={'clair':'LE Geist','editorial':'LE Instrument','contraste':'LE Bricolage'}[theme]
    rules.append(f":root{{--body-font:'LE Geist',Arial,sans-serif;--display-font:'{display}',{'Georgia,serif' if theme=='editorial' else 'Arial,sans-serif'}}}")
    return '\n'.join(rules)
