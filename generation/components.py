"""Profession-independent, escaped HTML components with explicit visual variants."""
from dataclasses import dataclass
from html import escape
from types import MappingProxyType
from urllib.parse import quote
import re

from .composition import SectionPlan
from .content import PageContent
from .icons import icon_name, icon_svg
from .profile import BusinessProfile, ProfileError

IDS = MappingProxyType({'hero':'accueil','about':'presentation','services':'prestations',
    'benefits':'points-forts','gallery':'images','testimonials':'temoignages',
    'areas':'zones','faq':'questions','contact':'contact'})
LABEL_KEYS = MappingProxyType({'about':'about_title','services':'services_title',
    'benefits':'benefits_title','gallery':'gallery_title','testimonials':'testimonials_title',
    'areas':'areas_title','faq':'faq_title','contact':'contact_title'})


def e(value):
    return escape(str(value),quote=True)


@dataclass(frozen=True)
class ComponentContext:
    profile: BusinessProfile
    content: PageContent = PageContent()
    navigation: tuple[tuple[str,str], ...] = ()
    contact_mode: str = 'preview'

    def __post_init__(self):
        if self.contact_mode not in {'preview','direct'}:
            raise ProfileError('contact_mode','Mode de contact inconnu.')
        if not isinstance(self.profile,BusinessProfile) or not isinstance(self.content,PageContent):
            raise ProfileError('context','Une fiche et un contenu typés sont attendus.')
        # Revalidate direct dataclass construction at the rendering boundary.
        try:
            profile_data=self.profile.to_dict()
            content_data=self.content.to_dict()
        except (TypeError,ValueError):
            raise ProfileError('context','Les données du contexte sont mal formées.') from None
        object.__setattr__(self,'profile',BusinessProfile.from_dict(profile_data))
        object.__setattr__(self,'content',PageContent.from_dict(content_data))
        if not isinstance(self.navigation,(tuple,list)) or any(not isinstance(item,(tuple,list)) for item in self.navigation):
            raise ProfileError('navigation','Une liste de liens est attendue.')
        nav = tuple(tuple(item) for item in self.navigation)
        if len(nav)>len(IDS) or any(len(item)!=2 or not all(isinstance(v,str) for v in item) or not re.fullmatch(r'[a-z][a-z0-9-]*',item[1]) for item in nav):
            raise ProfileError('navigation','Liens de navigation invalides.')
        object.__setattr__(self,'navigation',nav)

    @property
    def contact_target(self):
        if any(target=='contact' for _,target in self.navigation):
            return '#contact'
        if self.profile.phone:
            return 'tel:' + re.sub(r'[^+\d]','',self.profile.phone)
        if self.profile.email:
            return 'mailto:' + quote(self.profile.email,safe='@')
        return ''


def image_markup(image, *, logo=False, eager=False):
    alt = '' if logo else image.alt
    return (f'<img class="le-logo-image" src="{e(image.src)}" alt="" width="48" height="48">' if logo else
            f'<img src="{e(image.src)}" alt="{e(alt)}" width="1280" height="900" loading="{"eager" if eager else "lazy"}">')


def nav_markup(context, label='Navigation principale', entries=None):
    entries=context.navigation if entries is None else entries
    if not entries:
        return ''
    return f'<nav aria-label="{e(label)}">' + ''.join(f'<a href="#{e(target)}">{e(title)}</a>' for title,target in entries) + '</nav>'


def brand_markup(context):
    logo = next((image for image in context.profile.images if image.role=='logo'),None)
    initials=''.join(word[0] for word in context.profile.name.split()[:2]).upper()
    symbol=f'<span class="le-brand-symbol" aria-hidden="true">{e(initials)}</span>' if context.contact_mode=='direct' and not logo else ''
    return '<a class="le-brand" href="#contenu">' + (image_markup(logo,logo=True) if logo else symbol) + f'<span class="le-brand-name">{e(context.profile.name)}</span></a>'


def phone_href(profile):
    return 'tel:' + re.sub(r'[^+\d]','',profile.phone) if profile.phone else ''


