#!/usr/bin/env bash
mkdir -p docs/docstrings

# pip install requests>=2.13.0 lazydocs
lazydocs \
    --output-path="./docs/docstrings" \
    --overview-file="README.md" \
    --src-base-url="https://github.com/Sindri-Labs/sindri-python/blob/main/" \
    --no-watermark \
    src/sindri_labs

# pip install mkdocs mkdocs-awesome-pages-plugin
echo "Hosting docs on http://localhost:1111"
mkdocs serve -a localhost:1111
