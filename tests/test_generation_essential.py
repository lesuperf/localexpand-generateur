import base64
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from bs4 import BeautifulSoup

from generation.essential import prepare_essential, render_essential
from generation.exporter import export_essential,zip_export
from generation.profile import BusinessProfile,ImageAsset,ProfileError,Service,VisualPreferences

FIXTURES=Path(__file__).resolve().parents[1]/'generation/fixtures'
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6wwAAAABJRU5ErkJggg==')


def fixture(key='plombier'):
    return BusinessProfile.from_dict(json.loads((FIXTURES/f'{key}.json').read_text(encoding='utf-8')))


def minimal():
    return BusinessProfile(name='Fiche de test',profession='Activité libre',description='Présentation vérifiée.',
                           services=(Service('Prestation fournie'),),email='test@example.test')


class AutomaticEssentialTests(unittest.TestCase):
    def test_all_eleven_components_can_be_composed_from_supplied_facts(self):
        from tests.test_generation_components import complete_profile
        from generation.components import RENDERERS
        profile=complete_profile()
        draft=prepare_essential(profile,demo=True)
        self.assertEqual({section.component for section in draft.plan.sections},set(RENDERERS))
        self.assertEqual(draft.profile.testimonials,profile.testimonials)
        self.assertEqual(draft.profile.projects,profile.projects)
        self.assertEqual(draft.profile.faq,profile.faq)
        self.assertEqual(render_essential(draft).status,'generated')

    def test_contraste_is_the_automatic_style_for_every_activity(self):
        themes=[]
        for name in ['plombier','garage','nettoyage']:
            profile=fixture(name);original=profile.to_dict();draft=prepare_essential(profile,demo=True)
            result=render_essential(draft)
            self.assertEqual(profile.to_dict(),original)
            self.assertFalse(profile.website)
            self.assertEqual(result.status,'generated')
            self.assertFalse(result.delivery_ready)
            self.assertIn('ENTREPRISE FICTIVE',result.document)
            self.assertTrue(result.quality.passed)
            themes.append(draft.theme)
        self.assertEqual(themes,['contraste','contraste','contraste'])
        self.assertEqual(prepare_essential(minimal()).theme,'contraste')

    def test_empty_optional_sections_are_omitted(self):
        draft=prepare_essential(minimal());names=[s.component for s in draft.plan.sections]
        self.assertNotIn('gallery',names);self.assertNotIn('testimonials',names)
        self.assertNotIn('benefits',names);self.assertNotIn('areas',names)
        self.assertNotIn('faq',names)
        soup=BeautifulSoup(render_essential(draft).document,'html.parser')
        self.assertFalse(soup.select('form'))
        self.assertEqual(soup.select_one('.le-contact a')['href'],'mailto:test@example.test')

    def test_supplied_text_and_faq_never_replaced(self):
        draft=prepare_essential(fixture('garage'))
        self.assertEqual(draft.profile.services,fixture('garage').services)
        self.assertEqual(draft.content.headline,fixture('garage').headline)
        twice=prepare_essential(draft.profile)
        self.assertEqual(twice.profile.faq,draft.profile.faq)

    def test_neutral_text_uses_only_service_and_name(self):
        draft=prepare_essential(minimal())
        self.assertIn('prestation fournie',draft.profile.services[0].description)
        self.assertNotIn('certifié',render_essential(draft).document)
        self.assertTrue(draft.copy_sources)

    def test_manual_theme_and_colors_override_automatic_choice(self):
        profile=replace(fixture('garage'),visuals=VisualPreferences('#123456','#eeeeee',''))
        draft=prepare_essential(profile,theme='editorial')
        self.assertEqual(draft.theme,'editorial')
        self.assertEqual(draft.profile.visuals.primary,'#123456')
        self.assertIn('--primary:#123456',render_essential(draft).document)

    def test_missing_required_facts_block_generation(self):
        for profile in [BusinessProfile(),replace(minimal(),services=()),replace(minimal(),email='')]:
            with self.subTest(profile=profile),self.assertRaises(ProfileError):prepare_essential(profile)

    def test_invalid_theme_or_demo_is_rejected(self):
        with self.assertRaises(ProfileError):prepare_essential(minimal(),theme='premium')
        with self.assertRaises(ProfileError):prepare_essential(minimal(),demo='true')

    def test_extreme_valid_lengths_do_not_break_automatic_copy(self):
        profile=replace(minimal(),profession='M'*120,city='V'*80,description='W'*2000,
                        areas=tuple(str(i)+'Z'*97 for i in range(20)))
        draft=prepare_essential(profile)
        self.assertLessEqual(len(draft.content.headline),180)
        self.assertEqual(render_essential(draft).status,'generated')

    def test_export_missing_asset_fails_before_writing_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination=Path(temporary)/'export'
            with self.assertRaises(ProfileError):export_essential(prepare_essential(fixture()),destination,assets_root=temporary)
            self.assertFalse(destination.exists())

    def test_export_css_assets_and_zip_are_self_contained(self):
        profile=replace(minimal(),images=(ImageAsset('data:image/png;base64,'+base64.b64encode(PNG).decode(),'Photo de test','hero'),))
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)/'site'
            report=export_essential(prepare_essential(profile),folder)
            soup=BeautifulSoup((folder/'index.html').read_text(encoding='utf-8'),'html.parser')
            self.assertFalse(soup.select('style'))
            self.assertEqual(soup.select_one('link')['href'],'styles.css')
            self.assertEqual((folder/soup.img['src']).read_bytes(),PNG)
            self.assertTrue(report['structure']['passed']);self.assertFalse(report['delivery_ready'])
            self.assertFalse(report['browser']['completed'])
            archive=io.BytesIO();zip_export(folder,archive)
            with zipfile.ZipFile(archive) as zipped:
                self.assertIn('styles.css',zipped.namelist())
                self.assertIn(soup.img['src'],zipped.namelist())
                self.assertNotIn('fiche.json',zipped.namelist())
            with self.assertRaises(FileExistsError):export_essential(prepare_essential(profile),folder)

    def test_asset_symlink_cannot_escape_root(self):
        # Windows symlink creation is privileged; mock canonical resolution.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'assets';root.mkdir()
            profile=replace(minimal(),images=(ImageAsset('photo.png','Photo','hero'),))
            original=Path.resolve
            def resolve(path,*args,**kwargs):
                return Path(temporary)/'outside.png' if path.name=='photo.png' else original(path,*args,**kwargs)
            with patch.object(Path,'resolve',resolve),self.assertRaises(ProfileError):
                export_essential(prepare_essential(profile),Path(temporary)/'site',assets_root=root)


if __name__=='__main__':unittest.main()
