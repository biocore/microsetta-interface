import unittest
import hashlib
import os
import re
import uuid
from unittest.mock import patch
import jwt
from microsetta_interface.server import app
from microsetta_interface.implementation import TOKEN_KEY_NAME
from microsetta_interface.config_manager import SERVER_CONFIG
import requests
import datetime
import time
import random


# check if microsetta-private-api appears to be running
PRIVATE_API_AVAILABLE = False
try:
    req = requests.get(SERVER_CONFIG['private_api_endpoint'] + '/ui')
except:  # noqa
    PRIVATE_API_AVAILABLE = False
else:
    PRIVATE_API_AVAILABLE = (req.status_code == 200)


# obtain the JWT key if it exists
PRIVKEY_ENVVAR = 'MICROSETTA_INTERFACE_DEBUG_JWT_PRIV'
if os.environ.get(PRIVKEY_ENVVAR, False):
    PRIV_KEY = open(os.environ[PRIVKEY_ENVVAR]).read()
else:
    PRIVATE_API_AVAILABLE = False


def _uniqify(email):
    now = datetime.datetime.now()
    ts = time.mktime(now.timetuple())
    r = random.random()
    return "%f.%0.5f.%s" % (ts, r, email)


def _get_consent_id_from_webpage(webpage, consent_type):
    start_pos = webpage.rfind("consent_id")
    end_pos = webpage.find(consent_type)
    consent_data = webpage[start_pos:end_pos]

    pattern = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    obj_match = re.search(pattern, consent_data)
    if obj_match:
        return obj_match.group()

    return None


def _fake_jwt(email, verified, uniqify=False):
    if PRIVATE_API_AVAILABLE:
        # lie and say we're from authrocket
        payload = {'email': email,
                   'email_verified': verified,
                   'iss': 'https://authrocket.com',
                   'sub': hashlib.md5(email.encode('ascii')).hexdigest()}
        encoded = jwt.encode(payload, PRIV_KEY, algorithm='RS256')
        return encoded


# we cannot have fine grain control over the state of the private-api
# during integration testing. we also do not have control over the
# order in which tests are executed. as such, treat each user with
# care, and define new users on an as need basis.
USER_NEW_EMAIL = 'user_new@foo.bar'
USER_NEW = _fake_jwt(USER_NEW_EMAIL, True)

USER_NEW_UNVERIFIED_EMAIL = 'user_unverified@foo.bar'
USER_NEW_UNVERIFIED = _fake_jwt(USER_NEW_UNVERIFIED_EMAIL, False)

USER_NEW_CREATE_ACCOUNT_EMAIL = _uniqify('user_create@foo.bar')
USER_NEW_CREATE_ACCOUNT = _fake_jwt(USER_NEW_CREATE_ACCOUNT_EMAIL, True, True)

USER_WITH_VALID_SAMPLE_EMAIL = "th-dq)wort@3'rey.i3l"
USER_WITH_VALID_SAMPLE = _fake_jwt(USER_WITH_VALID_SAMPLE_EMAIL, True)

# PGP_AmsFQ (test db has 5 unassigned in the test db)
TEST_KIT_1 = 'PGP_AmsFQ'
TEST_KIT_1_SAMPLE_1_BARCODE = '000005097'
TEST_KIT_1_SAMPLE_1_SAMPLE_ID = 'ddbb117b-c8fa-9a94-e040-8a80115d1380'

ADULT_CONSENT = {
                 "participant_name": "foo bar",
                 "age_range": "18-plus",
                 "parent_1_name": None,
                 "assent_obtainer": None,
                 "consent_type": "adult_data",
                 "consent_id": "4f3c5b1e-a16c-485a-b7af-a236409ea0d4"}

