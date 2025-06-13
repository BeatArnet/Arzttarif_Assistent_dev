"""Hilfsskript zum Entfernen unerlaubter Steuerzeichen aus JSON-Dateien."""

from __future__ import annotations

import re
import json
from pathlib import Path
import sys


def clean_file(src_path: Path) -> Path:
    """Liest ``src_path``, entfernt Steuerzeichen und speichert ``*.clean.json``.

    Gibt den Pfad zur bereinigten Datei zurück.
    """

    dst = src_path.with_suffix(".clean.json")

    raw = src_path.read_text(encoding="utf-8", errors="surrogateescape")
    raw_clean = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", raw)

    # validieren
    json.loads(raw_clean)

    dst.write_text(raw_clean, encoding="utf-8")
    return dst


def main(argv: list[str]) -> None:
    src = Path(argv[1]) if len(argv) > 1 else Path("data/TARDOC_Interpretationen.json")
    cleaned = clean_file(src)
    print(f"✅ Bereinigt & validiert → {cleaned}")


if __name__ == "__main__":
    main(sys.argv)

