# ocw_studio

OCW Studio manages deployments for OCW courses.

**SECTIONS**

- [ocw_studio](#ocw_studio)
- [Initial Setup](#initial-setup)
  - [Testing Touchstone login with SAML via SSOCircle](#testing-touchstone-login-with-saml-via-ssocircle)
  - [Commits](#commits)
- [Testing and Formatting](#testing-and-formatting)
  - [JS/CSS Tests and Linting](#jscss-tests-and-linting)
    - [JS tests](#js-tests)
    - [JS formatting, linting, and typechecking](#js-formatting-linting-and-typechecking)
- [Defining local starter projects and site configs](#defining-local-starter-projects-and-site-configs)
  - [The `localdev` folder](#the-localdev-folder)
  - [Importing starter projects from Github](#importing-starter-projects-from-github)
  - [Automatically updating starters from Github](#automatically-updating-starters-from-github)
- [Enabling GitHub integration](#enabling-github-integration)
- [Local S3 emulation with Minio](#local-s3-emulation-with-minio)
- [Enabling Concourse-CI integration](#enabling-concourse-ci-integration)
  - [Running a Local Concourse Docker Container](#running-a-local-concourse-docker-container)
  - [End to end testing of site pipelines](#end-to-end-testing-of-site-pipelines)
- [Running OCW Studio on Apple Silicon](#running-ocw-studio-on-apple-silicon)
- [Video Workflow](#video-workflow)
- [Enabling YouTube integration](#enabling-youtube-integration)
- [Enabling Google Drive integration](#enabling-google-drive-integration)
- [Enabling AWS MediaConvert transcoding](#enabling-aws-mediaconvert-transcoding)
- [Enabling 3Play integration](#enabling-3play-integration)
- [Enabling Open Catalog Search Webhooks](#enabling-open-catalog-search-webhooks)

# Initial Setup

`ocw_studio` follows the same [initial setup steps outlined in the common ODL web app guide](https://mitodl.github.io/handbook/how-to/common-web-app-guide.html).
Run through those steps **including the addition of `/etc/hosts` aliases and the optional step for running the
`createsuperuser` command**.

Websites are created using a template called a "starter." You can import a standard set of starters by running:

```sh
docker-compose exec web ./manage.py import_website_starters https://github.com/mitodl/ocw-hugo-projects
```

The `ocw-www` starter is meant for creating a home page, aka the "root website." This is called `ocw-www` by default, but the name of the site can be set on `ROOT_WEBSITE_NAME` in your environment if you wish to change it. The other starters are different types of websites that can be built within `ocw-studio`. After you have imported some starters, you are ready to start creating websites. To publish those websites, follow the guides in the table of contents above for setting up:

- A Github organization
- Google Drive integration for resources
- AWS S3 credentials (Minio S3 emulation should work out of the box for local development)
- Youtube / AWS MediaConvert / 3Play if you need to work with videos

### Testing Touchstone login with SAML via SSOCircle

_Note: Testing with ShibTest instead of SSOCircle fails unless python-saml3 is downgraded to 1.2.6 and `use="signing"` is removed from the `KeyDescriptor` tag of the SP metadata_

- NOTE: your app's BASE_URL hostname and the x509 FQDN must match, additionally SSOCircle enforces an requirement that this value be unique per user, so you'll need to pick a hostname no one else on our team is using
- Create an X.509 certificate & key with the following command, picking a unique FQDN for yourself (e.g. MYNAME.ocw-studio.odl.local):
  ```
  openssl req -new -x509 -days 365 -nodes -out saml.crt -keyout saml.key
  ```
- Enter values for the following [SAML configuration variables](http://python-social-auth-docs.readthedocs.io/en/latest/backends/saml.html) in your `.env` file
  ```sh
  SOCIAL_AUTH_SAML_SP_ENTITY_ID=http://MYNAME.ocw-studio.odl.local:8043/  # replace with the one entered into the x509 cert above
  SOCIAL_AUTH_SAML_SP_PUBLIC_CERT=<saml.crt contents, no spaces or returns>
  SOCIAL_AUTH_SAML_SP_PRIVATE_KEY= <saml.key contents, no spaces or returns>
  SOCIAL_AUTH_SAML_SECURITY_ENCRYPTED=false
  SOCIAL_AUTH_SAML_ORG_DISPLAYNAME=ODL Test
  SOCIAL_AUTH_SAML_CONTACT_NAME=<Your Name>
  SOCIAL_AUTH_SAML_IDP_ENTITY_ID=https://idp.ssocircle.com
  SOCIAL_AUTH_SAML_IDP_URL=https://idp.ssocircle.com:443/sso/SSORedirect/metaAlias/publicidp
  SOCIAL_AUTH_SAML_LOGIN_URL=https://idp.ssocircle.com:443/sso/SSORedirect/metaAlias/publicidp
  SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_PERM_ID=EmailAddress
  SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_NAME=FirstName
  SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_EMAIL=EmailAddress
  # The value for SOCIAL_AUTH_SAML_IDP_X509 comes from https://idp.ssocircle.com/meta-idp.xml:
  SOCIAL_AUTH_SAML_IDP_X509=<get value from https://idp.ssocircle.com/meta-idp.xml>
  ```
- Go to `http://MYNAME.ocw-studio.odl.local:8043/saml/metadata/` and copy the XML response
- Register & login for a free account at `ssocircle.net`, the email that you use to register will be used as your social-auth identifier.

  _SSOCircle free accounts are limited to three concurrent sessions. See https://www.ssocircle.com/en/portfolio/publicidp/idp-pricing/_

- After confirming your registration, go to https://idp.ssocircle.com/sso/hos/ManageSPMetadata.jsp
  - Click `Add new Service Provider`
  - Enter your FQDN as the FQDN
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

Writing tests, running the test suite, and formatting code follows the same steps that are outlined in [the common ODL web app guide](https://mitodl.github.io/handbook/how-to/common-web-app-guide.html#testing-and-formatting).
Below are some steps that may be particular to this project.

## JS/CSS Tests and Linting

The JS linting, testing, and formatting tools can be used either in the `watch`
(node.js) container or on the host computer from the command line.

To run these things in the Docker container, preface the commands below with
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
all be run ether in the Docker container or the host machine.

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

# Defining local starter projects and site configs

The `ocw-studio` software allows you to create websites based on a configuration called a "starter." These configuration files are named `ocw-studio.yaml` by default but that name can be overridden by setting `OCW_STUDIO_SITE_CONFIG_FILE` in your environment. These starters can be imported into `ocw-studio` in a couple of different ways.

### The `localdev` folder

More details on this are in [this readme file](localdev/README.md)

### Importing starter projects from Github

MIT OCW has a set of starter configs that are used in building the official OCW site. They are stored in a repo called [`ocw-hugo-projects`](https://github.com/mitodl/ocw-hugo-projects). This repo can be used as a reference for setting up your own repo. When you make your own repo, make sure that your config files in the repo are in their own folder and the filenames match what is set to `OCW_STUDIO_SITE_CONFIG_FILE`, which is `ocw-studio.yaml` by default. The folder name is used to determine the `slug` property of the resulting starter object, and the config file is read from that folder and applied to the `config` property. When your repo is ready, make sure it is publically accessible and then you can import the starter configs from it by running:

```sh
docker-compose exec web ./manage.py import_website_starters https://github.com/mitodl/ocw-hugo-projects
```

If you wish to use your own Github repo containing starters use that URL instead. If any starters already exist with the same slug as one being imported, their configuration will be updated.

### Automatically updating starters from Github

If you are hosting `ocw-studio` on the internet and wish to have your starter updated automatically when you make changes to the starter configurations in your Github repo, this is possible by configuring a webhook. In order to accomplish this, you will need to first set `GITHUB_WEBHOOK_BRANCH` in your environment to the branch that you wish to watch for changes on (i.e. `release`). Then, you will need to configure a webhook in the settings of your Github repo targeting `/api/starters/site_configs` on your instance of `ocw-studio`. After this is set up, on pushes to the configured branch, a webhook will be fired to your `ocw-studio` instance which will trigger automatic updating of your starter configurations.

# Enabling GitHub integration

You can enable git integration so that website content will be synced with GitHub:

- Create an organization within Github
- Create a Github personal access token, with all `repo` permissions
- Add the following to your .env file:
  ```
  CONTENT_SYNC_BACKEND=content_sync.backends.github.GithubBackend
  GIT_ORGANIZATION=<your_organization>
  ```
- If you need to use a custom git domain, add `GIT_API_URL=<your_domain>/api/v3`
- If you would like git commits to be anonymized, add `FEATURE_GIT_ANONYMOUS_COMMITS=True`

You will also need authenticate using either a personal access token or via a github app.
Both options have a base rate limit of 5K/hour, but a github app will allow for an additional
50/hr for each repo in your organization if you have at least 20 repos.

If you wish to authenticate using a personal access token, create one in Github then set the following
in your .env file:

```
GIT_TOKEN=<your_token>
```

If you wish to use a github app,
[create one for your organization](https://docs.github.com/en/developers/apps/building-github-apps/creating-a-github-app):

- The homepage url can be anything
- You do not need a callback url or webhook url (disable webhooks)
- For Repository Permissions, choose "read/write" permission for "Administration", "Contents", "Pull Requests", "Commit Statuses"
- After it is created, add the "App ID" to your .env file:
  ```
  GITHUB_APP_ID=<app id>
  ```
- Generate a private key. A pem file will download. You need to use the content of this file in your .env file:
  ```
  GITHUB_APP_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\nMIIEpQ......\n-----END RSA PRIVATE KEY-----
  ```
- Install the app (follow instructions in link above) to your organization for "All repositories"

# Local S3 emulation with Minio

Our `docker-compose` configuration includes an instance of [Minio](https://github.com/minio/minio) which emulates Amazon's S3 service locally.
This works in conjunction with the `ENVIRONMENT` env variable being set to "dev." When this is set, usage of the `boto3` library will automatically
set `endpoint_url` to the internal Docker IP address of the Minio instance. You will need a few env variables:

```python
MINIO_ROOT_USER=minio_user
MINIO_ROOT_PASSWORD=minio_password
AWS_ACCESS_KEY_ID=minio_user
AWS_SECRET_ACCESS_KEY=minio_password
AWS_STORAGE_BUCKET_NAME=ol-ocw-studio-app
AWS_PREVIEW_BUCKET_NAME=ocw-content-draft
AWS_PUBLISH_BUCKET_NAME=ocw-content-live
AWS_TEST_BUCKET_NAME=ocw-content-test
AWS_OFFLINE_PREVIEW_BUCKET_NAME=ocw-content-offline-draft
AWS_OFFLINE_PUBLISH_BUCKET_NAME=ocw-content-offline-live
AWS_OFFLINE_TEST_BUCKET_NAME=ocw-content-offline-test
AWS_ARTIFACTS_BUCKET_NAME=ol-eng-artifacts
OCW_HUGO_THEMES_BRANCH=main
OCW_HUGO_PROJECTS_BRANCH=main
STATIC_API_BASE_URL=https://ocw.mit.edu
RESOURCE_BASE_URL_DRAFT=https://draft.ocw.mit.edu
RESOURCE_BASE_URL_LIVE=https://ocw.mit.edu
```

Notice how `MINIO_ROOT_USER` is the same value as `AWS_ACCESS_KEY_ID` and `MINIO_ROOT_PASSWORD` is the same as `AWS_SECRET_ACCESS_KEY`. This is to
ensure that the Minio server is initialized with the same access keys that `ocw-studio` is using. The rest of the AWS bucket name keys are the same
as a standard AWS configuration. the `RESOURCE_BASE_URL` keys are for use with the Concourse container. When using Minio in conjunction with Concourse
and running any of the management commands that upsert pipelines, these values will be used for the `RESOURCE_BASE_URL` env variable when building sites.

In sites that support resource upload, you should be able to upload anything except videos to Google Drive using the RC Google Drive credentials, then
in your site click "Sync w/ Google Drive." If you visit http://localhost:9001 in your web browser, you should be brought to the Minio control panel.
You can log into this with whatever you set `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` to. Inside, you should be able to browse the files you uploaded
to the bucket. Videos are not currently supported locally beacuse of the transcoding service that is normally used with this. The preview and publish
buckets are exposed via nginx locally at http://localhost:8044 and http://localhost:8045 respectively.

In order to complete your local development setup, you will need to follow the instructions below to configure a Concourse Docker container so you
can run pipelines and have them push their output to your Minio S3 buckets. The `OCW_HUGO_THEMES_BRANCH` and `OCW_HUGO_PROJECTS_BRANCH` settings will
control the branch of each of these repos that are pulled down in pipelines that build sites. If you are debugging an issue with a specific branch,
This is where you want to change them before you run a command that pushes up a pipeline like `docker-compose exec web ./manage.py backpopulate_pipelines --filter etc...`

Note that you may also want to set `OCW_STUDIO_DRAFT_URL=https://localhost:8044`and `OCW_STUDIO_LIVE_URL=http://localhost:8045` in your `.env` file
so that the URLs in the publish drawer will point to your Minio published content. If you do this, you will likely need to also set `STATIC_API_BASE_URL_DRAFT=https://draft.ocw.mit.edu`
and `STATIC_API_BASE_URL_LIVE=https://ocw.mit.edu`. Usually the best way to get started getting content into your local instance of `ocw-studio` is to dump
and restore the production database to your local instance. One side effect of doing this is that the `ocw-www` site in production has a bunch of different sites linked
to it via various course lists. When building `ocw-www`, Hugo will attempt to fetch static JSON data related to these linked courses and will encounter errors if it cannot
fetch them. To avoid this, make sure `STATIC_API_BASE_URL_DRAFT` and `STATIC_API_BASE_URL_LIVE` are set as detailed above. If `STATIC_API_BASE_URL` is not set,
it will fall back to `OCW_STUDIO_DRAFT_URL` or `OCW_STUDIO_LIVE_URL` depending on the context of the pipeline. So, if you have this set to a URL where the courses
referenced in your `ocw-www` site's course lists haven't been published, you will have issues.

# Enabling Concourse-CI integration

Concourse-CI integration is enabled by default to create and trigger publishing pipelines, but you
will need to follow some additional steps before it is fully functional.

- Set up Github integration as described above
- Set up a Concourse-CI instance with a team, username, and password
- Add the following to your .env file:

  ```
  AWS_PREVIEW_BUCKET_NAME=<S3 bucket for draft content>
  AWS_PUBLISH_BUCKET_NAME=<S3 bucket for live content>
  GIT_DOMAIN=<root domain for github repos, ie github.com>
  ROOT_WEBSITE_NAME=<Website.name for the website that should be the 'home page'>

  CONCOURSE_URL=<The URL of your Concourse-CI instance>
  CONCOURSE_TEAM=<Concourse-CI team, defaults to "ocw">
  CONCOURSE_USERNAME=<Concourse-CI username>
  CONCOURSE_PASSWORD=<Concourse-CI password>
  CONCOURSE_IS_PRIVATE_REPO=<True if repo is private, False otherwise>
  API_BEARER_TOKEN=<some hard to guess string>
  ```

- Draft and live pipelines should then be created for every new `Website` based on a `WebsiteStarter` with `source=github` and a valid github `path`.
- There are also several management commands for Concourse-CI pipelines:
  - `backpopulate_pipelines`: to create/update pipelines for all or some existing `Websites` (filters available)
  - `trigger_pipelines <version>`: to manually trigger the draft or live pipeline for all or some existing `Websites` (filters available)
- If you wish to disable concourse integration, set `CONTENT_SYNC_PIPELINE_BACKEND=` in your .env file.

### Running a Local Concourse Docker Container

You will need to set the following .env variables for the concourse Docker container:

```python
CONCOURSE_URL=http://concourse:8080
CONCOURSE_PASSWORD=test
CONCOURSE_USERNAME=test
CONCOURSE_TEAM=main
```

When you spin up `ocw-studio` with `docker-compose up`, the Concourse container will come up with everything else.
The concourse UI will be available for login at http://concourse:8080 (You should add `127.0.0.1 concourse` to your hosts file.)
When you create a new website or run one of the various management commands that push pipelines up to Concourse, they will go to
your local instance instead. The pipeline templates with the `-dev` suffix are used when `settings.ENVIRONMENT` is set to "dev."

When you click publish on a site, the pipelines in your local instance of Concourse will be triggered. If you set up Minio as
detailed above, the pipelines will publish their output to your locally-running S3 buckets inside it. As also described above,
you can view the output of your sites at http://localhost:8044 and http://localhost:8045 for draft and live respectively. You will
need to also make sure you run `docker-compose exec web ./manage.py upsert_theme_assets_pipeline` to push up the theme assets
pipeline to your local Concourse instance. You will then need to log into Concourse, unpause the pipeline and start a run of it.
This will place theme assets into the bucket you have configured at `AWS_ARTIFACTS_BUCKET_NAME` that your site pipelines can
reference. If you have already-existing sites that don't have their pipelines pushed up into your local Concourse yet, you will
need to run `docker-compose exec web ./manage.py backpopulate_pipelines` and use the `--filter` or `--filter-json` arguments to
specify the sites to push up pipelines for. The mass build sites pipeline can be pushed up with `docker-compose exec web ./manage.py upsert_mass_build_pipeline`.
Beware that when testing the mass build pipeline locally, you will likely need to limit the amount of sites in your local instance
as using only one dockerized worker publishing the entire OCW site will take a very long time.

### End to end testing of site pipelines

There is a pipeline definition for end to end testing of sites using the `ocw-www` and `ocw-course` starters. It can be run locally in Concourse using the following steps to set it up.

Firstly, there are some environment variables you will want to set:

```
OCW_TEST_SITE_SLUGS=["ocw-ci-test-www", "ocw-ci-test-course"]
AWS_TEST_BUCKET_NAME=ocw-content-test
AWS_OFFLINE_TEST_BUCKET_NAME=ocw-content-offline-test
STATIC_API_BASE_URL_TEST=http://10.1.0.102:8046
```

There are fixtures for two test websites in the `test_site_fixtures` folder. These contain two sites; `ocw-ci-test-www` and `ocw-ci-test-course` along with test content. In `test_websites.json`, the ID's of the `ocw-www` and `ocw-course` starters are referenced. If these ID's are not correct on your system, you can get the ID's of your starters in Django admin and modify the fixture. They can be loaded into the database with the following commands:

```
docker-compose exec web ./manage.py loaddata test_site_fixtures/test_websites.json
docker-compose exec web ./manage.py loaddata test_site_fixtures/test_website_content.json
```

Once the test sites are in your database, you will need to get them up to your Github org. The easiest way to do this is to run the following commands:

```
docker-compose exec web ./manage.py reset_sync_states --filter "ocw-ci-test-www, ocw-ci-test-course" --skip_sync
docker-compose exec web ./manage.py sync_website_to_backend --filter "ocw-ci-test-www, ocw-ci-test-course"
```

At this point, you should be able to see the test sites in your Github org and the content should be on the `main` branch. In order to get the content up into the `release` branch, you will need to click the publish button on both sites:

http://localhost:8043/sites/ocw-ci-test-www
http://localhost:8043/sites/ocw-ci-test-course

Publishing of the sites will fail because of missing fixtures, but that doesn't matter. All you need to run the end to end testing pipelines is for the content to be in the `release` branch in Github. The last prerequisite you need to set up is to load the static assets into Minio:

- Download the contents of this Google Drive folder: https://drive.google.com/drive/folders/14Hlid31Qy7Yy5V4OgHUwNleYUFuJ5BH2?usp=sharing
- Browse to the Minio web UI at http://localhost:9001 and log in with your credentials
- Browse to the `ol-ocw-studio-app` bucket, go to the `courses` folder and create a folder here called `ocw-ci-test-course`
- In this folder, upload the files you downloaded from Google Drive

You are now ready to push up the test pipeline to Concourse, which can be done by running:

```
docker-compose exec web ./manage.py upsert_e2e_test_pipeline --themes-branch main --projects-branch main
```

You can alter the themes branch and projects branches to suit your needs if you are testing a different branch of `ocw-hugo-themes` or `ocw-hugo-projects`. Keep in mind that for any branch of `ocw-hugo-themes` you use, you will need to have built theme assets in Minio. You'll need to run the `upsert_theme_assets` pipeline for that branch and then run it.

You should now have a pipeline in Concourse called `e2e-test-pipeline`. Run this pipeline and it will:

- Pull down all the necessary git repos
- Build the test sites
- Deploy them to Minio
- Run Playwright tests against the output

# Running OCW Studio on Apple Silicon

Currently, the default Docker image for Concourse is not compatible with Apple Silicon. Therefore, run the following command prior to running `docker-compose up`:

```
cp docker-compose-arm64.yml docker-compose.override.yml
```

# Video Workflow

The video workflow for OCW is [described here](/videos/README.md). Note that YouTube integration, Google Drive integration, AWS transcoding, and 3Play integration all need to be set up for the video workflow to work properly. These are described next.

# Enabling YouTube integration

_Note: The steps below describe the process for setting up YouTube integration from scratch. MIT OL Engineers may use YouTube credentials from RC as an acceptable, easier alternative._

- Create a new project at https://console.cloud.google.com/apis/dashboard
  - Save the project ID in your `.env` file as `YT_PROJECT_ID`
- Create an OAuth client ID for the project (type: `Web application`)
  - Add an authorized JavaScript origin (ie `https://<your_domain>/`)
  - Add an authorized redirect URI: `https://<your_domain>/api/youtube-tokens/`
  - You may need to create an oauth consent screen if prompted; make sure to publish it.
  - Save your client ID and client secret in your `.env` file (as `YT_CLIENT_ID` and `YT_CLIENT_SECRET`)
- Enable the YouTube Data API v3 for your project
- Go to `https://<your_domain>/api/youtube-tokens/`.
- You should be prompted to choose a Google account. Choose an account that has upload permissions for your Youtube channel.
- You will then be prompted to choose an account or brand account. Choose whichever is appropriate.
- After clicking through these and allowing any requested permissions, you should be redirected back to an API response containing values for YT_ACCESS_TOKEN and YT_REFRESH_TOKEN. Add these to your .env file.

# Enabling Google Drive integration

With Google Drive integration enabled, a folder on the specified Team Drive will be created for each new website.
The folder will have the same name as the `short_id` of the website. Under this folder will be 3 subfolders:
`files`, `files_final`, `videos_final`. Videos should be uploaded to `videos_final`; everything else should be uploaded
to `files_final`. The `files` folder is just for temporary storage.

If this integration is enabled, manual resource creation and file uploads will no longer be possible. Files must
be uploaded to Google Drive first, and then the "Sync w/Google Drive" button will import and create resources for them.

- Add the following to your .env file:

  ```
  AWS_STORAGE_BUCKET_NAME=The S3 bucket to upload Google Drive files to. Also populate AWS authentication settings.
  DRIVE_SHARED_ID=The id of your Google Team Drive
  DRIVE_SERVICE_ACCOUNT_CREDS=The required Google service account credentials in JSON format.
  DRIVE_UPLOADS_PARENT_FOLDER_ID=Optional, the folder id in the team drive where course folders should go.
  ```

- If your site configuration for resources has a non-standard field name for type, add the following to your .env file:
  ```
  RESOURCE_TYPE_FIELDS=resourcetype,filetype,<your_custom_field_name>
  ```

_Note: MIT OL Engineers may use Google Drive credentials from RC as an alternative to creating their own Google Drive folders._

# Enabling AWS MediaConvert transcoding

The following environment variables need to be defined in your .env file:

```
AWS_ACCOUNT_ID
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_STORAGE_BUCKET_NAME
VIDEO_S3_TRANSCODE_ENDPOINT
AWS_ROLE_NAME
DRIVE_SHARED_ID
DRIVE_SERVICE_ACCOUNT_CREDS
API_BEARER_TOKEN
```

This will allow for videos to be submitted for transcoding to the AWS MediaConvert service. This is done automatically once a video has been synced to Studio from Google Drive.

# Enabling 3Play integration

The following environment variables need to be defined in your .env file (for a pre-configured 3Play account):

```
THREEPLAY_API_KEY
THREEPLAY_CALLBACK_KEY
THREEPLAY_PROJECT_ID
```

# Enabling Open Catalog Search Webhooks

The following environment variables need to be defined in your .env file in order to notify external course catalogs like MIT Open when OCW sites are created/updated.

```
OPEN_CATALOG_URLS=delimited list of api endpoint urls that webhooks should be sent to
OPEN_CATALOG_WEBHOOK_KEY=secret key that will be used to confirm that webhook requests are legitimate
```

# Checking External Resource Availability

This feaature sets up a cron job to validate external resource urls. The workflow for checking external Resource availabity is described [here](/external_resources/README.md).
