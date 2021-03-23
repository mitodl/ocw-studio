# Site config schema

This app is responsible for defining the schema that site config files must follow, and validating site configs
against that schema.

We use [yamale](https://github.com/23andMe/Yamale) to define the schema. 
If we intend to change the schema, our schema definition (`site-config-schema.yml`)
should be updated to reflect that change.

If the schema does not provide a way to define a certain type of constraint, we can define additional custom rules.
Those can be defined in `websites/config_schema/validators.py` then appended to the list of added rules in
`websites/config_schema/api.py`.
