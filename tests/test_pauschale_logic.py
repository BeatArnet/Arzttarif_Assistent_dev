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

    def test_group_operator_oder_between_groups(self):
        conditions = [
            {"BedingungsID": 1, "Pauschale": "TEST", "Gruppe": 1, "Operator": "UND", "Bedingungstyp": "ANZAHL", "Vergleichsoperator": ">=", "Werte": "2"},
            {"BedingungsID": 2, "Pauschale": "TEST", "Gruppe": 2, "Operator": "UND", "Bedingungstyp": "ANZAHL", "Vergleichsoperator": ">=", "Werte": "1"},
        ]
        context = {"Anzahl": 1}
        self.assertTrue(
            evaluate_structured_conditions("TEST", context, conditions, {}, group_operator="ODER")
        )

    def test_group_operator_und_between_groups(self):
        conditions = [
            {"BedingungsID": 1, "Pauschale": "TEST", "Gruppe": 1, "Operator": "UND", "Bedingungstyp": "ANZAHL", "Vergleichsoperator": ">=", "Werte": "1"},
            {"BedingungsID": 2, "Pauschale": "TEST", "Gruppe": 2, "Operator": "UND", "Bedingungstyp": "ICD", "Werte": "A12"},
        ]
        context = {"Anzahl": 1, "ICD": []}
        self.assertFalse(
            evaluate_structured_conditions("TEST", context, conditions, {}, group_operator="UND")
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

        # Should pass because first condition is true and combined with OR
        self.assertTrue(
            evaluate_structured_conditions("CAT", context, conditions, {})
        )

if __name__ == "__main__":
    unittest.main()
