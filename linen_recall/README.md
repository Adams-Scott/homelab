# Recall

Recall is a local-first note-taking app for small, easy-to-forget notes.

The first implementation uses:

- Python and FastAPI for the API and web UI
- SQLite for local persistence
- A scheduled worker that enriches pending notes with elaboration and tags
- Docker Compose for local deployment

## Services

- API server: CRUD, search, and bot control endpoints
- Web interface: browser-based note management
- Worker: scheduled enrichment of unprocessed notes
- Tags page: manage predefined tags used during enrichment
- Context page: edit the shared AI context file used during enrichment

## Run locally

1. Build and start the stack with Docker Compose.
2. Open the web interface on port 8001.
3. Use the API on port 8000 for JSON access.

### Docker Compose commands

Start all services in the background:

```bash
docker compose up -d
```

Stop all services:

```bash
docker compose down
```

Rebuild images and restart services:

```bash
docker compose up -d --build
```

Rebuild and restart a single service (example: worker):

```bash
docker compose up -d --build worker
```

## Notes

- The original note is preserved.
- Enrichment output is stored separately from the source note.
- Search scans the original note, elaboration, and tags.

## Worker LLM Configuration

The worker reads AI settings from a runtime YAML file at `recall_data/llm_config.yaml`
(mounted in containers as `/data/llm_config.yaml`).

- If the file does not exist, the worker creates it on startup.
- Default provider is `ollama`.
- You can point to your network Ollama server by setting `ollama.base_url`.

Example:

```yaml
provider: ollama
ollama:
	base_url: http://192.168.1.50:11434
	model: llama3.1:8b
	timeout_seconds: 30
```

If Ollama is unreachable or returns invalid JSON, enrichment is marked as `error`
for that note with the failure reason in `last_enrichment_error`.

## AI context file

The shared context file lives at `recall_data/context.md` and is mounted inside
containers as `/data/context.md`.

- Use the Context page to add personal facts and preferences.
- The file is sent with every enrichment request.
