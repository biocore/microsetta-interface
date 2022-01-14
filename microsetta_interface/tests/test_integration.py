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


def _fake_jwt(email, verified):
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

USER_WITH_VALID_SAMPLE_EMAIL = "th-dq)wort@3'rey.i3l"
USER_WITH_VALID_SAMPLE = _fake_jwt(USER_WITH_VALID_SAMPLE_EMAIL, True)

# PGP_AmsFQ (test db has 5 unassigned in the test db)
TEST_KIT_1 = 'PGP_AmsFQ'
TEST_KIT_1_SAMPLE_1_BARCODE = '000005097'
TEST_KIT_1_SAMPLE_1_SAMPLE_ID = 'ddbb117b-c8fa-9a94-e040-8a80115d1380'


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
        try:
            self.mock_session.pop(TOKEN_KEY_NAME)
        except KeyError:
            pass

    def idsFromURL(self, url):
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

    def assertPageTitle(self, resp, title, exp_code=200):
        self.assertEqual(resp.status_code, exp_code)
        data = self._html_page(resp)
        self.assertIn(f'<title>Microsetta {title}</title>', data)

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

    def test_new_user_unverified(self):
        self._login(USER_NEW_UNVERIFIED)

        resp = self.app.get('/home')
        self.assertPageTitle(resp, 'Awaiting Email Confirmation')

    def test_user_with_valid_sample(self):
        self._login(USER_WITH_VALID_SAMPLE)

        resp = self.app.get('/home')
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
        # land on the secondary survey page
        # opt out of secondary surveys
        # claim a sample
        # collect sample information
        self._login(USER_WITH_VALID_SAMPLE)

        resp = self.app.get('/home')
        self.assertRedirect(resp, suffix_is_uuid=True)

        url = self.redirectURL(resp)
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Account')

        account_id, _, _ = self.idsFromURL(url)
        url = f'/accounts/{account_id}/create_human_source'
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Consent')

        # for consent, we POST to the same place we GET
        consent_body = {"participant_email": 'foo@bar.com',
                        "participant_name": "foo bar",
                        "age_range": "18-plus",
                        "parent_1_name": None,
                        "parent_2_name": None,
                        "deceased_parent": 'false',
                        "obtainer_name": None}
        resp = self.app.post(url, data=consent_body)
        self.assertRedirect(resp, 'take_survey?survey_template_id=1')
        url = self.redirectURL(resp)
        resp = self.app.get(url)
        self.assertPageTitle(resp, 'Participant Survey')

        # let's complete the primary survey, and advance to the covid survey
        survey_body = {"112": "1970"}
        resp = self.app.post(url, json=survey_body, follow_redirects=True)

        # we should still be on the survey page, but now for COVID
        self.assertPageTitle(resp, 'Participant Survey')
        data = self._html_page(resp)
        self.assertIn('COVID19', data)

        # complete the COVID survey
        survey_body = {"209": "An integration test"}
        account_id, source_id, _ = self.idsFromURL(url)
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


if __name__ == '__main__':
    unittest.main()
