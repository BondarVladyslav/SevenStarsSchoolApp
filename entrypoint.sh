#!/bin/sh
set -e

chown -R appuser:appuser /app/staticfiles 2>/dev/null || true
chown -R appuser:appuser /app/media 2>/dev/null || true

gosu appuser python manage.py collectstatic --noinput
gosu appuser python manage.py migrate --noinput

exec gosu appuser "$@"