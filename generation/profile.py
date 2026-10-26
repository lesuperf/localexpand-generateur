"""Versioned, immutable business facts, independent of scraping and profession.

Parsing rejects malformed input; completeness is assessed separately so a draft
can be represented without inventing missing information. No I/O is performed.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import asdict, dataclass
import re
from urllib.parse import unquote, urlsplit

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    code: str
    message: str
    severity: str = 'error'


class ProfileError(ValueError):
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(message)


def text(value, field, limit=2000, multiline=False):
    if not isinstance(value, str):
        raise ProfileError(field, 'Une valeur texte est attendue.')
    value = value.strip()
    if len(value) > limit:
        raise ProfileError(field, f'Ce champ est limité à {limit} caractères.')
    if any(ord(c) < 32 and (not multiline or c not in '\n\r\t') for c in value):
        raise ProfileError(field, 'Un caractère de contrôle non autorisé est présent.')
    return value


def record(value, field, allowed):
    if not isinstance(value, dict):
        raise ProfileError(field, 'Un objet est attendu.')
    if any(not isinstance(key, str) for key in value):
        raise ProfileError(field, 'Les noms des champs doivent être du texte.')
    unknown = set(value) - set(allowed)
    if unknown:
        raise ProfileError(field, 'Champs inconnus : ' + ', '.join(sorted(unknown)))
    return value


def sequence(value, field, limit):
    if not isinstance(value, (list, tuple)) or len(value) > limit:
        raise ProfileError(field, f'Une liste de {limit} éléments maximum est attendue.')
    return value


def strings(value, field, count, length):
    result = []
    for index, item in enumerate(sequence(value, field, count)):
        item = text(item, f'{field}.{index}', length)
        if not item:
            raise ProfileError(f'{field}.{index}', 'Une valeur vide ne peut pas être ajoutée.')
        if item not in result:
            result.append(item)
    return tuple(result)


def web_url(value, field):
    value = text(value, field, 2000)
    if not value:
        return ''
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in {'http', 'https'} and parsed.hostname
                 and not parsed.username and not parsed.password and parsed.port in {None, 80, 443}
                 and not re.search(r'\s|[<>"\\]', value))
    except ValueError:
        valid = False
    if not valid:
        raise ProfileError(field, 'Une URL HTTP ou HTTPS sans identifiants est attendue.')
    return value


def image_source(value, field):
    value = text(value, field, 12_000_000)
    if value.startswith('data:'):
        match = re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)', value)
        if not match:
            raise ProfileError(field, 'Seules les images PNG, JPEG et WebP sont acceptées.')
        try:
            raw = base64.b64decode(match[2], validate=True)
        except (binascii.Error, ValueError):
            raise ProfileError(field, 'Image encodée invalide.') from None
        signatures = {'png': raw.startswith(b'\x89PNG\r\n\x1a\n'),
                      'jpeg': raw.startswith(b'\xff\xd8\xff'),
                      'webp': raw.startswith(b'RIFF') and raw[8:12] == b'WEBP'}
        if len(raw) > 8 * 1024 * 1024 or not signatures[match[1]]:
            raise ProfileError(field, 'Image invalide ou supérieure à 8 Mo.')
        return value
    decoded = unquote(value)
    # Only relative packaged assets. No file/network reads or directory escapes.
    if (not decoded or decoded != value or decoded.startswith(('/', '\\'))
            or any(part in {'', '.', '..'} for part in decoded.split('/'))
            or re.search(r'[:\\?#<>"\x00-\x1f]', decoded)
            or not re.search(r'\.(?:png|jpe?g|webp)$', decoded, re.I)):
        raise ProfileError(field, 'Une image locale relative PNG, JPEG ou WebP est attendue.')
    return value


@dataclass(frozen=True)
class Service:
    title: str
    description: str = ''

    @classmethod
    def parse(cls, data, field):
        if isinstance(data, str):
            data = {'title': data}
        data = record(data, field, {'title', 'description'})
        title = text(data.get('title', ''), field + '.title', 100)
        if not title:
            raise ProfileError(field + '.title', 'Indiquez le nom du service.')
        return cls(title, text(data.get('description', ''), field + '.description', 600, True))


@dataclass(frozen=True)
class ImageAsset:
    src: str
    alt: str
    role: str = 'gallery'

    @classmethod
    def parse(cls, data, field):
        data = record(data, field, {'src', 'alt', 'role'})
        role = text(data.get('role', 'gallery'), field + '.role', 20)
        if role not in {'logo', 'hero', 'gallery'}:
            raise ProfileError(field + '.role', 'Rôle d’image inconnu.')
        return cls(image_source(data.get('src', ''), field + '.src'),
                   text(data.get('alt', ''), field + '.alt', 180), role)


@dataclass(frozen=True)
class Project:
    title: str
    image: ImageAsset
    description: str = ''

    @classmethod
    def parse(cls, data, field):
        data = record(data, field, {'title', 'image', 'description'})
        title = text(data.get('title', ''), field + '.title', 120)
        if not title:
            raise ProfileError(field + '.title', 'Indiquez le titre de la réalisation.')
        image = ImageAsset.parse(data.get('image', {}), field + '.image')
        if image.role != 'gallery':
            raise ProfileError(field + '.image.role', 'Une réalisation utilise une image de galerie.')
        return cls(title, image, text(data.get('description', ''), field + '.description', 600, True))


@dataclass(frozen=True)
class Testimonial:
    quote: str
    author: str
    source_url: str = ''

    @classmethod
    def parse(cls, data, field):
        data = record(data, field, {'quote', 'author', 'source_url'})
        quote = text(data.get('quote', ''), field + '.quote', 1200, True)
        author = text(data.get('author', ''), field + '.author', 120)
        if not quote or not author:
            raise ProfileError(field, 'Le témoignage et son auteur doivent être renseignés.')
        return cls(quote, author, web_url(data.get('source_url', ''), field + '.source_url'))


@dataclass(frozen=True)
class FAQItem:
    question: str
    answer: str

    @classmethod
    def parse(cls, data, field):
        data = record(data, field, {'question', 'answer'})
        question = text(data.get('question', ''), field + '.question', 200)
        answer = text(data.get('answer', ''), field + '.answer', 1200, True)
        if not question or not answer:
            raise ProfileError(field, 'La question et la réponse doivent être renseignées.')
        return cls(question, answer)


@dataclass(frozen=True)
class VisualPreferences:
    primary: str = ''
    accent: str = ''
    theme: str = ''

    @classmethod
    def parse(cls, data):
        data = record(data, 'visuals', {'primary', 'accent', 'theme'})
        colors = []
        for name in ['primary', 'accent']:
            color = text(data.get(name, ''), 'visuals.' + name, 7)
            if color and not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                raise ProfileError('visuals.' + name, 'Une couleur hexadécimale #RRGGBB est attendue.')
            colors.append(color.lower())
        theme = text(data.get('theme', ''), 'visuals.theme', 40)
        if theme and not re.fullmatch(r'[a-z][a-z0-9-]*', theme):
            raise ProfileError('visuals.theme', 'Identifiant de thème invalide.')
        return cls(*colors, theme)


@dataclass(frozen=True)
class BusinessProfile:
    name: str = ''
    profession: str = ''
    description: str = ''
    headline: str = ''
    city: str = ''
    areas: tuple[str, ...] = ()
    phone: str = ''
    email: str = ''
    website: str = ''
    services: tuple[Service, ...] = ()
    images: tuple[ImageAsset, ...] = ()
    benefits: tuple[str, ...] = ()
    projects: tuple[Project, ...] = ()
    testimonials: tuple[Testimonial, ...] = ()
    faq: tuple[FAQItem, ...] = ()
    additional_information: tuple[tuple[str, str], ...] = ()
    visuals: VisualPreferences = VisualPreferences()

    @classmethod
    def from_dict(cls, data):
        allowed = set(cls.__dataclass_fields__) | {'schema_version'}
        data = record(data, 'profile', allowed)
        version = data.get('schema_version', SCHEMA_VERSION)
        if type(version) is not int or version != SCHEMA_VERSION:
            raise ProfileError('schema_version', 'Version de fiche non prise en charge.')
        limits = {'name':120, 'profession':120, 'description':2000, 'headline':180,
                  'city':80, 'phone':60, 'email':254}
        values = {key: text(data.get(key, ''), key, limit, key == 'description') for key, limit in limits.items()}
        phone = values['phone']
        if phone and (not re.fullmatch(r'\+?[\d\s().-]+', phone) or not 6 <= len(re.sub(r'\D','',phone)) <= 15):
            raise ProfileError('phone', 'Numéro de téléphone invalide.')
        if values['email'] and not re.fullmatch(r'[^\s@?&#<>"\\]+@[^\s@?&#<>"\\]+\.[^\s@?&#<>"\\]+', values['email']):
            raise ProfileError('email', 'Adresse e-mail invalide.')
        values['website'] = web_url(data.get('website', ''), 'website')
        values['areas'] = strings(data.get('areas', []), 'areas', 20, 100)
        values['benefits'] = strings(data.get('benefits', []), 'benefits', 12, 200)
        for key, parser, maximum in [('services', Service, 8), ('images', ImageAsset, 8),
                                     ('projects', Project, 6), ('testimonials', Testimonial, 8), ('faq', FAQItem, 12)]:
            values[key] = tuple(parser.parse(item, f'{key}.{i}') for i, item in enumerate(sequence(data.get(key, []), key, maximum)))
        for role in ['logo', 'hero']:
            if sum(image.role == role for image in values['images']) > 1:
                raise ProfileError('images', 'Un seul logo et une seule image principale sont autorisés.')
        extra = data.get('additional_information', {})
        if not isinstance(extra, dict) or len(extra) > 20:
            raise ProfileError('additional_information', 'Un objet de 20 informations maximum est attendu.')
        values['additional_information'] = tuple((text(k, 'additional_information.key', 80), text(v, 'additional_information.' + str(k), 12000 if k in {'mentions_legales','politique_confidentialite'} else 1000, True)) for k,v in extra.items())
        if any(not key for key, _ in values['additional_information']):
            raise ProfileError('additional_information', 'Une information doit avoir un nom.')
        keys=[key for key,_ in values['additional_information']]
        if len(keys)!=len(set(keys)):
            raise ProfileError('additional_information', 'Deux informations portent le même nom après normalisation.')
        values['visuals'] = VisualPreferences.parse(data.get('visuals', {}))
        return cls(**values)

    def to_dict(self):
        result = asdict(self)
        result['schema_version'] = SCHEMA_VERSION
        result['additional_information'] = dict(self.additional_information)
        return result


def profile_issues(profile: BusinessProfile) -> tuple[ValidationIssue, ...]:
    """Report absent facts; never fill them with assertions or example contacts."""
    issues = []
    for field, message in [('name','Indiquez le nom de l’entreprise.'),
                           ('profession','Indiquez la profession.'),
                           ('description','Présentez l’activité de l’entreprise.'),
                           ('services','Indiquez au moins une prestation.')]:
        if not getattr(profile, field):
            issues.append(ValidationIssue(field, 'required', message))
    if not profile.phone and not profile.email:
        issues.append(ValidationIssue('contact', 'required', 'Indiquez un téléphone ou un e-mail.'))
    if not profile.city and not profile.areas:
        issues.append(ValidationIssue('areas', 'missing', 'La zone d’intervention reste à préciser.', 'warning'))
    images = [(f'images.{i}', image) for i, image in enumerate(profile.images)]
    images += [(f'projects.{i}.image', project.image) for i, project in enumerate(profile.projects)]
    for field, image in images:
        if image.role != 'logo' and not image.alt:
            issues.append(ValidationIssue(field + '.alt', 'missing', 'Décrivez cette image pour son alternative textuelle.', 'warning'))
    return tuple(issues)
