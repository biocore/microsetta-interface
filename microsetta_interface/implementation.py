import json

import flask
import flask_babel
from flask_babel import gettext
from flask import render_template, session, redirect, make_response, request, \
    jsonify
import jwt
import requests
from requests.auth import AuthBase
from urllib.parse import quote
from os import path
from datetime import datetime
import base64
import functools
from microsetta_interface.model_i18n import translate_source, \
    translate_sample, translate_survey_template, EN_US_KEY, LANGUAGES, \
    ES_MX_KEY

# Authrocket uses RS256 public keys, so you can validate anywhere and safely
# store the key in code. Obviously using this mechanism, we'd have to push code
# to roll the keys, which is not ideal, but you can instead hold this in a
# config somewhere and reload

# Python is dumb, don't put spaces anywhere in this string.
from werkzeug.exceptions import BadRequest, Unauthorized

from microsetta_interface.config_manager import SERVER_CONFIG
import importlib.resources as pkg_resources
from microsetta_interface.redis_cache import RedisCache
from microsetta_interface.util import has_non_keyword_arguments, \
    parse_request_csv_col


# TODO: source from a microsetta_private_api endpoint
class Source:
    SOURCE_TYPE_HUMAN = "human"
    SOURCE_TYPE_ANIMAL = "animal"
    SOURCE_TYPE_ENVIRONMENT = "environmental"


PUB_KEY = pkg_resources.read_text(
    'microsetta_interface',
    "authrocket.pubkey")

TOKEN_KEY_NAME = 'token'
ADMIN_MODE_KEY = 'admin_mode'
LOGIN_INFO_KEY = 'login_info'
LANG_KEY = "language"

HOME_URL = "/home"
HELP_EMAIL = "microsetta@ucsd.edu"
REROUTE_KEY = "reroute"

ACTIVATION_CODE_KEY = "code"
KIT_NAME_KEY = "kit_name"
EMAIL_CHECK_KEY = "email_checked"
ACCT_FNAME_KEY = "first_name"
ACCT_LNAME_KEY = "last_name"
ACCT_EMAIL_KEY = "email"
ACCT_ADDR_KEY = "address"
ACCT_WRITEABLE_KEYS = [ACCT_FNAME_KEY, ACCT_LNAME_KEY, ACCT_EMAIL_KEY,
                       ACCT_ADDR_KEY]
ACCT_ADDR_STREET_KEY = "street"
ACCT_ADDR_CITY_KEY = "city"
ACCT_ADDR_STATE_KEY = "state"
ACCT_ADDR_POST_CODE_KEY = "post_code"
ACCT_ADDR_COUNTRY_CODE_KEY = "country_code"
ACCT_LANG_KEY = "language"

# States
NEEDS_REROUTE = "NeedsReroute"
NEEDS_LOGIN = "NeedsLogin"
NEEDS_ACCOUNT = "NeedsAccount"
NEEDS_EMAIL_CHECK = "NeedsEmailCheck"
NEEDS_SURVEY = "NeedsSurvey"
HOME_PREREQS_MET = "TokenPrereqsMet"
ACCT_PREREQS_MET = "AcctPrereqsMet"
SOURCE_PREREQS_MET = "SourcePrereqsMet"

# TODO FIXME HACK:  VIOSCREEN_ID is just hardcoded.  Api does not specify what
#  special handling is required.  API must specify per-sample survey templates
#  in some way, as well as any special handling for external surveys.
VIOSCREEN_ID = 10001


SYSTEM_MSG_DICTIONARY = {
        "going_down": {
            EN_US_KEY: "The system is going down at ",
            ES_MX_KEY: "El sistema se apaga a las "
        }
    }

client_state = RedisCache()


def _render_with_defaults(template_name, **context):
    defaults = {}

    admin_mode = session.get(ADMIN_MODE_KEY, False)
    defaults["login_info"] = session.get(LOGIN_INFO_KEY, None)
    defaults["admin_mode"] = admin_mode

    msg, style, hours, minutes = client_state.get(RedisCache.SYSTEM_BANNER,
                                                  (None, None, None, None))

    today = datetime.today()
    if hours is None:
        sys_msg_dt = datetime(today.year, today.month, today.day)
    else:
        sys_msg_dt = datetime(today.year, today.month, today.day, int(hours),
                              int(minutes))

    defaults["system_msg_text"] = msg
    defaults["system_msg_style"] = style
    defaults["system_msg_time"] = flask_babel.format_datetime(sys_msg_dt,
                                                              'h:mm a')
    defaults["system_msg_dictionary"] = SYSTEM_MSG_DICTIONARY

    endpoint = SERVER_CONFIG["endpoint"]
    public_endpoint = SERVER_CONFIG["public_api_endpoint"]
    authrocket_url = SERVER_CONFIG["authrocket_url"]
    defaults["endpoint"] = endpoint
    defaults["authrocket_url"] = authrocket_url
    defaults["public_endpoint"] = public_endpoint

    defaults["EN_US_KEY"] = EN_US_KEY
    defaults["languages"] = LANGUAGES

    defaults.update(context)

    return render_template(template_name, **defaults)


def _get_req_survey_templates_by_source_type(source_type):
    if source_type == Source.SOURCE_TYPE_HUMAN:
        return [1, 6]
    elif source_type == Source.SOURCE_TYPE_ANIMAL:
        return []
    elif source_type == Source.SOURCE_TYPE_ENVIRONMENT:
        return []
    else:
        raise ValueError("Unknown source type: '%s'" % source_type)


def _make_path(account_id=None, source_id=None, suffix=None):
    result = "/accounts"
    if account_id is not None:
        result = path.join(result, account_id)
        if source_id is not None:
            result = path.join(result, "sources", source_id)

    if suffix is not None:
        result = path.join(result, suffix)

    return result


def _make_acct_path(account_id, suffix=None):
    return _make_path(account_id=account_id, suffix=suffix)


def _make_source_path(account_id, source_id, suffix=None):
    return _make_path(account_id=account_id, source_id=source_id,
                      suffix=suffix)


def _check_home_prereqs():
    current_state = {}
    if TOKEN_KEY_NAME not in session:
        return NEEDS_LOGIN, current_state

    if not session.get(ADMIN_MODE_KEY, False):
        # Do they need to make an account? YES-> account_details.html
        needs_reroute, accts_output, _ = ApiRequest.get("/accounts")
        # if there's an error, reroute to error page
        if needs_reroute:
            current_state[REROUTE_KEY] = accts_output
            return NEEDS_REROUTE, current_state

        if len(accts_output) == 0:
            # NB: Overwriting outputs from get call above
            needs_reroute, accts_output, _ = ApiRequest.post(
                "/accounts/legacies")
            if needs_reroute:
                current_state[REROUTE_KEY] = accts_output
                return NEEDS_REROUTE, current_state
            # if no legacy account found, need new account
            if len(accts_output) == 0:
                return NEEDS_ACCOUNT, current_state

    # If you got here, you have a token and you have (at least one) account
    # (True even of admins who skipped the above account check, as you can't
    # be an admin unless you have a microsetta account that says you are)
    return HOME_PREREQS_MET, current_state


