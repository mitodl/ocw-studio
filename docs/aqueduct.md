# Typed settings via django-aqueduct (opt-in)

`ocw-studio` ships two **opt-in** settings modules built on top of
[`django-aqueduct`](https://github.com/mitodl/django-aqueduct), a typed,
Pydantic-based settings layer for Django. They exist alongside the
project's normal settings and change nothing unless explicitly selected.

## What's here

- `main/aqueduct_settings.py` — a Pydantic `BaseSettings` model
  (`AqueductSettings`) describing every setting currently produced by
  `main/settings.py`, plus a `DevAqueductSettings` subclass for local
  development.
- `main/settings_aqueduct.py` — a thin shim that instantiates
  `AqueductSettings` and injects its values into Django via
  `django_aqueduct.configure_django_settings`.
- `main/settings_aqueduct_dev.py` — the same shim using
  `DevAqueductSettings`, which additionally pulls any settings missing from
  the environment/`.env` file from Vault (KV v2, mount `secret-ocw-studio`)
  using OIDC authentication.

## Selecting a settings module

Nothing changes by default. `main/settings.py` remains the settings module
used everywhere (`manage.py`, Celery workers, tests, deployments) unless you
explicitly point `DJANGO_SETTINGS_MODULE` elsewhere:

```shell
# Standard settings (default, untouched):
DJANGO_SETTINGS_MODULE=main.settings

# Aqueduct-based settings, populated from env vars / .env:
DJANGO_SETTINGS_MODULE=main.settings_aqueduct

# Aqueduct-based settings for local dev, falling back to Vault via OIDC
# for anything missing from the environment:
DJANGO_SETTINGS_MODULE=main.settings_aqueduct_dev
```

## Regenerating the scaffold

`main/aqueduct_settings.py` was originally produced with:

```shell
python manage.py generate_aqueduct_settings \
    --modules main.settings \
    --include-envparser \
    --output main/aqueduct_settings.py
```

and then hand-refined: descriptions/required-ness were reconciled between
the plain module scan and the mitol `EnvParser` registry scan, aliasing was
added wherever a Django setting name differs from its backing environment
variable name (e.g. `SITE_ID` reads from `OCW_STUDIO_SITE_ID`), and
`@model_validator` methods were added to reproduce the derived settings and
cross-field validation that exist in `main/settings.py` today (`DATABASES`,
`INSTALLED_APPS`/`MIDDLEWARE`, `CELERY_BEAT_SCHEDULE`, the S3-credentials
completeness check, the `OCW_EXTRA_THEMES_GTM_IDS` subset check, the
`PLAYWRIGHT_IMAGE_ARCH` enum check, and the `GITHUB_APP_PRIVATE_KEY`
unicode-escape transform). If you re-run the generator, re-apply those
refinements rather than committing the raw scaffold directly.

## Known gaps / follow-ups

- `VAULT_AQUEDUCT_PATH` and the default OIDC role (`"ocw-studio"`) used by
  `DevAqueductSettings` are placeholders. They need to be confirmed against
  the live Vault server (e.g. `vault kv list secret-ocw-studio/`) before
  `main.settings_aqueduct_dev` is used for real.
- A number of fields are still typed `Any` with a `# TODO: refine type`
  marker — these are settings whose original value couldn't be
  automatically inferred as a precise type (e.g. values that were `None` at
  generation time). Narrowing these further is optional follow-up work.