def email_href(profile):
    return 'mailto:' + quote(profile.email,safe='@') if profile.email else ''


def service_icon(service, profile):
    return f'<span class="le-service-icon" aria-hidden="true">{icon_svg(icon_name(service.title,profile.profession,service.description))}</span>'


def about_image(context):
    """Essentiel spreads photos through the page: the first gallery photo
    illustrates the presentation instead of waiting in the gallery."""
    if context.contact_mode!='direct':return None
    return next((image for image in context.profile.images if image.role=='gallery'),None)


def contact_links(profile):
    links = []
    if profile.phone:
        number = re.sub(r'[^+\d]','',profile.phone)
        links.append(f'<a href="tel:{e(number)}">{e(profile.phone)}</a>')
    if profile.email:
        links.append(f'<a href="mailto:{e(quote(profile.email,safe="@"))}">{e(profile.email)}</a>')
    if profile.website:
        links.append(f'<a href="{e(profile.website)}" rel="noopener noreferrer">{e(profile.website)}</a>')
    address=dict(profile.additional_information).get('adresse','')
    if address:links.append(f'<span>{e(address)}</span>')
    return '<div class="le-contact-links">' + ''.join(links) + '</div>'


def section(name, variant, title, body, context=None):
    heading=f'<h2 id="{IDS[name]}-titre">{e(title)}</h2>'
    if context and context.contact_mode=='direct':
        labels={'about':'À propos','services':'Les prestations','benefits':'Notre approche','gallery':'En images',
                'testimonials':'Vos témoignages','areas':'À proximité','faq':'Avant notre échange','contact':'Et maintenant ?'}
        position=next((str(i).zfill(2) for i,(_,target) in enumerate(context.navigation,1) if target==IDS[name]),'')
        kicker=f'<p class="le-section-kicker"><span aria-hidden="true">{position}</span>{labels[name]}</p>'
        heading='<div class="le-section-heading">'+kicker+heading+'</div>'
    return f'<section id="{IDS[name]}" class="le-section le-{name} le-{name}--{variant}" data-component="{name}" data-variant="{variant}" aria-labelledby="{IDS[name]}-titre"><div class="le-wrap">{heading}{body}</div></section>'


def header(context, variant):
    brand,nav = brand_markup(context),nav_markup(context)
    if context.contact_mode=='direct' and context.navigation:
        short={'prestations':'Prestations','presentation':'À propos','images':'Galerie','temoignages':'Témoignages',
               'zones':'Notre secteur','questions':'Questions','contact':'Contact','points-forts':'Notre approche'}
        entries=tuple((short.get(target,title),target) for title,target in context.navigation)
        desktop=tuple(item for item in entries if item[1] not in {'contact','questions'})[:3]
        cta=f'<a class="le-header-cta" href="{e(context.contact_target)}">{e(context.content.cta_label)} <span aria-hidden="true">↗</span></a>'
        nav='<div class="le-desktop-nav">'+nav_markup(context,entries=desktop)+cta+'</div><details class="le-mobile-nav"><summary>Menu <span aria-hidden="true">＋</span></summary>'+nav_markup(context,'Navigation mobile',entries)+'</details>'
    inner = f'<div class="le-header-brand">{brand}</div>{nav}' if variant=='stacked' else brand + nav
    return f'<header class="le-header le-header--{variant}" data-component="header" data-variant="{variant}"><div class="le-wrap">{inner}</div></header>'


