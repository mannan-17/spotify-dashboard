"""Streamlit dashboard showcasing the owner's "goated" Spotify playlist.

Quick start:
    pip install -r requirements.txt
    cp .env.example .env          # then fill in your app credentials
    python mint_refresh_token.py  # one-time owner login → refresh token
    streamlit run app.py

Visitors never authenticate: the server holds the OWNER's refresh token
and shows the owner's playlists to everyone (Spotify's Feb 2026 dev-mode
rules only serve playlist contents to their owner/collaborators).
"""
from __future__ import annotations

import plotly.express as px
import spotipy
import streamlit as st
from dotenv import load_dotenv

import reccobeats
import spotify_client as sc
import taste

load_dotenv()

PLAYLIST_ID = "59NdHYUwBpNCIjPWrrL2yX"  # the "goated" playlist — the only one shown

# Warm graphic-EQ palette: amber lead, teal/coral/gold supporting.
AMBER = "#F2A93B"
COLORWAY = ["#F2A93B", "#3FB8AF", "#E2574C", "#E8C547", "#8E7DBE", "#5B8C5A", "#D98C5F"]

st.set_page_config(page_title="Playlist Dashboard", page_icon="🎚️", layout="wide")
px.defaults.template = "plotly_dark"
px.defaults.color_discrete_sequence = COLORWAY


def style(fig, height: int = 360):
    """Apply the shared visual theme to a Plotly figure."""
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=46, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color="#EDE7F2", size=13),
        title_font=dict(size=16, color="#FFFFFF"),
        showlegend=False,
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    return fig


@st.cache_resource(show_spinner=False)
def get_spotify():
    """One app-authenticated client, shared across all sessions.

    Safe to share because the token belongs to the APP, not to any user —
    there is no per-user state. cache_resource keeps a single instance
    alive for the whole server process.
    """
    return sc.get_client()


@st.cache_data(ttl=900, show_spinner="Analyzing how the playlist sounds…")
def load_features(playlist_id: str, _df, _sp):
    """Audio features via ReccoBeats; keyed on playlist_id (df mirrors it)."""
    return reccobeats.fetch_features(_sp, _df)


@st.cache_data(ttl=900, show_spinner="Loading playlist from Spotify…")
def load_data(playlist_id: str, _sp):
    meta = _sp.playlist(
        playlist_id,
        fields="name,description,owner.display_name,images,followers.total,external_urls",
    )
    items = sc.fetch_all_playlist_items(_sp, playlist_id)
    df = sc.build_tracks_dataframe(items)
    return meta, df


# --------------------------------------------------------------------------
sp = get_spotify()

try:
    meta, df = load_data(PLAYLIST_ID, sp)
except spotipy.SpotifyException as e:
    st.error(f"Spotify returned an error (HTTP {e.http_status}). Try another playlist.")
    st.stop()

if df.empty:
    st.warning("No playable tracks found in this playlist.")
    st.stop()

# ---- Header --------------------------------------------------------------
head = st.columns([1, 6])
images = meta.get("images") or []
if images:
    head[0].image(images[0]["url"], width=150)
with head[1]:
    st.title(meta.get("name", "Playlist"))
    owner = (meta.get("owner") or {}).get("display_name", "")
    followers = (meta.get("followers") or {}).get("total", 0)
    st.caption(f"by {owner}  ·  {followers:,} followers")

# ---- KPIs ----------------------------------------------------------------
years = df["release_year"].dropna()
year_span = f"{int(years.min())}–{int(years.max())}" if not years.empty else "—"

k = st.columns(5)
k[0].metric("Tracks", f"{len(df)}")
k[1].metric("Artists", f"{df['primary_artist'].nunique()}")
k[2].metric("Albums", f"{df['album'].nunique()}")
k[3].metric("Total time", f"{df['duration_ms'].sum() / 3_600_000:.1f} h")
k[4].metric("Year range", year_span)

st.divider()

# ---- Row 1: artists + genres --------------------------------------------
r1 = st.columns(2)
with r1[0]:
    top_artists = df["primary_artist"].value_counts().head(15).sort_values()
    fig = px.bar(
        x=top_artists.values, y=top_artists.index, orientation="h",
        title="Most-featured artists",
    )
    fig.update_traces(marker_color=AMBER)
    fig.update_layout(xaxis_title="Tracks", yaxis_title="")
    st.plotly_chart(style(fig), use_container_width=True)

with r1[1]:
    # Genre data is no longer served to dev-mode apps, so chart albums instead.
    top_albums = df["album"].value_counts().head(15).sort_values()
    fig = px.bar(x=top_albums.values, y=top_albums.index, orientation="h", title="Top albums")
    fig.update_traces(marker_color="#3FB8AF")
    fig.update_layout(xaxis_title="Tracks", yaxis_title="")
    st.plotly_chart(style(fig), use_container_width=True)

