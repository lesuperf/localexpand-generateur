"""Pure input adapters for the two existing journeys; no route or stored data changes."""
from __future__ import annotations

from .profile import BusinessProfile, ProfileError


def from_legacy_profile(data: dict, *, profession: str = '') -> BusinessProfile:
    """Read an existing reviewed profile without rewriting its original schema.

    `profession` can be supplied by the caller's existing sector catalogue. The
    core deliberately has no fixed list of professions or old design names.
    """
    if not isinstance(data, dict):
        raise ProfileError('profile', 'Une fiche existante est attendue.')
    images = []
    for role in ['logo', 'hero']:
        if data.get(role):
            images.append({'src':data[role], 'role':role, 'alt':data.get('hero_alt', '') if role=='hero' else ''})
    return BusinessProfile.from_dict({
        'name':data.get('company',''), 'profession':profession or data.get('sector',''),
        'description':data.get('intro',''), 'headline':data.get('headline',''),
        'city':data.get('city',''), 'phone':data.get('phone',''), 'email':data.get('email',''),
        'website':data.get('source_url',''), 'services':data.get('services',[]), 'images':images,
        'visuals':{'primary':data.get('primary',''), 'accent':data.get('accent','')},
    })


def from_public_form(data: dict, photos: dict | None = None, *, profession: str = '') -> BusinessProfile:
    """Accept current form values and optional already-resized browser images.

    No storage/upload is introduced. The caller decides when to invoke the
    adapter; the existing browser-only creator continues working unchanged.
    """
    if not isinstance(data, dict):
        raise ProfileError('profile', 'Les valeurs du formulaire sont attendues.')
    services = data.get('services', [])
    if isinstance(services, str):
        services = [line.strip() for line in services.splitlines() if line.strip()]
    zones = data.get('zones', '')
    if not isinstance(zones, str):
        raise ProfileError('zones', 'La zone doit contenir du texte.')
    photos = photos if photos is not None else {}
    if not isinstance(photos, dict) or set(photos) - {'logo','hero','gallery'}:
        raise ProfileError('photos', 'Les emplacements logo, hero et gallery sont attendus.')
    images = []
    for role in ['logo','hero']:
        photo = photos.get(role)
        if photo is not None:
            if not isinstance(photo, dict):
                raise ProfileError('photos.' + role, 'Une image est attendue.')
            images.append({'src':photo.get('src',''), 'alt':photo.get('caption',''), 'role':role})
    gallery = photos.get('gallery', [])
    if not isinstance(gallery, (list,tuple)) or len(gallery)>6:
        raise ProfileError('photos.gallery', 'Six photos maximum sont autorisées.')
    for i, photo in enumerate(gallery):
        if not isinstance(photo, dict):
            raise ProfileError(f'photos.gallery.{i}', 'Une image est attendue.')
        # A caption describes an image, not evidence of a completed project.
        # Only explicitly structured projects can populate profile.projects.
        image = {'src':photo.get('src',''), 'alt':photo.get('caption',''), 'role':'gallery'}
        images.append(image)
    return BusinessProfile.from_dict({
        'name':data.get('company',data.get('business','')),
        'profession':profession or data.get('trade',''), 'description':data.get('presentation',''),
        'headline':data.get('headline',''), 'city':data.get('city',''),
        'areas':[zone.strip() for zone in zones.split(',') if zone.strip()],
        'phone':data.get('phone',''), 'email':data.get('email',''),
        'services':services, 'images':images,
    })
