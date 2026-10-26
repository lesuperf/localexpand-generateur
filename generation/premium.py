"""Future Premium input contract only: no Premium rendering or order service."""
from dataclasses import dataclass

from .composition import PagePlan
from .profile import ProfileError


@dataclass(frozen=True)
class PremiumBrief:
    direction: str
    pages: tuple[PagePlan, ...]
    questionnaire_validated: bool = False
    order_reference: str = ''

    def __post_init__(self):
        if not isinstance(self.pages,(list,tuple)):
            raise ProfileError('premium.pages', 'Une liste de plans de page est attendue.')
        object.__setattr__(self,'pages',tuple(self.pages))
        if self.direction not in {'commercial','creatif'}:
            raise ProfileError('premium.direction', 'Choisissez Commercial ou Créatif.')
        if not 3<=len(self.pages)<=5 or any(not isinstance(page,PagePlan) for page in self.pages):
            raise ProfileError('premium.pages', 'Premium prévoit trois à cinq plans de page.')
        if len({page.slug for page in self.pages})!=len(self.pages):
            raise ProfileError('premium.pages', 'Les identifiants de page doivent être uniques.')
        if type(self.questionnaire_validated) is not bool:
            raise ProfileError('premium.questionnaire_validated', 'Une validation explicite est attendue.')
        from .profile import text
        text(self.order_reference,'premium.order_reference',120)

    @property
    def can_request_mockup(self):
        return bool(self.order_reference.strip() and self.questionnaire_validated)
