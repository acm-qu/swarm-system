"""Old entry point, kept so `python hub/server.py ...` still works.

The hub now lives in this package (see hub/__main__.py). Prefer, from the repository folder:
    python -m hub [adduser <name> | token | rotate | --headless]
"""

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from hub.__main__ import main
    main()
