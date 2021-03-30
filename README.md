# ocw_studio
OCW Studio manages deployments for OCW courses.

**SECTIONS**
1. [Initial Setup](#initial-setup)
1. [Testing and Formatting](#testing-and-formatting)
1. [Importing OCW course sites](#importing-ocw-course-sites)
1. [Defining local starter projects and site configs](#defining-local-starter-projects-and-site-configs)


# Initial Setup

ocw_studio follows the same [initial setup steps outlined in the common ODL web app guide](https://github.com/mitodl/handbook/blob/master/common-web-app-guide.md).
Run through those steps **including the addition of `/etc/hosts` aliases and the optional step for running the
`createsuperuser` command**.


### Testing Touchstone login with SAML via SSOCircle

*Note: Testing with ShibTest instead of SSOCircle fails unless python-saml3 is downgraded to 1.2.6 and `use="signing"` is removed from the `KeyDescriptor` tag of the SP metadata*

- NOTE: your app's BASE_URL hostname and the x509 FQDN must match, additionally SSOCircle enforces an requirement that this value be unique per user, so you'll need to pick a hostname no one else on our team is using
- Create an X.509 certificate & key with the following command, picking a unique FQDN for yourself (e.g. MYNAME.ocw-studio.odl.local):
  ```
  openssl req -new -x509 -days 365 -nodes -out saml.crt -keyout saml.key
  ```
- Enter values for the following [SAML configuration variables](http://python-social-auth-docs.readthedocs.io/en/latest/backends/saml.html) in your `.env` file
  ```
  SOCIAL_AUTH_SAML_SP_ENTITY_ID=http://MYNAME.ocw-studio.odl.local:8043/  # replace with the one entered into the x509 cert above
  SOCIAL_AUTH_SAML_SP_PUBLIC_CERT=<saml.crt contents, no spaces or returns>
  SOCIAL_AUTH_SAML_SP_PRIVATE_KEY= <saml.key contents, no spaces or returns>
  SOCIAL_AUTH_SAML_ORG_DISPLAYNAME=ODL Test
  SOCIAL_AUTH_SAML_CONTACT_NAME=<Your Name>
  SOCIAL_AUTH_SAML_IDP_ENTITY_ID=https://idp.ssocircle.com
  SOCIAL_AUTH_SAML_IDP_URL=https://idp.ssocircle.com:443/sso/SSORedirect/metaAlias/publicidp
  SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_PERM_ID=EmailAddress
  SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_NAME=FirstName
  SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_EMAIL=EmailAddress
  SOCIAL_AUTH_SAML_IDP_X509=MIIEYzCCAkugAwIBAgIDIAZmMA0GCSqGSIb3DQEBCwUAMC4xCzAJBgNVBAYTAkRFMRIwEAYDVQQKDAlTU09DaXJjbGUxCzAJBgNVBAMMAkNBMB4XDTE2MDgwMzE1MDMyM1oXDTI2MDMwNDE1MDMyM1owPTELMAkGA1UEBhMCREUxEjAQBgNVBAoTCVNTT0NpcmNsZTEaMBgGA1UEAxMRaWRwLnNzb2NpcmNsZS5jb20wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCAwWJyOYhYmWZF2TJvm1VyZccs3ZJ0TsNcoazr2pTWcY8WTRbIV9d06zYjngvWibyiylewGXcYONB106ZNUdNgrmFd5194Wsyx6bPvnjZEERny9LOfuwQaqDYeKhI6c+veXApnOfsY26u9Lqb9sga9JnCkUGRaoVrAVM3yfghv/Cg/QEg+I6SVES75tKdcLDTt/FwmAYDEBV8l52bcMDNF+JWtAuetI9/dWCBe9VTCasAr2Fxw1ZYTAiqGI9sW4kWS2ApedbqsgH3qqMlPA7tg9iKy8Yw/deEn0qQIx8GlVnQFpDgzG9k+jwBoebAYfGvMcO/BDXD2pbWTN+DvbURlAgMBAAGjezB5MAkGA1UdEwQCMAAwLAYJYIZIAYb4QgENBB8WHU9wZW5TU0wgR2VuZXJhdGVkIENlcnRpZmljYXRlMB0GA1UdDgQWBBQhAmCewE7aonAvyJfjImCRZDtccTAfBgNVHSMEGDAWgBTA1nEA+0za6ppLItkOX5yEp8cQaTANBgkqhkiG9w0BAQsFAAOCAgEAAhC5/WsF9ztJHgo+x9KV9bqVS0MmsgpG26yOAqFYwOSPmUuYmJmHgmKGjKrj1fdCINtzcBHFFBC1maGJ33lMk2bM2THx22/O93f4RFnFab7t23jRFcF0amQUOsDvltfJw7XCal8JdgPUg6TNC4Fy9XYv0OAHc3oDp3vl1Yj8/1qBg6Rc39kehmD5v8SKYmpE7yFKxDF1ol9DKDG/LvClSvnuVP0b4BWdBAA9aJSFtdNGgEvpEUqGkJ1osLVqCMvSYsUtHmapaX3hiM9RbX38jsSgsl44Rar5Ioc7KXOOZFGfEKyyUqucYpjWCOXJELAVAzp7XTvA2q55u31hO0w8Yx4uEQKlmxDuZmxpMz4EWARyjHSAuDKEW1RJvUr6+5uA9qeOKxLiKN1jo6eWAcl6Wr9MreXR9kFpS6kHllfdVSrJES4ST0uh1Jp4EYgmiyMmFCbUpKXifpsNWCLDenE3hllF0+q3wIdu+4P82RIM71n7qVgnDnK29wnLhHDat9rkC62CIbonpkVYmnReX0jze+7twRanJOMCJ+lFg16BDvBcG8u0n/wIDkHHitBI7bU1k6c6DydLQ+69h8SCo6sO9YuD+/3xAGKad4ImZ6vTwlB4zDCpu6YgQWocWRXE+VkOb+RBfvP755PUaLfL63AFVlpOnEpIio5++UjNJRuPuAA=
  ```
- Go to `http://MYNAME.ocw-studio.odl.local:8043/saml/metadata/` and copy the XML response  
- Register & login for a free account at `ssocircle.net`, the email that you use to register will be used as your social-auth identifier
- After confirming your registration, go to https://idp.ssocircle.com/sso/hos/ManageSPMetadata.jsp
  - Click `Add new Service Provider`
  - Enter your FDQN as the FQDN
  - Check `FirstName`, `EmailAddress`
  - Paste the XML response from above into the text field
  - Submit the form
- In an incognito browser window, go to `http://MYNAME.ocw-studio.odl.local:8043/login/saml/?next=%2F&idp=default`
- You should be redirected to SSOCircle, fill out the captcha and click `Continue SAML Single Sign On`
- You should be redirected back to the /sites/ pages, and be logged in.
- Log out & back in as a superuser and to go the Users admin page.
  - There should be a new user with the same email address and name that you used to register with SSOCircle.

### Commits

To ensure commits to github are safe, you should install the following first:
```
pip install pre_commit
pre-commit install
```

To automatically install precommit hooks when cloning a repo, you can run this:
```
git config --global init.templateDir ~/.git-template
pre-commit init-templatedir ~/.git-template
```


# Testing and Formatting

Writing tests, running the test suite, and formatting code follows the same steps that are outlined in [the common ODL web app guide](https://github.com/mitodl/handbook/blob/master/common-web-app-guide.md#testing-and-formatting).
Below are some steps that may be particular to this project.

## JS/CSS Tests and Linting

The JS linting, testing, and formatting tools can be used either in the `watch`
(node.js) container or on the host computer from the command line.

To run these things in the docker container, preface the commands below with
`docker-compose run --rm watch`.

### JS tests

We use [Jest](https://jestjs.io/) for our JavaScript tests. It's a nice batteries-included
testing framework built for testing React components from the ground up.

To run the tests:

```sh
npm test
```

For watch mode (`jest --watch`):

```sh
npm run test:watch
```

To run a specific test by name:

```sh
npm test -- -t "my test name"
```

(note that this will find partial matches too).

To generate a coverage report:

```sh
npm run test:coverage
```

### JS formatting, linting, and typechecking

We're using TypeScript for typechecking, eslint for linting, and prettier for
opinionated code formatting. Just as with the tests above, these commands can
all be run ether in the docker container or the host machine.

To run the typechecker:

```sh
npm run typecheck
```

This runs `tsc --noEmit`, which basically typechecks the program and outputs
any error but does not run a full compilation. We have incremental compilation
turned on, so this should be relatively fast. It uses a file called
`.tsbuildinfo` for incremental compilation.

To run the linter:

```sh
npm run lint
```

And to format, try:

```sh
npm run fmt
```

You can also try `npm run fmt:check` to see if any files need to be reformatted.


# Importing OCW course sites

We have raw data for numerous course sites in cloud storage. These sites can be imported into OCW Studio and
saved into the database via a management command: `import_ocw_course_sites`.

This command will only work if you have the following:
1. The name of the AWS bucket which contains the course data. Ask a fellow developer for this.
1. Valid settings for `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. As with other settings, these should be
   specified in your `.env` file. You can copy these from heroku, or ask a fellow developer for them.

Some example commands:

```bash
# List the data file names of all available course sites
manage.py import_ocw_course_sites -b <bucket_name> --list

# List the data file names of all course sites that match a filter
manage.py import_ocw_course_sites -b <bucket_name> --filter frameworks-of-urban-governance --list

# Import course sites with a data file name that matches a filter
manage.py import_ocw_course_sites -b <bucket_name> --filter frameworks-of-urban-governance

# Import ALL course sites (this will take quite a while)
manage.py import_ocw_course_sites -b <bucket_name>
```


# Defining local starter projects and site configs

This project includes some tools that simplify development with starter projects and site configs. These tools allow you to do the following:
- Define entire starter projects within this repo and load them into your database
- Override the site config for starters with a particular `slug` value

See the [README in localdev/starters](localdev/starters/) for instructions.
