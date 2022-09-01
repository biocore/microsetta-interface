from unittest import TestCase, main
from unittest.mock import patch
from microsetta_interface.server import app

import microsetta_interface.implementation as impl


class TestBase(TestCase):
    def setUp(self):
        # mocking derived from
        # https://realpython.com/testing-third-party-apis-with-mocks/
        self.patch_for_get = patch('microsetta_interface.implementation.'
                                   'requests.get')
        self.mock_get = self.patch_for_get.start()

        self.patch_for_render_template = patch('microsetta_interface.'
                                               'implementation.'
                                               'render_template')
        self.mock_render_template = self.patch_for_render_template.start()

        mock_token = {impl.TOKEN_KEY_NAME: '42',
                      impl.ADMIN_MODE_KEY: False,
                      impl.EMAIL_CHECK_KEY: True}

        self.patch_for_session = patch("microsetta_interface."
                                       "implementation.session",
                                       mock_token)
        self.mock_session = self.patch_for_session.start()

        app.app.testing = True
        self.app = app.app.test_client()
        self.app.__enter__()

    def tearDown(self):
        self.patch_for_get.stop()
        self.patch_for_render_template.stop()
        self.patch_for_session.stop()
        self.app.__exit__(None, None, None)


class TestImplementation(TestBase):
    def test_get_source_redirect_on_source_prereqs_error(self):
        # NB: Can't use a MagicMock here as tested code does
        # response.status_code >= 400, and >= is not implemented
        # for comparing an int (400) with a MagicMock (e.g., status_code
        # being a MagicMock--with return_value 422--returned by another
        # MagicMock for response).
        class TestResponse:
            def __init__(self, status_code, text, json_val, headers=None):
                self.status_code = status_code
                self.text = text
                self.headers = headers
                self.json = lambda: json_val

        dummy_err_html = "dummy html"
        self.mock_render_template.return_value = dummy_err_html
        # first response mocks accounts GET in _check_home_prereqs
        # second response mocks (failing) /accounts/%s/sources/%s GET
        # in _check_source_prereqs
        self.mock_get.side_effect = [TestResponse(200, "{dummy:1}",
                                                  {'dummy': 1}),
                                     TestResponse(401, dummy_err_html, {})]

        response = impl.get_source(account_id="1", source_id="2")
        self.assertEqual(302, response.status_code)
        self.assertEqual('/home', response.headers['Location'])

    def test_authrocket_callback_noargs_error(self):
        # We are observing exceptions on /authrocket_callback which occur with
        # malformed requests. Currently,we are throwing a 500, but instead
        # we should redirect
        exp_status = 302
        exp_location = '/home'

        resp = self.app.get('/authrocket_callback')
        self.assertEqual(exp_status, resp.status_code)
        self.assertTrue(resp.headers['Location'].endswith(exp_location))


if __name__ == '__main__':
    main()
