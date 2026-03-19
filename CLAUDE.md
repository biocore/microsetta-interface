# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

microsetta-interface is the web UI for the Microsetta Initiative (primarily the American Gut Project). It's a Python Flask app (via Connexion/OpenAPI) that communicates with microsetta-private-api for data persistence and business logic.

## Common Commands

```bash
# Install (conda environment)
conda create --yes -n microsetta-interface python=3.11
conda install --yes -n microsetta-interface --file ci/conda_requirements.txt
conda activate microsetta-interface
pip install -r ci/pip_requirements.txt
pip install -e . --no-deps

# Compile translation catalogs (required before running)
python setup.py compile_catalog

# Run development server (localhost:8083)
python microsetta_interface/server.py

# Lint
make lint          # or: flake8 microsetta_interface

# Run all tests
make test          # or: pytest

# Run tests with coverage
make test-cov      # or: pytest --cov=microsetta_interface

# Run a single test
pytest microsetta_interface/tests/test_implementation.py::TestImplementation::test_get_source_redirect_on_source_prereqs_error

# Verify package installs correctly
make test-install
```

## Integration Tests

Integration tests (`test_integration.py`) require:
- microsetta-private-api running with `disable_authentication: true`
- PostgreSQL on port 5432
- Redis server running
- JWT keys via `source keys_for_testing.sh` (sets `MICROSETTA_INTERFACE_DEBUG_JWT_PRIV`)

Integration tests are run as a script (`python microsetta_interface/tests/test_integration.py`), not via pytest.

## Architecture

### Request Flow

Connexion loads `routes.yaml` (OpenAPI 3.0 spec) which maps HTTP endpoints to functions in `implementation.py`. The Flask app is created in `server.py` via `build_app()`.

### Prerequisite State Machine

The `@prerequisite` decorator (`implementation.py:700`) enforces a workflow state machine on route handlers. Before a handler executes, the decorator checks the user's current state and redirects if prerequisites aren't met. States progress in order:

`NeedsReroute` → `NeedsLogin` → `NeedsAccount` → `NeedsEmailCheck` → `NeedsPrimarySurveys` → `TokenPrereqsMet` → `AcctPrereqsMet` → `SourcePrereqsMet` → `BiospecimenPrereqsMet`

Each route declares which states it accepts. Prerequisite checks are chained: `_check_home_prereqs` → `_check_acct_prereqs` → `_check_source_prereqs` → `_check_biospecimen_prereqs`.

### Key Modules

- **`implementation.py`** — All route handlers and business logic (~4000 lines). Manages JWT auth (Authrocket RS256), session state, and API calls to microsetta-private-api.
- **`server.py`** — App factory (`build_app()`), Babel i18n setup, reverse proxy support.
- **`routes.yaml`** — OpenAPI spec defining all endpoints and mapping to `implementation.py` functions.
- **`config_manager.py`** — Loads `server_config.json` at import time into `SERVER_CONFIG`.
- **`model_i18n.py`** — Translation utilities for source types, sample types, and survey labels.
- **`redis_cache.py`** — Redis wrapper for system banner caching.

### Internationalization (i18n)

Four locales supported: `en_US`, `es_MX`, `es_ES`, `ja_JP`. Uses Flask-Babel with Jinja2 template extraction.

To update translation files after changing translatable strings:
```bash
cd microsetta_interface
pybabel extract -F ../babel.cfg -o translations/base.pot .
pybabel update -i translations/base.pot -d translations
```

### Frontend

Server-side rendered Jinja2 templates with client-side Vue.js, jQuery, Bootstrap 5, and DataTables. Emperor is used for microbiome PCoA visualizations. All vendor JS/CSS is committed in `static/vendor/`.

### Testing Patterns

Unit tests (`test_implementation.py`) mock `requests.get`, `render_template`, and `session` via `unittest.mock.patch`. Tests use Flask's test client. The `TestResponse` helper class is used instead of MagicMock because tested code uses comparison operators on `status_code`.

### Dependency Constraints

connexion < 2.7.1 is the binding constraint for nearly all dependency ceilings. It uses private/removed APIs in Flask, Werkzeug, jsonschema, and openapi-spec-validator. Until connexion is upgraded to 3.x (a full rewrite), these ceilings apply:

- Flask < 2.3.0 (2.3 removed `flask.json.JSONEncoder` used by connexion)
- Werkzeug < 2.4.0
- jsonschema < 4.0.0 (connexion uses `jsonschema._utils.types_msg()` removed in 4.0)
- openapi-spec-validator < 0.4.0 (0.4.0+ requires jsonschema >= 4)


### Configuration

`server_config.json` holds runtime config: API endpoints, port, SSL, Authrocket URL, Flask secret key. The private API defaults to `localhost:8082/api`.
