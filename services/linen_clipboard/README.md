# Clipboard

A tiny self-hosted public clipboard for home/LAN use. Post text, upload files, or paste
an image straight from your clipboard. Each item auto-expires after 1 day, 1 week, or
1 month (your choice per-post).

No auth, no HTTPS — it's meant to sit on your LAN only. Don't expose it to the internet.

## Run it

```bash
docker compose up -d --build
```

Then open `http://<host>:8090`.

Data (SQLite DB + uploaded files) is stored in `./data`, which is bind-mounted into the
container, so it survives rebuilds/restarts.

## Usage

- **Text**: type into the box, pick an expiry, hit Post (or Cmd/Ctrl+Enter).
- **Files**: click "Attach file", or just drag a file anywhere onto the page.
- **Images**: copy an image anywhere (screenshot tool, browser, etc.) and paste
  (Ctrl/Cmd+V) anywhere on the page — no need to focus a specific field.
- Items show a live countdown and are deleted (DB row + file on disk) automatically
  once they expire. A background sweep also runs every 60 seconds as a backup.
- Each item has a Copy/Download button and a Delete button if you want it gone early.

## Notes

- Default port mapping is `8090:5000` — change the left side in `docker-compose.yml`
  if that collides with something else in your homelab.
- Max upload size is set generously (1 GB) since this is for trusted home use.
- Storage is just SQLite + the filesystem — no external services needed.
