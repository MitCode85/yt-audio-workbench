from __future__ import annotations

import json
from pathlib import Path
from typing import Any

class Language:
    """Tiny JSON-based language lookup with dot-path keys, e.g. 'tooltips.sample_rate'."""

    def __init__(self, lang_dir: str | Path, code: str = "en") -> None:
        self.lang_dir = Path(lang_dir)
        self.code = code
        self._data: dict[str, Any] = {}
        self.load(self.code)

    def load(self, code: str) -> None:
        self._data = {}
        try:
            path = self.lang_dir / f"{code}.json"
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            # fall back to English if not present
            if code != "en":
                try:
                    with open(self.lang_dir / "en.json", encoding="utf-8") as f:
                        self._data = json.load(f)
                except Exception:
                    self._data = {}

    def get(self, key: str, default: str | None = None) -> str | None:
        # Resolve dot path
        cur: Any = self._data
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        if isinstance(cur, (str, int, float)):
            return str(cur)
        return default

    def available_locales(self) -> dict[str, Path]:
        locales: dict[str, Path] = {}
        if not self.lang_dir.exists():
            return locales
        for p in self.lang_dir.glob("*.json"):
            locales[p.stem] = p
        return locales
