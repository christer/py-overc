#!/bin/sh

# This script do
# 1. create a virtualenv in the current directory.
# 2. install needed dependencies in it.
# 3. run the overc server using a sqlite database stored in the virtualenv.
#
# Dependencies:
# - python 2.?
# - virtualenv
#
# You need to stand in the same directory as this file for this script to work.

set -e

export OVERC_CONFIG=misc/quickstart_server.ini

VE=quickstart_server.ve
if [[ ! -d $VE ]]; then
    virtualenv -p $(which python2) $VE
fi
$VE/bin/pip install --quiet flask sqlalchemy .

export PYTHONPATH=$(pwd):$PYTHONPATH
exec $VE/bin/python -m werkzeug.serving -b 0.0.0.0:5000 overc.wsgi:app