# ---- Row 2: decade + growth ---------------------------------------------
r2 = st.columns(2)
with r2[0]:
    dec = df["decade"].dropna().astype(int)
    if not dec.empty:
        counts = dec.value_counts().sort_index()
        fig = px.bar(x=[f"{d}s" for d in counts.index], y=counts.values, title="Tracks by decade")
        fig.update_traces(marker_color="#E8C547")
        fig.update_layout(xaxis_title="", yaxis_title="Tracks")
        st.plotly_chart(style(fig), use_container_width=True)

with r2[1]:
    growth = df.dropna(subset=["added_at"]).sort_values("added_at").copy()
    if not growth.empty:
        growth["cumulative"] = range(1, len(growth) + 1)
        fig = px.area(growth, x="added_at", y="cumulative", title="Playlist growth over time")
        fig.update_traces(line_color=AMBER, fillcolor="rgba(242,169,59,0.18)")
        fig.update_layout(xaxis_title="", yaxis_title="Tracks")
        st.plotly_chart(style(fig), use_container_width=True)
    else:
        st.info("No 'date added' data available for a growth chart.")

# ---- Row 3: curation activity + duration ---------------------------------
r3 = st.columns(2)
with r3[0]:
    added = df.dropna(subset=["added_at"])
    if not added.empty:
        per_year = added["added_at"].dt.year.value_counts().sort_index()
        fig = px.bar(x=per_year.index.astype(str), y=per_year.values, title="Tracks added per year")
        fig.update_traces(marker_color="#E2574C")
        fig.update_layout(xaxis_title="", yaxis_title="Tracks added")
        st.plotly_chart(style(fig), use_container_width=True)

with r3[1]:
    fig = px.histogram(x=df["duration_min"], nbins=20, title="Track length distribution")
    fig.update_traces(marker_color="#8E7DBE")
    fig.update_layout(xaxis_title="Duration (min)", yaxis_title="Tracks")
    st.plotly_chart(style(fig), use_container_width=True)

st.divider()

# ---- Taste profile (research-inspired, not a personality test) -------------
st.subheader("🧠 Taste profile")
st.caption(
    "Lenses borrowed from the [psychology of music preference]"
    "(https://en.wikipedia.org/wiki/Psychology_of_music_preference) "
    "literature — descriptive stats about this playlist, not a diagnosis."
)

tp = st.columns(4)
tp[0].metric(
    "Diversity", f"{taste.diversity_score(df)}/100",
    help="Normalized Shannon entropy of the artist mix. Research links broad, "
         "even listening with openness to experience.",
)
tp[1].metric(
    "Discovery ratio", f"{taste.discovery_ratio(df)}%",
    help="Share of artists appearing exactly once — a novelty-seeking signal.",
)
tp[2].metric(
    "Loyalty index", f"{taste.loyalty_index(df)}%",
    help="Share of tracks from the top-5 artists. The mere-exposure effect: "
         "familiarity breeds liking.",
)
tp[3].metric(
    "Era spread", f"±{taste.era_spread(df)} yrs",
    help="Standard deviation of release years — how far the playlist roams in time.",
)

fy = st.columns([1, 2])
with fy[0]:
    st.markdown("**Whose formative years?**")
    birth_year = st.number_input(
        "Your birth year", min_value=1930, max_value=2016, value=2003, step=1,
    )
    share, win_lo, win_hi = taste.formative_share(df, int(birth_year))
    st.metric(
        "From your formative years", f"{share}%",
        help=f"Tracks released {win_lo}–{win_hi}, while you were "
             f"{taste.FORMATIVE_START_AGE}–{taste.FORMATIVE_END_AGE}. Research "
             "suggests musical taste crystallizes in that window (the "
             "'reminiscence bump').",
    )
with fy[1]:
    year_counts = df["release_year"].dropna().astype(int).value_counts().sort_index()
    fig = px.bar(x=year_counts.index, y=year_counts.values, title="Tracks by release year")
    fig.update_traces(marker_color="#5B8C5A")
    fig.add_vrect(
        x0=win_lo - 0.5, x1=win_hi + 0.5,
        fillcolor=AMBER, opacity=0.18, line_width=0,
        annotation_text="your formative years", annotation_font_color=AMBER,
    )
    fig.update_layout(xaxis_title="", yaxis_title="Tracks")
    st.plotly_chart(style(fig), use_container_width=True)

st.divider()

# ---- How it sounds (audio features via ReccoBeats) -------------------------
st.subheader("🎭 How it sounds")

try:
    fdf = load_features(PLAYLIST_ID, df, sp)
except Exception:
    fdf = None

analyzed = fdf.dropna(subset=["energy", "valence"]) if fdf is not None else None

if analyzed is None or analyzed.empty:
    st.info(
        "Audio features are temporarily unavailable (the third-party "
        "analysis API didn't respond). The rest of the dashboard is unaffected."
    )
