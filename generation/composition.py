"""Explicit component/page plans. No automatic offer or profession composer yet."""
from dataclasses import dataclass
import re

from .profile import ProfileError

VARIANTS = {
    'header':('inline','stacked'), 'hero':('split','centered'),
    'about':('editorial','panel'), 'services':('cards','list'),
    'benefits':('list','cards'), 'gallery':('grid','featured'),
    'testimonials':('cards','quotes'), 'areas':('chips','text'),
    'faq':('accordion','list'), 'contact':('split','compact'),
    'footer':('columns','minimal'),
}


@dataclass(frozen=True)
class SectionPlan:
    component: str
    variant: str = ''

    def __post_init__(self):
        if not isinstance(self.component,str) or self.component not in VARIANTS:
            raise ProfileError('component', 'Composant inconnu.')
        if self.variant and self.variant not in VARIANTS[self.component]:
            raise ProfileError('variant', 'Variante non disponible pour ce composant.')

    @property
    def selected_variant(self):
        return self.variant or VARIANTS[self.component][0]


@dataclass(frozen=True)
class PagePlan:
    sections: tuple[SectionPlan, ...]
    slug: str = 'index'

    def __post_init__(self):
        if not isinstance(self.sections,(list,tuple)):
            raise ProfileError('page.sections', 'Une liste de sections est attendue.')
        object.__setattr__(self,'sections',tuple(self.sections))
        if not isinstance(self.slug,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,59}',self.slug):
            raise ProfileError('page.slug', 'Identifiant de page invalide.')
        if not self.sections or len(self.sections)>11 or any(not isinstance(s,SectionPlan) for s in self.sections):
            raise ProfileError('page.sections', 'Une à onze sections typées sont attendues.')
        components = [section.component for section in self.sections]
        if len(components)!=len(set(components)):
            raise ProfileError('page.sections', 'Un composant ne doit pas être répété sur une page.')
        if 'header' in components and components[0]!='header':
            raise ProfileError('page.sections', 'Le header doit être placé en premier.')
        if 'footer' in components and components[-1]!='footer':
            raise ProfileError('page.sections', 'Le footer doit être placé en dernier.')


def preview_plan():
    """An explicit technical fixture plan, not an Essentiel generation workflow."""
    return PagePlan(tuple(SectionPlan(name) for name in VARIANTS))
