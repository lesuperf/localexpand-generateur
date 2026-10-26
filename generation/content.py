"""Explicit page copy, separate from facts, theme, markup and component selection.

This is a content contract, not an AI writer. Missing editorial text is not
generated from profession-specific marketing promises in Phase B.
"""
from dataclasses import asdict, dataclass

from .profile import record, text


@dataclass(frozen=True)
class PageContent:
    headline: str = ''
    introduction: str = ''
    about_title: str = 'Présentation'
    services_title: str = 'Nos prestations'
    benefits_title: str = 'Nos points forts'
    gallery_title: str = 'En images'
    testimonials_title: str = 'Témoignages'
    areas_title: str = 'Zone d’intervention'
    faq_title: str = 'Questions fréquentes'
    contact_title: str = 'Parlons de votre besoin'
    cta_label: str = 'Nous contacter'
    seo_title: str = ''
    seo_description: str = ''

    @classmethod
    def from_dict(cls, data):
        data = record(data, 'content', cls.__dataclass_fields__)
        defaults = cls()
        values = {}
        for key in cls.__dataclass_fields__:
            limit = 2000 if key=='introduction' else 180 if key=='headline' else 300 if key=='seo_description' else 120
            values[key] = text(data.get(key,getattr(defaults,key)), 'content.' + key, limit, key=='introduction')
            if key not in {'headline','introduction','seo_title','seo_description'} and not values[key]:
                from .profile import ProfileError
                raise ProfileError('content.'+key, 'Ce libellé ne peut pas être vide.')
        return cls(**values)

    def to_dict(self):
        return asdict(self)
