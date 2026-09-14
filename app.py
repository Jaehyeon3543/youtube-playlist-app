import re
import sqlite3
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, g, jsonify, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "playlist.db"

# 장르(카테고리) 목록 - key는 URL/DB에 저장되는 값, label은 화면 표시용
GENRES = [
    {"key": "kpop", "label": "K-POP"},
    {"key": "pop", "label": "Pop"},
    {"key": "rock", "label": "Rock"},
    {"key": "hiphop", "label": "Hip-Hop"},
    {"key": "rnb", "label": "R&B / Soul"},
    {"key": "ballad", "label": "발라드"},
    {"key": "edm", "label": "EDM"},
    {"key": "jazz", "label": "Jazz"},
    {"key": "classical", "label": "Classical"},
    {"key": "indie", "label": "Indie"},
    {"key": "ost", "label": "OST"},
    {"key": "lofi", "label": "Lo-fi"},
    {"key": "etc", "label": "기타"},
]
GENRE_MAP = {g["key"]: g["label"] for g in GENRES}

YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)

app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                video_id TEXT NOT NULL,
                genre TEXT NOT NULL,
                created_at TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                is_favorite INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(songs)")}
        if "position" not in columns:
            db.execute("ALTER TABLE songs ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
        if "is_favorite" not in columns:
            db.execute("ALTER TABLE songs ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0")

        # 기존 데이터(마이그레이션 이전에 추가된 곡)에 순서 값을 채워준다.
        rows = db.execute(
            "SELECT id FROM songs WHERE position = 0 ORDER BY created_at ASC, id ASC"
        ).fetchall()
        for position, row in enumerate(rows, start=1):
            db.execute("UPDATE songs SET position = ? WHERE id = ?", (position, row[0]))
        db.commit()


def next_position(db, genre_key):
    row = db.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 FROM songs WHERE genre = ?", (genre_key,)
    ).fetchone()
    return row[0]


def extract_video_id(url: str) -> str | None:
    match = YOUTUBE_ID_RE.search(url.strip())
    return match.group(1) if match else None


def fetch_youtube_title(video_id: str) -> str:
    try:
        resp = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json().get("title", "")
    except requests.RequestException:
        return ""


@app.context_processor
def inject_globals():
    return {"genres": GENRES}


@app.route("/")
def index():
    db = get_db()
    rows = db.execute(
        "SELECT genre, COUNT(*) AS cnt FROM songs GROUP BY genre"
    ).fetchall()
    counts = {row["genre"]: row["cnt"] for row in rows}
    total = sum(counts.values())
    return render_template("index.html", counts=counts, total=total)


@app.route("/genre/<genre_key>")
def genre_view(genre_key):
    if genre_key not in GENRE_MAP:
        return redirect(url_for("index"))
    db = get_db()
    songs = db.execute(
        "SELECT * FROM songs WHERE genre = ? ORDER BY position ASC",
        (genre_key,),
    ).fetchall()
    return render_template(
        "category.html",
        genre_key=genre_key,
        genre_label=GENRE_MAP[genre_key],
        songs=songs,
    )


@app.route("/favorites")
def favorites_view():
    db = get_db()
    songs = db.execute(
        "SELECT * FROM songs WHERE is_favorite = 1 ORDER BY genre ASC, position ASC"
    ).fetchall()
    return render_template(
        "category.html",
        genre_key=None,
        genre_label="즐겨찾기",
        songs=songs,
    )


@app.route("/add", methods=["POST"])
def add_song():
    title = request.form.get("title", "").strip()
    url = request.form.get("url", "").strip()
    genre_key = request.form.get("genre", "").strip()

    video_id = extract_video_id(url)
    if not title and video_id:
        title = fetch_youtube_title(video_id)

    if title and video_id and genre_key in GENRE_MAP:
        db = get_db()
        db.execute(
            "INSERT INTO songs (title, video_id, genre, created_at, position) VALUES (?, ?, ?, ?, ?)",
            (
                title,
                video_id,
                genre_key,
                datetime.now().isoformat(timespec="seconds"),
                next_position(db, genre_key),
            ),
        )
        db.commit()

    return redirect(url_for("genre_view", genre_key=genre_key or "etc"))


@app.route("/song/<int:song_id>/edit", methods=["GET", "POST"])
def edit_song(song_id):
    db = get_db()
    song = db.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone()
    if song is None:
        return redirect(url_for("index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        url = request.form.get("url", "").strip()
        genre_key = request.form.get("genre", "").strip()
        video_id = extract_video_id(url)

        if title and video_id and genre_key in GENRE_MAP:
            position = (
                next_position(db, genre_key) if genre_key != song["genre"] else song["position"]
            )
            db.execute(
                "UPDATE songs SET title = ?, video_id = ?, genre = ?, position = ? WHERE id = ?",
                (title, video_id, genre_key, position, song_id),
            )
            db.commit()
            return redirect(url_for("genre_view", genre_key=genre_key))

    return render_template("edit.html", song=song, genre_key=song["genre"])


@app.route("/genre/<genre_key>/reorder", methods=["POST"])
def reorder_songs(genre_key):
    if genre_key not in GENRE_MAP:
        return jsonify({"error": "invalid genre"}), 400

    order = (request.get_json(silent=True) or {}).get("order", [])
    db = get_db()
    for position, song_id in enumerate(order, start=1):
        db.execute(
            "UPDATE songs SET position = ? WHERE id = ? AND genre = ?",
            (position, song_id, genre_key),
        )
    db.commit()
    return jsonify({"status": "ok"})


@app.route("/song/<int:song_id>/favorite", methods=["POST"])
def toggle_favorite(song_id):
    db = get_db()
    song = db.execute("SELECT is_favorite FROM songs WHERE id = ?", (song_id,)).fetchone()
    if song is None:
        return jsonify({"error": "not found"}), 404

    new_value = 0 if song["is_favorite"] else 1
    db.execute("UPDATE songs SET is_favorite = ? WHERE id = ?", (new_value, song_id))
    db.commit()
    return jsonify({"is_favorite": bool(new_value)})


@app.route("/api/youtube-title")
def youtube_title():
    video_id = extract_video_id(request.args.get("url", ""))
    if not video_id:
        return jsonify({"error": "invalid url"}), 400

    title = fetch_youtube_title(video_id)
    if not title:
        return jsonify({"error": "lookup failed"}), 502

    return jsonify({"title": title})


@app.route("/delete/<int:song_id>", methods=["POST"])
def delete_song(song_id):
    db = get_db()
    row = db.execute("SELECT genre FROM songs WHERE id = ?", (song_id,)).fetchone()
    db.execute("DELETE FROM songs WHERE id = ?", (song_id,))
    db.commit()
    genre_key = row["genre"] if row else "etc"
    return redirect(url_for("genre_view", genre_key=genre_key))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