def hero(context, variant):
    profile,content = context.profile,context.content
    location = ' · ' + profile.city if profile.city else ''
    title = content.headline or profile.headline or profile.name
    intro = content.introduction or profile.description
    cta = f'<a class="le-button" href="{e(context.contact_target)}">{e(content.cta_label)}</a>' if context.contact_target else ''
    title_html=e(title)
    meta=''
    if context.contact_mode=='direct':
        words=title.split()
        if len(words)>4:
            title_html=e(' '.join(words[:-3]))+' '+f'<span class="le-title-accent">{e(" ".join(words[-3:]))}</span>'
        # A visible number converts better than an anchor for local services.
        if profile.phone:
            cta=f'<a class="le-button le-button--call" href="{e(phone_href(profile))}">Appeler le {e(profile.phone)}</a>'
        secondary='<a class="le-hero-secondary" href="#prestations">Découvrir les prestations <span aria-hidden="true">↓</span></a>' if any(target=='prestations' for _,target in context.navigation) else ''
        cta='<div class="le-hero-actions">'+cta+secondary+'</div>'
        zones=profile.areas or ((profile.city,) if profile.city else ())
        if zones:
            meta='<div class="le-hero-location"><span class="le-location-icon" aria-hidden="true">⌖</span><div><span>Votre secteur</span><p>'+e(' · '.join(zones[:3]))+'</p></div></div>'
    copy = f'<div class="le-hero-copy"><p class="le-eyebrow">{e(profile.profession + location)}</p><h1>{title_html}</h1><p class="le-lead">{e(intro)}</p>{cta}{meta}</div>'
    image = next((image for image in profile.images if image.role=='hero'),None)
    caption='<figcaption>Illustration d’ambiance · Démonstration fictive</figcaption>' if context.contact_mode=='direct' and dict(profile.additional_information).get('visuels_demonstration')=='oui' else ''
    if context.contact_mode=='direct' and dict(profile.additional_information).get('maquette_interne')=='oui':
        caption='<figcaption>Illustration temporaire · Ne représente pas l’entreprise</figcaption>'
    visual = '<figure class="le-hero-image">' + image_markup(image,eager=True) + caption + '</figure>' if image else ''
    if context.contact_mode=='direct' and not visual:
        # Without a photo, a composed visual of the supplied services, in brand colours.
        initials = ''.join(word[0] for word in profile.name.split()[:2]).upper()
        tiles=''.join(f'<li>{service_icon(service,profile)}<span>{e(service.title)}</span></li>' for service in profile.services[:3])
        visual = f'<div class="le-identity le-hero-graphic" aria-hidden="true"><span class="le-hero-graphic-mark">{e(initials)}</span><ul>{tiles}</ul></div>'
    if variant=='split' and not visual:
        initials = ''.join(word[0] for word in profile.name.split()[:2]).upper()
        visual = f'<div class="le-identity" aria-hidden="true"><span>{e(initials)}</span></div>'
    return f'<section id="accueil" class="le-hero le-hero--{variant}" data-component="hero" data-variant="{variant}"><div class="le-wrap">{copy}{visual}</div></section>'


def about(context, variant):
    extra = ''
    if context.profile.additional_information:
        facts=''.join(f'<div><dt>{e(key)}</dt><dd>{e(value)}</dd></div>' for key,value in context.profile.additional_information if key not in {'visuels_demonstration','maquette_interne','mentions_legales','politique_confidentialite','adresse','horaires'})
        extra = '<dl class="le-facts">' + facts + '</dl>' if facts else ''
    paragraphs='<p>'+e(context.profile.description)+'</p>'
    if context.contact_mode=='direct':paragraphs=''.join('<p>'+e(part)+'</p>' for part in context.profile.description.split('\n\n') if part.strip())
    image=about_image(context)
    figure=f'<figure class="le-about-image">{image_markup(image)}</figure>' if image else ''
    return section('about',variant,context.content.about_title,f'{figure}<div class="le-prose">{paragraphs}{extra}</div>',context)


def services(context, variant):
    entries = []
    for index, service in enumerate(context.profile.services,1):
        description = f'<p>{e(service.description)}</p>' if service.description else ''
        icon=service_icon(service,context.profile) if context.contact_mode=='direct' else ''
        body = f'{icon}<h3>{e(service.title)}</h3>{description}'
        entries.append(f'<article class="le-card">{body}</article>' if variant=='cards' else f'<li>{body}</li>')
    wrapper = 'div' if variant=='cards' else 'ol'
    body = f'<{wrapper} class="le-services-items">' + ''.join(entries) + f'</{wrapper}>'
    # One call to action after the list instead of the same link on every item.
    if context.contact_mode=='direct' and context.contact_target:
        body+=f'<div class="le-services-cta"><p>Une question sur l’une de ces prestations&nbsp;?</p><a class="le-button" href="{e(context.contact_target)}">{e(context.content.cta_label)}</a></div>'
    return section('services',variant,context.content.services_title,body,context)


