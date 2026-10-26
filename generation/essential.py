"""Automatic one-page Essentiel composition and fact-based copy, with no API."""
from dataclasses import dataclass, replace
import re
import unicodedata

from .composition import PagePlan, SectionPlan
from .content import PageContent
from .engine import PreviewResult, build_preview
from .profile import BusinessProfile, ProfileError, Service, VisualPreferences, profile_issues
from .themes import resolve_theme


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFD',value.lower()) if unicodedata.category(c)!='Mn')


def activity_family(profession):
    """A vocabulary/theme hint, never a separate profession renderer."""
    value=normalized(profession)
    if re.search(r'\b(garage|automobile|mecanique|carrosserie)\b',value):return 'atelier'
    if re.search(r'\b(nettoyage|proprete|entretien de locaux)\b',value):return 'lieux'
    if re.search(r'\b(plombier|plomberie|sanitaire|chauffagiste)\b',value):return 'habitat'
    return 'local'


def french_list(items):
    items=list(items)
    return items[0] if len(items)==1 else ', '.join(items[:-1])+' et '+items[-1]


def service_summary(profile):
    """Hero lead built only from supplied services and zones, so the full
    description stays in the About section instead of being repeated."""
    if len(profile.services)<2:return ''
    titles=[item.title for item in profile.services]
    # Keep acronyms (« VMC ») but lowercase ordinary titles after the first.
    titles=titles[:1]+[t if len(t)>1 and t[1].isupper() else t[0].lower()+t[1:] for t in titles[1:]]
    zones=profile.areas or ((profile.city,) if profile.city else ())
    location=(' à '+french_list(zones[:3])+(' et alentours' if len(zones)>3 else '')) if zones else ''
    summary=french_list(titles)+location+'.'
    return summary if len(summary)<=240 else ''


@dataclass(frozen=True)
class EssentialDraft:
    profile: BusinessProfile
    content: PageContent
    plan: PagePlan
    theme: str
    decisions: tuple[str, ...]
    copy_sources: tuple[tuple[str, str], ...]
    demo: bool = False
    internal_preview: bool = False


