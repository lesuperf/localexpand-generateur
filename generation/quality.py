"""Bounded structural checks for foundation previews, not delivery certification."""
from dataclasses import dataclass
import base64
import binascii
import json
import re

from bs4 import BeautifulSoup

from .profile import ProfileError, ValidationIssue, image_source


@dataclass(frozen=True)
class CheckResult:
    code: str
    passed: bool


@dataclass(frozen=True)
class QualityReport:
    checks: tuple[CheckResult, ...]
    issues: tuple[ValidationIssue, ...]

    @property
    def passed(self):
        return all(check.passed for check in self.checks) and not any(issue.severity=='error' for issue in self.issues)


def css_balanced(styles):
    """Detect unclosed CSS delimiters/strings; this is not a full CSS validator."""
    stack, quote, escaped, comment = [], '', False, False
    pairs = {'}':'{',')':'(',']':'['}
    index=0
    while index<len(styles):
        char=styles[index]
        pair=styles[index:index+2]
        index+=1
        if comment:
            if pair=='*/':comment=False;index+=1
            continue
        if escaped:
            escaped=False
        elif char=='\\':
            escaped=True
        elif quote:
            if char==quote:quote=''
        elif char in {'"',"'"}:
            quote=char
        elif pair=='/*':
            comment=True;index+=1
        elif char in '{([':
            stack.append(char)
        elif char in '})]':
            if not stack or stack.pop()!=pairs[char]:return False
    return not stack and not quote and not escaped and not comment


def css_without_remote_resources(styles):
    """Only valid embedded WOFF2 fonts are allowed as CSS URL resources."""
    def font(match):
        try:
            raw=base64.b64decode(match[1],validate=True)
            return '' if 48<=len(raw)<=2*1024*1024 and raw.startswith(b'wOF2') else match[0]
        except (ValueError,binascii.Error):return match[0]
    stripped=re.sub(r'url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)',font,styles)
    return not re.search(r'@import|url\s*\(|image-set\s*\(',stripped,re.I)


def check_document(document, local_styles=None, *, preview=True):
    local_styles=local_styles or {}
    soup = BeautifulSoup(document,'html.parser')
    ids = [node['id'] for node in soup.select('[id]')]
    id_set=set(ids)
    checks,issues=[],[]

    def check(code,condition,message):
        checks.append(CheckResult(code,bool(condition)))
        if not condition:issues.append(ValidationIssue('document',code,message))

    check('language',bool(soup.html and soup.html.get('lang')=='fr'),'La langue du document est absente.')
    check('main',len(soup.select('main'))==1,'La page doit contenir un seul contenu principal.')
    check('h1',len(soup.select('h1'))==1,'La page doit contenir un seul titre principal.')
    check('unique_ids',len(ids)==len(id_set),'Les identifiants HTML doivent être uniques.')
    check('anchors',all(a['href'][1:] in id_set for a in soup.select('a[href^="#"]')),'Un lien interne pointe vers une section absente.')
    check('links',all(node.get('href','').strip() for node in soup.select('a')),'Un lien n’a pas de destination.')
    check('title',bool(soup.title and soup.title.get_text(strip=True)),'Le titre SEO est absent.')
    description=soup.select_one('meta[name="description"]')
    check('description',bool(description and description.get('content','').strip()),'La description SEO est absente.')
    check('viewport',bool(soup.select_one('meta[name="viewport"]')),'La balise viewport est absente.')
    robots=soup.select_one('meta[name="robots"]')
    if preview:
        check('preview_noindex',bool(robots and 'noindex' in robots.get('content','')),'L’aperçu doit rester non indexable.')
    check('images_alt',all(node.has_attr('alt') for node in soup.select('img')),'Une image ne possède pas d’alternative textuelle.')
    check('labels',all(node.get('id') and soup.find('label',attrs={'for':node['id']}) for node in soup.select('input:not([type="hidden"]),textarea,select')),'Un champ ne possède pas de libellé associé.')
    check('aria_references',all(target in id_set for node in soup.select('[aria-labelledby],[aria-describedby]') for attr in ['aria-labelledby','aria-describedby'] for target in node.get(attr,'').split()),'Une référence d’accessibilité est absente.')
    check('buttons',all(node.get_text(strip=True) or node.get('aria-label') for node in soup.select('button')),'Un bouton n’a pas de nom accessible.')
    check('forms_inert',all(not form.get('action') and all(control.has_attr('disabled') or control.find_parent('fieldset',disabled=True) for control in form.select('input,textarea,select,button')) for form in soup.select('form')),'Un formulaire de l’aperçu pourrait transmettre des données.')
    check('no_executable_script',all(node.get('type')=='application/ld+json' for node in soup.select('script')) and not any(attr.lower().startswith('on') for node in soup.find_all(True) for attr in node.attrs),'Du code exécutable non prévu est présent.')
    check('safe_links',all(re.match(r'^(?:#[a-z]|https?://|tel:\+?\d|mailto:)',node.get('href','')) for node in soup.select('a')),'Un lien utilise un protocole non autorisé.')
    check('no_remote_dependencies',not soup.select('iframe,object,embed,script[src]') and all(node.get('rel')==['stylesheet'] and node.get('href') in local_styles for node in soup.select('link[href]')),'L’aperçu contient une dépendance externe non prévue.')
    image_valid=True
    for i,img in enumerate(soup.select('img')):
        try:image_source(img.get('src',''),f'images.{i}')
        except ProfileError:image_valid=False
    check('image_sources',image_valid,'Une source d’image n’est pas autorisée.')
    styles='\n'.join(node.get_text() for node in soup.select('style'))
    styles+='\n'+'\n'.join(local_styles.values())
    styles+='\n'+'\n'.join(node['style'] for node in soup.select('[style]'))
    check('css_structure',bool(styles) and css_balanced(styles),'Les délimiteurs CSS ne sont pas équilibrés.')
    check('css_no_imports',css_without_remote_resources(styles),'Une dépendance CSS externe est présente.')
    check('reduced_motion','prefers-reduced-motion' in styles,'La préférence de mouvement réduit n’est pas prise en compte.')
    try:
        structured=[json.loads(node.string or '') for node in soup.select('script[type="application/ld+json"]')]
        schema_valid=len(structured)==1 and structured[0].get('@type')=='LocalBusiness' and bool(structured[0].get('name'))
    except (ValueError,AttributeError):schema_valid=False
    check('structured_data',schema_valid,'Les données structurées sont absentes ou invalides.')
    return QualityReport(tuple(checks),tuple(issues))
