#!/usr/bin/env bash

# python3 -m venv venv
# source venv/bin/activate
# pip install poetry; poetry install

set -e

mkdir -p docs/docstrings


TAG="${TAG:-main}"

lazydocs \
    --output-path="./docs/docstrings" \
    --overview-file="README.md" \
    --src-base-url="https://github.com/Sindri-Labs/sindri-python/blob/$TAG/" \
    --no-watermark \
    src/sindri/sindri.py


echo "Hosting docs on http://localhost:1111"
mkdocs serve -a localhost:1111