def benefits(context, variant):
    body = '<ul class="le-benefits-items">' + ''.join(f'<li>{e(value)}</li>' for value in context.profile.benefits) + '</ul>'
    return section('benefits',variant,context.content.benefits_title,body,context)


def gallery(context, variant):
    figures = []
    for project in context.profile.projects:
        caption = f'<strong>{e(project.title)}</strong>' + (f'<span>{e(project.description)}</span>' if project.description else '')
        figures.append(f'<figure>{image_markup(project.image)}<figcaption>{caption}</figcaption></figure>')
    shown=[image for image in context.profile.images if image.role=='gallery']
    # The presentation photo is not repeated, unless nothing else would remain.
    if about_image(context) and (len(shown)>1 or figures):shown=shown[1:]
    for image in shown:
        if image.role=='gallery':
            caption = f'<figcaption>{e(image.alt)}</figcaption>' if image.alt else ''
            figures.append(f'<figure>{image_markup(image)}{caption}</figure>')
    return section('gallery',variant,context.content.gallery_title,'<div class="le-gallery-items">' + ''.join(figures) + '</div>',context)


def testimonials(context, variant):
    entries = []
    for item in context.profile.testimonials:
        source = f'<a href="{e(item.source_url)}" rel="noopener noreferrer">Voir la source</a>' if item.source_url else ''
        entries.append(f'<figure><blockquote><p>{e(item.quote)}</p></blockquote><figcaption>{e(item.author)}{source}</figcaption></figure>')
    return section('testimonials',variant,context.content.testimonials_title,'<div class="le-testimonials-items">' + ''.join(entries) + '</div>',context)


def areas(context, variant):
    zones = context.profile.areas or ((context.profile.city,) if context.profile.city else ())
    body = ('<ul class="le-zone-list">' + ''.join(f'<li>{e(zone)}</li>' for zone in zones) + '</ul>' if variant=='chips' else '<p>' + e(' · '.join(zones)) + '</p>')
    return section('areas',variant,context.content.areas_title,body,context)


def faq(context, variant):
    if variant=='accordion':
        body = '<div class="le-faq-items">' + ''.join(f'<details><summary>{e(item.question)}</summary><p>{e(item.answer)}</p></details>' for item in context.profile.faq) + '</div>'
    else:
        body = '<dl class="le-faq-items">' + ''.join(f'<div><dt>{e(item.question)}</dt><dd>{e(item.answer)}</dd></div>' for item in context.profile.faq) + '</dl>'
    return section('faq',variant,context.content.faq_title,body,context)


