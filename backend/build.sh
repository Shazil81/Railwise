#!/usr/bin/env bash
set -euo pipefail
pip install -r requirements-production.txt
python manage.py collectstatic --noinput
