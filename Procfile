web: bin/start-nginx bin/start-pgbouncer newrelic-admin run-program uwsgi uwsgi.ini
worker: bin/start-pgbouncer newrelic-admin run-program celery -A main.celery:app worker -B -l $OCW_STUDIO_LOG_LEVEL
extra_worker: bin/start-pgbouncer newrelic-admin run-program celery -A main.celery:app worker -l $OCW_STUDIO_LOG_LEVEL
