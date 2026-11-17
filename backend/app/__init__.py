from pathlib import Path

from dotenv import load_dotenv

# Secrets live in backend/.env (gitignored); real env vars still win.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
