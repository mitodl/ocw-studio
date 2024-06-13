web: bin/start-nginx bin/start-pgbouncer newrelic-admin run-program uwsgi uwsgi.ini
worker: bin/start-pgbouncer newrelic-admin run-program celery -E -A main.celery:app worker -Q publish,batch,default -B -l $OCW_STUDIO_LOG_LEVEL
extra_worker: bin/start-pgbouncer newrelic-admin run-program celery -E -A main.celery:app worker -Q publish,batch,default -l $OCW_STUDIO_LOG_LEVEL