BASIC_INFO_ID = 10
AT_HOME_ID = 11
LIFESTYLE_ID = 12
GUT_ID = 13
GENERAL_HEALTH_ID = 14
HEALTH_DIAG_ID = 15
ALLERGIES_ID = 16
DIET_ID = 17
DETAILED_DIET_ID = 18
COVID19_ID = 21
OTHER_ID = 22
VIOSCREEN_ID = 10001
MYFOODREPO_ID = 10002
POLYPHENOL_FFQ_ID = 10003
SPAIN_FFQ_ID = 10004

BASIC_INFO_SIMPLE = {"112": "1970"}
AT_HOME_SIMPLE = {"313": "Unspecified"}
LIFESTYLE_SIMPLE = {"16": "Month"}
GUT_SIMPLE = {"37": "One"}
GENERAL_HEALTH_SIMPLE = {"50": "No"}
HEALTH_DIAGNOSIS_SIMPLE = {"85": "Self-diagnosed"}
ALLERGIES_SIMPLE = {"53": "Yes"}
DIET_SIMPLE = {"1": "Omnivore"}
DETAILED_DIET_SIMPLE = {"56": "Daily"}
COVID19_SIMPLE = {"209": "Janitor"}
OTHER_SIMPLE = {"116": "I like microbiomes"}


