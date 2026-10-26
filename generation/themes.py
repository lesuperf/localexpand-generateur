"""Small visual token catalogue; themes contain no business content or prices."""
from dataclasses import dataclass, replace
import re

from .profile import ProfileError, VisualPreferences


def luminance(color):
    values = [int(color[i:i+2],16)/255 for i in (1,3,5)]
    values = [c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in values]
    return sum(a*b for a,b in zip(values,(.2126,.7152,.0722)))


def contrast(first, second):
    light,dark = sorted((luminance(first),luminance(second)),reverse=True)
    return (light+.05)/(dark+.05)


def on_color(background):
    return '#ffffff' if contrast(background,'#ffffff') > contrast(background,'#000000') else '#000000'


@dataclass(frozen=True)
class Theme:
    key: str
    primary: str
    accent: str
    paper: str
    surface: str
    ink: str
    muted: str
    radius: str
    heading_font: str

    def css_variables(self):
        """Only catalogue tokens and validated colors may become CSS."""
        if not re.fullmatch(r'[a-z][a-z0-9-]*', self.key):
            raise ProfileError('theme.key', 'Identifiant de thème invalide.')
        for key in ['primary','accent','paper','surface','ink','muted']:
            if not re.fullmatch(r'#[0-9a-fA-F]{6}',getattr(self,key)):
                raise ProfileError('theme.'+key, 'Couleur de thème invalide.')
        if self.radius not in {'0px','8px','20px'} or self.heading_font not in {'Arial, sans-serif','Georgia, serif'}:
            raise ProfileError('theme', 'Les tokens de thème doivent appartenir au catalogue.')
        if contrast(self.paper,self.ink)<4.5 or contrast(self.surface,self.ink)<4.5:
            raise ProfileError('theme.ink', 'Le contraste du texte du thème est insuffisant.')
        if contrast(self.paper,self.muted)<4.5 or contrast(self.surface,self.muted)<4.5:
            raise ProfileError('theme.muted', 'Le contraste des textes secondaires est insuffisant.')
        colors = ';'.join(f'--{key}:{getattr(self,key)}' for key in ['primary','accent','paper','surface','ink','muted'])
        primary_ink=self.primary if min(contrast(self.primary,self.paper),contrast(self.primary,self.surface))>=4.5 else self.ink
        return ':root{' + colors + f';--primary-ink:{primary_ink};--on-primary:{on_color(self.primary)};--on-accent:{on_color(self.accent)};--radius:{self.radius};--heading-font:{self.heading_font}' + '}'


THEMES = (
    Theme('clair','#215b45','#b8dcac','#f5f5ef','#ffffff','#18231d','#4d5a51','8px','Arial, sans-serif'),
    Theme('editorial','#304d65','#e3c593','#f7f2e9','#fffdf8','#242a30','#565b60','0px','Georgia, serif'),
    Theme('contraste','#f2ca55','#9dddc8','#141c21','#202a30','#f4f5ef','#bcc8cb','20px','Arial, sans-serif'),
)


def resolve_theme(key='', preferences=None):
    preferences = preferences or VisualPreferences()
    # Validate direct dataclass callers as well as parsed profiles.
    preferences = VisualPreferences.parse({'primary':preferences.primary,'accent':preferences.accent,'theme':preferences.theme})
    chosen = key or preferences.theme or 'clair'
    theme = next((item for item in THEMES if item.key==chosen),None)
    if theme is None:
        raise ProfileError('theme', 'Choisissez un thème disponible.')
    theme = replace(theme,primary=preferences.primary or theme.primary,accent=preferences.accent or theme.accent)
    theme.css_variables()
    return theme