def prepare_essential(profile, *, theme='auto', demo=False, internal_preview=False):
    if not isinstance(profile,BusinessProfile):
        raise ProfileError('profile','Une fiche entreprise commune est attendue.')
    if type(demo) is not bool:
        raise ProfileError('demo','Le mode démonstration doit être explicite.')
    if type(internal_preview) is not bool or (demo and internal_preview):
        raise ProfileError('internal_preview','Choisissez une fiche fictive ou une maquette interne d’entreprise réelle.')
    profile=BusinessProfile.from_dict(profile.to_dict())
    # Reserved rendering marker: only the explicit mode controls this flag.
    extras=tuple((key,value) for key,value in profile.additional_information if key!='maquette_interne')
    if internal_preview:extras+=(('maquette_interne','oui'),)
    profile=replace(profile,additional_information=extras)
    missing=[issue for issue in profile_issues(profile) if issue.severity=='error']
    if missing:raise ProfileError(missing[0].field,missing[0].message)
    family=activity_family(profile.profession)
    preferred=profile.visuals.theme
    # Contraste is the house style for every activity; Clair and Éditorial
    # remain available as explicit choices.
    automatic='contraste'
    chosen=(preferred or automatic) if theme=='auto' else theme
    if chosen not in {'clair','editorial','contraste'}:
        raise ProfileError('theme','Choisissez Automatique, Clair, Éditorial ou Contraste.')
    # Bright accents readable on the dark Contraste paper, one per activity family.
    palettes={'habitat':('#5cc8ff','#1d3a4b'),'atelier':('#efbd70','#35434d'),'lieux':('#7fe0b4','#21423a')}
    base_primary,base_accent=palettes.get(family,('',''))
    # Palette defaults follow the chosen theme; only automatic selection suggests
    # an activity palette. Explicit user colors always take precedence.
    use_activity=theme=='auto' and not preferred
    visuals=VisualPreferences(profile.visuals.primary or (base_primary if use_activity else ''),
                              profile.visuals.accent or (base_accent if use_activity else ''),chosen)
    resolve_theme(chosen,visuals)
    sources=[]
    services=[]
    for i,item in enumerate(profile.services):
        description=item.description or f'Vous avez un besoin en {item.title.lower()} ? Contactez {profile.name} pour préciser votre demande.'
        services.append(Service(item.title,description))
        sources.append((f'services.{i}.description','fourni' if item.description else 'titre du service + nom de l’entreprise'))
    # No FAQ is generated: questions restating the services and contacts
    # already on the page added length without information.
    profile=replace(profile,services=tuple(services),visuals=visuals)
    # Revalidate generated lengths and shapes before rendering.
    profile=BusinessProfile.from_dict(profile.to_dict())
    headline=profile.headline or (profile.profession + (' à '+profile.city if profile.city else ''))[:180]
    summary=service_summary(profile)
    paragraph=profile.description.split('\n\n')[0]
    introduction=summary or (paragraph if len(paragraph)<=300 else paragraph[:297].rsplit(' ',1)[0]+'…')
    sources.extend([('headline','fourni' if profile.headline else 'profession + ville fournies'),
                    ('introduction','prestations + zones fournies' if summary else 'description fournie, éventuellement raccourcie')])
    labels={'atelier':('L’atelier','Nos interventions','Parlons de votre véhicule'),
            'lieux':('Notre approche','Des prestations pour vos espaces','Parlons de vos locaux'),
            'habitat':('Votre interlocuteur','Nos interventions','Parlons de votre installation'),
            'local':('Présentation','Nos prestations','Parlons de votre besoin')}
    about_title,services_title,contact_title=labels[family]
    content=PageContent.from_dict({'headline':headline,'introduction':introduction,
        'about_title':about_title,'services_title':services_title,'contact_title':contact_title,
        'cta_label':'Prendre contact','seo_title':f'{profile.name} — {profile.profession}'[:120],
        'seo_description':(f'{profile.name} : {summary}' if summary else ' '.join(profile.description.split()))[:160]})
    # One composition algorithm shared by every profession. Visual variants are
    # chosen by theme and available content, never by a profession template.
    sections=[SectionPlan('header','stacked' if chosen=='editorial' else 'inline'),
              SectionPlan('hero','centered' if chosen=='editorial' else 'split'),
              SectionPlan('services','list' if chosen=='contraste' or len(profile.services)>4 else 'cards'),
              SectionPlan('about','panel' if chosen=='clair' else 'editorial')]
    if profile.benefits:sections.append(SectionPlan('benefits','cards' if chosen=='contraste' else 'list'))
    # The first gallery photo illustrates the presentation; a gallery needs more.
    if profile.projects or sum(image.role=='gallery' for image in profile.images)>1:sections.append(SectionPlan('gallery','featured' if chosen=='editorial' else 'grid'))
    if profile.testimonials:sections.append(SectionPlan('testimonials','quotes' if chosen=='editorial' else 'cards'))
    if profile.areas or profile.city:sections.append(SectionPlan('areas','text' if chosen=='editorial' else 'chips'))
    if profile.faq:sections.append(SectionPlan('faq','accordion'))
    sections.extend([SectionPlan('contact','compact' if chosen=='editorial' else 'split'),SectionPlan('footer','minimal' if chosen=='editorial' else 'columns')])
    decisions=(f'Thème {chosen} : '+('choix automatique à partir de la fiche.' if theme=='auto' else 'choix manuel.'),
               'Sections sélectionnées uniquement selon les données disponibles.',
               'Contact direct par téléphone/e-mail, sans formulaire d’envoi non configuré.',
               'Accroche composée des prestations et zones fournies.' if summary else 'Accroche reprise de la présentation fournie.')
    return EssentialDraft(profile,content,PagePlan(tuple(sections)),chosen,decisions,tuple(sources),demo,internal_preview)


def render_essential(draft: EssentialDraft) -> PreviewResult:
    note='ENTREPRISE FICTIVE · Démonstration LocalExpand · Coordonnées de test' if draft.demo else 'Aperçu LocalExpand · Validation avant mise en ligne'
    if draft.internal_preview:
        note='MAQUETTE INTERNE NON OFFICIELLE · Entreprise non cliente de LocalExpand · Illustrations temporaires'
    return build_preview(draft.profile,draft.plan,draft.content,theme=draft.theme,contact_mode='direct',notice=note)
