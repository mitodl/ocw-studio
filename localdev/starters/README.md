### Local starter projects

Starter projects can be defined within this directory for development use. `example-starter` is the only directory
under version control. Any other starter projects you add will be ignored by Git.

Usage:
1. Add a directory with the appropriate site config file and templates under the `localdev/starters` directory.
2. Run the management command to load the starter projects into the database (`populate_local_starters`)

### Config override

In production, OCW Studio will pull site configs from a starter repo on Github. We want at least one starter project
to be available in all environments (the OCW course site starter), and for local development purposes it's not very
convenient to depend on the site config being up-to-date in that external repo. `site-config-override.yml` lets us define
site configs within this repo and run a management command to update the relevant `WebsiteStarter` database records.

This file is version-controlled to ensure that everyone gets the same config updates.

You can target a `WebsiteStarter` in the config override by adding a top-level key that matches its `slug` value. 
For example, if `site-config-override.yml` looks like this, the `WebsiteStarter` with `slug="starter1"` would be updated
with the given config if the management command was run:

```yaml
starter1:
  collections:
    - label: "Page"
      name: "page"
      fields:
        - {label: "Title", name: "title", widget: "string"}
```

With that config override file in place, simply run `python manage.py override_site_configs`.