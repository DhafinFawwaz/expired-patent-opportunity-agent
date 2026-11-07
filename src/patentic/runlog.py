import json
import re
from pathlib import Path
from typing import Final

from patentic.adapters.http import utc_now

_SECRET: Final[re.Pattern[str]] = re.compile(
    r"api_key|token|authorization|secret|password", re.IGNORECASE
)
SNIPPET_LIMIT: Final[int] = 200


def redact(value: object, key: str = "") -> object:
    if key and _SECRET.search(key):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if key == "raw_snippet" and isinstance(value, str):
        return value[:SNIPPET_LIMIT]
    return value


class EventLog:
    def __init__(self, path: Path, thread_id: str) -> None:
        self.path: Path = path
        self.thread_id: str = thread_id
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict[str, object]) -> None:
        record: dict[str, object] = {
            "ts": utc_now().isoformat(),
            "thread_id": self.thread_id,
            **event,
        }
        cleaned: object = redact(record)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(cleaned, default=str) + "\n")
