#!/bin/bash
mkdir -p /tmp/Alii;
cp ~/Alii/venv/* /tmp/Alii/
mv /tmp/Alii/venv /opt/
export PYTHONPATH=\$PYTHONPATH:\$OPT/