def contact(context, variant):
    if context.contact_mode=='direct':
        profile=context.profile
        means=' ou '.join(label for label,value in [('par téléphone',profile.phone),('par e-mail',profile.email)] if value)
        actions=''
        if profile.phone:
            actions+=f'<a class="le-contact-action le-contact-action--primary" href="{e(phone_href(profile))}"><span>Appeler</span><strong>{e(profile.phone)}</strong></a>'
        if profile.email:
            actions+=f'<a class="le-contact-action" href="{e(email_href(profile))}"><span>Écrire un e-mail</span><strong>{e(profile.email)}</strong></a>'
        if profile.website:
            actions+=f'<a class="le-contact-action" href="{e(profile.website)}" rel="noopener noreferrer"><span>Site web</span><strong>{e(profile.website)}</strong></a>'
        intro=f'<div class="le-contact-copy"><p>Une question ou un projet&nbsp;? Contactez {e(profile.name)} directement {means}.</p><div class="le-contact-actions">{actions}</div></div>'
        extras=dict(profile.additional_information)
        details=''
        if extras.get('adresse'):
            maps='https://www.google.com/maps/search/?api=1&query='+quote(profile.name+', '+extras['adresse'])
            details+=f'<div><dt>Adresse</dt><dd>{e(extras["adresse"])}<a href="{e(maps)}" rel="noopener noreferrer">Voir sur la carte <span aria-hidden="true">↗</span></a></dd></div>'
        if extras.get('horaires'):
            details+=f'<div><dt>Horaires</dt><dd class="le-hours">{e(extras["horaires"])}</dd></div>'
        aside=f'<dl class="le-contact-details">{details}</dl>' if details else ''
        mobile_label=(f'{e(profile.name)}<small>{e(profile.phone)}</small>' if profile.phone else f'{e(profile.name)}<small>Par e-mail</small>')
        mobile=f'<div class="le-mobile-contact"><span>{mobile_label}</span><a href="{e(phone_href(profile) or email_href(profile))}">{"Appeler" if profile.phone else "Écrire"} <span aria-hidden="true">↗</span></a></div>'
        return section('contact',variant,context.content.contact_title,f'<div class="le-contact-layout">{intro}{aside}</div>',context)+mobile
    # A foundation preview is deliberately not a connected customer contact form.
    form = '''<form class="le-contact-form" aria-describedby="contact-demo"><fieldset disabled><legend>Formulaire de démonstration</legend><label for="contact-nom">Nom<input id="contact-nom" name="name" autocomplete="name" maxlength="120"></label><label for="contact-email">E-mail<input id="contact-email" name="email" type="email" autocomplete="email" maxlength="254"></label><label for="contact-message">Message<textarea id="contact-message" name="message" rows="4" maxlength="2000"></textarea></label><button type="button" disabled>Envoi non activé</button></fieldset><p id="contact-demo">Aperçu technique : ce formulaire ne transmet aucune donnée.</p></form>'''
    intro = f'<div class="le-contact-copy">{contact_links(context.profile)}</div>'
    return section('contact',variant,context.content.contact_title,f'<div class="le-contact-layout">{intro}{form}</div>')


def footer(context, variant):
    summary = brand_markup(context) + f'<p>{e(context.profile.profession)}</p>'
    if variant=='columns':
        body = f'<div class="le-footer-grid"><div>{summary}</div>{nav_markup(context,"Navigation du pied de page")}{contact_links(context.profile)}</div>'
    else:
        body = f'<div class="le-footer-line">{summary}{contact_links(context.profile)}</div>'
    wordmark=f'<div class="le-footer-wordmark" aria-hidden="true">{e(context.profile.name)}</div>' if context.contact_mode=='direct' and len(context.profile.name)<=32 else ''
    extras=dict(context.profile.additional_information)
    legal=''.join(f'<details class="le-legal"><summary>{label}</summary><p>{e(extras[key])}</p></details>'
                  for key,label in [('mentions_legales','Mentions légales'),('politique_confidentialite','Confidentialité')] if extras.get(key))
    return f'<footer class="le-footer le-footer--{variant}" data-component="footer" data-variant="{variant}"><div class="le-wrap">{body}{wordmark}{legal}<div class="le-footer-note"><small>Aperçu technique LocalExpand · Contenus à valider</small><a href="#contenu">Retour en haut ↑</a></div></div></footer>'


RENDERERS = MappingProxyType({name:globals()[name] for name in [
    'header','hero','about','services','benefits','gallery','testimonials','areas','faq','contact','footer']})


def available(name, profile):
    if name=='services':return bool(profile.services)
    if name=='benefits':return bool(profile.benefits)
    if name=='gallery':return bool(profile.projects or any(image.role=='gallery' for image in profile.images))
    if name=='testimonials':return bool(profile.testimonials)
    if name=='areas':return bool(profile.city or profile.areas)
    if name=='faq':return bool(profile.faq)
    return name in RENDERERS


def render_component(name, context, variant=''):
    plan = SectionPlan(name,variant)
    if not isinstance(context,ComponentContext):
        raise ProfileError('context','Un contexte de composant est attendu.')
    if not available(name,context.profile):
        return ''
    return RENDERERS[name](context,plan.selected_variant)
