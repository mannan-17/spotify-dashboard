"""One-time setup: log in as the playlist owner and store a refresh token.

Run this ONCE on your own machine:

    python mint_refresh_token.py

It opens a browser for the Spotify consent screen, captures the redirect on
http://127.0.0.1:8501 (make sure that exact URI is registered in your app's
settings on the Spotify Developer Dashboard, and that nothing else is using
port 8501 while this runs), then:

  1. writes SPOTIPY_REFRESH_TOKEN into your local .env, and
  2. prints the line to paste into Streamlit Cloud's Settings → Secrets.

The deployed app uses this token to read YOUR playlists on visitors' behalf —
visitors themselves never log in. The token only carries read-only playlist
scopes, and it can be revoked anytime at https://www.spotify.com/account/apps/
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyOAuth

from spotify_client import SCOPE

ENV_PATH = Path(__file__).parent / ".env"


def main() -> None:
    load_dotenv(ENV_PATH)
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("Set SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET in .env first.")

    oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8501"),
        scope=SCOPE,
        cache_handler=MemoryCacheHandler(),  # keep the token out of files
        open_browser=True,
    )

    # Opens the browser, runs a tiny local server to catch the redirect,
    # and exchanges the ?code=... for tokens.
    token_info = oauth.get_access_token(as_dict=True)
    refresh_token = token_info["refresh_token"]

    # Update or append SPOTIPY_REFRESH_TOKEN in .env
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    lines = [l for l in lines if not l.startswith("SPOTIPY_REFRESH_TOKEN=")]
    lines.append(f"SPOTIPY_REFRESH_TOKEN={refresh_token}")
    ENV_PATH.write_text("\n".join(lines) + "\n")

    print("\n✅ Saved SPOTIPY_REFRESH_TOKEN to .env")
    print("\nFor Streamlit Cloud, add this line under Settings → Secrets:")
    print(f'\nSPOTIPY_REFRESH_TOKEN = "{refresh_token}"\n')


if __name__ == "__main__":
    main()
