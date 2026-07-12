from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable
import json
import re
from urllib import error, request


@dataclass(frozen=True)
class EnrichmentResult:
    title: str
    elaborated_note: str
    tags: list[str]


class BaseLLMClient:
    def enrich(self, note_text: str, context_text: str = "", allowed_tags: list[str] | None = None) -> EnrichmentResult:
        raise NotImplementedError


class HeuristicLLMClient(BaseLLMClient):
    def enrich(self, note_text: str, context_text: str = "", allowed_tags: list[str] | None = None) -> EnrichmentResult:
        combined_text = " ".join(part for part in [context_text.strip(), note_text.strip()] if part)
        words = re.findall(r"[A-Za-z0-9']+", combined_text.lower())
        keywords = _top_keywords(words)
        tags = _select_tags(keywords, allowed_tags)
        title = _generate_title(note_text, keywords)
        elaborated = (
            "Original note: "
            f"{note_text.strip()}\n\n"
            "Elaboration: This note has been expanded into a clearer memory aid. "
            f"Key themes include {', '.join(tags)}."
        )
        if context_text.strip():
            elaborated += f"\n\nContext: {context_text.strip()}"
        return EnrichmentResult(title=title, elaborated_note=elaborated, tags=tags)


class OllamaLLMClient(BaseLLMClient):
    def __init__(self, base_url: str, model: str, timeout_seconds: int = 30):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def enrich(self, note_text: str, context_text: str = "", allowed_tags: list[str] | None = None) -> EnrichmentResult:
        tag_guidance = ""
        if allowed_tags:
            tag_guidance = f" Use only these enabled tags: {', '.join(allowed_tags)}."
        prompt = (
            "You create JSON only for note enrichment. "
            'Return strictly valid JSON with keys: title (string), elaborated_note (string), tags (array of short strings).'
            f"{tag_guidance}\n\n"
            f"Context: {context_text.strip() or 'None'}\n\n"
            f"Note: {note_text.strip()}"
        )
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": prompt,
        }
        req = request.Request(
            url=f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
                raw_response = str(data.get("response", "")).strip()
            parsed = json.loads(raw_response)
            title = str(parsed.get("title", "")).strip()
            elaborated = str(parsed.get("elaborated_note", "")).strip()
            tags_raw = parsed.get("tags", [])
            tags = [str(tag).strip() for tag in tags_raw if str(tag).strip()]
            if allowed_tags:
                allowed_lookup = {tag.lower(): tag for tag in allowed_tags}
                tags = [allowed_lookup[tag.lower()] for tag in tags if tag.lower() in allowed_lookup]
            if not title or not elaborated:
                raise RuntimeError("Ollama response missing required fields: title or elaborated_note")
            if not tags:
                tags = ["note"]
            return EnrichmentResult(title=title, elaborated_note=elaborated, tags=tags[:8])
        except error.URLError as exc:
            raise RuntimeError(f"Failed to connect to Ollama at {self.base_url}: {exc}") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"Timed out calling Ollama at {self.base_url}") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid Ollama response: {exc}") from exc


def _top_keywords(words: Iterable[str]) -> list[str]:
    counts: dict[str, int] = {}
    stop_words = {"the", "and", "for", "with", "this", "that", "from", "have", "you", "your", "are", "was", "were", "will", "into", "about", "note", "remember"}
    for word in words:
        if len(word) < 3 or word in stop_words:
            continue
        counts[word] = counts.get(word, 0) + 1
    return [word for word, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def _generate_title(note_text: str, keywords: list[str]) -> str:
    if keywords:
        title_words = [word.capitalize() for word in keywords[:4]]
        return " ".join(title_words)

    words = re.findall(r"[A-Za-z0-9']+", note_text.strip())
    if words:
        return " ".join(words[:6])[:80]

    return "Untitled Note"


def _select_tags(keywords: list[str], allowed_tags: list[str] | None) -> list[str]:
    if allowed_tags:
        allowed_lookup = {tag.lower(): tag for tag in allowed_tags}
        matched = [allowed_lookup[word] for word in keywords if word in allowed_lookup]
        return matched[:5] or allowed_tags[:5] or ["note"]
    return keywords[:5] or ["note"]


def build_llm_client(
    provider: str,
    ollama_base_url: str | None = None,
    ollama_model: str | None = None,
    ollama_timeout_seconds: int = 30,
) -> BaseLLMClient:
    if provider.strip().lower() == "ollama":
        return OllamaLLMClient(
            base_url=ollama_base_url or "http://host.docker.internal:11434",
            model=ollama_model or "llama3.1:8b",
            timeout_seconds=ollama_timeout_seconds,
        )
    return HeuristicLLMClient()
