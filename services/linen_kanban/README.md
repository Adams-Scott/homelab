# Linen Kanban

A simple, self-hosted kanban board app. Python (Flask) backend, boards stored as
plain YAML files on disk, drag-and-drop UI, no database, no auth (built for local/LAN use).

## Features

- Home screen listing all boards, with quick create
- Each board is a single YAML file under `data/boards/`
- Custom sections per board — add, rename, delete, reorder (drag)
- Tasks — add, edit, delete, and drag between sections
- Boards are addressable by URL: `/board/<board-id>`
- Autosaves shortly after any change (see the status text next to the board title)

## Run with Docker Compose (recommended)

```bash
docker compose up -d --build
```

Then open **http://localhost:8420**.

Boards are persisted to `./data/boards/*.yaml` on the host via a bind mount, so
they survive container rebuilds/restarts. Edit the port mapping in
`docker-compose.yml` if 8420 is already taken on your machine.

To stop:

```bash
docker compose down
```

## Run with plain Docker

```bash
docker build -t linen-kanban .
docker run -d -p 8420:5000 -v "$(pwd)/data/boards:/app/data/boards" --name linen-kanban linen-kanban
```

## Run without Docker

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**.

## Board file format

Each board is a YAML file at `data/boards/<board-id>.yaml`:

```yaml
id: home-automation-backlog
name: Home Automation Backlog
created: 2026-07-12T18:00:00Z
updated: 2026-07-12T18:04:00Z
sections:
  - id: a1b2c3d4
    name: To Do
    tasks:
      - id: e5f6a7b8
        title: Wire up the Reolink E1 Pro
        description: Person-detection zone for the garage.
  - id: c9d0e1f2
    name: In Progress
    tasks: []
  - id: f3a4b5c6
    name: Done
    tasks: []
```

You can back these up, edit them by hand, or sync the `data/boards/` folder
however you like — they're just files.

## Notes

- This app has no authentication or access control. It's meant to be run on a
  trusted local network, not exposed to the internet.
- Board IDs are derived from the board name at creation time (slugified, with a
  numeric suffix if there's a collision) and don't change if you later rename
  the board.
