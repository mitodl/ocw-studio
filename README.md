# ocw_studio
OCW Studio manages deployments for OCW courses.

**SECTIONS**
1. [Initial Setup](#initial-setup)
1. [Testing and Formatting](#testing-and-formatting)
1. [Importing OCW course sites](#importing-ocw-course-sites)


# Initial Setup

ocw_studio follows the same [initial setup steps outlined in the common ODL web app guide](https://github.com/mitodl/handbook/blob/master/common-web-app-guide.md).
Run through those steps **including the addition of `/etc/hosts` aliases and the optional step for running the
`createsuperuser` command**.

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


# Defining starter projects locally

OCW Studio in production will make use of separate Github repos as starter projects, and those starter projects will
define a site config. To simplify development, you can create some mock starter repos locally. 
See [localdev/starters](localdev/starters/) for instructions.  
