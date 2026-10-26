"""Phase D behavior, resource boundaries and preservation of verified facts."""
import base64
from dataclasses import replace
from pathlib import Path
import re
import tempfile
import unittest

from bs4 import BeautifulSoup

from generation.components import ComponentContext,header
from generation.essential import prepare_essential,render_essential
from generation.exporter import export_essential
from generation.profile import BusinessProfile,ImageAsset,VisualPreferences
from generation.quality import css_without_remote_resources
from generation.themes import THEMES,contrast
from generation.typefaces import embedded_typefaces
from tests.test_generation_components import complete_profile
from tests.test_generation_essential import minimal


class EssentialDesignTests(unittest.TestCase):
    def test_catalogue_fonts_are_valid_embedded_woff2_with_licenses(self):
        for theme in ['clair','contraste','editorial']:
            css=embedded_typefaces(theme)
            blobs=re.findall(r'url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)',css)
            self.assertGreaterEqual(len(blobs),1)
            for encoded in blobs:self.assertTrue(base64.b64decode(encoded,validate=True).startswith(b'wOF2'))
            self.assertIn('SIL OPEN FONT LICENSE',css)
            self.assertIn('--display-font:',css)
            self.assertTrue(css_without_remote_resources(css))

    def test_css_resource_guard_still_rejects_remote_and_invalid_resources(self):
        for css in ['@import "https://example.test/a.css";',
                    'body{background:url(https://example.test/a.png)}',
                    'body{background:url(data:image/png;base64,AAAA)}',
                    'body{background:image-set("https://example.test/a.png" 1x)}',
                    '@font-face{src:url(data:font/woff2;base64,AAAA)}',
                    '@font-face{src:url(data:font/woff2;base64,***?)}']:
            with self.subTest(css=css):self.assertFalse(css_without_remote_resources(css))

    def test_primary_text_token_remains_readable_for_extreme_user_colors(self):
        for theme in THEMES:
            for color in ['#ffffff','#000000','#ffff00','#ffffff']:
                current=replace(theme,primary=color)
                token=re.search(r'--primary-ink:(#[a-f0-9]{6})',current.css_variables())[1]
                self.assertGreaterEqual(contrast(token,current.paper),4.5)
                self.assertGreaterEqual(contrast(token,current.surface),4.5)

    def test_header_uses_compact_desktop_navigation_but_keeps_full_mobile_access(self):
        profile=complete_profile();draft=prepare_essential(profile)
        soup=BeautifulSoup(render_essential(draft).document,'html.parser')
        self.assertLessEqual(len(soup.select('.le-desktop-nav nav a')),3)
        self.assertEqual(soup.select_one('.le-desktop-nav .le-header-cta')['href'],'#contact')
        self.assertEqual(len(soup.select('.le-mobile-nav nav a')),len(draft.plan.sections)-3)

    def test_visual_emphasis_does_not_change_or_inject_headline(self):
        title='Un titre fourni avec <script>alert(1)</script> & une fin personnalisée'
        profile=replace(minimal(),headline=title)
        doc=render_essential(prepare_essential(profile)).document
        soup=BeautifulSoup(doc,'html.parser')
        self.assertEqual(soup.h1.get_text(),title)
        self.assertTrue(soup.h1.select_one('.le-title-accent'))
        self.assertFalse(soup.select('script:not([type="application/ld+json"])'))

    def test_identity_uses_name_initials_without_fictitious_certification(self):
        profile=replace(minimal(),name='Atelier Exemple')
        soup=BeautifulSoup(render_essential(prepare_essential(profile)).document,'html.parser')
        self.assertEqual(soup.select_one('.le-header .le-brand-symbol').get_text(),'AE')
        self.assertEqual(soup.select_one('.le-header .le-brand-name').get_text(),profile.name)
        for claim in ['certifié','4.9','100% satisfait','20 ans']:self.assertNotIn(claim,soup.get_text())

    def test_mobile_contact_uses_only_supplied_coordinates(self):
        for profile,href in [(minimal(),'mailto:test@example.test'),(replace(minimal(),phone='01 23 45 67 89'),'tel:0123456789')]:
            soup=BeautifulSoup(render_essential(prepare_essential(profile)).document,'html.parser')
            self.assertEqual(soup.select_one('.le-mobile-contact>a')['href'],href)
            self.assertFalse(soup.select('form'))

    def test_optional_secondary_link_does_not_point_to_absent_section(self):
        from generation.composition import PagePlan,SectionPlan
        from generation.engine import build_preview
        result=build_preview(minimal(),PagePlan((SectionPlan('hero'),SectionPlan('contact'))),contact_mode='direct')
        self.assertEqual(result.status,'generated')
        self.assertNotIn('href="#prestations"',result.document)

    def test_all_sections_and_real_content_remain_present(self):
        original=complete_profile();snapshot=original.to_dict()
        result=render_essential(prepare_essential(original,demo=True))
        soup=BeautifulSoup(result.document,'html.parser')
        self.assertEqual(len(soup.select('[data-component]')),11)
        self.assertEqual(original.to_dict(),snapshot)
        self.assertEqual(len(soup.select('.le-section-kicker')),8)
        self.assertIn(original.testimonials[0].quote,soup.get_text())
        self.assertIn(original.projects[0].title,soup.get_text())

    def test_export_contains_self_contained_typefaces_and_licenses(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)/'site'
            report=export_essential(prepare_essential(minimal(),theme='editorial'),folder)
            css=(folder/'styles.css').read_text(encoding='utf-8')
            html=(folder/'index.html').read_text(encoding='utf-8')
            self.assertIn('data:font/woff2;base64,',css)
            self.assertIn('SIL OPEN FONT LICENSE',css)
            self.assertIn('font-src data:',html)
            self.assertEqual(report['design_version'],'essentiel-phase-d-v1')
            self.assertTrue(report['structure']['passed'])
            self.assertFalse(report['delivery_ready'])

    def test_foundation_mode_does_not_get_essentiel_mobile_actions_or_fonts(self):
        from generation.engine import build_preview
        from generation.composition import preview_plan
        result=build_preview(minimal(),preview_plan())
        self.assertNotIn('data:font/woff2',result.document)
        self.assertNotIn('class="le-mobile-contact"',result.document)
        self.assertIn('Envoi non activé',result.document)


if __name__=='__main__':unittest.main()