else:
    st.caption(
        f"Audio features for **{len(analyzed)} of {len(fdf)}** tracks, independently "
        "estimated by [ReccoBeats](https://reccobeats.com) — Spotify no longer "
        "provides these, so values are directional, not official."
    )

    sound = st.columns(5)
    sound[0].metric("Energy", f"{analyzed['energy'].mean():.2f}",
                    help="0 = calm, 1 = intense. Playlist average.")
    sound[1].metric("Valence", f"{analyzed['valence'].mean():.2f}",
                    help="Musical positivity: 0 = dark/sad, 1 = euphoric.")
    sound[2].metric("Danceability", f"{analyzed['danceability'].mean():.2f}",
                    help="Rhythmic groove: 0 = free-form, 1 = made for dancing.")
    sound[3].metric("Acousticness", f"{analyzed['acousticness'].mean():.2f}",
                    help="0 = electric/produced, 1 = acoustic.")
    sound[4].metric("Tempo", f"{analyzed['tempo'].mean():.0f} BPM",
                    help="Average beats per minute.")

    # Mood map: Russell's circumplex — valence (x) vs energy (y).
    mood = analyzed.copy()
    mood["quadrant"] = mood.apply(
        lambda r: ("Euphoric" if r["valence"] >= 0.5 else "Aggressive")
        if r["energy"] >= 0.5
        else ("Serene" if r["valence"] >= 0.5 else "Melancholic"),
        axis=1,
    )
    quad_colors = {
        "Euphoric": "#E8C547", "Aggressive": "#E2574C",
        "Melancholic": "#8E7DBE", "Serene": "#3FB8AF",
    }
    counts = mood["quadrant"].value_counts()
    fig = px.scatter(
        mood, x="valence", y="energy", color="quadrant",
        color_discrete_map=quad_colors, hover_name="name",
        hover_data={"primary_artist": True, "quadrant": False,
                    "valence": ":.2f", "energy": ":.2f"},
        title="Mood map — every track by feel",
    )
    fig.update_traces(marker=dict(size=9, opacity=0.85))
    fig.add_hline(y=0.5, line_color="rgba(255,255,255,0.15)", line_dash="dot")
    fig.add_vline(x=0.5, line_color="rgba(255,255,255,0.15)", line_dash="dot")
    for label, (qx, qy) in {
        "Euphoric": (0.97, 0.97), "Aggressive": (0.03, 0.97),
        "Melancholic": (0.03, 0.03), "Serene": (0.97, 0.03),
    }.items():
        fig.add_annotation(
            x=qx, y=qy, text=f"{label} · {counts.get(label, 0)}",
            showarrow=False, font=dict(size=12, color=quad_colors[label]),
            xanchor="right" if qx > 0.5 else "left",
        )
    fig.update_layout(
        xaxis=dict(title="Valence  (sad → happy)", range=[-0.02, 1.02]),
        yaxis=dict(title="Energy  (calm → intense)", range=[-0.02, 1.02]),
        showlegend=False,
    )
    st.plotly_chart(style(fig, height=480), use_container_width=True)

    snd = st.columns(2)
    with snd[0]:
        fig = px.histogram(x=analyzed["tempo"], nbins=25, title="Tempo distribution")
        fig.update_traces(marker_color="#D98C5F")
        fig.update_layout(xaxis_title="BPM", yaxis_title="Tracks")
        st.plotly_chart(style(fig), use_container_width=True)
    with snd[1]:
        unanalyzed = fdf[fdf["energy"].isna()]
        if not unanalyzed.empty:
            st.markdown(f"**Not analyzable yet ({len(unanalyzed)})**")
            st.caption(
                "Not in ReccoBeats' analysis corpus under any pressing — mostly "
                "regional catalog and very new releases. They'll join the mood "
                "map automatically once analyzed upstream."
            )
            st.dataframe(
                unanalyzed[["name", "primary_artist", "release_year"]],
                hide_index=True, use_container_width=True, height=280,
            )

st.divider()

# ---- Tables ---------------------------------------------------------------
cols_show = ["name", "primary_artist", "album", "release_year", "duration_min"]
t1, t2, t3 = st.tabs(["🆕 Recently added", "🕰️ Oldest tracks", "📋 All tracks"])
with t1:
    recent = df.dropna(subset=["added_at"]).sort_values("added_at", ascending=False).head(10).copy()
    recent["added"] = recent["added_at"].dt.date
    st.dataframe(
        recent[["added"] + cols_show],
        hide_index=True, use_container_width=True,
    )
with t2:
    st.dataframe(
        df.dropna(subset=["release_year"]).sort_values("release_year").head(10)[cols_show],
        hide_index=True, use_container_width=True,
    )
with t3:
    st.dataframe(
        df[cols_show + ["explicit"]].sort_values("name"),
        hide_index=True, use_container_width=True,
    )
    st.download_button(
        "⬇ Download as CSV",
        df.drop(columns=["artist_ids"]).to_csv(index=False),
        file_name="playlist.csv", mime="text/csv",
    )