@unittest.skipIf(not PRIVATE_API_AVAILABLE,
                 "An instance of microsetta-private-api is not available")
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.claimed_samples = []
        self.patch_for_session = patch("microsetta_interface."
                                       "implementation.session",
                                       dict())
        self.mock_session = self.patch_for_session.start()

        app.app.testing = True
        app.app.config['SECRET_KEY'] = 'secretsecret'
        self.app = app.app.test_client()
        self.app.__enter__()

    def tearDown(self):
        for acct, src, samp in self.claimed_samples:
            self._delete_claimed_sample(acct, src, samp)

        self.patch_for_session.stop()
        self._logout()
        self.app.__exit__(None, None, None)

    def _delete_claimed_sample(self, acct, src, samp):
        # this is clean up, and the call may fail if the sample was never
        # actually claimed. so both 200 or 404 are both "valid" from
        # tearDown
        url = f'/accounts/{acct}/sources/{src}/samples/{samp}/remove'
        self.app.post(url)

    def _html_page(self, resp):
        return resp.get_data(as_text=True)

    def _login(self, token):
        self.mock_session[TOKEN_KEY_NAME] = token

    def _logout(self):
        self.app.get('/logout')

    def _ids_from_url(self, url):
        uuidre = '([a-f0-9-]+)'

        pats = [
            (f'/accounts/{uuidre}/sources/{uuidre}/samples/{uuidre}', 3),
            (f'/accounts/{uuidre}/sources/{uuidre}', 2),
            (f'/accounts/{uuidre}', 1)
        ]

        ids = [None, None, None]
        for pat, n in pats:
            match = re.search(pat, url)
            if match is None:
                continue

            groups = match.groups()
            if len(groups) == n:
                for i in range(n):
                    ids[i] = groups[i]
                return ids
            else:
                raise AssertionError(f"Unexpected URL: {url}")

    def _first_ids_from_html(self, page):
        # turns out the pattern matching for URLs just works
        return self._ids_from_url(page)

    def assertPageTitle(self, resp, title, exp_code=200):
        self.assertEqual(resp.status_code, exp_code)
        data = self._html_page(resp)
        self.assertIn(f'<title>Microsetta - {title}</title>', data)

    def assertPageContains(self, resp, string):
        data = self._html_page(resp)
        self.assertIn(string, data)

    def assertRedirect(self, resp, suffix=None, suffix_is_uuid=False):
        self.assertEqual(resp.status_code, 302)
        self.assertIn('Location', resp.headers)

        if suffix is not None:
            self.assertTrue(resp.headers['Location'].endswith(suffix))

        if suffix_is_uuid:
            url = resp.headers['Location']
            uuid_test = url.rsplit('/', 1)[1]

            try:
                uuid.UUID(uuid_test, version=4)
            except ValueError:
                raise AssertionError(f"{uuid_test} is not a UUID4")

    def redirectURL(self, resp):
        self.assertIn('Location', resp.headers)
        return resp.headers['Location']

    def test_home(self):
        # verify we access
        resp = self.app.get('/home')
        data = self._html_page(resp)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Sign Up', data)

    def test_home_es_mx(self):
        # make sure things come through in spanish
        resp = self.app.get('/home', headers={'Accept-Language': 'es_MX'})
        data = self._html_page(resp)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Sign Up', data)
        self.assertIn('Registrarse', data)

    def test_new_user(self):
        # we should get /home for login if we are not already logged in
        resp = self.app.get('/home')
        self.assertPageTitle(resp, 'Home')

        self._login(USER_NEW)

        # once logged in, we should redirect
        resp = self.app.get('/home')
        self.assertRedirect(resp, 'create_account')

        # this is a new user, so they should go to the account creation page
        new_url = resp.headers['Location']

        # make sure the creation page loads
        resp = self.app.get(new_url)
        self.assertPageTitle(resp, 'Account Details')

        # once logged out, we should not redirect and instead be at home
        self._logout()
        resp = self.app.get('/home')
        self.assertPageTitle(resp, 'Home')

    def test_new_user_create_account(self):
        resp, _, _ = self._new_to_create()
        self.assertPageTitle(resp, 'Account')

    def _new_to_create(self):
        email = _uniqify('user_creater@foo.bar')
        user_jwt = _fake_jwt(email, True, True)

        self._login(user_jwt)
        resp = self.app.get('/home', follow_redirects=True)
        self.assertPageTitle(resp, 'Account Details')
        url = '/create_account'
        body = {"first_name": "a",
                "last_name": "b",
                "street": "c",
                "street2": "",
                "email": email,
                "city": "d",
                "state": "e",
                "post_code": "f",
                "language": "en_US",
                "country_code": "US",
                "consent_privacy_terms": True
                }

        resp = self.app.post(url, data=body)
        url = resp.headers['Location']
        return self.app.get(url), url, user_jwt

    def test_new_user_unverified(self):
        self._login(USER_NEW_UNVERIFIED)

        resp = self.app.get('/home')
        self.assertPageTitle(resp, 'Awaiting Email Confirmation')

    def test_user_with_valid_sample(self):
        self._login(USER_WITH_VALID_SAMPLE)

        resp = self.app.get('/home', follow_redirects=False)
        self.assertRedirect(resp, suffix_is_uuid=True)

        url = self.redirectURL(resp)

        # we should now be on the Account Dashboard page
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Account')

    def test_new_human_source_to_sample(self):
        # construct a new source
        # sign a consent
        # take the primary survey
        # logout / login
        # take the covid survey
        # claim a sample
        # collect sample information

        # NOTE: this test is more specific on checking redirects to increase
        # granularity, rather than using helper methods, to make sure the flow
        # is as expected
        self._login(USER_WITH_VALID_SAMPLE)

        resp = self.app.get('/home')
        print(resp.headers)
        self.assertRedirect(resp, suffix_is_uuid=True)

        url = self.redirectURL(resp)
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Account')

        account_id, _, _ = self._ids_from_url(url)

        # The account that's used for integration tests has a country
        # code of GB, which doesn't have access to My Kits. Let's fix that.
        url = f'/accounts/{account_id}/details'
        body = {"first_name": "a",
                "last_name": "b",
                "email": USER_WITH_VALID_SAMPLE_EMAIL,
                "street": "c",
                "street2": "",
                "city": "d",
                "state": "e",
                "post_code": "f",
                "language": "en_US",
                "country_code": "US"
                }
        _ = self.app.post(url, data=body)

        # sign the consent
        url = f'/accounts/{account_id}/create_human_source'
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Consent')
        page_data = self._html_page(resp)
        consent_id = _get_consent_id_from_webpage(page_data, "adult_data")
        ADULT_CONSENT["consent_id"] = consent_id
        resp = self.app.post(url, data=ADULT_CONSENT)

        self.assertEqual(resp.status_code, 302)
        self.assertRedirect(resp, suffix_is_uuid=True)

        url = self.redirectURL(resp)
        account_id, source_id, _ = self._ids_from_url(url)

        # take the Basic Info survey
        self._complete_basic_survey(account_id, source_id)

        # go to the My Kits tab
        resp = self.app.get(f'/accounts/{account_id}/sources/{source_id}/kits')
        self.assertPageTitle(resp, "My Kits")

        # query for samples
        resp = self.app.get(f'/list_kit_samples?kit_name={TEST_KIT_1}')
        self.assertEqual(resp.status_code, 200)
        obs_barcodes = {d['sample_barcode'] for d in resp.json}
        self.assertIn(TEST_KIT_1_SAMPLE_1_BARCODE, obs_barcodes)

        # claim a sample
        url = f'/accounts/{account_id}/sources/{source_id}/claim_samples'
        body = {'sample_id': [TEST_KIT_1_SAMPLE_1_SAMPLE_ID, ]}
        sample_id = TEST_KIT_1_SAMPLE_1_SAMPLE_ID
        # note the sample for clean up
        self.claimed_samples.append((account_id, source_id, sample_id))
        resp = self.app.post(url, data=body, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        page_data = self._html_page(resp)
        con = "adult_biospecimen"
        consent_id = _get_consent_id_from_webpage(page_data, con)
        ADULT_CONSENT["consent_id"] = consent_id
        ADULT_CONSENT["consent_type"] = "adult_biospecimen"
        ADULT_CONSENT["sample_ids"] = sample_id
        url = f'/accounts/{account_id}/create_human_source'
        resp = self.app.post(url, data=ADULT_CONSENT)

        url = self.redirectURL(resp)
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'My Kits')
        data = self._html_page(resp)
        self.assertIn('/static/img/edit.svg', data)

        # get collection info
        url = f'/accounts/{account_id}/sources/{source_id}/samples/{sample_id}'
        resp = self.app.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertPageTitle(resp, 'My Kits')

        # set collection info
        collection_note = 'SAMPLE COLLECTED BY INTEGRATION TESTING'
        body = {'sample': TEST_KIT_1_SAMPLE_1_BARCODE,
                'sample_date': '1/1/2022',
                'sample_date_normalized': '1/1/2022',
                'sample_time': '07:00 AM',
                'sample_site': 'Stool',
                'sample_notes': collection_note}
        resp = self.app.post(url, data=body)
        self.assertRedirect(resp, suffix_is_uuid=True)
        url = self.redirectURL(resp)
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'My Kits')

        # verify we have our sample information
        # get collection info
        url = f'/accounts/{account_id}/sources/{source_id}/samples/{sample_id}'
        resp = self.app.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertPageTitle(resp, 'My Kits')
        data = self._html_page(resp)
        self.assertIn(collection_note, data)

    def _sign_consent(self, account_id, consent=ADULT_CONSENT):
        url = f'/accounts/{account_id}/create_human_source'
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Consent')

        page_data = self._html_page(resp)
        consent_id = _get_consent_id_from_webpage(page_data, "adult_data")
        consent["consent_id"] = consent_id
        consent["consent_type"] = "adult_data"
        resp = self.app.post(url, data=consent)
        url = resp.headers['Location']
        return self.app.get(url), url

    def _complete_basic_survey(self, account_id, source_id,
                               survey=BASIC_INFO_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, BASIC_INFO_ID
        )

    def _complete_at_home_survey(self, account_id, source_id,
                                 survey=AT_HOME_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, AT_HOME_ID
        )

    def _complete_lifestyle_survey(self, account_id, source_id,
                                   survey=LIFESTYLE_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, LIFESTYLE_ID
        )

    def _complete_gut_survey(self, account_id, source_id,
                             survey=GUT_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, GUT_ID
        )

    def _complete_general_health_survey(self, account_id, source_id,
                                        survey=GENERAL_HEALTH_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, GENERAL_HEALTH_ID
        )

    def _complete_health_diagnosis_survey(self, account_id, source_id,
                                          survey=HEALTH_DIAGNOSIS_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, HEALTH_DIAG_ID
        )

    def _complete_allergies_survey(self, account_id, source_id,
                                   survey=ALLERGIES_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, ALLERGIES_ID
        )

    def _complete_diet_survey(self, account_id, source_id,
                              survey=DIET_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, DIET_ID
        )

    def _complete_detailed_diet_survey(self, account_id, source_id,
                                       survey=DETAILED_DIET_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, DETAILED_DIET_ID
        )

    def _complete_covid19_survey(self, account_id, source_id,
                                 survey=COVID19_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, COVID19_ID
        )

    def _complete_other_survey(self, account_id, source_id,
                               survey=OTHER_SIMPLE):
        return self._complete_local_survey(
            account_id, source_id, survey, OTHER_ID
        )

    def _complete_local_survey(self, account_id, source_id, body, template_id,
                               target="home"):
        url = (
            f'/accounts/{account_id}/sources/{source_id}/'
            f'take_survey?survey_template_id={template_id}&target={target}'
        )
        return self.app.post(url, json=body)

    def _complete_myfoodrepo_survey(self, account_id, source_id):
        url = (f'/accounts/{account_id}/sources/{source_id}/'
               f'take_survey?survey_template_id=10002')
        return self.app.get(url), url

    def _complete_polyphenol_ffq_survey(self, account_id, source_id):
        url = (f'/accounts/{account_id}/sources/{source_id}/'
               f'take_survey?survey_template_id=10003')
        return self.app.get(url), url

    def _complete_spain_ffq_survey(self, account_id, source_id):
        url = (f'/accounts/{account_id}/sources/{source_id}/'
               f'take_survey?survey_template_id=10004')
        return self.app.get(url), url

    def test_new_user_to_source_listing(self):
        resp, url, user_jwt = self._new_to_create()
        account_id, _, _ = self._ids_from_url(url)
        resp, url = self._sign_consent(account_id)
        account_id, source_id, _ = self._ids_from_url(url)
        self.assertPageTitle(resp, 'My Profile')

    def test_new_source_data_consent(self):
        resp, url, user_jwt = self._new_to_create()
        account_id, _, _ = self._ids_from_url(url)
        url = f'/accounts/{account_id}/create_human_source'
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Consent')

        page_data = self._html_page(resp)
        consent_id = _get_consent_id_from_webpage(page_data, "adult_data")
        ADULT_CONSENT["consent_id"] = consent_id
        ADULT_CONSENT["consent_type"] = "adult_data"

        consent_data = ADULT_CONSENT
        resp = self.app.post(url, data=consent_data)
        self.assertEqual(302, resp.status_code)

        return resp

    def test_duplicate_source_name(self):
        resp, url, user_jwt = self._new_to_create()
        account_id, _, _ = self._ids_from_url(url)
        consent_body = {}
        consent_body["participant_name"] = ADULT_CONSENT["participant_name"]

        url = f'/accounts/{account_id}/check_duplicate_source'
        resp = self.app.post(url, json=consent_body)

        self.assertEqual(resp.status_code, 200)
        return resp

    def _sign_consent_document(self, acc_id, src_id, con_type, consent_data):
        url = f'/accounts/{acc_id}/source/{src_id}/consent/{con_type}'
        resp = self.app.post(url, data=consent_data)
        url = resp.headers['Location']
        return self.app.get(url), url

    def _is_consent_required(self, acc_id, source_id, consent_type):
        url = f'/accounts/{acc_id}/source/{source_id}/consent/{consent_type}'
        resp = self.app.get(url)
        return resp["result"]


if __name__ == '__main__':
    unittest.main()