def _check_acct_prereqs(account_id, current_state=None):
    current_state = {} if current_state is None else current_state
    current_state['account_id'] = account_id

    # If we haven't yet checked for email mismatches and gotten user decision,
    # and the user isn't an admin (who could be looking at another person's
    # account and thus have that email not match their login one):
    if not session.get(EMAIL_CHECK_KEY, False) and not session[ADMIN_MODE_KEY]:
        # Does email in our accounts table match email in authrocket?
        needs_reroute, email_match, _ = ApiRequest.get(
            '/accounts/{0}/email_match'.format(account_id))
        if needs_reroute:
            current_state[REROUTE_KEY] = email_match
            return NEEDS_REROUTE, current_state
        # if they don't match AND the user hasn't already refused update
        if not email_match["email_match"]:
            return NEEDS_EMAIL_CHECK, current_state

        session[EMAIL_CHECK_KEY] = True

    # IF we decide that every acct needs at least one source,
    # this is where that check would go

    return ACCT_PREREQS_MET, current_state


def _check_source_prereqs(acct_id, source_id, current_state=None):
    SURVEY_TEMPLATE_ID_KEY = "survey_template_id"
    current_state = {} if current_state is None else current_state
    current_state['source_id'] = source_id

    if not session[ADMIN_MODE_KEY]:
        # Get the input source
        needs_reroute, source_output, _ = ApiRequest.get(
            '/accounts/%s/sources/%s' %
            (acct_id, source_id))
        if needs_reroute:
            current_state[REROUTE_KEY] = source_output
            return NEEDS_REROUTE, current_state

        # Get all required survey template ids for this source type
        req_survey_template_ids = _get_req_survey_templates_by_source_type(
            source_output["source_type"])

        # Get all the current answered surveys for this source
        needs_reroute, surveys_output, _ = ApiRequest.get(
            '/accounts/{0}/sources/{1}/surveys'.format(acct_id, source_id))
        if needs_reroute:
            current_state[REROUTE_KEY] = surveys_output
            return NEEDS_REROUTE, current_state
        template_ids_of_answered_surveys = [x[SURVEY_TEMPLATE_ID_KEY] for x
                                            in surveys_output]

        # For each required survey template id for this source type
        for curr_req_survey_template_id in req_survey_template_ids:
            # Does this source LACK an answered survey with this template id?
            if curr_req_survey_template_id not in \
                    template_ids_of_answered_surveys:
                current_state["needed_survey_template_id"] = \
                    curr_req_survey_template_id
                return NEEDS_SURVEY, current_state

    return SOURCE_PREREQS_MET, current_state


def _check_relevant_prereqs(acct_id=None, source_id=None):
    # Check home prereqs
    prereq_step, current_state = _check_home_prereqs()
    if prereq_step != HOME_PREREQS_MET:
        return prereq_step, current_state

    # Check acct prereqs
    if acct_id is None:
        return prereq_step, current_state
    prereq_step, current_state = _check_acct_prereqs(acct_id, current_state)
    if prereq_step != ACCT_PREREQS_MET:
        return prereq_step, current_state

    # Check source prereqs
    if source_id is None:
        return prereq_step, current_state
    return _check_source_prereqs(acct_id, source_id, current_state)


# To send arguments to a decorator, you define a factory method with those args
# that returns a decorator.  The decorator then takes a function and returns
# a wrapper that you want to call instead.  Thus there should be three layers.
def prerequisite(allowed_states: list, **parameter_overrides):
    """
    Usage
    @prerequisite([NEEDS_EMAIL_CHECK])
    def get_update_email(account_id):
        # If client is not in the NEEDS_EMAIL_CHECK state, they will be
        # redirected rather than reaching get_update_email.

    @prerequisite([State1, State2, State3])
    def crazy_function(account_id, source_id):
        # If client is not in one of State1, State2, State3 stats, they will
        # be redirected.

    @prerequisite([State1, State2], survey_template_id=VIOSCREEN_ID)
    def vioscreen_callback(account_id, source_id, key):
        # If client is not in one of State1, State2, they will be redirected
        # Further, if they are determined to be in NEEDS_SURVEY, but their
        # required survey template id is not VIOSCREEN_ID, they will be
        # redirected.  Note that this makes use of the parameter_overrides to
        # set a specific parameter (survey_template_id) when the wrapped
        # function knows what would be sent, but does not expose it within its
        # method signature. (You might encounter this when the wrapped function
        # is a callback function that must match some defined signature)

    :param allowed_states: A list of states that are valid for
    entry to the decorated function
    :param parameter_overrides: A set of keyword arguments added or replacing
    the wrapped function's input args for the purpose of determining prereqs
    The wrapped function itself will never see these overridden values.
    """
    if not isinstance(allowed_states, list):
        raise TypeError("allowed_states must be a list")
    allowed_states = set(allowed_states)

    def decorator(func):

        if has_non_keyword_arguments(func):
            raise TypeError("Only functions with solely keyword arguments are "
                            "supported by this decorator.  "
                            "Example: f(*, a=1, b=2, c=3)")

        # Calling functools.wraps preserves information about the wrapped func
        # so introspection/reflection can pull the original documentation even
        # when passed the wrapper function.
        @functools.wraps(func)
        def wrapper(**kwargs):
            kwargs_copy = dict(kwargs)
            kwargs_copy.update(parameter_overrides)

            # Check relevant prereqs from those arguments
            prereqs_step, curr_state = _check_relevant_prereqs(
                kwargs_copy.get('account_id'),
                kwargs_copy.get('source_id')
            )

            # Route to closest sink if state doesn't match a required state
            if prereqs_step not in allowed_states:
                return _route_to_closest_sink(prereqs_step, curr_state)

            # For any states that require checking additional parameters, we do
            # so here.  (Remember to lookup from kwargs_copy)
            # TODO: Ensure state specific checks don't grow unwieldy
            if prereqs_step == NEEDS_SURVEY:
                passed_id = kwargs_copy.get('survey_template_id')
                needed_id = curr_state.get("needed_survey_template_id")
                if passed_id != needed_id:
                    return _route_to_closest_sink(prereqs_step, curr_state)

            # Add new state specific checks here
            # if prereqs_state == XXX:
            #   if something's not right, reroute.

            return func(**kwargs)

        return wrapper

    return decorator


# Client might not technically care who the user is, but if they do, they
# get the token, validate it, and pull email out of it.
def _parse_jwt(token):
    decoded = jwt.decode(token, PUB_KEY, algorithms=['RS256'], verify=True)
    email_verified = decoded.get('email_verified', False)
    return decoded["email"], email_verified


