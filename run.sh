#!/bin/bash

# Use variables from .env file
if [ -f .env ] ; then
  set -o allexport
  source .env
  set +o allexport
fi

python3 main.py --config data/config.ini