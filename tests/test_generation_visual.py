"""Decorative icons, composed hero without photo and photos spread through the page."""
from dataclasses import replace
import unittest

from bs4 import BeautifulSoup

from generation.essential import prepare_essential,render_essential
from generation.icons import PATHS,icon_name,icon_svg
from generation.profile import ImageAsset,Service
from tests.test_generation_components import PNG,complete_profile
from tests.test_generation_essential import minimal


def soup_for(profile,**options):
    return BeautifulSoup(render_essential(prepare_essential(profile,**options)).document,'html.parser')


class ServiceIconTests(unittest.TestCase):
    def test_icons_follow_supplied_words_and_fall_back_to_a_neutral_mark(self):
        for texts,expected in [(('Rénovation de salle de bain',),'bath'),(('Freinage',),'car'),
                               (('Installation électrique',),'bolt'),(('Parties communes','Nettoyage professionnel'),'sparkle'),
                               (('Bureaux','Un entretien pensé autour de vos espaces'),'wrench'),(('Clés et badges',),'key'),
                               (('Client fidèle',),'check'),(('Prestation fournie',),'check')]:
            with self.subTest(texts=texts):self.assertEqual(icon_name(*texts),expected)

    def test_icons_are_inline_decorative_and_local(self):
        for name in PATHS:
            svg=BeautifulSoup(icon_svg(name),'html.parser').svg
            self.assertEqual(svg['aria-hidden'],'true')
            self.assertEqual(svg['stroke'],'currentColor')
            self.assertNotIn('http',str(svg).replace('http://www.w3.org',''))

    def test_each_service_gets_an_icon_without_changing_its_text(self):
        profile=replace(minimal(),services=(Service('Dépannage plomberie'),Service('Pose de parquet')))
        soup=soup_for(profile)
        items=soup.select('.le-services h3')
        self.assertEqual([item.get_text() for item in items],['Dépannage plomberie','Pose de parquet'])
        self.assertEqual(len(soup.select('.le-services .le-service-icon svg')),2)
        self.assertFalse(soup.select('.le-services .le-service-number'))


class HeroAndPhotoTests(unittest.TestCase):
    def test_hero_without_photo_shows_supplied_services_in_a_decorative_visual(self):
        profile=replace(minimal(),services=tuple(Service(f'Prestation {i}') for i in range(5)))
        for theme in ['clair','editorial','contraste']:
            with self.subTest(theme=theme):
                graphic=soup_for(profile,theme=theme).select_one('.le-hero .le-hero-graphic')
                self.assertEqual(graphic['aria-hidden'],'true')
                self.assertEqual([li.get_text() for li in graphic.select('li')],['Prestation 0','Prestation 1','Prestation 2'])

    def test_hero_photo_replaces_the_visual(self):
        soup=soup_for(complete_profile())
        self.assertTrue(soup.select('.le-hero-image img'))
        self.assertFalse(soup.select('.le-hero-graphic'))

    def test_first_gallery_photo_illustrates_about_and_is_not_repeated(self):
        photos=tuple(ImageAsset(PNG,f'Photo {i}','gallery') for i in range(3))
        soup=soup_for(replace(minimal(),images=photos))
        self.assertEqual(soup.select_one('.le-about-image img')['alt'],'Photo 0')
        self.assertEqual([img['alt'] for img in soup.select('.le-gallery img')],['Photo 1','Photo 2'])

    def test_single_gallery_photo_goes_to_about_without_an_empty_gallery(self):
        draft=prepare_essential(replace(minimal(),images=(ImageAsset(PNG,'Seule photo','gallery'),)))
        self.assertNotIn('gallery',[section.component for section in draft.plan.sections])
        soup=BeautifulSoup(render_essential(draft).document,'html.parser')
        self.assertEqual(soup.select_one('.le-about-image img')['alt'],'Seule photo')
        self.assertFalse(soup.select('a[href="#images"]'))


if __name__=='__main__':unittest.main()