def _route_to_closest_sink(prereqs_step, current_state):
    print("Current Prereq Step:", prereqs_step)
    acct_id = current_state.get("account_id", None)
    source_id = current_state.get("source_id", None)

    if prereqs_step == NEEDS_REROUTE:
        # where you get rerouted to depends on why you need
        # rerouting: api authorization errors go back to home page,
        # all other api errors go to error page
        return current_state[REROUTE_KEY]
    elif prereqs_step == NEEDS_LOGIN or prereqs_step == HOME_PREREQS_MET:
        return redirect(HOME_URL)
    elif prereqs_step == NEEDS_ACCOUNT:
        return redirect("/create_account")
    elif prereqs_step == NEEDS_EMAIL_CHECK:
        return redirect(_make_acct_path(acct_id, suffix="update_email"))
    elif prereqs_step == NEEDS_SURVEY:
        needed_survey_template_id = current_state["needed_survey_template_id"]
        return redirect(_make_source_path(
            acct_id, source_id, suffix="take_survey?survey_template_id=%s"
                                       % needed_survey_template_id))
    elif prereqs_step == ACCT_PREREQS_MET:
        # redirect to the account details page (showing all the sources)
        return redirect(_make_acct_path(acct_id))
    elif prereqs_step == SOURCE_PREREQS_MET:
        # redirect to the source details page (showing all samples)
        return redirect(_make_source_path(acct_id, source_id))
    else:
        return get_show_error_page(
            "Unknown prereq_step: '{0}'".format(prereqs_step))


def _refresh_state_and_route_to_sink(account_id=None, source_id=None):
    prereqs_step, curr_state = _check_relevant_prereqs(account_id, source_id)
    return _route_to_closest_sink(prereqs_step, curr_state)


def _get_kit(kit_name):
    unable_to_validate_msg = gettext(
        "Unable to validate the kit name; please "
        "reload the page.")
    error_msg = None
    response = None

    try:
        # call api and find out if kit name has unclaimed samples.
        # NOT doing this through ApiRequest.get bc in this case
        # DON'T want the automated error-handling

        response = requests.get(
            ApiRequest.API_URL + '/kits/',  # appending slash saves a 308 redir
            auth=BearerAuth(session[TOKEN_KEY_NAME]),
            verify=ApiRequest.CAfile,
            params=ApiRequest.build_params({KIT_NAME_KEY: kit_name}))

        if response.status_code == 404:
            error_msg = \
                gettext(
                    "The provided kit id is not valid or has "
                    "already been used; please re-check your entry."
                )
        elif response.status_code > 200:
            error_msg = unable_to_validate_msg
    except:  # noqa
        error_msg = unable_to_validate_msg

    if error_msg is not None:
        if response is None:
            return None, error_msg, 500
        else:
            return None, error_msg, response.status_code

    return response.json(), None, response.status_code


def _associate_sample_to_survey(account_id, source_id, sample_id, survey_id):
    # Associate the input answered surveys with this sample.
    has_error, sample_survey_output, _ = ApiRequest.post(
        '/accounts/{0}/sources/{1}/samples/{2}/surveys'.format(
            account_id, source_id, sample_id
        ), json={"survey_id": survey_id}
    )
    if has_error:
        return sample_survey_output

    return None


# Error display does not require any prereqs, so this method doesn't check any
def get_show_error_page(error_msg):
    # output is general error page
    error_txt = quote(error_msg)
    mailto_url = "mailto:{0}?subject={1}&body={2}".format(
        HELP_EMAIL, quote("minimal interface error"), error_txt)

    output = _render_with_defaults('error.jinja2',
                                   mailto_url=mailto_url,
                                   error_msg=error_msg)

    return output


def get_home():
    email_verified = False
    accts_output = None
    has_session = TOKEN_KEY_NAME in session

    if has_session:
        try:
            # If user leaves the page open, the token can expire before the
            # session, so if our token goes back we need to force them to login
            # again.
            email, email_verified = _parse_jwt(session[TOKEN_KEY_NAME])
        except jwt.exceptions.ExpiredSignatureError:
            return redirect('/logout')

        if email_verified:
            home_step, curr_state = _check_home_prereqs()
            if home_step == NEEDS_REROUTE:
                return curr_state[REROUTE_KEY]

            has_error, accts_output, _ = ApiRequest.get("/accounts")
            # if there's an error, reroute to error page
            if has_error:
                return accts_output
        else:
            return _render_with_defaults('email_confirmation.jinja2')
    else:
        return _render_with_defaults('home.jinja2')

    # Switch out home page in administrator mode
    if session.get(ADMIN_MODE_KEY, False):
        return _render_with_defaults('admin_home.jinja2',
                                     accounts=[])

    if accts_output is not None and len(accts_output) > 0:
        account_id = accts_output[0]['account_id']
        return redirect(f'/accounts/{account_id}')
    else:
        # Note: account_details.jinja2 sends the user directly to authrocket
        # to complete the login if they aren't logged in yet.
        return redirect('/create_account')


def get_rootpath():
    return redirect(HOME_URL)


def get_authrocket_callback(token, redirect_uri=None):
    session[TOKEN_KEY_NAME] = token
    email, _ = _parse_jwt(token)
    session[LOGIN_INFO_KEY] = {
        "email": email
    }
    do_return, accts_output, _ = ApiRequest.get('/accounts')
    if do_return:
        return accts_output

    # new authrocket logins do not have an account yet
    if len(accts_output) > 0:
        primary = accts_output[0]
        session[ADMIN_MODE_KEY] = primary['account_type'] == 'admin'
        session[LOGIN_INFO_KEY] = {
            "account_id": primary['account_id'],
            "email": primary['email']
        }
        session[LANG_KEY] = primary["language"]
    else:
        session[ADMIN_MODE_KEY] = False
        session[LOGIN_INFO_KEY] = {
            "account_id": None,
            "email": email
        }

    if redirect_uri:
        uri = base64.urlsafe_b64decode(redirect_uri).decode()
        return redirect(uri)

    return redirect(HOME_URL)


def get_logout():
    session.clear()
    return redirect(HOME_URL)


@prerequisite([NEEDS_ACCOUNT])
def get_create_account():
    email, _ = _parse_jwt(session[TOKEN_KEY_NAME])

    browser_lang = request.accept_languages.best_match(
        [LANGUAGES[lang].value for lang in LANGUAGES],
        default=LANGUAGES[EN_US_KEY].value)
    # TODO:  Need to support other countries
    #  and not default to US and California
    default_account_values = {
        ACCT_EMAIL_KEY: email,
        ACCT_FNAME_KEY: '',
        ACCT_LNAME_KEY: '',
        ACCT_ADDR_KEY: {
            ACCT_ADDR_STREET_KEY: '',
            ACCT_ADDR_CITY_KEY: '',
            ACCT_ADDR_STATE_KEY: 'CA',
            ACCT_ADDR_POST_CODE_KEY: '',
            ACCT_ADDR_COUNTRY_CODE_KEY: 'US'
        },
        ACCT_LANG_KEY: browser_lang
    }

    return _render_with_defaults('account_details.jinja2',
                                 CREATE_ACCT=True,
                                 account=default_account_values)


