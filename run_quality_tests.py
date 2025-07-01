import json
from pathlib import Path
from typing import List

from server import app, load_data

BASELINE_PATH = Path(__file__).resolve().parent / "data" / "baseline_results.json"


def run_tests() -> None:
    """Run /api/test-example for all examples and print summary."""
    # Load baseline data directly from file
    with BASELINE_PATH.open("r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    if not load_data():
        print("Fehler: Daten konnten nicht geladen werden.")
        return

    results: List[bool] = []

    with app.test_client() as client:
        for ex_id, entry in baseline_data.items():
            langs = list(entry.get("baseline", {}).keys())
            for lang in langs:
                resp = client.post(
                    "/api/test-example",
                    json={"id": int(ex_id), "lang": lang},
                )
                if resp.status_code != 200:
                    print(f"Beispiel {ex_id} [{lang}] Fehler: HTTP {resp.status_code}")
                    results.append(False)
                    continue

                data = resp.get_json() or {}
                passed = bool(data.get("passed"))
                diff = data.get("diff", "")
                status = "PASS" if passed else "FAIL"
                print(f"Beispiel {ex_id} [{lang}]: {status}{' - ' + diff if diff else ''}")
                results.append(passed)

    total = len(results)
    passed_count = sum(1 for r in results if r)
    print(f"\n{passed_count}/{total} Tests bestanden.")


if __name__ == "__main__":
    run_tests()
