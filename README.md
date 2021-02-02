# ocw_studio
OCW Studio manages deployments for OCW courses.

**SECTIONS**
1. [Initial Setup](#initial-setup)
1. [Optional Setup](#optional-setup)
1. [Running Tests](#running-tests)

# Initial Setup

ocw_studio follows the same [initial setup steps outlined in the common ODL web app guide](https://github.com/mitodl/handbook/blob/master/common-web-app-guide.md).
Run through those steps **including the addition of `/etc/hosts` aliases and the optional step for running the
`createsuperuser` command**.

# Optional Setup

Described below are some setup steps that are not strictly necessary
for running the app

# Running tests

*NOTE: These commands can be run with ```docker-compose exec``` to execute them
in an already-running container, or with ```docker-compose run --rm``` to
execute them in a new container.*

## Python Tests/Linting


To run Python tests:

```sh
docker-compose run --rm web pytest
```

To run Python tests in a single file:

```sh
docker-compose run --rm web pytest /path/to/test.py
```

To run Python test cases in a single file that match some function/class name:

```sh
docker-compose run --rm web pytest /path/to/test.py -k test_some_logic
```

To run the Python linter:

```sh
docker-compose run --rm web pylint
```

## Python Formatting

We use [black](https://github.com/psf/black) to format our Python code.

To format all python files:

```sh
docker-compose run --rm web black .
```

To format a specific file:

```sh
docker-compose run --rm web black /path/to/file.py
```

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

# Running the app in a notebook

This repo includes a config for running a [Jupyter notebook](https://jupyter.org/) in a
Docker container. This enables you to do in a Jupyter notebook anything you might
otherwise do in a Django shell. To get started:

- Copy the example file
    ```bash
    # Choose any name for the resulting .ipynb file
    cp localdev/app.ipynb.example localdev/app.ipynb
    ```
- Build the `notebook` container _(for first time use, or when requirements change)_
    ```bash
    docker-compose -f docker-compose-notebook.yml build
    ```
- Run all the standard containers (`docker-compose up`)
- In another terminal window, run the `notebook` container
    ```bash
    docker-compose -f docker-compose-notebook.yml run --rm --service-ports notebook
    ```
- Visit the running notebook server in your browser. The `notebook` container log output will
  indicate the URL and `token` param with some output that looks like this:
    ```
    notebook_1  |     To access the notebook, open this file in a browser:
    notebook_1  |         file:///home/mitodl/.local/share/jupyter/runtime/nbserver-8-open.html
    notebook_1  |     Or copy and paste one of these URLs:
    notebook_1  |         http://(2c19429d04d0 or 127.0.0.1):8080/?token=2566e5cbcd723e47bdb1b058398d6bb9fbf7a31397e752ea
    ```
  Here is a one-line command that will produce a browser-ready URL from that output. Run this in a separate terminal:
    ```bash
    docker logs $(docker ps --format '{{.Names}}' | grep "_notebook_run_") | grep -E "http://(.*):8080[^ ]+\w" | tail -1 | sed -e 's/^[[:space:] or]*//'
    ```
  OSX users can pipe that output to `xargs open` to open a browser window directly with the URL from that command.
- Navigate to the `.ipynb` file that you created and click it to run the notebook
- Execute the first block to confirm it's working properly (click inside the block
  and press Shift+Enter)

From there, you should be able to run code snippets with a live Django app just like you
would in a Django shell.


# Commits

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