@prerequisite([NEEDS_ACCOUNT])
def post_create_account(*, body=None):
    kit_name = body[KIT_NAME_KEY]
    session[KIT_NAME_KEY] = kit_name

    api_json = {
        ACCT_FNAME_KEY: body['first_name'],
        ACCT_LNAME_KEY: body['last_name'],
        ACCT_EMAIL_KEY: body['email'],
        ACCT_ADDR_KEY: {
            ACCT_ADDR_STREET_KEY: body['street'],
            ACCT_ADDR_CITY_KEY: body['city'],
            ACCT_ADDR_STATE_KEY: body['state'],
            ACCT_ADDR_POST_CODE_KEY: body['post_code'],
            ACCT_ADDR_COUNTRY_CODE_KEY: body['country_code']
        },
        ACCT_LANG_KEY: body[LANG_KEY],
        KIT_NAME_KEY: kit_name,
        ACTIVATION_CODE_KEY: body["code"]
    }

    has_error, accts_output, _ = \
        ApiRequest.post("/accounts", json=api_json)
    if has_error:
        return accts_output

    new_acct_id = accts_output["account_id"]
    session[LOGIN_INFO_KEY] = {
        "account_id": new_acct_id,
        "email": accts_output["email"]
    }
    session[LANG_KEY] = accts_output['language']

    return _refresh_state_and_route_to_sink(new_acct_id)


@prerequisite([NEEDS_EMAIL_CHECK])
def get_update_email(*, account_id=None):
    return _render_with_defaults("update_email.jinja2",
                                 account_id=account_id)


@prerequisite([NEEDS_EMAIL_CHECK])
def post_update_email(*, account_id=None, body=None):
    # if the customer wants to update their email:
    update_email = body["do_update"] == "Yes"
    if update_email:
        # get the existing account object
        has_error, acct_output, _ = ApiRequest.get(
            '/accounts/%s' % account_id)
        if has_error:
            return acct_output

        # change the email to the one in the authrocket account
        authrocket_email, _ = _parse_jwt(session[TOKEN_KEY_NAME])
        acct_output[ACCT_EMAIL_KEY] = authrocket_email
        # retain only writeable fields; KeyError if any of them missing
        mod_acct = {k: acct_output[k] for k in ACCT_WRITEABLE_KEYS}

        # write back the updated account details
        has_error, put_output, _ = ApiRequest.put(
            '/accounts/%s' % account_id, json=mod_acct)
        if has_error:
            return put_output

    # even if they decided NOT to update, don't ask again this session
    session[EMAIL_CHECK_KEY] = True

    return _refresh_state_and_route_to_sink(account_id)


@prerequisite([ACCT_PREREQS_MET])
def get_account(*, account_id=None):
    has_error, account, _ = ApiRequest.get('/accounts/%s' % account_id)
    if has_error:
        return account

    has_error, sources, _ = ApiRequest.get('/accounts/%s/sources' % account_id)
    if has_error:
        return sources

    # Update their language preferences cookie whenever they load this page.
    # So if changed from another browser/tab/computer,
    # going home will reset language
    session[LANG_KEY] = account["language"]

    sources = [translate_source(s) for s in sources]
    return _render_with_defaults('account_overview.jinja2',
                                 account=account,
                                 sources=sources)


@prerequisite([ACCT_PREREQS_MET])
def get_account_details(*, account_id=None):
    has_error, account, _ = ApiRequest.get('/accounts/%s' % account_id)
    if has_error:
        return account

    return _render_with_defaults('account_details.jinja2',
                                 CREATE_ACCT=False,
                                 account=account)


@prerequisite([ACCT_PREREQS_MET])
def post_account_details(*, account_id=None, body=None):
    acct = {
        ACCT_FNAME_KEY: body['first_name'],
        ACCT_LNAME_KEY: body['last_name'],
        ACCT_EMAIL_KEY: body['email'],
        ACCT_ADDR_KEY: {
            ACCT_ADDR_STREET_KEY: body['street'],
            ACCT_ADDR_CITY_KEY: body['city'],
            ACCT_ADDR_STATE_KEY: body['state'],
            ACCT_ADDR_POST_CODE_KEY: body['post_code'],
            ACCT_ADDR_COUNTRY_CODE_KEY: body['country_code']
        },
        ACCT_LANG_KEY: body['language']
    }

    do_return, acct_output, _ = ApiRequest.put('/accounts/%s' %
                                               account_id, json=acct)
    if do_return:
        return acct_output

    session[LOGIN_INFO_KEY] = {
        "account_id": acct_output["account_id"],
        "email": acct_output["email"]
    }
    session[LANG_KEY] = acct_output["language"]

    return _refresh_state_and_route_to_sink(account_id)


@prerequisite([ACCT_PREREQS_MET])
def get_create_human_source(*, account_id=None):
    endpoint = SERVER_CONFIG["endpoint"]
    relative_post_url = _make_acct_path(account_id,
                                        suffix="create_human_source")
    post_url = endpoint + relative_post_url
    has_error, consent_output, _ = ApiRequest.get(
        "/accounts/{0}/consent".format(account_id),
        params={"consent_post_url": post_url})

    if has_error:
        return consent_output

    return _render_with_defaults('new_participant.jinja2',
                                 tl=consent_output,
                                 post_url=post_url)


@prerequisite([ACCT_PREREQS_MET])
def post_create_human_source(*, account_id=None, body=None):
    has_error, consent_output, _ = ApiRequest.post(
        "/accounts/{0}/consent".format(account_id), json=body)
    if has_error:
        return consent_output

    new_source_id = consent_output["source_id"]

    return _refresh_state_and_route_to_sink(account_id, new_source_id)


@prerequisite([ACCT_PREREQS_MET])
def get_create_nonhuman_source(*, account_id=None):
    return _render_with_defaults('create_nonhuman_source.jinja2',
                                 account_id=account_id)


@prerequisite([ACCT_PREREQS_MET])
def post_create_nonhuman_source(*, account_id=None, body=None):
    has_error, sources_output, _ = ApiRequest.post(
        "/accounts/{0}/sources".format(account_id), json=body)
    if has_error:
        return sources_output

    return _refresh_state_and_route_to_sink(account_id)


