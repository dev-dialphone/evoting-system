#!/bin/bash
cd "$(dirname "$0")"
export PYTHONPATH=/usr/local/lib/python3.11/dist-packages:$PYTHONPATH
/usr/bin/python3.11 app.py
