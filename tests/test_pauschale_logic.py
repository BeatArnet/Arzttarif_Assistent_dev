import unittest
import sys
import pathlib
import json
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from regelpruefer_pauschale import (
    evaluate_pauschale_logic_orchestrator,
    determine_applicable_pauschale,
)

class TestPauschaleLogic(unittest.TestCase):
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
            evaluate_pauschale_logic_orchestrator(
                pauschale_code="C00.10A", context=context, all_pauschale_bedingungen_data=bedingungen, tabellen_dict_by_table=tab_dict
            )
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
            evaluate_pauschale_logic_orchestrator(
                pauschale_code="C03.26D", context=context, all_pauschale_bedingungen_data=bedingungen, tabellen_dict_by_table=tab_dict
            )
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
            evaluate_pauschale_logic_orchestrator(
                pauschale_code="C04.51B", context=context_ok, all_pauschale_bedingungen_data=bedingungen, tabellen_dict_by_table=tab_dict, debug=True
            )
        )

        context_missing_lavage = {
            "ICD": ["J98.6"],
            "LKN": ["C04.GC.0020", "C04.GC.Z005"], # Lavage C04.GC.Z001 is missing
        }
        self.assertTrue(
            evaluate_pauschale_logic_orchestrator(pauschale_code="C04.51B", context=context_missing_lavage, all_pauschale_bedingungen_data=bedingungen, tabellen_dict_by_table=tab_dict, debug=True)
        )

    def test_score_based_selection(self):
        """Higher scoring Pauschale should be chosen even if suffix later."""
        from regelpruefer_pauschale import determine_applicable_pauschale # Corrected import

        pauschale_bedingungen_data = [
            {"Pauschale": "X00.01A", "Gruppe": 1, "Bedingungstyp": "LKN", "Werte": "ANY", "BedingungsID": 1},
            {"Pauschale": "X00.01B", "Gruppe": 1, "Bedingungstyp": "LKN", "Werte": "ANY", "BedingungsID": 2}, # Different ID
        ]
        tabellen_dict_by_table = {}
        leistungskatalog_dict = {}


        pauschalen_dict = {
            "X00.01A": {"Pauschale": "X00.01A", "Pauschale_Text": "A", "Taxpunkte": "100"},
            "X00.01B": {"Pauschale": "X00.01B", "Pauschale_Text": "B", "Taxpunkte": "200"},
        }
        context = {"LKN": ["ANY"]}

        result = determine_applicable_pauschale(
            user_input="",
            rule_checked_leistungen=[],
            context=context,
            pauschale_lp_data=[], 
            pauschale_bedingungen_data=pauschale_bedingungen_data,
            pauschalen_dict=pauschalen_dict,
            leistungskatalog_dict=leistungskatalog_dict,
            tabellen_dict_by_table=tabellen_dict_by_table,
            potential_pauschale_codes_input={"X00.01A", "X00.01B"}
        )
        self.assertEqual(result["details"]["Pauschale"], "X00.01B")

    def test_finger_fracture_scenario_c08_30e_should_be_true(self):
        context = {"LKN": ["C08.GD.0030", "WA.10.0020"], "ICD": ["S62.60"], "useIcd": False}
        bedingungen_c08_30e = [
            {"BedingungsID": 1424, "Pauschale": "C08.30E", "Gruppe": 1, "Operator": "UND", "Bedingungstyp": "HAUPTDIAGNOSE IN TABELLE", "Werte": "CAP08", "Ebene": 1},
            {"BedingungsID": 1427, "Pauschale": "C08.30E", "Gruppe": 1, "Operator": "UND", "Bedingungstyp": "LEISTUNGSPOSITIONEN IN TABELLE", "Werte": "C08.30_10,C08.30_12", "Ebene": 2},
            {"BedingungsID": 1428, "Pauschale": "C08.30E", "Gruppe": 1, "Bedingungstyp": "AST VERBINDUNGSOPERATOR", "Werte": "ODER", "Ebene": 0}, # AST op in "Werte"
            {"BedingungsID": 1429, "Pauschale": "C08.30E", "Gruppe": 3, "Operator": "UND", "Bedingungstyp": "HAUPTDIAGNOSE IN TABELLE", "Werte": "CAP08", "Ebene": 1},
            {"BedingungsID": 1432, "Pauschale": "C08.30E", "Gruppe": 3, "Operator": "UND", "Bedingungstyp": "LEISTUNGSPOSITIONEN IN TABELLE", "Werte": "C08.30_5", "Ebene": 2},
            {"BedingungsID": 1433, "Pauschale": "C08.30E", "Gruppe": 3, "Operator": "UND", "Bedingungstyp": "LEISTUNGSPOSITIONEN IN TABELLE", "Werte": "ANAST", "Ebene": 2},
        ]
        tabellen_mock = {
            "cap08": [{"Code": "S62.60"}], "c08.30_10": [], "c08.30_12": [],
            "c08.30_5": [{"Code": "C08.GD.0030", "Tabelle_Typ": "service_catalog"}],
            "anast": [{"Code": "WA.10.0020", "Tabelle_Typ": "service_catalog"}]
        }
        self.assertTrue(
            evaluate_pauschale_logic_orchestrator("C08.30E", context, bedingungen_c08_30e, tabellen_mock, debug=True),
            "C08.30E sollte für Fingerfraktur mit Anästhesie und passender HD als ERFÜLLT gelten."
        )

    def test_finger_fracture_scenario_c05_15a_should_be_false(self):
        context = {"LKN": ["C08.GD.0030", "WA.10.0020"], "ICD": ["S62.60"], "useIcd": False}
        bedingungen_c05_15a_modified = [
            {"BedingungsID": 956, "Pauschale": "C05.15A", "Gruppe": 1, "Operator": "UND", "Bedingungstyp": "HAUPTDIAGNOSE IN TABELLE", "Werte": "CAP05", "Ebene": 1},
            {"BedingungsID": 958, "Pauschale": "C05.15A", "Gruppe": 1, "Operator": "UND", "Bedingungstyp": "LEISTUNGSPOSITIONEN IN TABELLE", "Werte": "C05.15_1", "Ebene": 2},
            {"BedingungsID": 9991, "Pauschale": "C05.15A", "Gruppe": 1, "Bedingungstyp": "AST VERBINDUNGSOPERATOR", "Werte": "ODER", "Ebene": 0}, # AST op in "Werte"
            {"BedingungsID": 959, "Pauschale": "C05.15A", "Gruppe": 2, "Operator": "UND", "Bedingungstyp": "LEISTUNGSPOSITIONEN IN TABELLE", "Werte": "C05.15_2", "Ebene": 1},
            {"BedingungsID": 960, "Pauschale": "C05.15A", "Gruppe": 2, "Operator": "UND", "Bedingungstyp": "LEISTUNGSPOSITIONEN IN TABELLE", "Werte": "ANAST", "Ebene": 2}
        ]
        tabellen_mock = {
            "cap05": [{"Code": "I47.1"}], "c05.15_1": [{"Code": "LKN_ABLATION"}],
            "c05.15_2": [{"Code": "LKN_ECHO_DIAG"}],
            "anast": [{"Code": "WA.10.0020"}]
        }
        self.assertFalse(
            evaluate_pauschale_logic_orchestrator(
                "C05.15A", context, bedingungen_c05_15a_modified, tabellen_mock, debug=True
            ),
           "C05.15A sollte für Fingerfraktur NICHT als erfüllt gelten, wenn die spezifischen Bedingungen nicht zutreffen."
        )

if __name__ == "__main__":
    unittest.main()