@prerequisite([NEEDS_SURVEY])
def get_fill_local_source_survey(*,
                                 account_id=None,
                                 source_id=None,
                                 survey_template_id=None):
    has_error, survey_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s/survey_templates/%s' %
        (account_id, source_id, survey_template_id))
    if has_error:
        return survey_output

    return _render_with_defaults("survey.jinja2",
                                 account_id=account_id,
                                 source_id=source_id,
                                 survey_template_id=survey_template_id,
                                 survey_schema=survey_output[
                                     'survey_template_text'])


@prerequisite([NEEDS_SURVEY])
def post_ajax_fill_local_source_survey(*, account_id=None, source_id=None,
                                       survey_template_id=None, body=None):
    has_error, surveys_output, _ = ApiRequest.post(
        "/accounts/%s/sources/%s/surveys" % (account_id, source_id),
        json={
            "survey_template_id": survey_template_id,
            "survey_text": body
        })
    if has_error:
        return surveys_output

    return _refresh_state_and_route_to_sink(account_id, source_id)


@prerequisite([SOURCE_PREREQS_MET, NEEDS_SURVEY])
def get_fill_vioscreen_remote_sample_survey(*,
                                            account_id=None,
                                            source_id=None,
                                            sample_id=None,
                                            survey_template_id=None):
    if survey_template_id != VIOSCREEN_ID:
        return get_show_error_page("Non-vioscreen remote surveys are "
                                   "not yet supported")

    suffix = "samples/%s/vspassthru" % sample_id
    redirect_url = SERVER_CONFIG["endpoint"] + \
        _make_source_path(account_id, source_id, suffix=suffix)
    params = {
        'survey_redirect_url': redirect_url,
        'vioscreen_ext_sample_id': sample_id
    }
    has_error, survey_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s/survey_templates/%s' %
        (account_id, source_id, VIOSCREEN_ID), params=params)
    if has_error:
        return survey_output

    # remote surveys go to an external url, not our jinja2 template
    return redirect(survey_output['survey_template_text']['url'])


# NB: There is no post_fill_sample_survey because right now the ONLY
# per-sample survey we have is the remote food frequency questionnaire
# administered through vioscreen, and saving that requires its own special
# handling (this function).
@prerequisite([SOURCE_PREREQS_MET, NEEDS_SURVEY],
              survey_template_id=VIOSCREEN_ID)
def get_to_save_vioscreen_remote_sample_survey(*,
                                               account_id=None,
                                               source_id=None,
                                               sample_id=None,
                                               key=None):
    # TODO FIXME HACK:  This is insanity.  I need to see the vioscreen docs
    #  to interface with our API...
    has_error, surveys_output, surveys_headers = ApiRequest.post(
        "/accounts/%s/sources/%s/surveys" % (account_id, source_id),
        json={
            "survey_template_id": VIOSCREEN_ID,
            "survey_text": {"key": key}
        })
    if has_error:
        return surveys_output

    answered_survey_id = surveys_headers['Location']
    answered_survey_id = answered_survey_id.split('/')[-1]

    # associate this answered vioscreen survey to this sample
    sample_survey_output = _associate_sample_to_survey(
        account_id, source_id, sample_id, answered_survey_id)
    if sample_survey_output is not None:
        return sample_survey_output

    return _refresh_state_and_route_to_sink(account_id, source_id)


@prerequisite([SOURCE_PREREQS_MET])
def top_food_report(*,
                    account_id=None,
                    source_id=None,
                    survey_id=None):
    return _render_with_defaults(
        "embedded_pdf.jinja2",
        page_title="Top Food Report",
        link_to_pdf='/accounts/%s'
                    '/sources/%s'
                    '/surveys/%s'
                    '/reports/topfoodreport/pdf'
                    % (account_id, source_id, survey_id))


@prerequisite([SOURCE_PREREQS_MET])
def top_food_report_pdf(*,
                        account_id=None,
                        source_id=None,
                        survey_id=None):
    has_error, pdf_bytes, _ = ApiRequest.get(
        '/accounts/%s/sources/%s/surveys/%s/reports/topfoodreport' %
        (account_id, source_id, survey_id),
        parse_json=False
    )
    if has_error:
        return pdf_bytes

    response = make_response(pdf_bytes)
    response.headers.set("Content-Type", "application/pdf")
    # TODO: Do we want it to download a file or be embedded in the html?
    # response.headers.set('Content-Disposition',
    #                      'attachment',
    #                      filename='top-food-report.pdf')

    return response


@prerequisite([SOURCE_PREREQS_MET])
def get_source(*, account_id=None, source_id=None):
    # Retrieve the account to determine which kit it was created with
    has_error, account_output, _ = ApiRequest.get(
        '/accounts/%s' % account_id)
    if has_error:
        return account_output

    # Check if there are any unclaimed samples in the kit
    original_kit, _, kit_status = _get_kit(account_output['kit_name'])
    if kit_status == 404:
        claim_kit_name_hint = None
    else:
        claim_kit_name_hint = account_output['kit_name']

    # Retrieve the source
    has_error, source_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s' %
        (account_id, source_id))
    if has_error:
        return source_output

    # Retrieve all samples from the source
    has_error, samples_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s/samples' % (account_id, source_id))
    if has_error:
        return samples_output

    # Retrieve all surveys available to the source
    has_error, surveys_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s/survey_templates' % (account_id, source_id))
    if has_error:
        return surveys_output

    per_sample = []
    per_source = []
    restrict_to = _get_req_survey_templates_by_source_type(
        source_output["source_type"])
    for survey in surveys_output:
        if survey['survey_template_id'] in restrict_to:
            per_source.append(survey)
        if survey['survey_template_id'] == VIOSCREEN_ID:
            per_sample.append(survey)

    # Identify answered surveys for the source
    has_error, survey_answers, _ = ApiRequest.get(
        '/accounts/%s/sources/%s/surveys' % (account_id, source_id))
    if has_error:
        return survey_answers

    # TODO: Would be nice to know when the user took the survey instead of a
    #  boolean
    for answer in survey_answers:
        template_id = answer['survey_template_id']
        for template in per_source:
            if template['survey_template_id'] == template_id:
                template['answered'] = True

    # Identify answered surveys for the samples
    for sample in samples_output:
        sample['ffq'] = None
        sample['ffq_status'] = None
        sample_id = sample['sample_id']
        # TODO:  This is a really awkward and slow way to get this information
        has_error, per_sample_answers, _ = ApiRequest.get(
            '/accounts/%s/sources/%s/samples/%s/surveys' %
            (account_id, source_id, sample_id))
        if has_error:
            return per_sample_answers

        for answer in per_sample_answers:
            if answer['survey_template_id'] == VIOSCREEN_ID:
                sample['ffq'] = answer['survey_id']
                sample['ffq_status'] = answer['survey_status']

    # prettify datetime
    needs_assignment = False
    for sample in samples_output:
        if sample['sample_datetime'] is None:
            needs_assignment = True
        else:
            dt = datetime.fromisoformat(sample['sample_datetime'])
            # rebase=True - show in user's locale, rebase=False, UTC (I think?)
            sample['sample_datetime'] = flask_babel.format_datetime(
                dt,
                format=None,  # Use babel default (short/medium/long/full)
                rebase=False)

    needs_assignment = any([sample['sample_datetime'] is None
                            for sample in samples_output])

    is_human = source_output['source_type'] == Source.SOURCE_TYPE_HUMAN

    samples_output = [translate_sample(s) for s in samples_output]
    per_source = [translate_survey_template(s) for s in per_source]

    return _render_with_defaults('source.jinja2',
                                 account_id=account_id,
                                 source_id=source_id,
                                 is_human=is_human,
                                 needs_assignment=needs_assignment,
                                 samples=samples_output,
                                 surveys=per_source,
                                 source_name=source_output['source_name'],
                                 vioscreen_id=VIOSCREEN_ID,
                                 claim_kit_name_hint=claim_kit_name_hint,
                                 taxonomy=SERVER_CONFIG["taxonomy_resource"],
                                 alpha_metric=SERVER_CONFIG["alpha_metric"],
                                 barcode_prefix=SERVER_CONFIG[
                                     "barcode_prefix"],
                                 )


