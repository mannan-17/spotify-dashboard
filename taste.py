"""Research-inspired playlist statistics. Pure pandas/math — no network.

Lenses borrowed from the psychology-of-music-preference literature
(https://en.wikipedia.org/wiki/Psychology_of_music_preference):
diversity/novelty (openness to experience), familiarity (mere-exposure
effect), and the ages 10-25 "reminiscence bump" when taste crystallizes.

These are descriptive stats about ONE playlist — not personality tests.
Most genre-personality correlations in the literature are weak (r < 0.1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FORMATIVE_START_AGE = 10
FORMATIVE_END_AGE = 25


def diversity_score(df: pd.DataFrame) -> float:
    """Normalized Shannon entropy of the artist mix, scaled to 0-100.

    0 = the whole playlist is one artist; 100 = every artist contributes
    equally. Entropy rewards *evenness*, not just artist count: 50 artists
    at ~4 tracks each scores higher than 1 dominant artist plus 49 cameos.
    """
    counts = df["primary_artist"].value_counts()
    if len(counts) <= 1:
        return 0.0
    probs = counts / counts.sum()
    entropy = float(-(probs * np.log(probs)).sum())
    return round(100 * entropy / np.log(len(counts)), 1)


def discovery_ratio(df: pd.DataFrame) -> float:
    """% of artists appearing exactly once — a novelty-seeking signal."""
    counts = df["primary_artist"].value_counts()
    return round(100 * int((counts == 1).sum()) / len(counts), 1)


def loyalty_index(df: pd.DataFrame, top_n: int = 5) -> float:
    """% of tracks from the top_n most-featured artists — familiarity signal."""
    counts = df["primary_artist"].value_counts()
    return round(100 * int(counts.head(top_n).sum()) / len(df), 1)


def era_spread(df: pd.DataFrame) -> float:
    """Standard deviation of release years — how widely the eras range."""
    years = df["release_year"].dropna()
    return round(float(years.std()), 1) if len(years) > 1 else 0.0


def formative_share(df: pd.DataFrame, birth_year: int) -> tuple[float, int, int]:
    """% of tracks released during someone's formative years (ages 10-25).

    Returns (percentage, window_start_year, window_end_year).
    """
    years = df["release_year"].dropna()
    lo = birth_year + FORMATIVE_START_AGE
    hi = birth_year + FORMATIVE_END_AGE
    if years.empty:
        return 0.0, lo, hi
    share = 100 * int(years.between(lo, hi).sum()) / len(years)
    return round(share, 1), lo, hi
