#!/bin/bash

NAME="ts_air_cargo"
DJANGODIR="/var/www/ts_air_cargo"
SOCKFILE="/var/www/ts_air_cargo/run/gunicorn.sock"
USER="www-data"
GROUP="www-data"
NUM_WORKERS=3
DJANGO_SETTINGS_MODULE="ts_air_cargo.settings"
DJANGO_WSGI_MODULE="ts_air_cargo.wsgi"

echo "Starting $NAME as `whoami`"

# Activate the virtual environment
cd $DJANGODIR
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

# Create the run directory if it doesn't exist
RUNDIR=$(dirname $SOCKFILE)
test -d $RUNDIR || mkdir -p $RUNDIR

# Start your Django Gunicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
exec venv/bin/gunicorn ${DJANGO_WSGI_MODULE}:application \
  --name $NAME \
  --workers $NUM_WORKERS \
  --user=$USER --group=$GROUP \
  --bind=unix:$SOCKFILE \
  --log-level=info \
  --log-file=-
