from copy import deepcopy
from dataclasses import replace
import unittest

from generation.adapters import from_legacy_profile, from_public_form
from generation.composition import PagePlan, SectionPlan, VARIANTS, preview_plan
from generation.content import PageContent
from generation.premium import PremiumBrief
from generation.profile import BusinessProfile, ProfileError, VisualPreferences
from generation.themes import THEMES, contrast, on_color, resolve_theme
from tests.test_generation_profile import business_data


class FoundationTests(unittest.TestCase):
    def test_existing_profile_converts_without_url_requirement_or_mutation(self):
        old={'company':'Entreprise','sector':'activité-libre','intro':'Texte fourni',
             'services':['Service fourni'],'phone':'04 00 00 00 00','primary':'#112233','accent':'#445566',
             'logo':'logo.png','hero':'hero.jpg','hero_alt':'Un visuel fourni','design':'studio','warnings':['À relire']}
        initial=deepcopy(old)
        common=from_legacy_profile(old,profession='Profession fournie')
        self.assertEqual(common.name,'Entreprise')
        self.assertEqual(common.profession,'Profession fournie')
        self.assertEqual(common.website,'')
        self.assertEqual(common.images[1].alt,'Un visuel fourni')
        self.assertEqual(old,initial)

    def test_public_values_and_photos_convert_without_invented_project(self):
        form={'company':'Entreprise','trade':'activité-libre','presentation':'Texte fourni',
              'services':' Service A\nService B\n','zones':'Zone A, Zone B','email':'test@example.test'}
        photos={'logo':{'src':'logo.png','name':'logo.png'}, 'gallery':[
            {'src':'photo.png','caption':''},{'src':'projet.png','caption':'Une légende fournie'}]}
        initial=deepcopy((form,photos))
        common=from_public_form(form,photos)
        self.assertEqual(common.areas,('Zone A','Zone B'))
        self.assertEqual([s.title for s in common.services],['Service A','Service B'])
        self.assertEqual(len(common.projects),0)
        self.assertEqual(len(common.images),3)
        self.assertEqual(common.images[-1].alt,'Une légende fournie')
        self.assertEqual((form,photos),initial)

    def test_public_adapter_rejects_malformed_images_and_zones(self):
        for data,photos in [({'zones':[]},None),({},[]),({}, {'gallery':[None]}),({}, {'logo':'x'}),({}, {'gallery':[{}]*7})]:
            with self.subTest(data=data,photos=photos),self.assertRaises(ProfileError):
                from_public_form(data,photos)

    def test_content_is_explicit_and_does_not_modify_business_facts(self):
        profile=BusinessProfile.from_dict(business_data())
        copy=PageContent.from_dict({'headline':'Titre fourni','services_title':'Interventions'})
        self.assertEqual(PageContent.from_dict(copy.to_dict()),copy)
        self.assertEqual(profile.headline,'')
        self.assertEqual(profile.description,business_data()['description'])
        for invalid in [{'cta_label':''},{'title_typo':'Texte'},{'headline':True}]:
            with self.subTest(invalid=invalid),self.assertRaises(ProfileError):PageContent.from_dict(invalid)

    def test_catalogue_themes_have_readable_text_and_independent_brand_colors(self):
        for theme in THEMES:
            with self.subTest(theme=theme.key):
                self.assertIn('--heading-font:',theme.css_variables())
                self.assertGreaterEqual(contrast(theme.paper,theme.ink),4.5)
                self.assertGreaterEqual(contrast(theme.primary,on_color(theme.primary)),4.5)
        preferences=VisualPreferences('#ffffff','#000000','editorial')
        theme=resolve_theme(preferences=preferences)
        self.assertEqual(theme.key,'editorial')
        self.assertEqual(theme.primary,'#ffffff')
        self.assertEqual(on_color(theme.primary),'#000000')
        self.assertEqual(THEMES[1].primary,'#304d65')

    def test_custom_brand_midtones_always_get_readable_button_text(self):
        for value in range(256):
            color='#'+f'{value:02x}'*3
            self.assertGreaterEqual(contrast(color,on_color(color)),4.5)

    def test_unknown_themes_and_unsafe_css_tokens_are_rejected(self):
        for key in ['../x','inexistant']:
            with self.assertRaises(ProfileError):resolve_theme(key)
        for theme in [replace(THEMES[0],heading_font='url(x)'),replace(THEMES[0],ink='#f5f5ef'),replace(THEMES[0],radius='999px;display:none')]:
            with self.assertRaises(ProfileError):theme.css_variables()

    def test_composition_selects_variants_without_profession_or_theme_logic(self):
        plan=PagePlan([SectionPlan('header','stacked'),SectionPlan('hero','centered'),SectionPlan('contact'),SectionPlan('footer')])
        self.assertIsInstance(plan.sections,tuple)
        self.assertEqual(plan.sections[1].selected_variant,'centered')
        self.assertEqual(len(preview_plan().sections),len(VARIANTS))
        self.assertEqual(len(VARIANTS),11)

    def test_bad_compositions_fail_before_rendering(self):
        for action in [lambda:SectionPlan('unknown'),lambda:SectionPlan('hero','cards'),
                       lambda:PagePlan(None),
                       lambda:PagePlan((SectionPlan('hero'),SectionPlan('hero'))),
                       lambda:PagePlan((SectionPlan('hero'),),slug='../index'),
                       lambda:PagePlan((SectionPlan('hero'),SectionPlan('header'))),
                       lambda:PagePlan((SectionPlan('footer'),SectionPlan('hero')))]:
            with self.assertRaises(ProfileError):action()

    def test_premium_only_carries_validated_multipage_requirements(self):
        pages=tuple(PagePlan((SectionPlan('hero'),),slug=name) for name in ['index','services','contact'])
        brief=PremiumBrief('commercial',pages)
        self.assertFalse(brief.can_request_mockup)
        self.assertFalse(replace(brief,order_reference='commande-test').can_request_mockup)
        self.assertTrue(replace(brief,order_reference='commande-test',questionnaire_validated=True).can_request_mockup)
        for invalid in [dict(direction='autre'),dict(pages=None),dict(pages=pages[:1]),dict(pages=(pages[0],)*3),dict(questionnaire_validated='oui')]:
            with self.subTest(invalid=invalid),self.assertRaises(ProfileError):replace(brief,**invalid)


if __name__ == '__main__':unittest.main()
