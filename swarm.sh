#!/usr/bin/env bash
# Mac/Linux launcher for the Swarm Hub:
#   ./swarm.sh setup              install the hub's packages (once) and create your login
#   ./swarm.sh                    start the hub
#   ./swarm.sh adduser <name>     any other hub command (token, rotate, --headless, ...)
set -e
cd "$(dirname "$0")"

PY=""
for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
        PY="$c"; break
    fi
done
if [ -z "$PY" ]; then
    echo "Python 3.9 or newer wasn't found. Install it from https://www.python.org/downloads/ and run this again."
    exit 1
fi

if [ "$1" = "setup" ]; then
    echo "Using $(command -v "$PY")"
    if ! "$PY" -m pip install --user --disable-pip-version-check --no-warn-script-location -r hub/requirements.txt; then
        echo "Installing the packages failed (see above). If pip says the environment is"
        echo "\"externally managed\", run:  $PY -m pip install --user --break-system-packages -r hub/requirements.txt"
        exit 1
    fi
    if [ ! -f data/users.json ]; then
        read -r -p "Pick a username for your hub login: " name
        "$PY" -m hub adduser "$name"
    fi
    echo "Ready. Start the hub with:  ./swarm.sh"
    exit 0
fi

exec "$PY" -m hub "$@"
