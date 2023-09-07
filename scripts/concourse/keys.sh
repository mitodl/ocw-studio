#!/bin/bash

ssh-keygen -t rsa -b 4096 -m PEM -f /concourse-keys/session_signing_key -q -N "" <<<$'ny' >/dev/null 2>&1
ssh-keygen -t rsa -b 4096 -m PEM -f /concourse-keys/tsa_host_key -q -N "" <<<$'ny' >/dev/null 2>&1
ssh-keygen -t rsa -b 4096 -m PEM -f /concourse-keys/worker_key -q -N "" <<<$'ny' >/dev/null 2>&1
cp /concourse-keys/worker_key.pub /concourse-keys/authorized_worker_keys
chmod 600 /concourse-keys/authorized_worker_keys
