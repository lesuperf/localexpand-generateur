import base64
from copy import deepcopy
import json
import unittest

from generation.profile import BusinessProfile, ProfileError, profile_issues


def business_data():
    return {'name':'Entreprise de test', 'profession':'Activité libre',
            'description':'Une présentation fournie par l’entreprise.',
            'city':'Ville de test', 'phone':'04 00 00 00 00',
            'services':[{'title':'Prestation fournie','description':'Une description confirmée.'}]}


class ProfileTests(unittest.TestCase):
    def test_business_without_website_and_unlisted_profession(self):
        profile = BusinessProfile.from_dict(business_data())
        self.assertEqual(profile.website, '')
        self.assertEqual(profile.profession, 'Activité libre')
        self.assertFalse(profile_issues(profile))

    def test_versioned_json_roundtrip_including_optional_facts(self):
        data = dict(business_data(), areas=['Zone A','Zone A','Zone B'], benefits=['Un point fourni'],
                    images=[{'src':'assets/logo.png','alt':'','role':'logo'}],
                    projects=[{'title':'Projet fourni','image':{'src':'assets/projet.webp','alt':'Description fournie'}}],
                    testimonials=[{'quote':'Un témoignage fourni','author':'Auteur fourni','source_url':'https://example.test/avis'}],
                    faq=[{'question':'Question fournie ?','answer':'Réponse fournie.'}],
                    additional_information={'horaires':'Sur rendez-vous'},
                    visuals={'primary':'#AABBCC','accent':'#112233','theme':'editorial'})
        original = deepcopy(data)
        profile = BusinessProfile.from_dict(data)
        loaded = BusinessProfile.from_dict(json.loads(json.dumps(profile.to_dict())))
        self.assertEqual(profile, loaded)
        self.assertEqual(profile.areas, ('Zone A','Zone B'))
        self.assertEqual(profile.visuals.primary, '#aabbcc')
        self.assertEqual(data, original)

    def test_incomplete_draft_is_represented_but_cannot_be_considered_complete(self):
        profile = BusinessProfile.from_dict({})
        self.assertEqual({i.field for i in profile_issues(profile) if i.severity=='error'},
                         {'name','profession','description','services','contact'})
        self.assertEqual(profile.services, ())
        self.assertEqual(profile.testimonials, ())

    def test_malformed_shapes_and_future_versions_fail_with_a_field(self):
        cases = [('schema_version',True),('schema_version',2),('name',True),
                 ('services','Un service'),('images',{}),('additional_information',[]),
                 ('description','x'*2001),('name','Texte\x01')]
        for field,value in cases:
            with self.subTest(field=field,value=str(value)[:30]), self.assertRaises(ProfileError) as caught:
                BusinessProfile.from_dict(dict(business_data(), **{field:value}))
            self.assertEqual(caught.exception.field,field)
        with self.assertRaises(ProfileError):
            BusinessProfile.from_dict(dict(business_data(), profession_typo='Autre'))

    def test_contact_urls_and_css_injections_are_rejected(self):
        for field,value in [('phone','javascript:alert(1)'),('phone','++33000000000'),
                            ('email','nom@example.test?subject=piège'),('website','javascript:alert(1)'),
                            ('website','https://user:secret@example.test/'),
                            ('visuals',{'primary':'red;url(x)'}),('visuals',{'theme':'../autre'})]:
            with self.subTest(field=field,value=value), self.assertRaises(ProfileError):
                BusinessProfile.from_dict(dict(business_data(), **{field:value}))

    def test_image_sources_are_bounded_local_or_embedded_and_not_fetched(self):
        embedded = 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()
        data = dict(business_data(), images=[{'src':embedded,'alt':'Une image'}])
        self.assertEqual(BusinessProfile.from_dict(data).images[0].src,embedded)
        for src in ['../photo.png','/photo.png','C:/photo.png','assets/%2e%2e/photo.png',
                    'https://example.test/photo.png','data:image/svg+xml,<svg/>',
                    'data:image/png;base64,bm90LWFuLWltYWdl','photo.svg','assets\\photo.png']:
            with self.subTest(src=src), self.assertRaises(ProfileError):
                BusinessProfile.from_dict(dict(business_data(),images=[{'src':src}]))

    def test_duplicate_primary_image_and_incomplete_optional_evidence_rejected(self):
        cases = [dict(images=[{'src':'a.png','role':'hero'},{'src':'b.png','role':'hero'}]),
                 dict(testimonials=[{'quote':'Sans auteur'}]),
                 dict(faq=[{'question':'Sans réponse ?'}]),dict(services=['']),
                 dict(projects=[{'title':'Projet','image':{'src':'a.png','role':'logo'}}])]
        for extra in cases:
            with self.subTest(extra=extra), self.assertRaises(ProfileError):
                BusinessProfile.from_dict(dict(business_data(),**extra))

    def test_optional_missing_image_description_is_a_warning(self):
        profile = BusinessProfile.from_dict(dict(business_data(),images=[{'src':'photo.jpg'}]))
        issues=profile_issues(profile)
        self.assertEqual(len(issues),1)
        self.assertEqual(issues[0].severity,'warning')

    def test_normalization_never_silently_discards_duplicate_additional_facts(self):
        with self.assertRaises(ProfileError):
            BusinessProfile.from_dict(dict(business_data(),additional_information={'Nom ':'Premier',' Nom':'Second'}))


if __name__ == '__main__':
    unittest.main()
