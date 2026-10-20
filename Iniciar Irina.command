#!/bin/zsh
# Abra este arquivo com duplo clique no macOS.
cd -- "$(dirname -- "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv || exit 1
fi
if ! .venv/bin/python -c 'import numpy, cv2, pygame' >/dev/null 2>&1; then
    .venv/bin/python -m pip install -r requirements.txt || exit 1
fi
exec .venv/bin/python main.py "$@"
