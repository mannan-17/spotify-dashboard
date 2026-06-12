"""Spotify auth + data-fetching helpers for the playlist dashboard.

All network access goes through here so app.py stays focused on the UI.

Auth model ("curator showcase"): the playlist OWNER authorizes once via
mint_refresh_token.py; the resulting refresh token is stored as a secret.
The server uses it to read the owner's playlists — visitors never log in.
This is the only shape Spotify's Feb 2026 dev-mode rules allow for a public
app: playlist contents are only served for playlists the authenticated
user owns or collaborates on, and client-credentials tokens can't read
playlist items at all.

Audio-features / recommendations endpoints are intentionally NOT used:
Spotify deprecated them in Nov 2024 for apps created after that date.
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import spotipy
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyOAuth

# Read-only access to the owner's playlists. Deliberately minimal: the
# refresh token lives on the server, so grant it nothing it doesn't need.
SCOPE = "playlist-read-private playlist-read-collaborative"


def get_client() -> spotipy.Spotify:
    """Build a Spotify client authenticated as the playlist owner.

    Exchanges the long-lived SPOTIPY_REFRESH_TOKEN for a fresh access token
    at startup; spotipy then auto-renews it (hourly) via the auth_manager
    for as long as the process lives.
    """
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    refresh_token = os.getenv("SPOTIPY_REFRESH_TOKEN")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing Spotify credentials. Locally: copy .env.example to .env "
            "and set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET. On Streamlit "
            "Cloud: add both under the app's Settings → Secrets."
        )
    if not refresh_token:
        raise RuntimeError(
            "Missing SPOTIPY_REFRESH_TOKEN. Run `python mint_refresh_token.py` "
            "once on your machine to authorize and store it."
        )

    oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8501"),
        scope=SCOPE,
        cache_handler=MemoryCacheHandler(),
    )
    # Mint an access token now; spotipy caches it (with the refresh token)
    # in the MemoryCacheHandler and silently refreshes on expiry.
    oauth.refresh_access_token(refresh_token)
    return spotipy.Spotify(auth_manager=oauth, retries=3, status_retries=3)


def fetch_all_playlist_items(sp: spotipy.Spotify, playlist_id: str) -> list[dict[str, Any]]:
    """Page through every track in a playlist (handles playlists >100 tracks)."""
    items: list[dict[str, Any]] = []
    results = sp.playlist_items(playlist_id, additional_types=("track",), limit=100)
    items.extend(results["items"])
    while results.get("next"):
        results = sp.next(results)
        items.extend(results["items"])
    return items


def _release_year(release_date: str | None) -> int | None:
    """Spotify release_date may be 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD'."""
    if not release_date:
        return None
    head = release_date.split("-")[0]
    return int(head) if head.isdigit() else None


def build_tracks_dataframe(items: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten raw playlist items into a tidy dataframe, skipping non-tracks."""
    rows: list[dict[str, Any]] = []
    for item in items:
        # Feb 2026 API nests the track under "item"; older responses used "track".
        track = item.get("item") or item.get("track")
        # Skip removed tracks, local files without metadata, and podcast episodes.
        if not track or track.get("type") != "track" or not track.get("id"):
            continue

        artists = track.get("artists", []) or []
        artist_names = [a.get("name", "") for a in artists]
        artist_ids = [a.get("id") for a in artists if a.get("id")]
        album = track.get("album", {}) or {}
        year = _release_year(album.get("release_date"))
        duration_ms = track.get("duration_ms", 0) or 0

        rows.append(
            {
                "track_id": track["id"],
                "name": track.get("name", ""),
                "artists": artist_names,
                "primary_artist": artist_names[0] if artist_names else "",
                "artist_ids": artist_ids,
                "album": album.get("name", ""),
                "release_date": album.get("release_date"),
                "release_year": year,
                "decade": (year // 10 * 10) if year else None,
                "duration_ms": duration_ms,
                "duration_min": round(duration_ms / 60000, 2),
                "explicit": bool(track.get("explicit")),
                "added_at": item.get("added_at"),
                "url": (track.get("external_urls", {}) or {}).get("spotify", ""),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df["added_at"] = pd.to_datetime(df["added_at"], errors="coerce", utc=True)
    return df


# NOTE: genre and popularity data are gone for dev-mode apps (verified
# empirically, June 2026): the artist object no longer includes "genres",
# and "popularity" is absent from both playlist items and the single-track
# endpoint. The dashboard charts top albums and curation activity instead.
