"""Audio-features client (ReccoBeats) for the playlist dashboard.

Spotify removed its audio-features endpoints for new apps (Nov 2024), so
the classic nine features (energy, valence, danceability, tempo, ...)
come from ReccoBeats — a free, no-auth API that re-derives them with
open audio-analysis tools, keyed by Spotify track ids. The values are
independent ESTIMATES: directionally comparable to Spotify's originals,
not byte-identical.

Matching is two-pass:
  1. batch lookup by the playlist's own Spotify track ids;
  2. for misses, search Spotify for canonical versions of the same
     recording — accepted only if an artist matches AND the duration is
     within ±7.5 s, so a remix can't impersonate the original.
Anything still unmatched stays NaN and is reported, never guessed.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
import requests
import spotipy

API = "https://api.reccobeats.com/v1/audio-features"
FEATURE_COLS = ["energy", "valence", "danceability", "acousticness", "tempo"]
_DURATION_TOLERANCE_MS = 7500
_BATCH = 40  # ReccoBeats accepts up to 40 ids per request


def _batch_features(track_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Map spotify_id -> feature dict for every id ReccoBeats knows."""
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(track_ids), _BATCH):
        resp = requests.get(
            API, params={"ids": ",".join(track_ids[i : i + _BATCH])}, timeout=20
        )
        resp.raise_for_status()
        for feat in resp.json().get("content", []):
            sid = feat.get("href", "").rsplit("/", 1)[-1]
            if sid:
                out[sid] = feat
    return out


def _canonical_candidates(sp: spotipy.Spotify, row: pd.Series) -> list[str]:
    """Other Spotify ids likely to be the same recording as this track."""
    base = re.sub(r"\s*[\(\[].*?[\)\]]", "", row["name"]).strip()
    ours = {a.lower() for a in row["artists"]}
    queries = dict.fromkeys(
        [f"{row['name']} {row['primary_artist']}", f"{base} {row['primary_artist']}"]
    )
    candidates: list[str] = []
    for query in queries:
        try:
            results = sp.search(query, type="track", limit=5)["tracks"]["items"]
        except spotipy.SpotifyException:
            continue
        for t in results:
            theirs = {a["name"].lower() for a in t["artists"]}
            if (
                t["id"] != row["track_id"]
                and ours & theirs
                and abs(t["duration_ms"] - row["duration_ms"]) <= _DURATION_TOLERANCE_MS
            ):
                candidates.append(t["id"])
        if candidates:
            break
    return candidates


def fetch_features(sp: spotipy.Spotify, df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with FEATURE_COLS added (NaN where unanalyzable)."""
    features = _batch_features(df["track_id"].tolist())

    for _, row in df[~df["track_id"].isin(features)].iterrows():
        candidates = _canonical_candidates(sp, row)
        if not candidates:
            continue
        hits = _batch_features(candidates)
        for cand in candidates:  # keep search-ranking order
            if cand in hits:
                features[row["track_id"]] = hits[cand]
                break

    df = df.copy()
    for col in FEATURE_COLS:
        df[col] = df["track_id"].map(lambda tid: (features.get(tid) or {}).get(col))
    return df
