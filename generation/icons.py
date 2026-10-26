"""Decorative inline service icons chosen from supplied words; never a business claim.

Shapes are original 24px line drawings using currentColor, so every theme
colours them and no remote resource is loaded.
"""
import re
import unicodedata

PATHS = {
    'bath':'<path d="M4 12h16v2a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/><path d="M6 12V6.5a2.5 2.5 0 0 1 5 0"/><path d="M7 19l-1 2M17 19l1 2"/>',
    'flame':'<path d="M12 3c.8 3 4.5 5 4.5 9.5a4.5 4.5 0 0 1-9 0c0-2.2 1.1-3.6 2.3-4.6.1 1.8.9 3 2.2 3.4-.2-3.2-1-5.6 0-8.3z"/>',
    'bolt':'<path d="M13 3 5 14h6l-1 7 8-11h-6z"/>',
    'droplet':'<path d="M12 3s6 6.4 6 11a6 6 0 0 1-12 0c0-4.6 6-11 6-11z"/><path d="M9.5 14.5a2.5 2.5 0 0 0 2.5 2.5"/>',
    'car':'<path d="M4 16v-3l2.2-5h11.6L20 13v3z"/><path d="M6 16v2.5M18 16v2.5M4 13h16"/><circle cx="8" cy="14.5" r=".6"/><circle cx="16" cy="14.5" r=".6"/>',
    'sparkle':'<path d="M11 3l1.8 5.2L18 10l-5.2 1.8L11 17l-1.8-5.2L4 10l5.2-1.8z"/><path d="M18.5 15l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
    'brush':'<path d="M14 4l6 6-7.5 7.5-6-6z"/><path d="M6.5 11.5 4 14c-1 1-1 4 0 6 2 1 5 1 6 0l2.5-2.5"/>',
    'leaf':'<path d="M5 19C5 10 10 5 20 4c0 10-5 15-14 15"/><path d="M5 19l8-8"/>',
    'key':'<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l2.5 2.5M14 9l2 2"/>',
    'hammer':'<path d="M13 5l3-2 5 5-2 3z"/><path d="M14.5 6.5 4 17l3 3 10.5-10.5"/>',
    'home':'<path d="M4 11.5 12 4l8 7.5"/><path d="M6 10v10h12V10"/><path d="M10 20v-5h4v5"/>',
    'search':'<circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5 5M8 10.5h5"/>',
    'scissors':'<circle cx="6.5" cy="17.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/><path d="M8.3 15.7 18 4M15.7 15.7 6 4"/>',
    'utensils':'<path d="M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10"/><path d="M17 3c-2 2-2.5 6 0 8v10"/>',
    'shield':'<path d="M12 3l7 3v6c0 4.2-3 7.3-7 9-4-1.7-7-4.8-7-9V6z"/><path d="M9 12l2 2 4-4"/>',
    'heart':'<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    'document':'<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M9.5 12h5M9.5 16h5"/>',
    'truck':'<path d="M3 6h11v10H3zM14 10h4l3 3v3h-7"/><circle cx="7" cy="17.5" r="1.5"/><circle cx="17" cy="17.5" r="1.5"/>',
    'wrench':'<path d="M14.7 6.3a4 4 0 0 0-5.3 5.1L4 16.8 7.2 20l5.4-5.4a4 4 0 0 0 5.1-5.3l-2.4 2.4-2.6-.6-.6-2.6z"/>',
    'check':'<circle cx="12" cy="12" r="9"/><path d="M8 12.2l2.7 2.8L16 9.5"/>',
}

# Most specific words first: « Rénovation de salle de bain » is a bath, not a house.
KEYWORDS = (
    ('bath',r'salle de bain|douche|baignoire|sanitaire'),
    ('flame',r'chauff|chaudiere|pompe a chaleur|cheminee|poele|climatis'),
    ('bolt',r'electri|eclairage|tableau|prise|borne|domotique'),
    ('droplet',r'plomb|fuite|eau|canalisation|robinet|debouch|ballon'),
    ('car',r'automobile|autos?\b|voiture|vehicule|pneu|frein|vidange|carross|moteur|garage|mecani'),
    ('sparkle',r'nettoy|menage|proprete|vitre|desinfect|entretien de locaux'),
    ('brush',r'peint|decor|enduit|papier peint|ravalement'),
    ('leaf',r'jardin|paysag|elagage|tonte|espaces? verts?|haie'),
    ('key',r'serrur|cles?\b|clef|blindage|ouverture de porte'),
    ('hammer',r'menuis|charpent|parquet|montage|agencement|bois|pose'),
    ('home',r'renov|macon|construct|maison|extension|toiture|couverture|facade|batiment'),
    ('document',r'comptab|juridi|avocat|administr|document|assurance|fiscal'),
    ('search',r'diagnos|controle|audit|conseil|etude|expertise|inspection'),
    ('scissors',r'coiff|coupe|barb|couture'),
    ('utensils',r'restaur|cuisine|traiteur|repas|menu|boulang|patiss'),
    ('shield',r'securi|alarme|surveill|video|protection'),
    ('heart',r'soin|massage|beaute|esthet|sante|bien-etre|therap'),
    ('truck',r'demenag|livraison|transport|evacuation|debarras'),
    ('wrench',r'depann|repar|entretien|maintenance|install|reglage'),
)


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFD',value.lower()) if unicodedata.category(c)!='Mn')


def icon_name(*texts):
    """First matching icon for the supplied texts, in order; a neutral check otherwise."""
    for value in texts:
        value=normalized(value or '')
        for name,pattern in KEYWORDS:
            if re.search(r'\b(?:'+pattern+')',value):return name
    return 'check'


def icon_svg(name):
    return ('<svg class="le-icon" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" '
            'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
            + PATHS[name] + '</svg>')
