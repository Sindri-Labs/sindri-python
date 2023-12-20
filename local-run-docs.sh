#!/usr/bin/env bash
mkdir -p docs/docstrings

set -e

# pip install lazydocs
lazydocs \
    --output-path="./docs/docstrings" \
    --overview-file="README.md" \
    --src-base-url="https://github.com/Sindri-Labs/sindri-python/blob/main/" \
    --no-watermark \
    src/sindri_labs

# Transform markdown to jsx syntax so it can be rendered in Docusaurus
python3 _transform_md_to_jsx.py

# pip install mkdocs mkdocs-awesome-pages-plugin
echo "Hosting docs on http://localhost:1111"
mkdocs serve -a localhost:1111
