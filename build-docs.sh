#!/usr/bin/env bash

### For lazydocs command:
# pip install poetry; poetry install

set -e

mkdir -p docs/docstrings

TAG="${TAG:-main}"

lazydocs \
    --output-path="docs/docstrings" \
    --overview-file="README.md" \
    --src-base-url="https://github.com/Sindri-Labs/sindri-python/blob/$TAG/" \
    --no-watermark \
    src/sindri/sindri.py
