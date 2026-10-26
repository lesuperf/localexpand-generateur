"""Assemble an explicitly planned technical preview. No workflow, storage or API.

This is the low-level integration seam. Phase C automatic content and
composition live in essential.py; private workflow/storage live in projects.py.
"""
from dataclasses import dataclass
from html import escape
import json
from pathlib import Path

from .components import ComponentContext, IDS, LABEL_KEYS, available, render_component
from .composition import PagePlan
from .content import PageContent
from .profile import BusinessProfile, ProfileError, ValidationIssue, profile_issues
from .quality import QualityReport, check_document
from .themes import resolve_theme
from .typefaces import embedded_typefaces

ENGINE_VERSION = 'components-foundation-v1'


@dataclass(frozen=True)
class PreviewResult:
    document: str | None
    status: str
    issues: tuple[ValidationIssue, ...]
    quality: QualityReport | None = None

    @property
    def delivery_ready(self):
        # No technical preview is silently promoted to a validated customer site.
        return False


def build_preview(profile: BusinessProfile, plan: PagePlan, content: PageContent | None = None, *, theme='', contact_mode='preview', notice=None) -> PreviewResult:
    """Render only a supplied plan; never infer facts, fetch data or write files."""
    issues=[]
    try:
        if not isinstance(profile,BusinessProfile) or not isinstance(plan,PagePlan):
            raise ProfileError('request','Une fiche entreprise et un plan de page sont attendus.')
        content=content if content is not None else PageContent()
        context=ComponentContext(profile,content,contact_mode=contact_mode)
        profile,content=context.profile,context.content
        issues.extend(profile_issues(profile))
        if 'hero' not in [section.component for section in plan.sections]:
            issues.append(ValidationIssue('page.sections','missing_hero','Le plan de cet aperçu nécessite un composant Hero.'))
        if any(issue.severity=='error' for issue in issues):
            return PreviewResult(None,'incomplete',tuple(issues))
        visual=resolve_theme(theme,profile.visuals)
        selected=[]
        for section in plan.sections:
            if available(section.component,profile):
                selected.append(section)
            else:
                issues.append(ValidationIssue('sections.'+section.component,'omitted','Section omise : aucune donnée fournie.','warning'))
        navigation=tuple((getattr(content,LABEL_KEYS[section.component]),IDS[section.component]) for section in selected if section.component in LABEL_KEYS)
        context=ComponentContext(profile,content,navigation,contact_mode)
        fragments=[(section.component,render_component(section.component,context,section.selected_variant)) for section in selected]
        head=''.join(fragment for name,fragment in fragments if name=='header')
        foot=''.join(fragment for name,fragment in fragments if name=='footer')
        main=''.join(fragment for name,fragment in fragments if name not in {'header','footer'})
        title=content.seo_title or f'{profile.name} — {profile.profession}' + (' · '+profile.city if profile.city else '')
        description=content.seo_description or ' '.join(profile.description.split())[:160]
        schema={'@context':'https://schema.org','@type':'LocalBusiness','name':profile.name}
        if profile.phone:schema['telephone']=profile.phone
        if profile.email:schema['email']=profile.email
        if profile.areas or profile.city:schema['areaServed']=list(profile.areas) or [profile.city]
        # Supplied facts only, to help local search engines read the page.
        extras=dict(profile.additional_information)
        schema['description']=' '.join(profile.description.split())[:300]
        if extras.get('adresse'):schema['address']=extras['adresse']
        if profile.website:schema['url']=profile.website
        if profile.services:schema['makesOffer']=[{'@type':'Offer','itemOffered':{'@type':'Service','name':item.title}} for item in profile.services]
        jsonld=json.dumps(schema,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
        css=visual.css_variables()+'\n'+Path(__file__).with_name('styles.css').read_text(encoding='utf-8')
        if contact_mode=='direct':
            css+='\n'+Path(__file__).with_name('essential.css').read_text(encoding='utf-8')
            css+='\n'+Path(__file__).with_name('essential-design.css').read_text(encoding='utf-8')
            css+='\n'+embedded_typefaces(visual.key)
        if notice is not None and (not isinstance(notice,str) or len(notice)>300):
            raise ProfileError('notice','Le texte d’aperçu est invalide.')
        note='Aperçu technique · Contenus à valider · Aucun envoi de formulaire' if notice is None else notice
        document=f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex, nofollow"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>{escape(title)}</title><meta name="description" content="{escape(description,quote=True)}"><script type="application/ld+json">{jsonld}</script><style>{css}</style></head><body class="le-page" data-renderer="{ENGINE_VERSION}" data-theme="{visual.key}"><a class="le-skip" href="#contenu">Aller au contenu</a><div class="le-preview-note">Aperçu technique · Contenus à valider · Aucun envoi de formulaire</div>{head}<main id="contenu" tabindex="-1">{main}</main>{foot}</body></html>'''
        if contact_mode=='direct':
            document=document.replace("img-src 'self' data:;", "img-src 'self' data:; font-src data:;",1)
            document=document.replace('class="le-page"','class="le-page le-essential"',1)
            document=document.replace('Aperçu technique · Contenus à valider · Aucun envoi de formulaire',escape(note),1)
        quality=check_document(document)
        issues.extend(quality.issues)
        remaining='Aperçu : validation des contenus, des coordonnées et des mentions légales nécessaire.' if contact_mode=='direct' else 'Aperçu technique : contrôle visuel et finalisation du contact restent nécessaires.'
        issues.append(ValidationIssue('preview','not_delivery',remaining,'warning'))
        if not quality.passed:return PreviewResult(None,'incomplete',tuple(issues),quality)
        return PreviewResult(document,'generated',tuple(issues),quality)
    except ProfileError as error:
        return PreviewResult(None,'incomplete',tuple(issues)+(ValidationIssue(error.field,'invalid',str(error)),))
    except OSError:
        return PreviewResult(None,'incomplete',tuple(issues)+(ValidationIssue('renderer','unavailable','Une ressource du moteur est indisponible.'),))
