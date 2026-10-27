#!/usr/bin/env bash
# Baked once into the sandbox snapshot; every new thread clones it.
set -euo pipefail

pip install --break-system-packages --quiet \
  pandas==3.1.0 altair==6.3.0 vl-convert-python==1.9.0.post1 statsmodels==0.15.0
mkdir -p /workspace/data /workspace/out
