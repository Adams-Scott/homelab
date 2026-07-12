import os
import re
import uuid
import datetime
from pathlib import Path

import yaml
from flask import Flask, jsonify, render_template, request, abort

app = Flask(__name__)

BOARDS_DIR = Path(os.environ.get("BOARDS_DIR", "data/boards"))
BOARDS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SECTIONS = ["To Do", "In Progress", "Done"]

ID_RE = re.compile(r"^[a-z0-9\-]+$")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "board"


def board_path(board_id):
    if not ID_RE.match(board_id or ""):
        abort(404)
    return BOARDS_DIR / f"{board_id}.yaml"


def load_board(board_id):
    path = board_path(board_id)
    if not path.exists():
        abort(404, description="Board not found")
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    return data


def save_board(board_id, data):
    path = board_path(board_id)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def new_id():
    return uuid.uuid4().hex[:8]


def make_unique_board_id(name):
    base = slugify(name)
    candidate = base
    i = 2
    while (BOARDS_DIR / f"{candidate}.yaml").exists():
        candidate = f"{base}-{i}"
        i += 1
    return candidate


def board_summary(data):
    sections = data.get("sections", [])
    task_count = sum(len(s.get("tasks", [])) for s in sections)
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "section_count": len(sections),
        "task_count": task_count,
        "updated": data.get("updated"),
        "created": data.get("created"),
    }


def validate_board_payload(data):
    if not isinstance(data, dict):
        abort(400, description="Invalid board payload")
    if "name" not in data or not isinstance(data["name"], str) or not data["name"].strip():
        abort(400, description="Board name is required")
    sections = data.get("sections", [])
    if not isinstance(sections, list):
        abort(400, description="Sections must be a list")
    for section in sections:
        if not isinstance(section, dict):
            abort(400, description="Invalid section")
        if "id" not in section or "name" not in section:
            abort(400, description="Section requires id and name")
        section.setdefault("tasks", [])
        for task in section["tasks"]:
            if not isinstance(task, dict):
                abort(400, description="Invalid task")
            if "id" not in task or "title" not in task:
                abort(400, description="Task requires id and title")
            task.setdefault("description", "")
    return data


# ---------- Page routes ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/board/<board_id>")
def board_page(board_id):
    if not board_path(board_id).exists():
        abort(404)
    return render_template("board.html", board_id=board_id)


# ---------- API routes ----------

@app.route("/api/boards", methods=["GET"])
def api_list_boards():
    boards = []
    for path in sorted(BOARDS_DIR.glob("*.yaml")):
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            boards.append(board_summary(data))
        except Exception:
            continue
    boards.sort(key=lambda b: b.get("updated") or "", reverse=True)
    return jsonify(boards)


@app.route("/api/boards", methods=["POST"])
def api_create_board():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        abort(400, description="Board name is required")

    board_id = make_unique_board_id(name)
    timestamp = now_iso()
    data = {
        "id": board_id,
        "name": name,
        "created": timestamp,
        "updated": timestamp,
        "sections": [
            {"id": new_id(), "name": section_name, "tasks": []}
            for section_name in DEFAULT_SECTIONS
        ],
    }
    save_board(board_id, data)
    return jsonify(data), 201


@app.route("/api/boards/<board_id>", methods=["GET"])
def api_get_board(board_id):
    return jsonify(load_board(board_id))


@app.route("/api/boards/<board_id>", methods=["PUT"])
def api_update_board(board_id):
    existing = load_board(board_id)
    payload = request.get_json(silent=True) or {}
    payload = validate_board_payload(payload)

    payload["id"] = board_id
    payload["created"] = existing.get("created", now_iso())
    payload["updated"] = now_iso()

    save_board(board_id, payload)
    return jsonify(payload)


@app.route("/api/boards/<board_id>", methods=["DELETE"])
def api_delete_board(board_id):
    path = board_path(board_id)
    if not path.exists():
        abort(404)
    path.unlink()
    return jsonify({"deleted": board_id})


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": str(e.description) if hasattr(e, "description") else "Not found"}), 404


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": str(e.description) if hasattr(e, "description") else "Bad request"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
