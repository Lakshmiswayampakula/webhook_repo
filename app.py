"""
Gunicorn entrypoint for Render.

Render start command shown in logs: `gunicorn app:app`
So this file must expose a module-level variable named `app`.
"""

from app import create_app

app = create_app()

