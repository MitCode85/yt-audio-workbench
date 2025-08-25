
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Optional

class Language:
    def __init__(self, lang_dir: Path, code: str = "en") -> None:
        self.lang_dir = Path(lang_dir)
        self.code = code
        self._data: Dict[str, Any] = {}
        self.load(self.code)

    def load(self, code: str) -> None:
        self.code = code
        path = self.lang_dir / f"{code}.json"
        self._data = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            # fallback to English if available
            if code != "en":
                try:
                    with open(self.lang_dir / "en.json", "r", encoding="utf-8") as f:
                        self._data = json.load(f)
                except Exception:
                    self._data = {}

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
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

    def available_locales(self) -> Dict[str, Path]:
        locales = {}
        if not self.lang_dir.exists():
            return locales
        for p in self.lang_dir.glob("*.json"):
            code = p.stem
            locales[code] = p
        return dict(sorted(locales.items()))
