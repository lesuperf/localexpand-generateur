import base64
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from generation.components import ComponentContext, RENDERERS, render_component
from generation.composition import PagePlan, SectionPlan, VARIANTS, preview_plan
from generation.content import PageContent
from generation.engine import build_preview
from generation.profile import BusinessProfile, ImageAsset, ProfileError
from generation.quality import check_document, css_balanced
from generation.themes import THEMES
from tests.test_generation_profile import business_data

# An isolated fixture, not a customer or an Essentiel/Premium generated project.
PNG = 'data:image/png;base64,' + base64.b64encode(base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j6X8AAAAASUVORK5CYII=')).decode()


def complete_profile():
    return BusinessProfile.from_dict(dict(business_data(), email='test@example.test',
        headline='Un titre explicitement fourni',areas=['Zone A','Zone B'],
        benefits=['Une information fournie','Une autre information fournie'],
        images=[{'src':PNG,'role':'logo','alt':''},{'src':PNG,'role':'hero','alt':'Photo fournie'},
                {'src':PNG,'role':'gallery','alt':'Un visuel fourni'}],
        projects=[{'title':'Un projet fourni','image':{'src':PNG,'alt':'Un projet illustré'},'description':'Description du projet fournie.'}],
        testimonials=[{'quote':'Un témoignage explicitement fourni.','author':'Auteur fourni','source_url':'https://example.test/avis'}],
        faq=[{'question':'Une question fournie ?','answer':'Une réponse fournie.'}],
        additional_information={'Information fournie':'Contenu fourni.'}))


class ComponentTests(unittest.TestCase):
    def test_every_component_renders_independently_in_each_variant(self):
        context=ComponentContext(complete_profile())
        self.assertEqual(set(RENDERERS),set(VARIANTS))
        for name,variants in VARIANTS.items():
            outputs=[]
            for variant in variants:
                with self.subTest(component=name,variant=variant):
                    fragment=render_component(name,context,variant)
                    soup=BeautifulSoup(fragment,'html.parser')
                    node=soup.select_one('[data-component]')
                    self.assertIsNotNone(node)
                    self.assertEqual(node['data-component'],name)
                    self.assertEqual(node['data-variant'],variant)
                    self.assertFalse(soup.select('script,[onclick],[onerror]'))
                    outputs.append(fragment)
            self.assertNotEqual(outputs[0],outputs[1])

    def test_optional_components_do_not_invent_missing_evidence(self):
        context=ComponentContext(BusinessProfile.from_dict(business_data()))
        for component in ['benefits','gallery','testimonials','faq']:
            with self.subTest(component=component):
                self.assertEqual(render_component(component,context),'')
        output=build_preview(context.profile,preview_plan())
        self.assertEqual(output.status,'generated')
        self.assertFalse(output.delivery_ready)
        self.assertEqual(sum(i.code=='omitted' for i in output.issues),4)
        self.assertNotIn('aggregateRating',output.document)
        self.assertNotIn('Témoignages',BeautifulSoup(output.document,'html.parser').get_text())

    def test_gallery_and_testimonials_only_present_supplied_evidence(self):
        context=ComponentContext(complete_profile())
        gallery=BeautifulSoup(render_component('gallery',context),'html.parser')
        self.assertEqual(len(gallery.select('figure')),2)
        self.assertIn('Un projet fourni',gallery.get_text())
        testimonial=BeautifulSoup(render_component('testimonials',context),'html.parser')
        self.assertEqual(testimonial.blockquote.get_text(),'Un témoignage explicitement fourni.')
        self.assertEqual(testimonial.select_one('a')['href'],'https://example.test/avis')
        self.assertNotIn('vérifié',testimonial.get_text().lower())

    def test_all_business_content_is_escaped(self):
        attack='</script><img src=x onerror=alert(1)>'
        profile=BusinessProfile.from_dict(dict(business_data(),name=attack,description=attack,
            services=[{'title':attack,'description':attack}],benefits=[attack],
            testimonials=[{'quote':attack,'author':attack}],faq=[{'question':attack,'answer':attack}],
            additional_information={attack:attack}))
        content=PageContent.from_dict({'headline':attack,'services_title':attack})
        result=build_preview(profile,preview_plan(),content)
        self.assertEqual(result.status,'generated')
        soup=BeautifulSoup(result.document,'html.parser')
        self.assertFalse(soup.select('[onerror],img[src=x]'))
        self.assertEqual(len(soup.select('script')),1)
        self.assertEqual(json.loads(soup.script.string)['name'],attack)
        self.assertEqual(soup.h1.get_text(),attack)

    def test_contact_has_labels_and_no_enabled_submission(self):
        soup=BeautifulSoup(render_component('contact',ComponentContext(complete_profile())),'html.parser')
        self.assertEqual(soup.select_one('a[href^="tel:"]')['href'],'tel:0400000000')
        self.assertEqual(soup.select_one('a[href^="mailto:"]')['href'],'mailto:test@example.test')
        self.assertIsNotNone(soup.select_one('fieldset[disabled]'))
        self.assertFalse(soup.select('form[action]'))
        for field in soup.select('input,textarea'):
            self.assertIsNotNone(soup.find('label',attrs={'for':field['id']}))

    def test_native_faq_has_accessible_question_and_answer(self):
        context=ComponentContext(complete_profile())
        soup=BeautifulSoup(render_component('faq',context,'accordion'),'html.parser')
        self.assertEqual(soup.summary.get_text(),'Une question fournie ?')
        self.assertEqual(soup.details.p.get_text(),'Une réponse fournie.')
        self.assertFalse(soup.select('script'))

    def test_render_boundary_rejects_direct_dataclass_injection(self):
        profile=replace(complete_profile(),images=(ImageAsset('javascript:alert(1)','Piège','hero'),))
        with self.assertRaises(ProfileError):ComponentContext(profile)
        with self.assertRaises(ProfileError):ComponentContext(complete_profile(),navigation=(('Lien','javascript:x'),))
        with self.assertRaises(ProfileError):render_component('hero',None)


class EngineTests(unittest.TestCase):
    def test_same_content_renders_with_every_theme_and_variant_set(self):
        profile=complete_profile()
        for theme in THEMES:
            for variant_index in [0,1]:
                with self.subTest(theme=theme.key,variants=variant_index):
                    plan=PagePlan(tuple(SectionPlan(name,variants[variant_index]) for name,variants in VARIANTS.items()))
                    result=build_preview(profile,plan,theme=theme.key)
                    self.assertEqual(result.status,'generated')
                    self.assertTrue(result.quality.passed)
                    self.assertFalse(result.delivery_ready)
                    soup=BeautifulSoup(result.document,'html.parser')
                    self.assertEqual(soup.body['data-theme'],theme.key)
                    self.assertEqual(len(soup.select('[data-component]')),11)
                    self.assertEqual(soup.h1.get_text(),profile.headline)
                    self.assertFalse(soup.select('link[href],script[src],img[src^="http"]'))

    def test_explicit_section_order_is_respected(self):
        plan=PagePlan((SectionPlan('header'),SectionPlan('hero'),SectionPlan('faq'),
                       SectionPlan('services'),SectionPlan('contact'),SectionPlan('footer')))
        result=build_preview(complete_profile(),plan)
        soup=BeautifulSoup(result.document,'html.parser')
        self.assertEqual([n['data-component'] for n in soup.select('main>[data-component]')],['hero','faq','services','contact'])

    def test_missing_facts_return_incomplete_without_document(self):
        result=build_preview(BusinessProfile.from_dict({}),preview_plan())
        self.assertEqual(result.status,'incomplete')
        self.assertIsNone(result.document)
        self.assertIsNone(result.quality)
        self.assertTrue(any(issue.field=='name' for issue in result.issues))

    def test_invalid_theme_plan_and_missing_resource_fail_explicitly(self):
        profile=complete_profile()
        for plan,theme in [(PagePlan((SectionPlan('services'),)),''),(preview_plan(),'unknown')]:
            with self.subTest(theme=theme):
                result=build_preview(profile,plan,theme=theme)
                self.assertEqual(result.status,'incomplete')
                self.assertIsNone(result.document)
        with patch('generation.engine.Path.read_text',side_effect=OSError('private-path')):
            result=build_preview(profile,preview_plan())
            self.assertEqual(result.status,'incomplete')
            self.assertNotIn('private-path',str(result.issues))

    def test_malformed_direct_context_is_reported_as_incomplete(self):
        malformed=replace(complete_profile(),additional_information=7)
        result=build_preview(malformed,preview_plan())
        self.assertEqual(result.status,'incomplete')
        self.assertIsNone(result.document)
        with self.assertRaises(ProfileError):ComponentContext(complete_profile(),navigation=None)

    def test_navigation_targets_only_selected_available_sections(self):
        profile=BusinessProfile.from_dict(business_data())
        plan=PagePlan((SectionPlan('header'),SectionPlan('hero'),SectionPlan('testimonials'),SectionPlan('services'),SectionPlan('footer')))
        result=build_preview(profile,plan)
        self.assertEqual(result.status,'generated')
        soup=BeautifulSoup(result.document,'html.parser')
        self.assertFalse(soup.select('a[href="#temoignages"],a[href="#contact"]'))
        self.assertTrue(soup.select('.le-hero a[href="tel:0400000000"]'))

    def test_preview_metadata_is_based_on_facts_without_production_claim(self):
        result=build_preview(complete_profile(),preview_plan())
        soup=BeautifulSoup(result.document,'html.parser')
        self.assertIn('Entreprise de test',soup.title.get_text())
        self.assertEqual(soup.select_one('meta[name=robots]')['content'],'noindex, nofollow')
        self.assertFalse(soup.select('link[rel=canonical]'))
        schema=json.loads(soup.script.string)
        self.assertEqual(schema['areaServed'],['Zone A','Zone B'])
        self.assertFalse({'review','aggregateRating','address','url'} & schema.keys())


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.document=build_preview(complete_profile(),preview_plan()).document

    def test_broken_links_metadata_and_accessibility_are_detected(self):
        cases=[('href="#prestations"','href="#absent"','anchors'),
               ('<h1>','<h2>','h1'),('name="description"','name="absent"','description'),
               ('for="contact-nom"','for="absent"','labels'),
               ('aria-describedby="contact-demo"','aria-describedby="absent"','aria_references'),
               ('id="presentation"','id="prestations"','unique_ids')]
        for old,new,expected in cases:
            with self.subTest(expected=expected):
                report=check_document(self.document.replace(old,new))
                self.assertFalse(report.passed)
                self.assertTrue(any(issue.code==expected for issue in report.issues))

    def test_active_scripts_forms_and_remote_resources_are_detected(self):
        mutations=[self.document.replace('</head>','<script>alert(1)</script></head>'),
                   self.document.replace('<form ','<form action="https://example.test" '),
                   self.document.replace('<fieldset disabled>','<fieldset>'),
                   self.document.replace('</head>','<link rel="stylesheet" href="https://example.test/style.css"></head>'),
                   self.document.replace('class="le-page"','class="le-page" style="background:url(https://example.test/image.png)"'),
                   self.document.replace('class="le-page"','class="le-page" onload="alert(1)"')]
        for doc in mutations:
            with self.subTest(doc=doc[-80:]):self.assertFalse(check_document(doc).passed)

    def test_malformed_css_and_structured_data_are_detected(self):
        self.assertFalse(css_balanced('body{color:red'))
        self.assertFalse(css_balanced('body{content:"unterminated}'))
        self.assertTrue(css_balanced('body{content:"}"}/* note */'))
        self.assertFalse(css_balanced('body{color:red}/* unfinished'))
        self.assertTrue(css_balanced('body{content:"/*"}'))
        doc=self.document.replace('"@type": "LocalBusiness"','"@type": INVALID')
        self.assertFalse(check_document(doc).passed)
        self.assertFalse(check_document(self.document.replace('</style>','body{</style>')).passed)

    def test_failed_structural_check_is_never_reported_as_generated(self):
        bad=check_document('<html></html>')
        with patch('generation.engine.check_document',return_value=bad):
            result=build_preview(complete_profile(),preview_plan())
        self.assertEqual(result.status,'incomplete')
        self.assertIsNone(result.document)


if __name__ == '__main__':unittest.main()
