#!/bin/bash

# File formatters
echo ""
echo "(python) black..."
black .


echo ""
echo "(python) isort..."
isort --overwrite-in-place .

# Analyze code and report errors
echo ""
echo "(python) flake8..."
flake8 .

echo ""
echo "(python) mypy..."
mypy .

