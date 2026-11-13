"""Thin wrapper around the Anthropic Messages API for image + text turns."""
import base64
import json
import os
import re
from pathlib import Path

import anthropic

_client: anthropic.Anthropic | None = None
_MEDIA = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Set ANTHROPIC_API_KEY to run the agent loop (or use --no-llm).")
        _client = anthropic.Anthropic(api_key=key)
    return _client


def image_block(path: Path, label: str | None = None) -> list[dict]:
    """A text label (optional) followed by the image, as Messages API content blocks."""
    path = Path(path)
    media = _MEDIA.get(path.suffix.lower())
    if media is None:
        raise ValueError(f"unsupported image type: {path.name}")
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    blocks: list[dict] = []
    if label:
        blocks.append({"type": "text", "text": label})
    blocks.append({"type": "image", "source": {"type": "base64", "media_type": media, "data": data}})
    return blocks


def ask(messages: list[dict], system: str, model: str, max_tokens: int = 8000) -> str:
    resp = client().messages.create(model=model, system=system, messages=messages, max_tokens=max_tokens)
    return "".join(block.text for block in resp.content if block.type == "text")


def extract_json(text: str) -> dict:
    """Parse the first JSON object in a model reply, tolerating code fences around it."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    raw = fenced.group(1) if fenced else text[text.index("{"): text.rindex("}") + 1]
    return json.loads(raw)


def extract_python(text: str) -> tuple[str, str]:
    """Return (python_code, rest_of_reply). The first ```python block is the model."""
    m = re.search(r"```python\s*\n(.*?)```", text, re.S)
    if not m:
        raise ValueError("reply contained no ```python block")
    return m.group(1), (text[: m.start()] + text[m.end():]).strip()
