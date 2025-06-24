import unittest
import sys
import pathlib
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

if __name__ == "__main__":
    unittest.main()