# Note: ideally this would be represented as a DELETE, not as a POST
# However, it is used as a form submission action, and HTML forms do not
# support delete as an action
@prerequisite([SOURCE_PREREQS_MET])
def post_remove_source(*,
                       account_id=None,
                       source_id=None):

    has_error, delete_output, _ = ApiRequest.delete(
        '/accounts/%s/sources/%s' %
        (account_id, source_id))

    if has_error:
        return delete_output

    return _refresh_state_and_route_to_sink(account_id)


@prerequisite([SOURCE_PREREQS_MET])
def get_update_sample(*, account_id=None, source_id=None, sample_id=None):
    has_error, source_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s' %
        (account_id, source_id)
    )
    if has_error:
        return source_output

    has_error, sample_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s/samples/%s' %
        (account_id, source_id, sample_id))
    if has_error:
        return sample_output

    source_type = source_output['source_type']
    is_environmental = source_type == Source.SOURCE_TYPE_ENVIRONMENT
    is_human = source_type == Source.SOURCE_TYPE_HUMAN

    if is_human:
        # Human Settings
        sample_sites = ["Blood (skin prick)", "Saliva", "Stool", "Mouth",
                        "Nares", "Nasal mucus", "Right hand", "Left hand",
                        "Forehead", "Torso", "Right leg", "Left leg",
                        "Vaginal mucus", "Tears", "Ear wax", "Hair", "Fur"]
        # babel scraping doesn't understand anything but constant strings.
        # do not collapse this into a for loop unless you can verify
        # that the POT file is correctly updated.
        sample_site_translations = [
            gettext("Blood (skin prick)"),
            gettext("Saliva"),
            gettext("Stool"),
            gettext("Mouth"),
            gettext("Nares"),
            gettext("Nasal mucus"),
            gettext("Right hand"),
            gettext("Left hand"),
            gettext("Forehead"),
            gettext("Torso"),
            gettext("Right leg"),
            gettext("Left leg"),
            gettext("Vaginal mucus"),
            gettext("Tears"),
            gettext("Ear wax"),
            gettext("Hair"),
            gettext("Fur")
        ]
    elif is_environmental:
        # Environment settings
        sample_sites = [None]
        sample_site_translations = [None]
    else:
        raise BadRequest("Sources of type %s are not supported at this time"
                         % source_output['source_type'])

    if sample_output['sample_datetime'] is not None:
        dt = datetime.fromisoformat(sample_output['sample_datetime'])
        # TODO: This might need some flask_babel calls, hmm...
        sample_output['date'] = dt.strftime("%m/%d/%Y")
        sample_output['time'] = dt.strftime("%-I:%M %p")
    else:
        sample_output['date'] = ""
        sample_output['time'] = ""

    return _render_with_defaults('sample.jinja2',
                                 account_id=account_id,
                                 source_id=source_id,
                                 source_name=source_output['source_name'],
                                 sample=sample_output,
                                 sample_sites=sample_sites,
                                 sample_sites_text=sample_site_translations,
                                 is_environmental=is_environmental)


# TODO: guess we should also rewrite as ajax post for sample vue form?
@prerequisite([SOURCE_PREREQS_MET])
def post_update_sample(*, account_id=None, source_id=None, sample_id=None):
    model = {}
    for x in flask.request.form:
        model[x] = flask.request.form[x]

    date = model.pop('sample_date_normalized')
    time = model.pop('sample_time')
    date_and_time = date + " " + time
    sample_datetime = datetime.strptime(date_and_time, "%m/%d/%Y %I:%M %p")
    model['sample_datetime'] = sample_datetime.isoformat()

    has_error, source_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s' %
        (account_id, source_id)
    )
    if has_error:
        return source_output

    has_error, sample_output, _ = ApiRequest.put(
        '/accounts/%s/sources/%s/samples/%s' %
        (account_id, source_id, sample_id),
        json=model)

    if has_error:
        return sample_output

    # If the user is human, see if they need ffq
    if source_output['source_type'] == Source.SOURCE_TYPE_HUMAN:
        # Check if this sample has an ffq associated with it,
        # if not, ask the user
        # if they'd like to fill one out.
        has_error, per_sample_answers, _ = ApiRequest.get(
            '/accounts/%s/sources/%s/samples/%s/surveys' %
            (account_id, source_id, sample_id))
        if has_error:
            return per_sample_answers

        has_ffq = False
        for answer in per_sample_answers:
            if answer['survey_template_id'] == VIOSCREEN_ID:
                has_ffq = True

        if not has_ffq:
            url = '/accounts/%s/sources/%s/samples/%s/after_edit_questionnaire'
            return redirect(url % (account_id, source_id, sample_id))
    return _refresh_state_and_route_to_sink(account_id, source_id)


@prerequisite([SOURCE_PREREQS_MET])
def check_questionnaire(*, account_id=None, source_id=None, sample_id=None):
    return _render_with_defaults('post_sample_questionnaire.jinja2',
                                 account_id=account_id,
                                 source_id=source_id,
                                 sample_id=sample_id,
                                 vioscreen_id=VIOSCREEN_ID)


@prerequisite([SOURCE_PREREQS_MET])
def get_sample_results(*, account_id=None, source_id=None, sample_id=None):
    has_error, source_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s' %
        (account_id, source_id)
    )
    if has_error:
        return source_output

    has_error, sample_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s/samples/%s' %
        (account_id, source_id, sample_id))
    if has_error:
        return sample_output

    if sample_output['sample_site'] == 'Stool':
        page = 'new_results_page.jinja2'
    else:
        page = 'sample_results.jinja2'

    return _render_with_defaults(page,
                                 account_id=account_id,
                                 source_id=source_id,
                                 sample=sample_output,
                                 source_name=source_output['source_name'],
                                 taxonomy=SERVER_CONFIG["taxonomy_resource"],
                                 alpha_metric=SERVER_CONFIG["alpha_metric"],
                                 beta_metric=SERVER_CONFIG["beta_metric"],
                                 barcode_prefix=SERVER_CONFIG["barcode_prefix"],  # noqa
                                 show_breadcrumbs=True
                                 )


