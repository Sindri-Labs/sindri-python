#!/usr/bin/env bash
mkdir -p docs/docstrings


lazydocs \
    --output-path="./docs/docstrings" \
    --overview-file="README.md" \
    --src-base-url="https://github.com/Sindri-Labs/sindri-python/blob/main/" \
    src/sindri_labs

echo "Hosting docs on http://localhost:1111"
mkdocs serve -a localhost:1111
