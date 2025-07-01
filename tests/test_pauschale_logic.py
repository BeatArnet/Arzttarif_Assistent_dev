import unittest
import sys
import pathlib
import json
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from regelpruefer_pauschale import evaluate_structured_conditions

class TestPauschaleLogic(unittest.TestCase):
    def test_or_operator_in_group(self):
        conditions = [
            {
                "BedingungsID": 1,
                "Pauschale": "TEST",
                "Gruppe": 1,
                "Operator": "ODER",
                "Bedingungstyp": "ANZAHL",
                "Vergleichsoperator": ">=",
                "Werte": "2"
            },
            {
                "BedingungsID": 2,
                "Pauschale": "TEST",
                "Gruppe": 1,
                "Operator": "UND",
                "Bedingungstyp": "ICD",
                "Werte": "A12"
            }
        ]
        context = {"Anzahl": 3, "ICD": []}
        # With the operator attached to the second rule, both conditions must
        # be met. Only the count criterion is satisfied here.
        self.assertTrue(
            evaluate_structured_conditions("TEST", context, conditions, {})
        )

    def test_bilateral_cataract_example(self):
        conditions = [
            {
                "BedingungsID": 1,
                "Pauschale": "CAT",
                "Gruppe": 1,
                "Operator": "ODER",
                "Bedingungstyp": "SEITIGKEIT",
                "Vergleichsoperator": "=",
                "Werte": "B"
            },
            {
                "BedingungsID": 2,
                "Pauschale": "CAT",
                "Gruppe": 1,
                "Operator": "UND",
                "Bedingungstyp": "ANZAHL",
                "Vergleichsoperator": ">=",
                "Werte": "2"
            },
            {
                "BedingungsID": 3,
                "Pauschale": "CAT",
                "Gruppe": 1,
                "Operator": "UND",
                "Bedingungstyp": "LEISTUNGSPOSITIONEN IN LISTE",
                "Werte": "OP"
            }
        ]
        context = {"Seitigkeit": "beidseits", "LKN": ["OP"]}
        # All rules must be met since the operators of the later rows are UND.
        self.assertTrue(
            evaluate_structured_conditions("CAT", context, conditions, {})
        )

    def test_operator_precedence(self):
        # Conditions mimic the real cataract rule order (OR then AND)
        conditions = [
            {
                "BedingungsID": 4,
                "Pauschale": "CAT",
                "Gruppe": 1,
                "Operator": "ODER",
                "Bedingungstyp": "SEITIGKEIT",
                "Vergleichsoperator": "=",
                "Werte": "B",
            },
            {
                "BedingungsID": 2,
                "Pauschale": "CAT",
                "Gruppe": 1,
                "Operator": "UND",
                "Bedingungstyp": "LEISTUNGSPOSITIONEN IN LISTE",
                "Werte": "OP",
            },
            {
                "BedingungsID": 3,
                "Pauschale": "CAT",
                "Gruppe": 1,
                "Operator": "UND",
                "Bedingungstyp": "ANZAHL",
                "Vergleichsoperator": ">=",
                "Werte": "2",
            },
        ]

        context = {"Seitigkeit": "beidseits", "LKN": ["OP"], "Anzahl": 1}

        # Bei strikter Links-nach-rechts-Auswertung muss auch die letzte
        # Bedingung erfüllt sein, da sie mit UND verknüpft wird.
        self.assertFalse(
            evaluate_structured_conditions("CAT", context, conditions, {})
        )

    def test_or_then_and_requires_last_condition(self):
        conditions = [
            {
                "BedingungsID": 1,
                "Pauschale": "TEST2",
                "Gruppe": 1,
                "Operator": "ODER",
                "Bedingungstyp": "LEISTUNGSPOSITIONEN IN LISTE",
                "Werte": "A",
            },
            {
                "BedingungsID": 2,
                "Pauschale": "TEST2",
                "Gruppe": 1,
                "Operator": "UND",
                "Bedingungstyp": "LEISTUNGSPOSITIONEN IN LISTE",
                "Werte": "B",
            },
            {
                "BedingungsID": 3,
                "Pauschale": "TEST2",
                "Gruppe": 1,
                "Operator": "UND",
                "Bedingungstyp": "LEISTUNGSPOSITIONEN IN LISTE",
                "Werte": "C",
            },
        ]
        context = {"LKN": ["A", "B"]}
        self.assertFalse(
            evaluate_structured_conditions("TEST2", context, conditions, {})
        )

    def test_icd_condition_ignored_when_use_icd_false(self):
        conditions = [
            {
                "BedingungsID": 1,
                "Pauschale": "ICDTEST",
                "Gruppe": 1,
                "Operator": "UND",
                "Bedingungstyp": "ICD",
                "Werte": "A12"
            }
        ]
        context = {"ICD": [], "useIcd": False}
        self.assertTrue(
            evaluate_structured_conditions("ICDTEST", context, conditions, {})
        )

    def test_c00_10a_requires_operation_and_anesthesia(self):
        """Real data for C00.10A should not match without a C00.70_11/12 code."""
        root = pathlib.Path(__file__).resolve().parents[1]
        with open(root / "data/PAUSCHALEN_Bedingungen.json", encoding="utf-8") as f:
            bedingungen = json.load(f)
        with open(root / "data/PAUSCHALEN_Tabellen.json", encoding="utf-8") as f:
            tabellen = json.load(f)

        tab_dict = {}
        for row in tabellen:
            name = row.get("Tabelle")
            if name:
                tab_dict.setdefault(name.lower(), []).append(row)

        context = {"LKN": ["WA.10.0010", "C08.GD.0030"]}

        self.assertFalse(
            evaluate_structured_conditions("C00.10A", context, bedingungen, tab_dict)
        )

    def test_c03_26d_requires_all_conditions(self):
        """C03.26D should not match when only anesthesia and a wrong LKN are present."""
        root = pathlib.Path(__file__).resolve().parents[1]
        with open(root / "data/PAUSCHALEN_Bedingungen.json", encoding="utf-8") as f:
            bedingungen = json.load(f)
        with open(root / "data/PAUSCHALEN_Tabellen.json", encoding="utf-8") as f:
            tabellen = json.load(f)

        tab_dict = {}
        for row in tabellen:
            name = row.get("Tabelle")
            if name:
                tab_dict.setdefault(name.lower(), []).append(row)

        context = {"LKN": ["WA.10.0010", "C08.GD.0030"]}

        self.assertFalse(
            evaluate_structured_conditions("C03.26D", context, bedingungen, tab_dict)
        )

    def test_c04_51b_mixed_operators(self):
        """C04.51B requires both bronchoscopy and lavage."""
        root = pathlib.Path(__file__).resolve().parents[1]
        with open(root / "data/PAUSCHALEN_Bedingungen.json", encoding="utf-8") as f:
            bedingungen = json.load(f)
        with open(root / "data/PAUSCHALEN_Tabellen.json", encoding="utf-8") as f:
            tabellen = json.load(f)

        tab_dict = {}
        for row in tabellen:
            name = row.get("Tabelle")
            if name:
                tab_dict.setdefault(name.lower(), []).append(row)

        context_ok = {
            "ICD": ["J98.6"],
            "LKN": ["C04.GC.0020", "C04.GC.Z005", "C04.GC.Z001"],
        }

        self.assertTrue(
            evaluate_structured_conditions("C04.51B", context_ok, bedingungen, tab_dict)
        )

        context_missing_lavage = {
            "ICD": ["J98.6"],
            "LKN": ["C04.GC.0020", "C04.GC.Z005"],
        }

        self.assertFalse(
            evaluate_structured_conditions("C04.51B", context_missing_lavage, bedingungen, tab_dict)
        )

if __name__ == "__main__":
    unittest.main()
