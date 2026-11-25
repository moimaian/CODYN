# -*- coding: utf-8 -*-
"""Tradução da interface (EN/PT) com troca em tempo real.

- Os textos ficam em BIN/i18n_texts.py: {"chave": {"en": "...", "pt": "..."}}.
- t(chave, idioma, **kw) devolve o texto (fallback: inglês e, por fim, a própria chave);
- detect_system_language() escolhe o idioma inicial pelo locale do sistema (pt* -> "pt");
- Translator guarda o idioma atual e registra (chave, setter, kwargs) para retraduzir os widgets
  sem recriá-los quando o usuário troca a bandeira.
"""

import locale
import sys
import os
from typing import Callable, List, Tuple

from BIN.i18n_texts import TEXTS

LANGUAGES = ("en", "pt")
DEFAULT_LANGUAGE = "en"


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    entry = TEXTS.get(key, {})
    value = entry.get(lang)
    if value is None:
        value = entry.get(DEFAULT_LANGUAGE, key)
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return value
    return value


def detect_system_language() -> str:
    """'pt' se o sistema estiver em português; caso contrário, 'en'."""
    candidates = [os.environ.get(v, "") for v in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG")]
    try:
        candidates.append((locale.getlocale()[0] or ""))
    except Exception:
        pass
    if sys.platform.startswith("win"):   # Windows: não há LANG; usa o idioma do usuário ("pt-BR", "en-US"...)
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(85)
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85):  # type: ignore[attr-defined]
                candidates.append(buf.value)
        except Exception:
            pass
    for c in candidates:
        c = (c or "").lower()
        if c.startswith("pt"):
            return "pt"
        if c.startswith("en"):
            return "en"
    return DEFAULT_LANGUAGE


class Translator:
    """Idioma atual + registro de widgets retraduzíveis."""

    def __init__(self, lang: str = DEFAULT_LANGUAGE):
        self.lang = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
        self._registry: List[Tuple[str, Callable[[str], None], dict]] = []
        self._listeners: List[Callable[[str], None]] = []

    def t(self, key: str, **kw) -> str:
        return t(key, self.lang, **kw)

    def tr(self, key: str, apply_fn: Callable[[str], None], **kw):
        """Registra e aplica agora: tr('btn_run', button.setText)."""
        self._registry.append((key, apply_fn, kw))
        apply_fn(self.t(key, **kw))

    def on_change(self, fn: Callable[[str], None]):
        self._listeners.append(fn)

    def set_language(self, lang: str):
        if lang not in LANGUAGES or lang == self.lang:
            return
        self.lang = lang
        alive = []
        for key, fn, kw in self._registry:
            try:
                fn(self.t(key, **kw))
                alive.append((key, fn, kw))
            except RuntimeError:  # widget C++ já destruído
                continue
        self._registry = alive
        for fn in list(self._listeners):
            try:
                fn(lang)
            except RuntimeError:
                self._listeners.remove(fn)
