FROM python:3.12.2
LABEL maintainer "ODL DevOps <mitx-devops@mit.edu>"

# Add package files, install updated node and pip
WORKDIR /tmp

# Install packages and add repo needed for postgres 16.3
COPY apt.txt /tmp/apt.txt
RUN apt-get update
RUN apt-get install -y $(grep -vE "^\s*#" apt.txt  | tr "\n" " ")

# pip
RUN curl --silent --location https://bootstrap.pypa.io/get-pip.py | python3 -

# Add, and run as, non-root user.
RUN mkdir /src
RUN adduser --disabled-password --gecos "" mitodl
RUN mkdir /var/media && chown -R mitodl:mitodl /var/media

# Install Python packages
## Set some poetry config
ENV  \
  POETRY_VERSION=1.5.1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_CACHE_DIR='/tmp/cache/poetry' \
  POETRY_HOME='/home/mitodl/.local' \
  VIRTUAL_ENV="/opt/venv"
ENV PATH="$VIRTUAL_ENV/bin:$POETRY_HOME/bin:$PATH"

COPY pyproject.toml poetry.toml /src/
RUN chown -R mitodl:mitodl /src
RUN mkdir ${VIRTUAL_ENV} && chown -R mitodl:mitodl ${VIRTUAL_ENV}

## Install poetry itself, and pre-create a venv with predictable name
USER mitodl
RUN curl -sSL https://install.python-poetry.org \
  | \
  POETRY_VERSION=${POETRY_VERSION} \
  POETRY_HOME=${POETRY_HOME} \
  python3 -q
WORKDIR /src
RUN python3 -m venv $VIRTUAL_ENV
RUN poetry install

# Add project
USER root
COPY . /src
WORKDIR /src
RUN chown -R mitodl:mitodl /src

RUN apt-get clean && apt-get purge

USER mitodl

EXPOSE 8043
ENV PORT 8043
CMD uwsgi uwsgi.ini
