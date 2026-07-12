import os
import sqlite3
import time
import uuid
import threading
import mimetypes
from datetime import datetime, timedelta, timezone

from flask import Flask, request, jsonify, send_file, g, render_template, abort
from werkzeug.utils import secure_filename

DATA_DIR = os.environ.get("DATA_DIR", "/data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "clipboard.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB, generous since this is home use

EXPIRY_OPTIONS = {
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
    "1m": timedelta(days=30),
}


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,             -- 'text' | 'file' | 'image'
            content TEXT,                   -- text content, or NULL for file/image
            filename TEXT,                  -- stored filename on disk, for file/image
            original_name TEXT,             -- original filename, for file/image
            mimetype TEXT,
            size INTEGER,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def purge_expired():
    """Delete expired items (rows + files on disk)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc).isoformat()
    rows = conn.execute(
        "SELECT id, filename FROM items WHERE expires_at <= ?", (now,)
    ).fetchall()
    for row in rows:
        if row["filename"]:
            path = os.path.join(UPLOAD_DIR, row["filename"])
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
    conn.execute("DELETE FROM items WHERE expires_at <= ?", (now,))
    conn.commit()
    conn.close()


def cleanup_loop():
    while True:
        try:
            purge_expired()
        except Exception as e:
            print(f"[cleanup] error: {e}")
        time.sleep(60)


def row_to_dict(row):
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(row["expires_at"])
    seconds_left = max(0, int((expires_at - now).total_seconds()))
    return {
        "id": row["id"],
        "kind": row["kind"],
        "content": row["content"],
        "original_name": row["original_name"],
        "mimetype": row["mimetype"],
        "size": row["size"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "seconds_left": seconds_left,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/items", methods=["GET"])
def list_items():
    purge_expired()
    db = get_db()
    rows = db.execute("SELECT * FROM items ORDER BY created_at DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/items", methods=["POST"])
def create_item():
    expiry = request.form.get("expiry", "1d")
    if expiry not in EXPIRY_OPTIONS:
        return jsonify({"error": "invalid expiry"}), 400

    item_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + EXPIRY_OPTIONS[expiry]

    db = get_db()

    # File or pasted image upload
    if "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        original_name = secure_filename(f.filename) or "upload"
        ext = os.path.splitext(original_name)[1]
        stored_name = f"{item_id}{ext}"
        path = os.path.join(UPLOAD_DIR, stored_name)
        f.save(path)
        size = os.path.getsize(path)
        mimetype = f.mimetype or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        kind = "image" if mimetype.startswith("image/") else "file"

        db.execute(
            """INSERT INTO items (id, kind, content, filename, original_name, mimetype, size, created_at, expires_at)
               VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)""",
            (item_id, kind, stored_name, original_name, mimetype, size,
             created_at.isoformat(), expires_at.isoformat()),
        )
        db.commit()
        return jsonify(row_to_dict(db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()))

    # Plain text
    text = request.form.get("text", "").strip()
    if text:
        db.execute(
            """INSERT INTO items (id, kind, content, filename, original_name, mimetype, size, created_at, expires_at)
               VALUES (?, 'text', ?, NULL, NULL, NULL, NULL, ?, ?)""",
            (item_id, text, created_at.isoformat(), expires_at.isoformat()),
        )
        db.commit()
        return jsonify(row_to_dict(db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()))

    return jsonify({"error": "no content provided"}), 400


@app.route("/api/items/<item_id>/download")
def download_item(item_id):
    db = get_db()
    row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None or not row["filename"]:
        abort(404)
    path = os.path.join(UPLOAD_DIR, row["filename"])
    if not os.path.exists(path):
        abort(404)
    # Images render inline so they can be previewed; other files download.
    as_attachment = row["kind"] != "image"
    return send_file(
        path,
        mimetype=row["mimetype"],
        as_attachment=as_attachment,
        download_name=row["original_name"],
    )


@app.route("/api/items/<item_id>", methods=["DELETE"])
def delete_item(item_id):
    db = get_db()
    row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    if row["filename"]:
        path = os.path.join(UPLOAD_DIR, row["filename"])
        if os.path.exists(path):
            os.remove(path)
    db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()
    return jsonify({"ok": True})


init_db()
threading.Thread(target=cleanup_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