# WARNING: this endpoint is NOT authenticated
def get_sample_results_experimental():
    # use an arbitrary set of credentials
    sample_output = {'account_id': 'NA',
                     'sample_barcode': '000004220',
                     'sample_datetime': '2013-04-21T22:00:00',
                     'sample_edit_locked': False,
                     'sample_id': 'NA',
                     'sample_notes': 'na',
                     'sample_projects': ['American Gut Project'],
                     'sample_remove_locked': False,
                     'sample_site': 'Stool',
                     'source_id': 'NA'}
    return _render_with_defaults(
        'new_results_page.jinja2',
        account_id='NA',
        source_id='NA',
        sample=sample_output,
        source_name='NA',
        taxonomy=SERVER_CONFIG["taxonomy_resource"],
        alpha_metric=SERVER_CONFIG["alpha_metric"],
        beta_metric=SERVER_CONFIG["beta_metric"],
        barcode_prefix=SERVER_CONFIG["barcode_prefix"],
        show_breadcrumbs=False
    )


@prerequisite([SOURCE_PREREQS_MET])
def get_sample_results_experimental_authenticated(*, account_id=None,
                                                  source_id=None,
                                                  sample_id=None):
    has_error, source_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s' %
        (account_id, source_id)
    )
    if has_error:
        return source_output

    has_error, sample_output, _ = ApiRequest.get(
        '/accounts/%s/sources/%s/samples/%s' %
        (account_id, source_id, sample_id))
    if has_error:
        return sample_output

    return _render_with_defaults('new_results_page.jinja2',
                                 account_id=account_id,
                                 source_id=source_id,
                                 sample=sample_output,
                                 source_name=source_output['source_name'],
                                 taxonomy=SERVER_CONFIG["taxonomy_resource"],
                                 alpha_metric=SERVER_CONFIG["alpha_metric"],
                                 beta_metric=SERVER_CONFIG["beta_metric"],
                                 barcode_prefix=SERVER_CONFIG["barcode_prefix"]
                                 )


# Note: ideally this would be represented as a DELETE, not as a POST
# However, it is used as a form submission action, and HTML forms do not
# support delete as an action
@prerequisite([SOURCE_PREREQS_MET])
def post_remove_sample_from_source(*,
                                   account_id=None,
                                   source_id=None,
                                   sample_id=None):
    has_error, delete_output, _ = ApiRequest.delete(
        '/accounts/%s/sources/%s/samples/%s' %
        (account_id, source_id, sample_id))

    if has_error:
        return delete_output

    return _refresh_state_and_route_to_sink(account_id, source_id)


def admin_emperor_playground():
    if not session.get(ADMIN_MODE_KEY, False):
        raise Unauthorized()

    return _render_with_defaults(
        "emperor.jinja2",
        user_sample_id="10317.000069368",  # Some arbitrary sample
        pcoa_url=SERVER_CONFIG["public_api_endpoint"] +
        "/plotting/diversity/beta/unweighted-unifrac"
        "/pcoa/oral/emperor"
        "?metadata_categories=age_cat"
        "&metadata_categories=bmi_cat"
        "&metadata_categories=latitude"
    )


def admin_barcode_search():
    if not session.get(ADMIN_MODE_KEY, False):
        raise Unauthorized()

    has_error, query_fields, _ = ApiRequest.get(
        '/admin/barcode_query_fields')

    if has_error:
        return query_fields

    return _render_with_defaults('admin_barcode_search.jinja2',
                                 query_fields=json.dumps(query_fields))


def admin_barcode_search_query(body):
    if not session.get(ADMIN_MODE_KEY, False):
        raise Unauthorized()

    has_error, query_results, _ = ApiRequest.post(
        '/admin/barcode_query',
        json=body
    )

    if has_error:
        return query_results
    return jsonify({'data': [[x] for x in query_results]}), 200


def get_ajax_check_kit_valid(kit_name):
    kit, error, _ = _get_kit(kit_name)
    result = True if error is None else error
    return flask.jsonify(result)


def get_ajax_list_kit_samples(kit_name):
    kit, error, code = _get_kit(kit_name)
    result = kit if error is None else error
    return flask.jsonify(result), code


def get_ajax_check_activation_code(code, email):
    response = requests.get(
        ApiRequest.API_URL + '/can_activate',
        auth=BearerAuth(session[TOKEN_KEY_NAME]),
        verify=ApiRequest.CAfile,
        params=ApiRequest.build_params({"email": email, "code": code}))
    if response.status_code != 200:
        # Damn, couldn't properly communicate to backend server...
        return gettext("Unable to validate Activation Code at this time")
    result_data = response.json()
    result = True if result_data["can_activate"] else result_data["error"]
    return flask.jsonify(result)


# NB: associating surveys with samples when samples are claimed means that any
# surveys added to this source AFTER these samples are claimed will NOT be
# associated with these samples.  This behavior is by design.
@prerequisite([SOURCE_PREREQS_MET])
def post_claim_samples(*, account_id=None, source_id=None, body=None):
    sample_ids_to_claim = body.get('sample_id')
    if sample_ids_to_claim is None:
        # User claimed no samples ... shrug
        return _refresh_state_and_route_to_sink(account_id, source_id)

    has_error, survey_output, _ = ApiRequest.get(
        '/accounts/{0}/sources/{1}/surveys'.format(account_id, source_id))
    if has_error:
        return survey_output

    # TODO: this will have to get more nuanced when we add animal surveys?
    # Grab all primary and covid surveys from the source and associate with
    # newly claimed samples; non-human sources always have none of these
    survey_ids_to_associate_with_samples = [
        x['survey_id'] for x in survey_output
        if x['survey_template_id'] in [1, 6]
    ]

    # TODO:  Any of these requests may fail independently, but we don't
    #  have a good policy to deal with partial failures.  Currently, we
    #  abort early but that will result in some set of associations being
    #  already made, one association failing, and the remaining
    #  associations not attempted.
    for curr_sample_id in sample_ids_to_claim:
        # Claim sample
        has_error, sample_output, _ = ApiRequest.post(
            '/accounts/{0}/sources/{1}/samples'.format(
                account_id, source_id),
            json={"sample_id": curr_sample_id})
        if has_error:
            return sample_output

        # Associate the input answered surveys with this sample.
        for survey_id in survey_ids_to_associate_with_samples:
            sample_survey_output = _associate_sample_to_survey(
                account_id, source_id, curr_sample_id, survey_id)
            if sample_survey_output is not None:
                return sample_survey_output

    return _refresh_state_and_route_to_sink(account_id, source_id)


