import unittest
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

if __name__ == "__main__":
    unittest.main()
