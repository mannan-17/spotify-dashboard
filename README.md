# 🎚️ Spotify Playlist Dashboard

A Streamlit dashboard that showcases a single curated Spotify playlist to
anyone with the link — visitors never log in. It renders charts for artists,
albums, release decades, track length, curation activity, and growth over
time. (The playlist ID is set at the top of `app.py`.)

## How it works (and why)

Spotify's **February 2026** dev-mode rules shaped this design:

- Playlist **contents** are only served for playlists the authenticated user
  **owns or collaborates on** — so "paste any playlist" apps are no longer
  possible for indie apps.
- App-level tokens (client-credentials flow) can't read playlist items at all.
- Per-user login is capped at 25 manually-allowlisted users.

So this app uses the **curator-showcase** pattern: the owner authorizes once
(`mint_refresh_token.py`), the long-lived **refresh token** is stored as a
server secret, and the server reads the owner's playlist on every visitor's
behalf. Unlimited visitors, zero logins, read-only playlist scopes.

> Also due to dev-mode limits: artist **genre** and track **popularity**
> data are no longer returned at all (the dashboard charts top albums and
> curation activity instead), and audio features (danceability/energy/tempo)
> remain deprecated since Nov 2024.

## What it shows

- **KPIs** — track count, unique artists/albums, total runtime, year range
- **Most-featured artists** and **top albums**
- **Tracks by decade** and a **growth-over-time** chart (from "date added")
- **Curation activity** (tracks added per year) and **track-length** distribution
- **🧠 Taste profile** — research-inspired stats (artist diversity, discovery
  ratio, loyalty, era spread) plus an interactive **formative-years** checker:
  enter a birth year and see how much of the playlist lands in the ages 10–25
  "reminiscence bump" window ([background](https://en.wikipedia.org/wiki/Psychology_of_music_preference))
- Sortable tables (recently added, oldest, all tracks) with **CSV export**

## Setup

You need a **Spotify Premium** account (required for new dev-mode apps).

### 1. Create a Spotify app (once)
1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) → **Create app**.
2. Register redirect URI exactly: `http://127.0.0.1:8501`
   (only used during the one-time token mint below).
3. **Settings** → copy your **Client ID** and **Client secret**.

### 2. Configure, authorize once, run
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then edit .env with your ID/secret
python mint_refresh_token.py     # browser opens; click Agree — token saved to .env
streamlit run app.py
```

## Deploy to Streamlit Community Cloud (free)

1. Push this repo to GitHub — **private repos work**; you grant Streamlit's
   GitHub app read access during setup. `.gitignore` keeps `.env` out of git.
2. At [share.streamlit.io](https://share.streamlit.io): **Create app** → pick
   this repo + `app.py`.
3. App **Settings → Secrets** (TOML format):
   ```toml
   SPOTIPY_CLIENT_ID = "your_client_id"
   SPOTIPY_CLIENT_SECRET = "your_client_secret"
   SPOTIPY_REFRESH_TOKEN = "printed by mint_refresh_token.py"
   ```
4. Deploy and share the `https://….streamlit.app` URL.

To revoke the token ever: [spotify.com/account/apps](https://www.spotify.com/account/apps/) → remove access, then re-run the mint script.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI and charts |
| `spotify_client.py` | Owner-token auth + data fetching/transforms |
| `mint_refresh_token.py` | One-time owner authorization script |
| `.streamlit/config.toml` | Theme |
| `.env.example` | Credential template |