# Administrator Mode Functionality
def get_interactive_account_search(email_query):
    if not session.get(ADMIN_MODE_KEY, False):
        raise Unauthorized()

    do_return, email_diagnostics, _ = ApiRequest.get(
        '/admin/search/account/%s' % (email_query,))
    if do_return:
        return email_diagnostics

    accounts = [{"email": acct['email'], "account_id": acct['id']}
                for acct in email_diagnostics['accounts']]
    return _render_with_defaults('admin_home.jinja2',
                                 accounts=accounts)


def get_interactive_activation(email_query=None, code_query=None):
    if not session.get(ADMIN_MODE_KEY, False):
        raise Unauthorized()

    do_return = False
    diagnostics = None
    if email_query is not None:
        do_return, diagnostics, _ = ApiRequest.get(
            "/admin/search/activation",
            params={"email_query": email_query}
        )
    elif code_query is not None:
        do_return, diagnostics, _ = ApiRequest.get(
            "/admin/search/activation",
            params={"code_query": code_query}
        )
    if do_return:
        return diagnostics

    return _render_with_defaults(
        'admin_activation_codes.jinja2',
        email_query=email_query,
        code_query=code_query,
        diagnostics=diagnostics
    )


def post_generate_activation(body):
    if not session.get(ADMIN_MODE_KEY, False):
        raise Unauthorized()

    if 'generate_csv' in body:
        emails, upload_err = parse_request_csv_col(
            request,
            'email_csv',
            'email'
        )
        if upload_err is not None:
            return upload_err
        else:
            emails = list({e.lower() for e in emails})
            code_map = {}
            for e in emails:
                do_return, diagnostics, _ = ApiRequest.post(
                    "/admin/activation",
                    json={"emails": [e]}
                )

                if do_return:
                    return diagnostics
                else:
                    do_return, diagnostics, _ = ApiRequest.get(
                        "/admin/search/activation",
                        params={"email_query": e}
                    )
                    if do_return:
                        return diagnostics
                    else:
                        code_map[e] = diagnostics[0]['code']

            csv_output = "EMAIL,ACTIVATION_CODE\n"
            for email, code in code_map.items():
                csv_output += email + "," + code + "\n"
            response = make_response(csv_output)
            response.headers["Content-Disposition"] = \
                "attachment; filename=activation_codes.csv"
            response.headers["Content-Type"] = "text/csv"
            return response
    else:
        email = body["email"]

        # Generate the activation code and update the list
        if 'generate' in body or 'generate_send' in body:
            do_return, diagnostics, _ = ApiRequest.post(
                "/admin/activation",
                json={"emails": [email]}
            )

            if do_return:
                return diagnostics

        # Also send an email out to the user
        if 'generate_send' in body:
            url = SERVER_CONFIG["endpoint"]
            do_return, diagnostics, _ = ApiRequest.post(
                "/admin/email",
                json={
                    "issue_type": "activation",
                    "template": "send_activation_code",
                    "template_args": {
                        "join_url": url,
                        "new_account_email": email
                        # don't need to send activation code,
                        # will be pulled from db on private api side.
                        # "new_account_code": XXX
                    }
                }
            )

            if do_return:
                return diagnostics
        return get_interactive_activation(email, None)


def get_system_message():
    if not session.get(ADMIN_MODE_KEY, False):
        raise Unauthorized()

    return _render_with_defaults('admin_system_panel.jinja2')


def post_system_message(body):
    # TODO: Localizing system messages means
    #  a dropdown instead of free text.
    if not session.get(ADMIN_MODE_KEY, False):
        raise Unauthorized()

    text = body.get("system_msg_text")
    style = body.get("system_msg_style")
    hours = body.get("system_msg_hours")
    minutes = body.get("system_msg_minutes")

    if text is None or len(text) == 0:
        text = None
        style = None
        hours = None
        minutes = None

    client_state[RedisCache.SYSTEM_BANNER] = (text, style, hours, minutes)

    return _render_with_defaults('admin_system_panel.jinja2')


def session_locale():
    # Based on snippet from https://flask-babel.tkte.ch/
    if LANG_KEY in session:
        return session[LANG_KEY]

    # Awful.  Can't resolve languages when inside unit tests,
    # so have to pick a default
    if not flask.has_request_context():
        return LANGUAGES[EN_US_KEY].value

    # TODO: We update this as we add support for new languages
    return request.accept_languages.best_match(
        [LANGUAGES[lang].value for lang in LANGUAGES])


class BearerAuth(AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers['Authorization'] = "Bearer " + self.token
        return r


class ApiRequest:
    API_URL = SERVER_CONFIG["private_api_endpoint"]
    CAfile = SERVER_CONFIG["CAfile"]

    @classmethod
    def build_params(cls, params):
        all_params = {}
        all_params["language_tag"] = session_locale()
        if params:
            for key in params:
                all_params[key] = params[key]
        return all_params

    @classmethod
    def _check_response(cls, response, parse_json=True):
        error_code = response.status_code
        output = None
        headers = None

        if response.status_code == 401 or response.status_code == 403:
            # output is redirect to home page for login or email verification
            output = redirect(HOME_URL)
        elif response.status_code >= 400:
            # output is general error page
            output = get_show_error_page(response.text)
        else:
            error_code = 0  # there is a response code but no *error* code
            headers = response.headers
            if parse_json:
                if response.text:
                    output = response.json()
            else:
                output = response.content

        return error_code, output, headers

    @classmethod
    def get(cls, input_path, parse_json=True, params=None):
        response = requests.get(
            ApiRequest.API_URL + input_path,
            auth=BearerAuth(session[TOKEN_KEY_NAME]),
            verify=ApiRequest.CAfile,
            params=cls.build_params(params))

        return cls._check_response(response, parse_json=parse_json)

    @classmethod
    def put(cls, input_path, params=None, json=None):
        response = requests.put(
            ApiRequest.API_URL + input_path,
            auth=BearerAuth(session[TOKEN_KEY_NAME]),
            verify=ApiRequest.CAfile,
            params=cls.build_params(params),
            json=json)

        return cls._check_response(response)

    @classmethod
    def post(cls, input_path, params=None, json=None):
        response = requests.post(
            ApiRequest.API_URL + input_path,
            auth=BearerAuth(session[TOKEN_KEY_NAME]),
            verify=ApiRequest.CAfile,
            params=cls.build_params(params),
            json=json)
        return cls._check_response(response)

    @classmethod
    def delete(cls, input_path, params=None):
        response = requests.delete(
            ApiRequest.API_URL + input_path,
            auth=BearerAuth(session[TOKEN_KEY_NAME]),
            verify=ApiRequest.CAfile,
            params=cls.build_params(params))

        return cls._check_response(response)
