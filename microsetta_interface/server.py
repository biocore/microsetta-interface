#!/usr/bin/env python3
import secrets
import logging

from microsetta_interface.config_manager import SERVER_CONFIG
from flask import jsonify, g, request
from werkzeug.utils import redirect

import connexion
from flask_babel import Babel


# https://stackoverflow.com/a/37842465
# allow for rewriting the scheme in a reverse proxy production
# environment. this is what allows url_for and redirect calls
# to use https
class ReverseProxied(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        scheme = SERVER_CONFIG.get('url_scheme')
        if scheme is not None:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


def handle_422(repo_exc):
    return jsonify(code=422, message=str(repo_exc)), 422


def build_app():
    # Create the application instance
    app = connexion.FlaskApp(__name__)

    # Client endpoints
    app.add_api('routes.yaml', validate_responses=True)
    flask_secret = SERVER_CONFIG["FLASK_SECRET_KEY"]

    if flask_secret is None:
        print("WARNING: FLASK_SECRET_KEY must be set to run with gUnicorn")
        flask_secret = secrets.token_urlsafe(16)

    app.app.secret_key = flask_secret
    app.app.config['SESSION_COOKIE_NAME'] = 'session-microsetta-interface'

    # attach the reverse proxy mechanism
    app.app.wsgi_app = ReverseProxied(app.app.wsgi_app)

    if not SERVER_CONFIG['debug']:
        gunicorn_logger = logging.getLogger('gunicorn.error')
        app.app.logger.handlers = gunicorn_logger.handlers
        app.app.logger.setLevel(gunicorn_logger.level)

    app.app.config['BABEL_DEFAULT_TIMEZONE'] = 'UTC'
    app.app.config['BABEL_TRANSLATION_DIRECTORIES'] = './translations'

    @app.route('/americangut/static/<path:filename>')
    def reroute_americangut(filename):
        # This is dumb as rocks, but it fixes static images referenced in
        # surveys without a schema change.
        return redirect('/static/' + filename)
    return app


def run(app):
    if SERVER_CONFIG["ssl_cert_path"] and SERVER_CONFIG["ssl_key_path"]:
        ssl_context = (
            SERVER_CONFIG["ssl_cert_path"], SERVER_CONFIG["ssl_key_path"]
        )
    else:
        ssl_context = None

    app.run(
        port=SERVER_CONFIG['port'],
        debug=SERVER_CONFIG['debug'],
        ssl_context=ssl_context
    )


app = build_app()
babel = Babel(app.app)


@babel.localeselector
def get_locale():
    # OKAY, So, we can use this snippet from https://flask-babel.tkte.ch/
    # to pick the user locale, or we can do something else.
    # User locale could come from:
    #   user preferences in microsetta-interface (EXPLICIT)
    #       Doesn't work on login page,
    #       all requests must have access to session to pull this
    #       requires special handoff to external services like
    #           vioscreen/authrocket
    #   user accept header (IMPLICIT)
    #       Generally set by user in browser,
    #       or more likely configured at user's OS
    #   exact url (EXPLICIT)
    #       microsetta-rest.ucsd.mx
    #       microsetta-rest.ucsd.edu/MX/resourcename
    #       microsetta-rest.ucsd.edu/blahblah?lang=es-MX
    # Best practice seems to be to use whatever user explicitly specified first
    # then if nothing is available, fall back to the user accept header.

    # TODO: We could move these settings into our SESSION cookie, but
    #  all the flask-babel examples seem to use this 'user' pattern, so
    #  may be standard practice to leave it exactly as is in their example.
    user = getattr(g, 'user', None)
    if user is not None:
        return user.locale

    # TODO: We update this as we add support for new languages
    return request.accept_languages.best_match(['en_US', 'es_MX'])


@babel.timezoneselector
def get_timezone():
    user = getattr(g, 'user', None)
    if user is not None:
        return user.timezone


# If we're running in stand alone mode, run the application
if __name__ == '__main__':
    run(app)
