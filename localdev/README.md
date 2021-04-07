# Local development tools

### Local starter projects

Starter projects can be defined within this directory for development use. `example-starter` is the only directory
under version control. Any other starter projects you add will be ignored by Git.

Usage:
1. Add a directory with the appropriate site config file and templates under the `localdev/starters` directory.
2. Run the management command to load the starter projects into the database (`populate_local_starters`)

### Config override

In production, OCW Studio will pull site configs from a starter repo on Github. We want at least one starter project
to be available in all environments (the OCW course site starter), and for local development purposes it's not very
convenient to depend on the site config being up-to-date in that external repo. The `override_site_config` management
command is included to update the site config for a `WebsiteStarter` database record with an example site config 
defined in this repo.

These files are version-controlled to ensure that everyone gets the same config updates.

```
# Overwrite the "course" starter with the "ocw-course-site-config.yml" example config file (these are the default values)
python manage.py override_site_config

# Overwrite the "example1" starter with the "my-new-example.yml" config file
python manage.py override_site_config --starter="example1" --config-path="localdev/configs/my-new-example.yml"
```
