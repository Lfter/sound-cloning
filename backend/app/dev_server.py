"""Development entrypoint for running the local FastAPI server."""

from __future__ import annotations

import sys


def main() -> None:
    """Start uvicorn with project-local defaults and a friendly dependency hint."""

    try:
        import uvicorn
    except ImportError:
        print("FastAPI runtime is not installed yet.")
        print("Run: python3 -m venv .venv && source .venv/bin/activate")
        print("Then: python -m pip install -r backend/requirements.txt")
        sys.exit(1)

    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8787, reload=False)


if __name__ == "__main__":
    main()
