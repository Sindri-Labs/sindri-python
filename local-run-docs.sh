#!/usr/bin/env bash

set -e

mkdir -p docs/docstrings


TAG="${TAG:-main}"

# pip install requests>=2.13.0 lazydocs==0.4.8
lazydocs \
    --output-path="./docs/docstrings" \
    --overview-file="README.md" \
    --src-base-url="https://github.com/Sindri-Labs/sindri-python/blob/$TAG/" \
    --no-watermark \
    src/sindri/sindri.py

# pip install mkdocs mkdocs-awesome-pages-plugin
echo "Hosting docs on http://localhost:1111"
mkdocs serve -a localhost:1111
