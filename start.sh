#!/usr/bin/env bash
set -euo pipefail
# Use the repository venv if present, otherwise fallback to system python3
VENV_PY=".venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
	echo "VENV python not found at $VENV_PY - falling back to system python3"
	VENV_PY="$(command -v python3 || true)"
fi

echo "Using python: $($VENV_PY -c 'import sys; print(sys.executable)')"
echo "PYTHON VERSION: $($VENV_PY -V 2>&1)"
# Ensure setuptools/wheel are installed into the venv FIRST
$VENV_PY -m pip install --upgrade --force-reinstall setuptools wheel
$VENV_PY -m pip show setuptools || true
# Print sys.path AFTER installation
$VENV_PY - <<'PY'
import sys
print('SYS.PATH:')
print('\n'.join(sys.path))
PY

# Test if app imports without error
echo "Testing app import..."
$VENV_PY -c "import app; print('App imported successfully')" || { echo "App import failed"; exit 1; }
echo "Starting Gunicorn using $VENV_PY"
exec "$VENV_PY" -m gunicorn app:app --bind 0.0.0.0:$PORT
