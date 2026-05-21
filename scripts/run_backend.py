"""Small compatibility entrypoint for launching the backend module."""

from backend.app.dev_server import main

# Keep this wrapper tiny so shell scripts can target one stable path.
if __name__ == "__main__":
    main()
