release: bash scripts/heroku-release-phase.sh
web: bin/start-nginx bin/start-pgbouncer uwsgi uwsgi.ini
worker: bin/start-pgbouncer celery -A main.celery:app worker -E -Q publish,batch,default -B -l $OCW_STUDIO_LOG_LEVEL
extra_worker: bin/start-pgbouncer celery -A main.celery:app worker -E -Q publish,batch,default -l $OCW_STUDIO_LOG_LEVEL
