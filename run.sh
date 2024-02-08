#!/bin/bash

# Use variables from .env file
if [ -f .env ] ; then
  set -o allexport
  source .env
  set +o allexport
fi

. .venv/bin/activate && python main.py --config config.ini
