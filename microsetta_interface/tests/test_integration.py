import unittest
import hashlib
import os
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


@unittest.skipIf(not PRIVATE_API_AVAILABLE,
                 "An instance of microsetta-private-api is not available")
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.patch_for_session = patch("microsetta_interface."
                                       "implementation.session",
                                       dict())
        self.mock_session = self.patch_for_session.start()

        app.app.testing = True
        app.app.config['SECRET_KEY'] = 'secretsecret'
        self.app = app.app.test_client()
        self.app.__enter__()

    def tearDown(self):
        self.patch_for_session.stop()
        self._logout()
        self.app.__exit__(None, None, None)

    def _html_page(self, resp):
        return resp.get_data(as_text=True)

    def _login(self, token):
        self.mock_session[TOKEN_KEY_NAME] = token

    def _logout(self):
        try:
            self.mock_session.pop(TOKEN_KEY_NAME)
        except KeyError:
            pass

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
        self.assertEqual(resp.status_code, 200)

        self._login(USER_NEW)

        # once logged in, we should redirect
        resp = self.app.get('/home')
        self.assertEqual(resp.status_code, 302)

        # this is a new user, so they should go to the account creation page
        new_url = resp.headers['Location']
        self.assertTrue(new_url.endswith('create_account'))

        # make sure the creation page loads
        resp = self.app.get(new_url)
        self.assertEqual(resp.status_code, 200)
        data = self._html_page(resp)
        self.assertIn('<title>Microsetta Account Details</title>', data)

        # once logged out, we should not redirect and instead be at home
        self._logout()
        resp = self.app.get('/home')
        self.assertEqual(resp.status_code, 200)

    def test_new_user_unverified(self):
        self._login(USER_NEW_UNVERIFIED)

        resp = self.app.get('/home')
        self.assertEqual(resp.status_code, 200)

        # email is unverified so user should get the corresponding page
        data = self._html_page(resp)
        self.assertIn('<title>Microsetta Awaiting Email Confirmation</title>',
                      data)

    def test_user_with_valid_sample(self):
        self._login(USER_WITH_VALID_SAMPLE)

        resp = self.app.get('/home')
        data = self._html_page(resp)
        self.assertEqual(resp.status_code, 302)

        new_url = resp.headers['Location']
        uuid_test = new_url.rsplit('/', 1)[1]

        # we should route to the accounts page, which ends with a valid UUID
        # this test will raise if uuid_test is not a UUID4
        uuid.UUID(uuid_test, version=4)

        # we should now be on the source listing page
        resp = self.app.get(new_url)
        self.assertEqual(resp.status_code, 200)
        data = self._html_page(resp)
        self.assertIn('<title>Microsetta Account</title>', data)


if __name__ == '__main__':
    unittest.main()
