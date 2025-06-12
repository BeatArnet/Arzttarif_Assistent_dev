import re
import json
import pathlib
import sys

# 1) Quelldatei = 1. CLI-Argument, sonst Default
src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else r"data/TARDOC_Interpretationen.json")
dst = src.with_suffix(".clean.json")

# 2) Datei als Text einlesen – surrogateescape schluckt "kaputte" Bytes ohne Absturz
raw = src.read_text(encoding="utf-8", errors="surrogateescape")

# 3) Alle Steuerzeichen entfernen **außer** Tab (0x09), Zeilen- & Wagenrücklauf (0x0A/0x0D)
raw_clean = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", raw)

# 4) Testweise parsen – schlägt das fehl, siehst du die nächste Fehlerstelle
json.loads(raw_clean)

# 5) Saubere Datei speichern
dst.write_text(raw_clean, encoding="utf-8")
print(f"✅ Bereinigt & validiert → {dst}")

