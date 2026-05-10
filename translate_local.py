"""
translate_local.py

Cheap, local Spanish->English translation used by the repair pipeline. The
goal is zero API calls.

Resolution order:
1. paired template English (free, perfect)        -- handled by the caller
2. argos-translate (offline neural MT)            -- if installed
3. None -> caller marks the row for manual review

Public API:
    LocalTranslator()       -- attempt to load argos
    .available -> bool
    .translate(spanish: str) -> str | None
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LocalTranslator:
    available: bool = False
    _translator: object | None = None
    backend: str = "none"

    def __post_init__(self) -> None:
        # Try argos-translate first.
        try:
            import argostranslate.translate as at  # type: ignore

            installed = at.get_installed_languages()
            es = next((l for l in installed if l.code == "es"), None)
            en = next((l for l in installed if l.code == "en"), None)
            if es and en:
                self._translator = es.get_translation(en)
                if self._translator is not None:
                    self.available = True
                    self.backend = "argos"
                    return
        except Exception:
            pass

        # Try transformers Helsinki-NLP MarianMT as a heavier fallback.
        try:
            from transformers import pipeline  # type: ignore

            self._translator = pipeline(
                "translation",
                model="Helsinki-NLP/opus-mt-es-en",
            )
            self.available = True
            self.backend = "marian"
        except Exception:
            self.available = False
            self.backend = "none"

    def translate(self, spanish: str) -> str | None:
        if not self.available or not self._translator:
            return None
        try:
            if self.backend == "argos":
                return self._translator.translate(spanish)  # type: ignore
            if self.backend == "marian":
                out = self._translator(spanish, max_length=64)  # type: ignore
                if out and isinstance(out, list):
                    return out[0].get("translation_text")
        except Exception:
            return None
        return None


_singleton: LocalTranslator | None = None


def get_translator() -> LocalTranslator:
    global _singleton
    if _singleton is None:
        _singleton = LocalTranslator()
    return _singleton
