import json
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
                 "parent_2_name": None,
                 "deceased_parent": 'false',
                 "obtainer_name": None,
                 "consent_type": "data",
                 "consent_id": "4f3c5b1e-a16c-485a-b7af-a236409ea0d4"}

# answer a quesion on each survey
PRIMARY_SURVEY_SIMPLE = {"112": "1970"}
COVID_SURVEY_SIMPLE = {"209": "An integration test"}
FERMENTED_SURVEY_SIMPLE = {"173": "im a test"}
SURFER_SURVEY_SIMPLE = {"174": "Other"}
PERSONAL_SURVEY_SIMPLE = {"208": "im definitely a test"}
OILS_SURVEY_SIMPLE = {"240": "Never"}


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
        self.assertIn(f'<title>Microsetta {title}</title>', data)

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
                "email": email,
                "city": "d",
                "state": "e",
                "post_code": "f",
                "language": "en_US",
                "country_code": "US"
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

        # we should now be on the source listing page
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
        self.assertRedirect(resp, suffix_is_uuid=True)

        url = self.redirectURL(resp)
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Account')

        # sign the consent
        account_id, _, _ = self._ids_from_url(url)
        url = f'/accounts/{account_id}/create_human_source'
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Consent')
        ADULT_CONSENT["consent_type"] = "adult_data"
        ADULT_CONSENT["consent_id"] = "4f3c5b1e-a16c-485a-b7af-a236409ea0d4"
        resp = self.app.post(url, data=ADULT_CONSENT)
        self.assertRedirect(resp, 'take_survey?survey_template_id=1')
        url = self.redirectURL(resp)
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Participant Survey')

        # let's complete the primary survey, and advance to the covid survey
        survey_body = PRIMARY_SURVEY_SIMPLE
        resp = self.app.post(url, json=survey_body, follow_redirects=True)

        # we should still be on the survey page, but now for COVID
        self.assertPageTitle(resp, 'Participant Survey')
        data = self._html_page(resp)
        self.assertIn('COVID19', data)

        # complete the COVID survey
        survey_body = COVID_SURVEY_SIMPLE
        account_id, source_id, _ = self._ids_from_url(url)
        url = url[:-1] + '6'
        resp = self.app.post(url, json=survey_body, follow_redirects=True)
        self.assertPageTitle(resp, 'Account Samples')

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
        self.assertPageTitle(resp, 'Account Samples')
        data = self._html_page(resp)
        self.assertIn('click on a barcode to provide collection information',
                      data)

        # get collection info
        url = f'/accounts/{account_id}/sources/{source_id}/samples/{sample_id}'
        resp = self.app.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertPageTitle(resp, 'Sample Information')

        # set collection info
        collection_note = 'SAMPLE COLLECTED BY INTEGRATION TESTING'
        body = {'sample': TEST_KIT_1_SAMPLE_1_BARCODE,
                'sample_date': '1/1/2022',
                'sample_date_normalized': '1/1/2022',
                'sample_time': '07:00 AM',
                'sample_site': 'Stool',
                'sample_notes': collection_note}
        resp = self.app.post(url, data=body)
        self.assertRedirect(resp, 'after_edit_questionnaire')
        url = self.redirectURL(resp)
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Optional Sample Surveys')

        # verify we have our sample information
        # get collection info
        url = f'/accounts/{account_id}/sources/{source_id}/samples/{sample_id}'
        resp = self.app.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertPageTitle(resp, 'Sample Information')
        data = self._html_page(resp)
        self.assertIn(collection_note, data)

    def _sign_consent(self, account_id, consent=ADULT_CONSENT):
        url = f'/accounts/{account_id}/create_human_source'
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Consent')
        print(str(ADULT_CONSENT))
        resp = self.app.post(url, data=consent)
        url = resp.headers['Location']
        return self.app.get(url), url

    def _complete_primary_survey(self, account_id, source_id,
                                 survey=PRIMARY_SURVEY_SIMPLE):
        return self._complete_local_survey(account_id, source_id, survey, '1')

    def _complete_oils_survey(self, account_id, source_id,
                              survey=OILS_SURVEY_SIMPLE):
        return self._complete_local_survey(account_id, source_id, survey, '7')

    def _complete_covid_survey(self, account_id, source_id,
                               survey=COVID_SURVEY_SIMPLE):
        return self._complete_local_survey(account_id, source_id, survey, '6')

    def _complete_fermented_survey(self, account_id, source_id,
                                   survey=FERMENTED_SURVEY_SIMPLE):
        return self._complete_local_survey(account_id, source_id, survey, '3')

    def _complete_personal_survey(self, account_id, source_id,
                                  survey=PERSONAL_SURVEY_SIMPLE):
        return self._complete_local_survey(account_id, source_id, survey, '5')

    def _complete_surfer_survey(self, account_id, source_id,
                                survey=SURFER_SURVEY_SIMPLE):
        return self._complete_local_survey(account_id, source_id, survey, '4')

    def _complete_local_survey(self, account_id, source_id, body, template_id):
        url = (f'/accounts/{account_id}/sources/{source_id}/'
               f'take_survey?survey_template_id={template_id}')
        resp = self.app.post(url, json=body)
        url = resp.headers['Location']
        return self.app.get(url), url

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
        self._complete_primary_survey(account_id, source_id)
        resp, url = self._complete_covid_survey(account_id, source_id)
        self.assertPageTitle(resp, 'Account Samples')

    def test_existing_user_to_secondary_survey(self):
        # test db doesn't have a completed covid survey, so let's do that
        # logout then back in
        self._login(USER_WITH_VALID_SAMPLE)
        resp = self.app.get('/home', follow_redirects=True)
        page = self._html_page(resp)
        account_id, source_id, _ = self._first_ids_from_html(page)
        self._complete_covid_survey(account_id, source_id)

        self._logout()

        self._login(USER_WITH_VALID_SAMPLE)
        url = f'/accounts/{account_id}/sources/{source_id}'
        resp = self.app.get(url, follow_redirects=True)
        self.assertPageTitle(resp, 'Account Samples')
        self.assertPageContains(resp, 'Fermented Foods Questionnaire')

    def test_only_untaken_secondarys_available(self):
        resp, url, user_jwt = self._new_to_create()
        account_id, _, _ = self._ids_from_url(url)
        resp, url = self._sign_consent(account_id)
        account_id, source_id, _ = self._ids_from_url(url)
        self._complete_primary_survey(account_id, source_id)
        self._complete_covid_survey(account_id, source_id)
        self._complete_fermented_survey(account_id, source_id)

        url = f'/accounts/{account_id}/sources/{source_id}'
        resp = self.app.get(url, follow_redirects=True)
        self.assertPageTitle(resp, 'Account Samples')
        data = self._html_page(resp)

        # we've taken the fermented food survey, so we should not
        # observe its URL in the rendered page
        # TODO: this check will likely break if/when survey editing is allowed
        self.assertIn('survey_template_id=10002', data)
        # removing Personal Microbiome from possible surveys
        # self.assertIn('survey_template_id=5', data)
        self.assertIn('survey_template_id=4', data)
        self.assertNotIn('survey_template_id=3', data)

    def test_new_source_data_consent(self):
        resp, url, user_jwt = self._new_to_create()
        account_id, _, _ = self._ids_from_url(url)
        url = f'/accounts/{account_id}/create_human_source'
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Consent')
        consent_data = ADULT_CONSENT
        resp = self.app.post(url, data=consent_data)

        consent_status = self._is_consent_required(
            account_id, resp["source_id"], "data")

        self.assertTrue(consent_status)

        source_id = resp["source_id"]
        resp = self._sign_consent_document(
            account_id, source_id, "data", consent_data)
        return resp

    def test_duplicate_source_name(self):
        resp, url, user_jwt = self._new_to_create()
        account_id, _, _ = self._ids_from_url(url)
        consent_body = {}
        consent_body["participant_name"] = ADULT_CONSENT["participant_name"]
        print("======body")
        print(type(consent_body))
        url = f'/accounts/{account_id}/check_duplicate_source'
        has_error, resp, _ = self.app.post(url, json=consent_body)
        print("====response")
        print(str(resp))
        self.assertTrue(resp["source_duplicate"])
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
