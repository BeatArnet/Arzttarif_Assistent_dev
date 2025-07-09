# regelpruefer_pauschale.py (Version mit korrigiertem Import und 9 Argumenten)
'''
Die Datei regelpruefer_pauschale.py implementiert eine mehrstufige Prüfung, um aus den möglichen Pauschalen die passende auszuwählen:

Potenzielle Pauschalen ermitteln
Aus den regelgeprüften LKNs werden mithilfe der Verknüpfungen aus PAUSCHALEN_Leistungspositionen.json und den LKN-Bedingungen 
in PAUSCHALEN_Bedingungen.json zunächst alle in Frage kommenden Pauschalen bestimmt

Strukturierte Bedingungsprüfung
Für jede gefundene Pauschale werden die Bedingungszeilen anhand der UND/ODER‑Logik geprüft (evaluate_structured_conditions). 
Dabei wird der in der Bedingungsdatei angegebene GruppenOperator beachtet. Innerhalb einer Gruppe wird 
der Operator jeder Zeile („UND“ oder „ODER“) berücksichtigt, sodass sich ein boolescher Ausdruck ergibt 
(z. B. (SEITIGKEIT = B ODER ANZAHL >= 2) UND LKN IN LISTE OP)

Beste Pauschale wählen
Nur Pauschalen, deren gesamte Bedingungslogik erfüllt ist, bleiben im Rennen. 
Aus diesen wird in determine_applicable_pauschale der Kandidat mit dem höchsten Score (Taxpunkte) und dem niedrigsten Suffix gewählt. 
Fallback‑Pauschalen (Codes C90‑C99) werden nur herangezogen, wenn keine spezifische Pauschale gültig ist

Ergebnisaufbereitung
check_pauschale_conditions erzeugt anschließend ein strukturiertes HTML mit dem Erfüllungsstatus jeder einzelnen Bedingung 
und liefert zusammen mit der Begründung das Endresultat zurück.

Zusammengefasst basiert die Pauschalenprüfung also auf einer systematischen Suche nach passenden Codes 
und einer detaillierten Auswertung der Bedingungsgruppen (UND/ODER‑Logik). 
Validierte Kandidaten werden nach Komplexität priorisiert und mit erläuternden Details ausgegeben.
'''
import traceback
import json
import logging
import time # Importiere das time Modul
from typing import Dict, List, Any, Set  # <-- Set hier importieren
from utils import escape, get_table_content, get_lang_field, translate, translate_condition_type
import re, html

logger = logging.getLogger(__name__)

__all__ = [
    "evaluate_structured_conditions",
    "check_pauschale_conditions",
    "get_simplified_conditions",
    "render_condition_results_html",
    "generate_condition_detail_html",
    "determine_applicable_pauschale",
]

# Standardoperator zur Verknüpfung der Bedingungsgruppen.
# "UND" ist der konservative Default und kann zentral angepasst werden.
DEFAULT_GROUP_OPERATOR = "UND"

# === FUNKTION ZUR PRÜFUNG EINER EINZELNEN BEDINGUNG ===
def check_single_condition(
    condition: Dict,
    context: Dict,
    tabellen_dict_by_table: Dict[str, List[Dict]]
) -> bool:
    """Prüft eine einzelne Bedingungszeile und gibt True/False zurück."""
    check_icd_conditions_at_all = context.get("useIcd", True)
    pauschale_code_for_debug = condition.get('Pauschale', 'N/A_PAUSCHALE') # Für besseres Debugging
    gruppe_for_debug = condition.get('Gruppe', 'N/A_GRUPPE') # Für besseres Debugging

    BED_TYP_KEY = 'Bedingungstyp'; BED_WERTE_KEY = 'Werte'; BED_FELD_KEY = 'Feld'
    BED_MIN_KEY = 'MinWert'; BED_MAX_KEY = 'MaxWert'
    bedingungstyp = condition.get(BED_TYP_KEY, "").upper()
    werte_str = condition.get(BED_WERTE_KEY, "") # Dies ist der Wert aus der Regel-DB
    feld_ref = condition.get(BED_FELD_KEY); min_val_regel = condition.get(BED_MIN_KEY) # Umbenannt für Klarheit
    max_val_regel = condition.get(BED_MAX_KEY); wert_regel_explizit = condition.get(BED_WERTE_KEY) # Umbenannt für Klarheit

    # Kontextwerte holen
    provided_icds_upper = {p_icd.upper() for p_icd in context.get("ICD", []) if p_icd}
    provided_gtins = set(context.get("GTIN", []))
    provided_lkns_upper = {p_lkn.upper() for p_lkn in context.get("LKN", []) if p_lkn}
    provided_alter = context.get("Alter")
    provided_geschlecht_str = str(context.get("Geschlecht", "unbekannt")).lower() # Default 'unbekannt' und lower
    provided_anzahl = context.get("Anzahl") # Aus dem Kontext für "ANZAHL" Typ
    provided_seitigkeit_str = str(context.get("Seitigkeit", "unbekannt")).lower() # Default 'unbekannt' und lower

    # print(f"--- DEBUG check_single --- P: {pauschale_code_for_debug} G: {gruppe_for_debug} Typ: {bedingungstyp}, Regel-Werte: '{werte_str}', Kontext: {context.get('Seitigkeit', 'N/A')}/{context.get('Anzahl', 'N/A')}")

    try:
        if bedingungstyp == "ICD": # ICD IN LISTE
            if not check_icd_conditions_at_all: return True
            required_icds_in_rule_list = {w.strip().upper() for w in str(werte_str).split(',') if w.strip()}
            if not required_icds_in_rule_list: return True # Leere Regel-Liste ist immer erfüllt
            return any(req_icd in provided_icds_upper for req_icd in required_icds_in_rule_list)

        elif bedingungstyp == "HAUPTDIAGNOSE IN TABELLE": # ICD IN TABELLE
            if not check_icd_conditions_at_all: return True
            table_ref = werte_str
            icd_codes_in_rule_table = {entry['Code'].upper() for entry in get_table_content(table_ref, "icd", tabellen_dict_by_table) if entry.get('Code')}
            if not icd_codes_in_rule_table: # Wenn Tabelle leer oder nicht gefunden
                 return False if provided_icds_upper else True # Nur erfüllt, wenn auch keine ICDs im Kontext sind
            return any(provided_icd in icd_codes_in_rule_table for provided_icd in provided_icds_upper)

        elif bedingungstyp == "GTIN" or bedingungstyp == "MEDIKAMENTE IN LISTE":
            werte_list_gtin = [w.strip() for w in str(werte_str).split(',') if w.strip()]
            if not werte_list_gtin: return True
            return any(req_gtin in provided_gtins for req_gtin in werte_list_gtin)

        elif bedingungstyp == "LKN" or bedingungstyp == "LEISTUNGSPOSITIONEN IN LISTE":
            werte_list_upper_lkn = [w.strip().upper() for w in str(werte_str).split(',') if w.strip()]
            if not werte_list_upper_lkn: return True
            return any(req_lkn in provided_lkns_upper for req_lkn in werte_list_upper_lkn)

        elif bedingungstyp == "GESCHLECHT IN LISTE": # Z.B. Werte: "Männlich,Weiblich"
            if werte_str: # Nur prüfen, wenn Regel einen Wert hat
                geschlechter_in_regel_lower = {g.strip().lower() for g in str(werte_str).split(',') if g.strip()}
                return provided_geschlecht_str in geschlechter_in_regel_lower
            return True # Wenn Regel keinen Wert hat, ist es für jedes Geschlecht ok

        elif bedingungstyp == "LEISTUNGSPOSITIONEN IN TABELLE" or bedingungstyp == "TARIFPOSITIONEN IN TABELLE":
            table_ref = werte_str
            lkn_codes_in_rule_table = {entry['Code'].upper() for entry in get_table_content(table_ref, "service_catalog", tabellen_dict_by_table) if entry.get('Code')}
            if not lkn_codes_in_rule_table: return False # Leere Tabelle kann nicht erfüllt werden, wenn LKNs im Kontext sind (implizit)
            return any(provided_lkn in lkn_codes_in_rule_table for provided_lkn in provided_lkns_upper)

        elif bedingungstyp == "PATIENTENBEDINGUNG": # Für Alter, Geschlecht (spezifisch)
            # feld_ref ist hier z.B. "Alter" oder "Geschlecht"
            # wert_regel_explizit ist der Wert aus der Spalte "Werte" der Bedingungstabelle
            # min_val_regel, max_val_regel sind MinWert/MaxWert aus der Bedingungstabelle
            if feld_ref == "Alter":
                if provided_alter is None: return False # Alter muss im Kontext sein
                try:
                    alter_patient = int(provided_alter); alter_ok = True
                    if min_val_regel is not None and alter_patient < int(min_val_regel): alter_ok = False
                    if max_val_regel is not None and alter_patient > int(max_val_regel): alter_ok = False
                    # Wenn weder Min noch Max, aber ein expliziter Wert in der Regel steht
                    if min_val_regel is None and max_val_regel is None and wert_regel_explizit is not None:
                        if alter_patient != int(wert_regel_explizit): alter_ok = False
                    return alter_ok
                except (ValueError, TypeError): return False
            elif feld_ref == "Geschlecht":
                 # Hier wird ein exakter String-Vergleich erwartet (z.B. Regelwert 'Männlich')
                 if isinstance(wert_regel_explizit, str):
                     return provided_geschlecht_str == wert_regel_explizit.strip().lower()
                 return False # Wenn Regelwert kein String ist
            else:
                logger.warning(
                    "WARNUNG (check_single PATIENTENBEDINGUNG): Unbekanntes Feld '%s'.",
                    feld_ref,
                )
                return True # Oder False, je nach gewünschtem Verhalten

        elif bedingungstyp == "ALTER IN JAHREN BEI EINTRITT":
            alter_eintritt = context.get("AlterBeiEintritt")
            if alter_eintritt is None:
                return False
            try:
                alter_val = int(alter_eintritt)
                regel_wert = int(werte_str)
                vergleichsoperator = condition.get("Vergleichsoperator")

                if vergleichsoperator == ">=":
                    return alter_val >= regel_wert
                elif vergleichsoperator == "<=":
                    return alter_val <= regel_wert
                elif vergleichsoperator == ">":
                    return alter_val > regel_wert
                elif vergleichsoperator == "<":
                    return alter_val < regel_wert
                elif vergleichsoperator == "=":
                    return alter_val == regel_wert
                elif vergleichsoperator == "!=":
                    return alter_val != regel_wert
                else:
                    logger.warning(
                        "WARNUNG (check_single ALTER BEI EINTRITT): Unbekannter Vergleichsoperator '%s'.",
                        vergleichsoperator,
                    )
                    return False
            except (ValueError, TypeError) as e_alter:
                logger.error(
                    "FEHLER (check_single ALTER BEI EINTRITT) Konvertierung: %s. Regelwert: '%s', Kontextwert: '%s'",
                    e_alter,
                    werte_str,
                    alter_eintritt,
                )
                return False

        elif bedingungstyp == "ANZAHL":
            if provided_anzahl is None: return False
            try:
                kontext_anzahl_val = int(provided_anzahl)
                regel_wert_anzahl_val = int(werte_str)
                vergleichsoperator = condition.get('Vergleichsoperator')

                if vergleichsoperator == ">=": return kontext_anzahl_val >= regel_wert_anzahl_val
                elif vergleichsoperator == "<=": return kontext_anzahl_val <= regel_wert_anzahl_val
                elif vergleichsoperator == ">": return kontext_anzahl_val > regel_wert_anzahl_val
                elif vergleichsoperator == "<": return kontext_anzahl_val < regel_wert_anzahl_val
                elif vergleichsoperator == "=": return kontext_anzahl_val == regel_wert_anzahl_val
                elif vergleichsoperator == "!=": return kontext_anzahl_val != regel_wert_anzahl_val
                else:
                    logger.warning(
                        "WARNUNG (check_single ANZAHL): Unbekannter Vergleichsoperator '%s'.",
                        vergleichsoperator,
                    )
                    return False
            except (ValueError, TypeError) as e_anzahl:
                logger.error(
                    "FEHLER (check_single ANZAHL) Konvertierung: %s. Regelwert: '%s', Kontextwert: '%s'",
                    e_anzahl,
                    werte_str,
                    provided_anzahl,
                )
                return False

        elif bedingungstyp == "SEITIGKEIT":
            # werte_str aus der Regel ist z.B. "'B'" oder "'E'"
            regel_wert_seitigkeit_norm = werte_str.strip().replace("'", "").lower()
            vergleichsoperator = condition.get('Vergleichsoperator')
            # provided_seitigkeit_str ist schon lower und hat Default 'unbekannt'

            if vergleichsoperator == "=":
                if regel_wert_seitigkeit_norm == 'b': return provided_seitigkeit_str == 'beidseits'
                elif regel_wert_seitigkeit_norm == 'e': return provided_seitigkeit_str in ['einseitig', 'links', 'rechts']
                elif regel_wert_seitigkeit_norm == 'l': return provided_seitigkeit_str == 'links'
                elif regel_wert_seitigkeit_norm == 'r': return provided_seitigkeit_str == 'rechts'
                else: return provided_seitigkeit_str == regel_wert_seitigkeit_norm # Direkter Vergleich
            elif vergleichsoperator == "!=":
                if regel_wert_seitigkeit_norm == 'b': return provided_seitigkeit_str != 'beidseits'
                elif regel_wert_seitigkeit_norm == 'e': return provided_seitigkeit_str not in ['einseitig', 'links', 'rechts']
                elif regel_wert_seitigkeit_norm == 'l': return provided_seitigkeit_str != 'links'
                elif regel_wert_seitigkeit_norm == 'r': return provided_seitigkeit_str != 'rechts'
                else: return provided_seitigkeit_str != regel_wert_seitigkeit_norm
            else:
                logger.warning(
                    "WARNUNG (check_single SEITIGKEIT): Unbekannter Vergleichsoperator '%s'.",
                    vergleichsoperator,
                )
                return False
        else:
            logger.warning(
                "WARNUNG (check_single): Unbekannter Pauschalen-Bedingungstyp '%s'. Wird als False angenommen.",
                bedingungstyp,
            )
            return False
    except Exception as e:
        logger.error(
            "FEHLER (check_single) für P: %s G: %s Typ: %s, Werte: %s: %s",
            pauschale_code_for_debug,
            gruppe_for_debug,
            bedingungstyp,
            werte_str,
            e,
        )
        traceback.print_exc()
        return False

def get_beschreibung_fuer_lkn_im_backend(lkn_code: str, leistungskatalog_dict: Dict, lang: str = 'de') -> str:
    details = leistungskatalog_dict.get(str(lkn_code).upper())
    if not details:
        return lkn_code
    return get_lang_field(details, 'Beschreibung', lang) or lkn_code

def get_beschreibung_fuer_icd_im_backend(
    icd_code: str,
    tabellen_dict_by_table: Dict,
    spezifische_icd_tabelle: str | None = None,
    lang: str = 'de'
) -> str:
    """Liefert die Beschreibung eines ICD-Codes in der gewünschten Sprache."""
    # Wenn eine spezifische Tabelle bekannt ist (z.B. aus der Bedingung), diese zuerst prüfen
    if spezifische_icd_tabelle:
        icd_entries_specific = get_table_content(spezifische_icd_tabelle, "icd", tabellen_dict_by_table, lang)
        for entry in icd_entries_specific:
            if entry.get('Code', '').upper() == icd_code.upper():
                return entry.get('Code_Text', icd_code)

    # Fallback: Suche in einer generellen Haupt-ICD-Tabelle, falls vorhanden und definiert
    # Du müsstest den Namen deiner Haupt-ICD-Tabelle hier eintragen, z.B. "icd10gm_codes"
    haupt_icd_tabelle_name = "icd_hauptkatalog" # Beispielname, anpassen!
    # print(f"DEBUG: Suche ICD {icd_code} in Haupttabelle {haupt_icd_tabelle_name}")
    icd_entries_main = get_table_content(haupt_icd_tabelle_name, "icd", tabellen_dict_by_table, lang)
    for entry in icd_entries_main:
        if entry.get('Code', '').upper() == icd_code.upper():
            return entry.get('Code_Text', icd_code)
            
    # print(f"DEBUG: ICD {icd_code} nicht in spezifischer oder Haupttabelle gefunden.")
    return icd_code # Wenn nirgends gefunden, Code selbst zurückgeben

def get_group_operator_for_pauschale(
    pauschale_code: str, bedingungen_data: List[Dict], default: str = DEFAULT_GROUP_OPERATOR
) -> str:
    """Liefert den Gruppenoperator (UND/ODER) fuer eine Pauschale."""
    for cond in bedingungen_data:
        if cond.get("Pauschale") == pauschale_code and "GruppenOperator" in cond:
            op = str(cond.get("GruppenOperator", "")).strip().upper()
            if op in ("UND", "ODER"):
                return op

    # Heuristik: Wenn keine explizite Angabe vorhanden ist, aber mehrere Gruppen
    # existieren und in der ersten Gruppe mindestens eine Zeile mit "ODER"
    # verknüpft ist, werten wir dies als globalen Gruppenoperator "ODER".
    first_group_id = None
    groups_seen: List[Any] = []
    first_group_has_oder = False
    for cond in bedingungen_data:
        if cond.get("Pauschale") != pauschale_code:
            continue
        grp = cond.get("Gruppe")
        if first_group_id is None:
            first_group_id = grp
        if grp not in groups_seen:
            groups_seen.append(grp)
        if grp == first_group_id:
            if str(cond.get("Operator", "")).strip().upper() == "ODER":
                first_group_has_oder = True

    if len(groups_seen) > 1 and first_group_has_oder:
        return "ODER"

    return default


def _evaluate_boolean_tokens(tokens: List[Any]) -> bool:
    """Evaluate a boolean expression represented as tokens.

    Parameters
    ----------
    tokens : list
        Sequence of tokens forming the expression. Each token is either
        ``True``/``False`` or one of the strings ``"AND"``, ``"OR"``,
        ``"("`` or ``")``.

    Returns
    -------
    bool
        Result of the evaluated boolean expression.

    Notes
    -----
    The implementation uses a simplified shunting-yard algorithm to
    transform the infix expression into Reverse Polish Notation before
    evaluation.

    Examples
    --------
    >>> _evaluate_boolean_tokens([True, "AND", False])
    False
    >>> _evaluate_boolean_tokens(["(", True, "OR", False, ")", "AND", True])
    True
    """
    precedence = {"AND": 2, "OR": 1}
    output: List[Any] = []
    op_stack: List[str] = []

    for tok in tokens:
        if isinstance(tok, bool):
            output.append(tok)
        elif tok in ("AND", "OR"):
            while op_stack and op_stack[-1] in ("AND", "OR") and precedence[op_stack[-1]] >= precedence[tok]:
                output.append(op_stack.pop())
            op_stack.append(tok)
        elif tok == "(":
            op_stack.append(tok)
        elif tok == ")":
            while op_stack and op_stack[-1] != "(":
                output.append(op_stack.pop())
            if not op_stack:
                raise ValueError("Unmatched closing parenthesis")
            op_stack.pop()
        else:
            raise ValueError(f"Unknown token {tok}")

    while op_stack:
        op = op_stack.pop()
        if op == "(":
            raise ValueError("Unmatched opening parenthesis")
        output.append(op)

    stack: List[bool] = []
    for tok in output:
        if isinstance(tok, bool):
            stack.append(tok)
        else:
            if len(stack) < 2:
                raise ValueError("Insufficient operands")
            b = stack.pop()
            a = stack.pop()
            stack.append(a and b if tok == "AND" else a or b)

    if len(stack) != 1:
        raise ValueError("Invalid boolean expression")
    return stack[0]

# === FUNKTION ZUR AUSWERTUNG DER STRUKTURIERTEN LOGIK (UND/ODER) ===
def evaluate_structured_conditions(
    pauschale_code: str,
    context: Dict,
    pauschale_bedingungen_data: List[Dict],
    tabellen_dict_by_table: Dict[str, List[Dict]],
    # group_operator: str = DEFAULT_GROUP_OPERATOR, # This parameter is no longer used directly as AST defines inter-group logic
    debug: bool = False,
) -> bool:
    """Prüft die UND/ODER-Bedingungen einer Pauschale unter Berücksichtigung von AST VERBINDUNGSOPERATOR.
    """
    PAUSCHALE_KEY = 'Pauschale'
    GRUPPE_KEY = 'Gruppe'
    OPERATOR_KEY = 'Operator'
    EBENE_KEY = 'Ebene'
    BED_ID_KEY = 'BedingungsID'
    BED_TYP_KEY = 'Bedingungstyp'
    AST_VERBINDUNGSOPERATOR_TYPE = "AST VERBINDUNGSOPERATOR"

    # Hilfsfunktion zur Auswertung der Logik *innerhalb* eines einzelnen logischen Blocks
    def _evaluate_intra_block_logic(
        conditions_in_block: List[Dict],
        block_debug_id: Any
        ) -> bool:
        if not conditions_in_block:
            if debug: logger.info("DEBUG Intra-Block %s: Leer, evaluiert zu True (Standard für leere Bedingungsliste)", block_debug_id)
            return True

        sorted_conditions_for_block = sorted(
            conditions_in_block,
            key=lambda c: (c.get(EBENE_KEY, 1), c.get(BED_ID_KEY, 0))
        )

        baseline_level_block = 1
        first_level_block = sorted_conditions_for_block[0].get(EBENE_KEY, 1)
        first_res_block = check_single_condition(
            sorted_conditions_for_block[0], context, tabellen_dict_by_table
        )
        tokens_block: List[Any] = ["("] * (first_level_block - baseline_level_block)
        tokens_block.append(bool(first_res_block))
        prev_level_block = first_level_block

        for cond_idx in range(1, len(sorted_conditions_for_block)):
            current_cond = sorted_conditions_for_block[cond_idx]
            linking_op = sorted_conditions_for_block[cond_idx -1].get(OPERATOR_KEY, "UND").upper()
            cur_level_block = current_cond.get(EBENE_KEY, baseline_level_block)

            if cur_level_block < prev_level_block:
                tokens_block.extend(")" for _ in range(prev_level_block - cur_level_block))

            tokens_block.append("AND" if linking_op == "UND" else "OR")

            if cur_level_block > prev_level_block:
                tokens_block.extend("(" for _ in range(cur_level_block - prev_level_block))

            cur_res_block = check_single_condition(current_cond, context, tabellen_dict_by_table)
            tokens_block.append(bool(cur_res_block))
            prev_level_block = cur_level_block

        tokens_block.extend(")" for _ in range(prev_level_block - baseline_level_block))

        expr_str_block = "".join(
            str(t).lower() if isinstance(t, bool) else (" and " if t == "AND" else " or " if t == "OR" else t)
            for t in tokens_block
        )
        try:
            block_result = _evaluate_boolean_tokens(tokens_block)
            if debug:
                logger.info("DEBUG Intra-Block %s (Bedingungen: %s): '%s' => %s",
                            block_debug_id,
                            [c.get(BED_ID_KEY) for c in sorted_conditions_for_block],
                            expr_str_block,
                            block_result)
            return block_result
        except Exception as e_eval_intra_block:
            logger.error(
                "FEHLER bei Intra-Block-Logik (Pauschale: %s, Block beginnend mit Gruppe ca. %s) '%s': %s",
                pauschale_code, block_debug_id, expr_str_block, e_eval_intra_block,
            )
            traceback.print_exc()
            return False

    all_conditions_for_pauschale = sorted(
        [cond for cond in pauschale_bedingungen_data if cond.get(PAUSCHALE_KEY) == pauschale_code],
        key=lambda c: (c.get(GRUPPE_KEY, 0), c.get(BED_ID_KEY, 0))
    )

    if not all_conditions_for_pauschale:
        return True

    evaluated_block_results: List[bool] = []
    inter_block_operators: List[str] = []
    current_block_sub_conditions: List[Dict] = []
    current_block_first_gruppe_id_for_debug = None

    for i, condition in enumerate(all_conditions_for_pauschale):
        cond_type = str(condition.get(BED_TYP_KEY, "")).upper()

        if cond_type == AST_VERBINDUNGSOPERATOR_TYPE:
            if current_block_sub_conditions:
                block_res = _evaluate_intra_block_logic(current_block_sub_conditions, current_block_first_gruppe_id_for_debug)
                evaluated_block_results.append(block_res)
                current_block_sub_conditions = []
                current_block_first_gruppe_id_for_debug = None

            if evaluated_block_results:
                op_value = str(condition.get(OPERATOR_KEY, DEFAULT_GROUP_OPERATOR)).upper()
                inter_block_operators.append(op_value if op_value in ("UND", "ODER") else DEFAULT_GROUP_OPERATOR)
                if debug:
                    logger.info("DEBUG Pauschale %s: AST Operator '%s' (aus Gruppe %s, BedID %s) zur Verknüpfungsliste hinzugefügt.",
                                pauschale_code, inter_block_operators[-1], condition.get(GRUPPE_KEY), condition.get(BED_ID_KEY))
            elif debug:
                 logger.info("DEBUG Pauschale %s: AST Operator '%s' (Gruppe %s, BedID %s) am Anfang ignoriert, da kein vorheriger Block existiert.",
                             pauschale_code, condition.get(OPERATOR_KEY), condition.get(GRUPPE_KEY), condition.get(BED_ID_KEY))
        else:
            if not current_block_sub_conditions:
                current_block_first_gruppe_id_for_debug = condition.get(GRUPPE_KEY)
            current_block_sub_conditions.append(condition)

    if current_block_sub_conditions:
        block_res = _evaluate_intra_block_logic(current_block_sub_conditions, current_block_first_gruppe_id_for_debug)
        evaluated_block_results.append(block_res)

    if not evaluated_block_results:
        if debug:
            logger.info("DEBUG Pauschale %s: Keine auswertbaren Blöcke (reguläre Bedingungen) gefunden.", pauschale_code)
        return False

    final_pauschale_result = evaluated_block_results[0]

    if debug:
         logger.info(
             "DEBUG Pauschale %s: Start-Ergebnis (aus erstem Block) = %s. "
             "Gesammelte Inter-Block-Operatoren: %s. Alle Block-Ergebnisse: %s",
             pauschale_code,
             final_pauschale_result,
             inter_block_operators,
             evaluated_block_results
         )

    expected_ops_count = len(evaluated_block_results) - 1 if len(evaluated_block_results) > 0 else 0

    if len(inter_block_operators) != expected_ops_count:
        logger.warning(
            "WARNUNG Pauschale %s: Inkonsistenz bei der Verknüpfung von Blöcken. "
            "Erwartet %s Inter-Block-Operatoren für %s Ergebnisblöcke, aber %s Operatoren gefunden. "
            "Operatoren: %s, Ergebnisse: %s. Die Regeldefinition könnte fehlerhaft sein. "
            "Die Pauschale wird als FALSCH bewertet.",
            pauschale_code, expected_ops_count, len(evaluated_block_results),
            len(inter_block_operators), inter_block_operators, evaluated_block_results
        )
        return False

    for i in range(len(inter_block_operators)):
        operator = inter_block_operators[i]
        next_block_result = evaluated_block_results[i+1]

        if debug:
            logger.info(
                "DEBUG Pauschale %s: Verknüpfe (aktuelles Ergebnis = %s) mit Operator '%s' und (nächstes Block-Ergebnis = %s)",
                pauschale_code, final_pauschale_result, operator, next_block_result
            )

        if operator == "ODER":
            final_pauschale_result = final_pauschale_result or next_block_result
        else:
            final_pauschale_result = final_pauschale_result and next_block_result

        if debug:
            logger.info("DEBUG Pauschale %s: Neues Zwischenergebnis = %s", pauschale_code, final_pauschale_result)

    if debug:
        logger.info(
            "DEBUG Finales Ergebnis Pauschale %s: %s",
            pauschale_code,
            final_pauschale_result,
        )

    return final_pauschale_result

# === PRUEFUNG DER BEDINGUNGEN (STRUKTURIERTES RESULTAT) ===
def check_pauschale_conditions(
    pauschale_code: str,
    context: dict,
    pauschale_bedingungen_data: list[dict],
    tabellen_dict_by_table: Dict[str, List[Dict]],
    # leistungskatalog_dict für Beschreibungen hinzugefügt
    leistungskatalog_dict: Dict[str, Dict[str, Any]],
    lang: str = "de"
) -> Dict[str, Any]: # Gibt jetzt Dict mit html, errors, trigger_lkn_condition_met zurück
    """
    Prueft alle Bedingungen einer Pauschale und generiert strukturiertes HTML.
    """
    PAUSCHALE_KEY = "Pauschale"
    BED_TYP_KEY = "Bedingungstyp"
    BED_ID_KEY = "BedingungsID"
    GRUPPE_KEY = "Gruppe"
    OPERATOR_KEY = "Operator" # Für UND/ODER Logik innerhalb der Gruppe
    BED_WERTE_KEY = "Werte"
    BED_FELD_KEY = "Feld"
    BED_MIN_KEY = "MinWert"
    BED_MAX_KEY = "MaxWert"
    BED_VERGLEICHSOP_KEY = "Vergleichsoperator"


    conditions_for_pauschale = [
        c for c in pauschale_bedingungen_data
        if c.get(PAUSCHALE_KEY) == pauschale_code
        and str(c.get(BED_TYP_KEY, "")).upper() != "AST VERBINDUNGSOPERATOR"
    ]

    if not conditions_for_pauschale:
        return {"html": f"<p><i>{translate('no_conditions_for_pauschale', lang)}</i></p>", "errors": [], "trigger_lkn_condition_met": False}

    # Bedingungen nach Gruppe sortieren und dann nach BedingungsID
    sorted_conditions = sorted(
        conditions_for_pauschale,
        key=lambda x: (x.get(GRUPPE_KEY, float("inf")), x.get(BED_ID_KEY, 0))
    )

    html_parts = []
    current_group = None
    trigger_lkn_condition_overall_met = False # Für das Resultat der Funktion

    for i, cond_data in enumerate(sorted_conditions):
        group_val = cond_data.get(GRUPPE_KEY)
        if group_val != current_group:
            if current_group is not None: # Schließe vorherige Gruppe ab
                html_parts.append("</div>") # condition-group
            current_group = group_val
            group_title = f"{translate('condition_group', lang)} {escape(str(current_group))}"
            html_parts.append(f"<div class=\"condition-group\"><div class=\"condition-group-title\">{group_title}</div>")

        # Intra-Gruppen Operator (ODER-Trenner)
        # Ein ODER-Trenner wird angezeigt, wenn der Operator der *vorherigen* Bedingung in derselben Gruppe ODER war.
        # Die erste Bedingung einer Gruppe hat nie einen Trenner davor.
        if i > 0 and sorted_conditions[i-1].get(GRUPPE_KEY) == current_group:
            prev_cond_operator = str(sorted_conditions[i-1].get(OPERATOR_KEY, "UND")).upper()
            if prev_cond_operator == "ODER":
                html_parts.append(f"<div class=\"condition-separator\">{translate('OR', lang)}</div>")

        condition_met = check_single_condition(cond_data, context, tabellen_dict_by_table)

        # Überprüfen, ob eine LKN-basierte Bedingung erfüllt ist (für das Funktionsergebnis)
        cond_type_upper = str(cond_data.get(BED_TYP_KEY, "")).upper()
        if condition_met and cond_type_upper in [
            "LEISTUNGSPOSITIONEN IN LISTE", "LKN",
            "LEISTUNGSPOSITIONEN IN TABELLE", "TARIFPOSITIONEN IN TABELLE"
        ]:
            trigger_lkn_condition_overall_met = True


        icon_svg_path = "#icon-check" if condition_met else "#icon-cross"
        icon_class = "condition-icon-fulfilled" if condition_met else "condition-icon-not-fulfilled"

        # Bedingungstext formatieren
        translated_cond_type = translate_condition_type(cond_data.get(BED_TYP_KEY, "N/A"), lang)

        # Werte-Darstellung verbessern
        werte_display = ""
        # ... (Logik zur besseren Darstellung von Werten, siehe vorherige Implementierung von `generate_condition_detail_html`)
        # Für den Moment: einfache Darstellung
        original_werte = str(cond_data.get(BED_WERTE_KEY, ""))

        if cond_type_upper in ["LEISTUNGSPOSITIONEN IN LISTE", "LKN"]:
            lkn_codes = [l.strip().upper() for l in original_werte.split(',') if l.strip()]
            lkn_details_parts = []
            if lkn_codes:
                for lkn_c in lkn_codes:
                    # leistungskatalog_dict wird jetzt direkt an check_pauschale_conditions übergeben
                    desc = get_beschreibung_fuer_lkn_im_backend(lkn_c, leistungskatalog_dict, lang)
                    lkn_details_parts.append(f"<b>{escape(lkn_c)}</b> ({escape(desc)})")
                werte_display = ", ".join(lkn_details_parts)
            else:
                werte_display = f"<i>{translate('no_lkns_spec', lang)}</i>"

        elif cond_type_upper in ["LEISTUNGSPOSITIONEN IN TABELLE", "TARIFPOSITIONEN IN TABELLE"]:
            table_names_orig = [t.strip() for t in original_werte.split(',') if t.strip()]
            table_links_parts = []
            if table_names_orig:
                for table_name_o in table_names_orig:
                    table_content_entries = get_table_content(table_name_o, "service_catalog", tabellen_dict_by_table, lang)
                    entry_count = len(table_content_entries)
                    details_content_html = ""
                    if table_content_entries:
                        details_content_html = "<ul class='table-content-list'>"
                        for item in sorted(table_content_entries, key=lambda x: x.get('Code', '')):
                            item_code = item.get('Code', 'N/A')
                            item_text = get_beschreibung_fuer_lkn_im_backend(item_code, leistungskatalog_dict, lang)
                            details_content_html += f"<li><b>{escape(item_code)}</b>: {escape(item_text)}</li>"
                        details_content_html += "</ul>"

                    table_links_parts.append(
                        f"<details class='inline-table-details'>"
                        f"<summary><i>{escape(table_name_o)}</i> ({entry_count} {translate('entries_label', lang)})</summary>{details_content_html}</details>"
                    )
                werte_display = "".join(table_links_parts) # Join without comma for multiple details/summary
            else:
                werte_display = f"<i>{translate('no_table_name', lang)}</i>"

        elif cond_type_upper in ["HAUPTDIAGNOSE IN TABELLE", "ICD IN TABELLE"]: # Unified ICD Table Handling
            table_names_icd = [t.strip() for t in original_werte.split(',') if t.strip()]
            table_links_icd_parts = []
            if table_names_icd:
                for table_name_i in table_names_icd:
                    # Hier 'icd' als table_type verwenden
                    table_content_entries_icd = get_table_content(table_name_i, "icd", tabellen_dict_by_table, lang)
                    entry_count_icd = len(table_content_entries_icd)
                    details_content_html_icd = ""
                    if table_content_entries_icd:
                        details_content_html_icd = "<ul class='table-content-list'>"
                        # ICDs haben typischerweise 'Code' und 'Code_Text'
                        for item_icd in sorted(table_content_entries_icd, key=lambda x: x.get('Code', '')):
                            item_code_icd = item_icd.get('Code', 'N/A')
                            # Für ICDs ist die Beschreibung oft direkt im Eintrag als 'Code_Text'
                            item_text_icd = item_icd.get('Code_Text', get_beschreibung_fuer_icd_im_backend(item_code_icd, tabellen_dict_by_table, spezifische_icd_tabelle=table_name_i, lang=lang))
                            details_content_html_icd += f"<li><b>{escape(item_code_icd)}</b>: {escape(item_text_icd)}</li>"
                        details_content_html_icd += "</ul>"

                    table_links_icd_parts.append(
                        f"<details class='inline-table-details'>"
                        f"<summary><i>{escape(table_name_i)}</i> ({entry_count_icd} {translate('entries_label', lang)})</summary>{details_content_html_icd}</details>"
                    )
                werte_display = "".join(table_links_icd_parts) # Join without comma
            else:
                werte_display = f"<i>{translate('no_table_name', lang)}</i>"

        elif cond_type_upper in ["ICD", "HAUPTDIAGNOSE IN LISTE"]: # ICD in List (existing logic)
            icd_codes_list = [icd.strip().upper() for icd in original_werte.split(',') if icd.strip()]
            icd_details_parts = []
            if icd_codes_list:
                for icd_c in icd_codes_list:
                    # Annahme: tabellen_dict_by_table ist im context oder global
                    desc_icd = get_beschreibung_fuer_icd_im_backend(icd_c, tabellen_dict_by_table, lang=lang)
                    icd_details_parts.append(f"<b>{escape(icd_c)}</b> ({escape(desc_icd)})")
                werte_display = ", ".join(icd_details_parts)
            else:
                 werte_display = f"<i>{translate('no_icds_spec', lang)}</i>"

        elif cond_type_upper == "PATIENTENBEDINGUNG":
            feld_name_pat = str(cond_data.get(BED_FELD_KEY, "")).capitalize()
            min_w_pat = cond_data.get(BED_MIN_KEY)
            max_w_pat = cond_data.get(BED_MAX_KEY)
            expl_wert_pat = cond_data.get(BED_WERTE_KEY)

            if feld_name_pat.lower() == "alter":
                if min_w_pat is not None or max_w_pat is not None:
                    val_disp = []
                    if min_w_pat is not None: val_disp.append(f"{translate('min', lang)} {escape(str(min_w_pat))}")
                    if max_w_pat is not None: val_disp.append(f"{translate('max', lang)} {escape(str(max_w_pat))}")
                    werte_display = " ".join(val_disp)
                else:
                    werte_display = escape(str(expl_wert_pat))
            else: # z.B. Geschlecht
                werte_display = escape(str(expl_wert_pat))
            translated_cond_type = translate('patient_condition_display', lang, field=escape(feld_name_pat))

        elif cond_type_upper == "ALTER IN JAHREN BEI EINTRITT":
            op_val = cond_data.get(BED_VERGLEICHSOP_KEY, "=")
            werte_display = f"{escape(op_val)} {escape(original_werte)}"

        elif cond_type_upper == "ANZAHL":
            op_val_anz = cond_data.get(BED_VERGLEICHSOP_KEY, "=")
            werte_display = f"{escape(op_val_anz)} {escape(original_werte)}"

        elif cond_type_upper == "SEITIGKEIT":
            op_val_seit = cond_data.get(BED_VERGLEICHSOP_KEY, "=")
            # Normalisiere Regelwert für Anzeige
            regel_wert_seit_norm_disp = original_werte.strip().replace("'", "").lower()
            if regel_wert_seit_norm_disp == 'b': regel_wert_seit_norm_disp = translate('bilateral', lang)
            elif regel_wert_seit_norm_disp == 'e': regel_wert_seit_norm_disp = translate('unilateral', lang)
            elif regel_wert_seit_norm_disp == 'l': regel_wert_seit_norm_disp = translate('left', lang)
            elif regel_wert_seit_norm_disp == 'r': regel_wert_seit_norm_disp = translate('right', lang)
            werte_display = f"{escape(op_val_seit)} {escape(regel_wert_seit_norm_disp)}"

        elif cond_type_upper == "GESCHLECHT IN LISTE":
            gender_list = [g.strip().lower() for g in original_werte.split(',') if g.strip()]
            translated_genders = [translate(g, lang) for g in gender_list]
            werte_display = escape(", ".join(translated_genders))

        else: # Fallback für andere Typen
            werte_display = escape(original_werte)

        # Kontext-Info für erfüllte Bedingungen
        context_match_info_html = ""
        if condition_met:
            match_details = [] # Hier Details sammeln, was genau zum Match geführt hat
            # Beispiel für ICD:
            if cond_type_upper == "ICD" or cond_type_upper == "HAUPTDIAGNOSE IN LISTE":
                provided_icds_upper = {p_icd.upper() for p_icd in context.get("ICD", []) if p_icd}
                required_icds_in_rule_list = {w.strip().upper() for w in str(cond_data.get(BED_WERTE_KEY, "")).split(',') if w.strip()}
                matching_icds = list(provided_icds_upper.intersection(required_icds_in_rule_list))
                if matching_icds:
                    match_details.append(f"{translate('fulfilled_by_icd', lang)}: {', '.join(matching_icds)}")
            # LKN in Liste
            elif cond_type_upper in ["LKN", "LEISTUNGSPOSITIONEN IN LISTE"]:
                provided_lkns_upper = {p_lkn.upper() for p_lkn in context.get("LKN", []) if p_lkn}
                required_lkns_in_rule_list = {w.strip().upper() for w in str(cond_data.get(BED_WERTE_KEY, "")).split(',') if w.strip()}
                matching_lkns = list(provided_lkns_upper.intersection(required_lkns_in_rule_list))
                if matching_lkns:
                    match_details.append(f"{translate('fulfilled_by_lkn', lang)}: {', '.join(matching_lkns)}")
            # LKN in Tabelle
            elif cond_type_upper in ["LEISTUNGSPOSITIONEN IN TABELLE", "TARIFPOSITIONEN IN TABELLE"]:
                provided_lkns_upper = {p_lkn.upper() for p_lkn in context.get("LKN", []) if p_lkn}
                table_ref = cond_data.get(BED_WERTE_KEY, "")
                lkn_codes_in_rule_table = {entry['Code'].upper() for entry in get_table_content(table_ref, "service_catalog", tabellen_dict_by_table) if entry.get('Code')}
                matching_lkns = list(provided_lkns_upper.intersection(lkn_codes_in_rule_table))
                if matching_lkns:
                    match_details.append(f"{translate('fulfilled_by_lkn_in_table', lang, table=escape(table_ref))}: {', '.join(matching_lkns)}")
            # ICD in Tabelle
            elif cond_type_upper == "HAUPTDIAGNOSE IN TABELLE": # ICD IN TABELLE
                if context.get("useIcd", True):
                    provided_icds_upper = {p_icd.upper() for p_icd in context.get("ICD", []) if p_icd}
                    table_ref_icd = cond_data.get(BED_WERTE_KEY, "")
                    icd_codes_in_rule_table = {entry['Code'].upper() for entry in get_table_content(table_ref_icd, "icd", tabellen_dict_by_table) if entry.get('Code')}
                    matching_icds = list(provided_icds_upper.intersection(icd_codes_in_rule_table))
                    if matching_icds:
                        match_details.append(f"{translate('fulfilled_by_icd_in_table', lang, table=escape(table_ref_icd))}: {', '.join(matching_icds)}")
                else:
                    match_details.append(f"({translate('icd_check_disabled', lang)})")

            # GTIN / Medikamente in Liste
            elif cond_type_upper in ["GTIN", "MEDIKAMENTE IN LISTE"]:
                provided_gtins = set(context.get("GTIN", []))
                required_gtins_in_rule_list = {w.strip() for w in str(cond_data.get(BED_WERTE_KEY, "")).split(',') if w.strip()}
                matching_gtins = list(provided_gtins.intersection(required_gtins_in_rule_list))
                if matching_gtins:
                    match_details.append(f"{translate('fulfilled_by_gtin', lang)}: {', '.join(matching_gtins)}")

            # Einfache Wertvergleiche
            elif cond_type_upper == "PATIENTENBEDINGUNG":
                feld_ref = cond_data.get(BED_FELD_KEY)
                if feld_ref == "Alter" and context.get("Alter") is not None:
                     match_details.append(f"{translate('context_age', lang)}: {context.get('Alter')}")
                elif feld_ref == "Geschlecht" and context.get("Geschlecht"):
                     match_details.append(f"{translate('context_gender', lang)}: {context.get('Geschlecht')}")
            elif cond_type_upper == "ALTER IN JAHREN BEI EINTRITT" and context.get("AlterBeiEintritt") is not None:
                match_details.append(f"{translate('context_age_at_entry', lang)}: {context.get('AlterBeiEintritt')}")
            elif cond_type_upper == "ANZAHL" and context.get("Anzahl") is not None:
                 match_details.append(f"{translate('context_quantity', lang)}: {context.get('Anzahl')}")
            elif cond_type_upper == "SEITIGKEIT" and context.get("Seitigkeit"):
                 match_details.append(f"{translate('context_laterality', lang)}: {context.get('Seitigkeit')}")
            elif cond_type_upper == "GESCHLECHT IN LISTE" and context.get("Geschlecht"):
                 match_details.append(f"{translate('context_gender', lang)}: {context.get('Geschlecht')}")


            if match_details:
                context_match_info_html = f"<span class=\"context-match-info fulfilled\">({'; '.join(match_details)})</span>"
            else: # Fallback, falls keine spezifischen Details gesammelt wurden, aber Bedingung erfüllt ist
                context_match_info_html = f"<span class=\"context-match-info fulfilled\">({translate('condition_met_context_generic', lang)})</span>"


        html_parts.append(f"""
            <div class="condition-item-row">
                <span class="condition-status-icon {icon_class}">
                    <svg viewBox="0 0 24 24"><use xlink:href="{icon_svg_path}"></use></svg>
                </span>
                <span class="condition-type-display">{escape(translated_cond_type)}:</span>
                <span class="condition-text-wrapper">{werte_display} {context_match_info_html}</span>
            </div>
        """)

    if current_group is not None: # Letzte Gruppe abschließen
        html_parts.append("</div>") # condition-group

    # Rückgabe als Dictionary, um konsistent mit der vorherigen Struktur zu sein,
    # die möglicherweise auch Fehler oder andere Infos zurückgeben könnte.
    return {
        "html": "".join(html_parts),
        "errors": [], # Vorerst keine Fehlerbehandlung hier, kann erweitert werden
        "trigger_lkn_condition_met": trigger_lkn_condition_overall_met
    }

# === RENDERER FUER CONDITION-ERGEBNISSE (WIRD NICHT MEHR DIREKT VERWENDET, LOGIK IST IN check_pauschale_conditions) ===
def render_condition_results_html(
    results: List[Dict[str, Any]], # results ist hier das Ergebnis von der alten check_pauschale_conditions
    lang: str = "de"
) -> str:
    """Wandelt die von der *alten* `check_pauschale_conditions` gelieferten Ergebnisse in HTML um.
       Diese Funktion wird für die neue HTML-Struktur nicht mehr direkt benötigt.
       Die Logik zur HTML-Erstellung ist jetzt in der neuen `check_pauschale_conditions`.
    """
    # Diese Funktion ist jetzt veraltet für die neue Anforderung der strukturierten HTML-Ausgabe.
    # Sie könnte für Debugging-Zwecke oder eine sehr einfache Darstellung beibehalten werden.
    # Für die Aufgabe hier, die CSS-Klassen zu implementieren, wird sie nicht verwendet.
    logger.warning("render_condition_results_html wird aufgerufen, ist aber für die neue HTML-Struktur veraltet.")
    html_parts = ["<ul class='legacy-condition-list'>"] # Hinweis auf veraltete Liste
    for item in results: # 'results' hier ist die Liste von Dictionaries mit 'erfuellt', 'Bedingungstyp', 'Werte'
        icon_text = "&#10003;" if item.get("erfuellt") else "&#10007;"
        typ_text = escape(str(item.get("Bedingungstyp", "")))
        wert_text = escape(str(item.get("Werte", "")))
        html_parts.append(f"<li>{icon_text} {typ_text}: {wert_text}</li>")
    html_parts.append("</ul>")
    return "".join(html_parts)


# --- Ausgelagerte Pauschalen-Ermittlung ---
def determine_applicable_pauschale(
    user_input: str, # Bleibt für potenzielles LLM-Ranking, aktuell nicht primär genutzt
    rule_checked_leistungen: list[dict], # Für die initiale Findung potenzieller Pauschalen
    context: dict, # Enthält LKN, ICD, Alter, Geschlecht, Seitigkeit, Anzahl, useIcd
    pauschale_lp_data: List[Dict],
    pauschale_bedingungen_data: List[Dict],
    pauschalen_dict: Dict[str, Dict], # Dict aller Pauschalen {code: details}
    leistungskatalog_dict: Dict[str, Dict], # Für LKN-Beschreibungen etc.
    tabellen_dict_by_table: Dict[str, List[Dict]], # Für Tabellen-Lookups
    potential_pauschale_codes_input: Set[str] | None = None, # Optional vorabgefilterte Codes
    lang: str = 'de',
    debug: bool = False
    ) -> dict:
    """Finde die bestmögliche Pauschale anhand der Regeln.

    Parameters
    ----------
    user_input : str
        Ursprüngliche Benutzereingabe (nur zu Loggingzwecken).
    rule_checked_leistungen : list[dict]
        Bereits regelgeprüfte Leistungen.
    context : dict
        Kontextdaten wie LKN, ICD, Alter oder Seitigkeit.
    pauschale_lp_data : list[dict]
        Zuordnung von LKN zu Pauschalen.
    pauschale_bedingungen_data : list[dict]
        Detaillierte Bedingungsdefinitionen.
    pauschalen_dict : dict
        Stammdaten aller Pauschalen.
    leistungskatalog_dict : dict
        LKN-Katalog für Beschreibungen.
    tabellen_dict_by_table : dict
        Inhalte referenzierter Tabellen.
    potential_pauschale_codes_input : set[str], optional
        Vorab festgelegte Kandidaten. Wird ``None`` übergeben, ermittelt die
        Funktion mögliche Codes aus den Kontext-LKN.
    lang : str, optional
        Sprache der Ausgaben, Standard ``"de"``.

    Returns
    -------
    dict
        Ergebnis mit ausgewählter Pauschale, Erklärungs-HTML und allen
        bewerteten Kandidaten.

    Notes
    -----
    Zunächst werden anhand der LKN sowie der Bedingungsdefinitionen mögliche
    Kandidaten gesammelt. Für jeden Code wird
    :func:`evaluate_structured_conditions` aufgerufen. Aus den gültigen
    Pauschalen wird der Kandidat mit dem höchsten Score (Taxpunkte) und dem
    niedrigsten Buchstabensuffix gewählt.

    Examples
    --------
    >>> result = determine_applicable_pauschale(
    ...     "",
    ...     rule_checked_leistungen,
    ...     {"LKN": ["C04.51B"], "Seitigkeit": "re"},
    ...     lp_data,
    ...     bedingungen,
    ...     pauschalen,
    ...     leistungskatalog,
    ...     tabellen,
    ... )
    >>> result["type"]
    'Pauschale'
    """
    logger.info("INFO: Starte Pauschalenermittlung mit strukturierter Bedingungsprüfung...")
    PAUSCHALE_ERKLAERUNG_KEY = 'pauschale_erklaerung_html'; POTENTIAL_ICDS_KEY = 'potential_icds'
    LKN_KEY_IN_RULE_CHECKED = 'lkn'; PAUSCHALE_KEY_IN_PAUSCHALEN = 'Pauschale' # In PAUSCHALEN_Pauschalen
    PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN = 'Pauschale_Text'
    LP_LKN_KEY = 'Leistungsposition'; LP_PAUSCHALE_KEY = 'Pauschale' # In PAUSCHALEN_Leistungspositionen
    BED_PAUSCHALE_KEY = 'Pauschale'; BED_TYP_KEY = 'Bedingungstyp' # In PAUSCHALEN_Bedingungen
    BED_WERTE_KEY = 'Werte'

    potential_pauschale_codes: Set[str] = set()
    if potential_pauschale_codes_input is not None:
        potential_pauschale_codes = potential_pauschale_codes_input
        logger.info(
            "DEBUG: Verwende übergebene potenzielle Pauschalen: %s",
            potential_pauschale_codes,
        )
    else:
        logger.info("DEBUG: Suche potenzielle Pauschalen (da nicht übergeben)...")
        # LKNs aus dem Kontext (regelkonform + gemappt) für die Suche verwenden
        context_lkns_for_search = {str(lkn).upper() for lkn in context.get("LKN", []) if lkn}
        # print(f"  Kontext-LKNs für Suche: {context_lkns_for_search}")

        # Methode a: Direkte Links aus PAUSCHALEN_Leistungspositionen
        for item in pauschale_lp_data:
            lkn_in_lp = item.get(LP_LKN_KEY)
            if lkn_in_lp and lkn_in_lp.upper() in context_lkns_for_search:
                pc = item.get(LP_PAUSCHALE_KEY)
                if pc and pc in pauschalen_dict: potential_pauschale_codes.add(pc)
        # print(f"  Potenzielle Pauschalen nach Methode a: {potential_pauschale_codes}")

        # Methode b & c: LKNs in Bedingungen (Liste oder Tabelle)
        # Cache für Tabellenzugehörigkeit von Kontext-LKNs
        context_lkns_in_tables_cache: Dict[str, Set[str]] = {}

        for cond in pauschale_bedingungen_data:
            pc = cond.get(BED_PAUSCHALE_KEY)
            if not (pc and pc in pauschalen_dict): continue # Nur für existierende Pauschalen

            bedingungstyp_cond = cond.get(BED_TYP_KEY, "").upper()
            werte_cond = cond.get(BED_WERTE_KEY, "")

            if bedingungstyp_cond == "LEISTUNGSPOSITIONEN IN LISTE" or bedingungstyp_cond == "LKN":
                werte_liste_cond = {w.strip().upper() for w in str(werte_cond).split(',') if w.strip()}
                if not context_lkns_for_search.isdisjoint(werte_liste_cond): # Schnittmenge nicht leer
                    potential_pauschale_codes.add(pc)

            elif bedingungstyp_cond == "LEISTUNGSPOSITIONEN IN TABELLE" or bedingungstyp_cond == "TARIFPOSITIONEN IN TABELLE":
                table_refs_cond = {t.strip().lower() for t in str(werte_cond).split(',') if t.strip()}
                for lkn_ctx in context_lkns_for_search:
                    if lkn_ctx not in context_lkns_in_tables_cache:
                        tables_for_lkn_ctx = set()
                        for table_name_key_norm, table_entries in tabellen_dict_by_table.items():
                            for entry in table_entries:
                                if entry.get('Code', '').upper() == lkn_ctx and \
                                   entry.get('Tabelle_Typ', '').lower() == "service_catalog":
                                    tables_for_lkn_ctx.add(table_name_key_norm) # Bereits normalisiert (lower)
                        context_lkns_in_tables_cache[lkn_ctx] = tables_for_lkn_ctx
                    
                    if not table_refs_cond.isdisjoint(context_lkns_in_tables_cache[lkn_ctx]):
                        potential_pauschale_codes.add(pc)
                        break # Ein Treffer für diese Bedingung reicht
        logger.info(
            "DEBUG: Finale potenzielle Pauschalen nach LKN-basierter Suche: %s",
            potential_pauschale_codes,
        )


    if not potential_pauschale_codes:
        return {"type": "Error", "message": "Keine potenziellen Pauschalen für die erbrachten Leistungen und den Kontext gefunden.", "evaluated_pauschalen": []}

    evaluated_candidates = []
    # print(f"INFO: Werte strukturierte Bedingungen für {len(potential_pauschale_codes)} potenzielle Pauschalen aus...")
    # print(f"  Kontext für evaluate_structured_conditions: {context}")
    for code in sorted(list(potential_pauschale_codes)): # Sortiert für konsistente Log-Reihenfolge
        if code not in pauschalen_dict:
            # print(f"  WARNUNG: Potenzieller Code {code} nicht in pauschalen_dict gefunden, überspringe.")
            continue
        
        is_pauschale_valid_structured = False
        bedingungs_html = ""
        if debug: logger.info("DEBUG: Prüfe Pauschale %s", code) # Log vor dem Aufruf
        start_time_eval = time.time()
        try:
            # grp_op = get_group_operator_for_pauschale(code, pauschale_bedingungen_data, default=DEFAULT_GROUP_OPERATOR) # No longer needed
            is_pauschale_valid_structured = evaluate_structured_conditions(
                code, context, pauschale_bedingungen_data, tabellen_dict_by_table, debug=debug # Removed grp_op, forward debug
            )
            end_time_eval = time.time()
            if debug: logger.info("DEBUG: Pauschale %s geprüft in %.4f Sekunden. Ergebnis: %s", code, end_time_eval - start_time_eval, is_pauschale_valid_structured)

            check_res = check_pauschale_conditions(
                code,
                context,
                pauschale_bedingungen_data,
                tabellen_dict_by_table,
                leistungskatalog_dict,
                lang,
            )
            bedingungs_html = check_res.get("html", "")
        except Exception as e_eval:
            logger.error(
                "FEHLER bei evaluate_structured_conditions für Pauschale %s: %s",
                code,
                e_eval,
            )
            traceback.print_exc()

        tp_raw = pauschalen_dict[code].get("Taxpunkte")
        try:
            tp_val = float(tp_raw) if tp_raw is not None else 0.0
        except (ValueError, TypeError):
            tp_val = 0.0

        evaluated_candidates.append({
            "code": code,
            "details": pauschalen_dict[code],
            "is_valid_structured": is_pauschale_valid_structured,
            "bedingungs_pruef_html": bedingungs_html,
            "taxpunkte": tp_val,
        })

    valid_candidates = [cand for cand in evaluated_candidates if cand["is_valid_structured"]]
    logger.info(
        "DEBUG: Struktur-gültige Kandidaten nach Prüfung: %s",
        [c["code"] for c in valid_candidates],
    )

    # Score pro gültigem Kandidaten berechnen (hier: Taxpunkte als Beispiel)
    for cand in valid_candidates:
        cand["score"] = cand.get("taxpunkte", 0)

    selected_candidate_info = None
    if valid_candidates:
        specific_valid_candidates = [c for c in valid_candidates if not str(c['code']).startswith('C9')]
        fallback_valid_candidates = [c for c in valid_candidates if str(c['code']).startswith('C9')]
        
        chosen_list_for_selection = []
        selection_type_message = ""

        if specific_valid_candidates:
            chosen_list_for_selection = specific_valid_candidates
            selection_type_message = "spezifischen"
        elif fallback_valid_candidates: # Nur wenn keine spezifischen gültig sind
            chosen_list_for_selection = fallback_valid_candidates
            selection_type_message = "Fallback (C9x)"
        
        if chosen_list_for_selection:
            logger.info(
                "INFO: Auswahl aus %s struktur-gültigen %s Kandidaten.",
                len(chosen_list_for_selection),
                selection_type_message,
            )

            # Score je Kandidat ermitteln (hier einfach Taxpunkte als Beispiel)
            for cand in chosen_list_for_selection:
                cand["score"] = cand.get("taxpunkte", 0)

            # Sortierung: Höchster Score zuerst, bei Gleichstand entscheidet nur der Buchstabensuffix
            def sort_key_score_suffix(candidate):
                code_str = str(candidate['code'])
                match = re.search(r"([A-Z])$", code_str)
                suffix_ord = ord(match.group(1)) if match else ord('Z') + 1
                return (-candidate.get("score", 0), suffix_ord)

            chosen_list_for_selection.sort(key=sort_key_score_suffix)
            selected_candidate_info = chosen_list_for_selection[0]
            logger.info(
                "INFO: Gewählte Pauschale nach Score-Sortierung: %s",
                selected_candidate_info["code"],
            )
            # print(f"   DEBUG: Sortierte Kandidatenliste ({selection_type_message}): {[c['code'] for c in chosen_list_for_selection]}")
        else:
             # Sollte nicht passieren, wenn valid_candidates nicht leer war, aber zur Sicherheit
             return {"type": "Error", "message": "Interner Fehler bei der Pauschalenauswahl (Kategorisierung fehlgeschlagen).", "evaluated_pauschalen": evaluated_candidates}
    else: # Keine valid_candidates (keine Pauschale hat die strukturierte Prüfung bestanden)
        logger.info("INFO: Keine Pauschale erfüllt die strukturierten Bedingungen.")
        # Erstelle eine informativere Nachricht, wenn potenzielle Kandidaten da waren
        if potential_pauschale_codes:
            # Hole die Namen der geprüften, aber nicht validen Pauschalen
            gepruefte_codes_namen = [f"{c['code']} ({get_lang_field(c['details'], PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A'})"
                                     for c in evaluated_candidates if not c['is_valid_structured']]
            msg_details = ""
            if gepruefte_codes_namen:
                msg_details = " Folgende potenziellen Pauschalen wurden geprüft, aber deren Bedingungen waren nicht erfüllt: " + ", ".join(gepruefte_codes_namen)

            return {"type": "Error", "message": f"Keine der potenziellen Pauschalen erfüllte die detaillierten UND/ODER-Bedingungen.{msg_details}", "evaluated_pauschalen": evaluated_candidates}
        else: # Sollte durch die Prüfung am Anfang von potential_pauschale_codes abgedeckt sein
            return {"type": "Error", "message": "Keine passende Pauschale gefunden (keine potenziellen Kandidaten).", "evaluated_pauschalen": evaluated_candidates}

    if not selected_candidate_info: # Doppelte Sicherheit
        return {"type": "Error", "message": "Interner Fehler: Keine Pauschale nach Auswahlprozess selektiert.", "evaluated_pauschalen": evaluated_candidates}

    best_pauschale_code = selected_candidate_info["code"]
    best_pauschale_details = selected_candidate_info["details"].copy() # Kopie für Modifikationen

    # Generiere HTML für die Bedingungsprüfung der ausgewählten Pauschale
    condition_errors_html_gen = [] # Initialize with an empty list
    try:
        condition_result_html_dict = check_pauschale_conditions(
            best_pauschale_code,
            context,
            pauschale_bedingungen_data,
            tabellen_dict_by_table,
            leistungskatalog_dict,
            lang
        )
        bedingungs_pruef_html_result = condition_result_html_dict.get("html", "<p class='error'>Fehler bei HTML-Generierung der Bedingungen.</p>")
        # Errors from check_pauschale_conditions itself (if any were designed to be returned, currently it's an empty list)
        condition_errors_html_gen.extend(condition_result_html_dict.get("errors", []))
    except Exception as e_html_gen:
        logger.error(
            "FEHLER bei Aufruf von check_pauschale_conditions (HTML-Generierung) für %s: %s",
            best_pauschale_code,
            e_html_gen,
        )
        traceback.print_exc()
        bedingungs_pruef_html_result = (
            f"<p class='error'>Schwerwiegender Fehler bei HTML-Generierung der Bedingungen: {escape(str(e_html_gen))}</p>"
        )
        condition_errors_html_gen = [f"Fehler HTML-Generierung: {e_html_gen}"]

    # Erstelle die Erklärung für die Pauschalenauswahl
    # Kontext-LKNs für die Erklärung (aus dem `context` Dictionary)
    lkns_fuer_erklaerung = [str(lkn) for lkn in context.get('LKN', []) if lkn]
    if lang == 'fr':
        pauschale_erklaerung_html = (
            f"<p>Sur la base du contexte (p.ex. LKN : {escape(', '.join(lkns_fuer_erklaerung) or 'aucun')}, "
            f"latéralité : {escape(str(context.get('Seitigkeit')))}, nombre : {escape(str(context.get('Anzahl')))}, "
            f"vérification ICD active : {context.get('useIcd', True)}) les forfaits suivants ont été vérifiés :</p>"
        )
    elif lang == 'it':
        pauschale_erklaerung_html = (
            f"<p>Sulla base del contesto (ad es. LKN: {escape(', '.join(lkns_fuer_erklaerung) or 'nessuna')}, "
            f"lateralità: {escape(str(context.get('Seitigkeit')))}, numero: {escape(str(context.get('Anzahl')))}, "
            f"verifica ICD activa: {context.get('useIcd', True)}) sono stati verificati i seguenti forfait:</p>"
        )
    else:
        pauschale_erklaerung_html = (
            f"<p>Basierend auf dem Kontext (u.a. LKNs: {escape(', '.join(lkns_fuer_erklaerung) or 'keine')}, "
            f"Seitigkeit: {escape(str(context.get('Seitigkeit')))}, Anzahl: {escape(str(context.get('Anzahl')))}, "
            f"ICD-Prüfung aktiv: {context.get('useIcd', True)}) wurden folgende Pauschalen geprüft:</p>"
        )
    
    # Liste aller potenziell geprüften Pauschalen (vor der Validierung)
    pauschale_erklaerung_html += "<ul>"
    for cand_eval in sorted(evaluated_candidates, key=lambda x: x['code']):
        if cand_eval['is_valid_structured']:
            status = translate('conditions_met', lang)
            status_text = f"<span style=\"color:green;\">{status}</span>"
        else:
            status = translate('conditions_not_met', lang)
            status_text = f"<span style=\"color:red;\">{status}</span>"
        code_str = escape(cand_eval['code'])
        link = f"<a href='#' class='pauschale-exp-link' data-code='{code_str}'>{code_str}</a>"
        pauschale_erklaerung_html += (
            f"<li><b>{link}</b>: "
            f"{escape(get_lang_field(cand_eval['details'], PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A')} "
            f"{status_text}</li>"
        )
    pauschale_erklaerung_html += "</ul>"
    
    if lang == 'fr':
        pauschale_erklaerung_html += (
            f"<p><b>Choix : {escape(best_pauschale_code)}</b> "
            f"({escape(get_lang_field(best_pauschale_details, PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A')}) - "
            "comme forfait avec la lettre suffixe la plus basse (p. ex. A avant B) parmi les candidats valides "
            "de la catégorie privilégiée (forfaits spécifiques avant forfaits de secours C9x).</p>"
        )
    elif lang == 'it':
        pauschale_erklaerung_html += (
            f"<p><b>Selezionato: {escape(best_pauschale_code)}</b> "
            f"({escape(get_lang_field(best_pauschale_details, PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A')}) - "
            "come forfait con la lettera suffisso più bassa (es. A prima di B) tra i candidati validi "
            "della categoria preferita (forfait specifici prima dei forfait di fallback C9x).</p>"
        )
    else:
        pauschale_erklaerung_html += (
            f"<p><b>Ausgewählt wurde: {escape(best_pauschale_code)}</b> "
            f"({escape(get_lang_field(best_pauschale_details, PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A')}) - "
            f"als die Pauschale mit dem niedrigsten Suffix-Buchstaben (z.B. A vor B) unter den gültigen Kandidaten "
            f"der bevorzugten Kategorie (spezifische Pauschalen vor Fallback-Pauschalen C9x).</p>"
        )

    # Vergleich mit anderen Pauschalen der gleichen Gruppe (Stamm)
    match_stamm = re.match(r"([A-Z0-9.]+)([A-Z])$", str(best_pauschale_code))
    pauschalen_stamm_code = match_stamm.group(1) if match_stamm else None
    
    if pauschalen_stamm_code:
        # Finde andere *potenzielle* Pauschalen (aus evaluated_candidates) in derselben Gruppe
        other_evaluated_codes_in_group = [
            cand for cand in evaluated_candidates
            if str(cand['code']).startswith(pauschalen_stamm_code) and str(cand['code']) != best_pauschale_code
        ]
        if other_evaluated_codes_in_group:
            if lang == 'fr':
                pauschale_erklaerung_html += f"<hr><p><b>Comparaison avec d'autres forfaits du groupe '{escape(pauschalen_stamm_code)}':</b></p>"
            elif lang == 'it':
                pauschale_erklaerung_html += f"<hr><p><b>Confronto con altri forfait del gruppo '{escape(pauschalen_stamm_code)}':</b></p>"
            else:
                pauschale_erklaerung_html += f"<hr><p><b>Vergleich mit anderen Pauschalen der Gruppe '{escape(pauschalen_stamm_code)}':</b></p>"
            selected_conditions_repr_set = get_simplified_conditions(best_pauschale_code, pauschale_bedingungen_data)

            for other_cand in sorted(other_evaluated_codes_in_group, key=lambda x: x['code']):
                other_code_str = str(other_cand['code'])
                other_details_dict = other_cand['details']
                other_was_valid_structured = other_cand['is_valid_structured']
                if other_was_valid_structured:
                    status = translate('conditions_also_met', lang)
                    validity_info_html = f"<span style=\"color:green;\">{status}</span>"
                else:
                    status = translate('conditions_not_met', lang)
                    validity_info_html = f"<span style=\"color:red;\">{status}</span>"

                other_conditions_repr_set = get_simplified_conditions(other_code_str, pauschale_bedingungen_data)
                additional_conditions_for_other = other_conditions_repr_set - selected_conditions_repr_set
                missing_conditions_in_other = selected_conditions_repr_set - other_conditions_repr_set

                diff_label = translate('diff_to', lang)
                pauschale_erklaerung_html += (
                    f"<details style='margin-left: 15px; font-size: 0.9em;'>"
                    f"<summary>{diff_label} <b>{escape(other_code_str)}</b> ({escape(get_lang_field(other_details_dict, PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A')}) {validity_info_html}</summary>"
                )

                if additional_conditions_for_other:
                    if lang == 'fr':
                        pauschale_erklaerung_html += f"<p>Exigences supplémentaires / autres pour {escape(other_code_str)}:</p><ul>"
                    elif lang == 'it':
                        pauschale_erklaerung_html += f"<p>Requisiti supplementari / altri per {escape(other_code_str)}:</p><ul>"
                    else:
                        pauschale_erklaerung_html += f"<p>Zusätzliche/Andere Anforderungen für {escape(other_code_str)}:</p><ul>"
                    for cond_tuple_item in sorted(list(additional_conditions_for_other)):
                        condition_html_detail_item = generate_condition_detail_html(cond_tuple_item, leistungskatalog_dict, tabellen_dict_by_table, lang)
                        pauschale_erklaerung_html += condition_html_detail_item
                    pauschale_erklaerung_html += "</ul>"
                  
                if missing_conditions_in_other:
                    if lang == 'fr':
                        pauschale_erklaerung_html += f"<p>Les exigences suivantes de {escape(best_pauschale_code)} manquent pour {escape(other_code_str)}:</p><ul>"
                    elif lang == 'it':
                        pauschale_erklaerung_html += f"<p>I seguenti requisiti di {escape(best_pauschale_code)} mancano in {escape(other_code_str)}:</p><ul>"
                    else:
                        pauschale_erklaerung_html += f"<p>Folgende Anforderungen von {escape(best_pauschale_code)} fehlen bei {escape(other_code_str)}:</p><ul>"
                    for cond_tuple_item in sorted(list(missing_conditions_in_other)):
                        condition_html_detail_item = generate_condition_detail_html(cond_tuple_item, leistungskatalog_dict, tabellen_dict_by_table, lang)
                        pauschale_erklaerung_html += condition_html_detail_item
                    pauschale_erklaerung_html += "</ul>"

                if not additional_conditions_for_other and not missing_conditions_in_other:
                    if lang == 'fr':
                        pauschale_erklaerung_html += "<p><i>Aucune différence de conditions essentielles trouvée (basé sur un contrôle simplifié type/valeur). Des différences détaillées peuvent exister au niveau du nombre ou de groupes logiques spécifiques.</i></p>"
                    elif lang == 'it':
                        pauschale_erklaerung_html += "<p><i>Nessuna differenza nelle condizioni principali trovata (basato su un confronto semplificato tipo/valore). Differenze dettagliate possibili nel numero o in gruppi logici specifici.</i></p>"
                    else:
                        pauschale_erklaerung_html += "<p><i>Keine unterschiedlichen Kernbedingungen gefunden (basierend auf vereinfachter Typ/Wert-Prüfung). Detaillierte Unterschiede können in der Anzahl oder spezifischen Logikgruppen liegen.</i></p>"
                pauschale_erklaerung_html += "</details>"
    
    best_pauschale_details[PAUSCHALE_ERKLAERUNG_KEY] = pauschale_erklaerung_html

    # Potenzielle ICDs für die ausgewählte Pauschale sammeln
    potential_icds_list = []
    pauschale_conditions_for_selected = [
        cond for cond in pauschale_bedingungen_data if cond.get(BED_PAUSCHALE_KEY) == best_pauschale_code
    ]
    for cond_item_icd in pauschale_conditions_for_selected:
        if cond_item_icd.get(BED_TYP_KEY, "").upper() == "HAUPTDIAGNOSE IN TABELLE":
            tabelle_ref_icd = cond_item_icd.get(BED_WERTE_KEY)
            if tabelle_ref_icd:
                icd_entries_list = get_table_content(tabelle_ref_icd, "icd", tabellen_dict_by_table, lang)
                for entry_icd in icd_entries_list:
                    code_icd = entry_icd.get('Code'); text_icd = entry_icd.get('Code_Text')
                    if code_icd: potential_icds_list.append({"Code": code_icd, "Code_Text": text_icd or "N/A"})
    
    unique_icds_dict_result = {icd_item['Code']: icd_item for icd_item in potential_icds_list if icd_item.get('Code')}
    best_pauschale_details[POTENTIAL_ICDS_KEY] = sorted(unique_icds_dict_result.values(), key=lambda x: x['Code'])

    final_result_dict = {
        "type": "Pauschale",
        "details": best_pauschale_details,
        "bedingungs_pruef_html": bedingungs_pruef_html_result,
        "bedingungs_fehler": condition_errors_html_gen, # Fehler aus der HTML-Generierung
        "conditions_met": True, # Da wir hier nur landen, wenn eine Pauschale als gültig ausgewählt wurde
        "evaluated_pauschalen": evaluated_candidates
    }
    return final_result_dict


# --- HILFSFUNKTIONEN (auf Modulebene) ---
def get_simplified_conditions(pauschale_code: str, bedingungen_data: list[dict]) -> set:
    """
    Wandelt Bedingungen in eine vereinfachte, vergleichbare Darstellung (Set von Tupeln) um.
    Dies dient dazu, Unterschiede zwischen Pauschalen auf einer höheren Ebene zu identifizieren.
    Die Logik hier muss nicht alle Details der `check_single_condition` abbilden,
    sondern eher die Art und den Hauptwert der Bedingung.
    """
    simplified_set = set()
    PAUSCHALE_KEY = 'Pauschale'; BED_TYP_KEY = 'Bedingungstyp'; BED_WERTE_KEY = 'Werte'
    BED_FELD_KEY = 'Feld'; BED_MIN_KEY = 'MinWert'; BED_MAX_KEY = 'MaxWert'
    BED_VERGLEICHSOP_KEY = 'Vergleichsoperator' # Hinzugefügt
    
    pauschale_conditions = [cond for cond in bedingungen_data if cond.get(PAUSCHALE_KEY) == pauschale_code]

    for cond in pauschale_conditions:
        typ_original = cond.get(BED_TYP_KEY, "").upper()
        wert = str(cond.get(BED_WERTE_KEY, "")).strip() # String und strip
        feld = str(cond.get(BED_FELD_KEY, "")).strip()
        vergleichsop = str(cond.get(BED_VERGLEICHSOP_KEY, "=")).strip() # Default '='
        
        condition_tuple = None
        # Normalisiere Typen für den Vergleich
        # Ziel ist es, semantisch ähnliche Bedingungen gleich zu behandeln
        
        final_cond_type_for_comparison = typ_original # Default

        if typ_original in ["LEISTUNGSPOSITIONEN IN TABELLE", "TARIFPOSITIONEN IN TABELLE", "LKN IN TABELLE"]:
            final_cond_type_for_comparison = 'LKN_TABLE'
            condition_tuple = (final_cond_type_for_comparison, tuple(sorted([t.strip().lower() for t in wert.split(',') if t.strip()]))) # Tabellennamen als sortiertes Tuple
        elif typ_original in ["HAUPTDIAGNOSE IN TABELLE", "ICD IN TABELLE"]:
            final_cond_type_for_comparison = 'ICD_TABLE'
            condition_tuple = (final_cond_type_for_comparison, tuple(sorted([t.strip().lower() for t in wert.split(',') if t.strip()])))
        elif typ_original in ["LEISTUNGSPOSITIONEN IN LISTE", "LKN"]:
            final_cond_type_for_comparison = 'LKN_LIST'
            condition_tuple = (final_cond_type_for_comparison, tuple(sorted([lkn.strip().upper() for lkn in wert.split(',') if lkn.strip()]))) # LKNs als sortiertes Tuple
        elif typ_original in ["HAUPTDIAGNOSE IN LISTE", "ICD"]:
             final_cond_type_for_comparison = 'ICD_LIST'
             condition_tuple = (final_cond_type_for_comparison, tuple(sorted([icd.strip().upper() for icd in wert.split(',') if icd.strip()])))
        elif typ_original in ["MEDIKAMENTE IN LISTE", "GTIN"]:
            final_cond_type_for_comparison = 'GTIN_LIST'
            condition_tuple = (final_cond_type_for_comparison, tuple(sorted([gtin.strip() for gtin in wert.split(',') if gtin.strip()])))
        elif typ_original == "PATIENTENBEDINGUNG" and feld:
            final_cond_type_for_comparison = f'PATIENT_{feld.upper()}' # z.B. PATIENT_ALTER
            # Für Alter mit Min/Max eine normalisierte Darstellung
            if feld.lower() == "alter":
                min_w = cond.get(BED_MIN_KEY)
                max_w = cond.get(BED_MAX_KEY)
                if min_w is not None or max_w is not None:
                    wert_repr = f"min:{min_w or '-'}_max:{max_w or '-'}"
                else:
                    wert_repr = f"exact:{wert}"
                condition_tuple = (final_cond_type_for_comparison, wert_repr)
            else: # Für andere Patientenbedingungen (z.B. Geschlecht)
                condition_tuple = (final_cond_type_for_comparison, wert.lower())
        elif typ_original == "ALTER IN JAHREN BEI EINTRITT":
            final_cond_type_for_comparison = 'PATIENT_ALTER_EINTRITT'
            condition_tuple = (final_cond_type_for_comparison, f"{vergleichsop}{wert}")
        elif typ_original == "ANZAHL":
            final_cond_type_for_comparison = 'ANZAHL_CHECK'
            condition_tuple = (final_cond_type_for_comparison, f"{vergleichsop}{wert}")
        elif typ_original == "SEITIGKEIT":
            final_cond_type_for_comparison = 'SEITIGKEIT_CHECK'
            # Normalisiere den Regelwert für den Vergleich (z.B. 'B' -> 'beidseits')
            norm_regel_wert = wert.strip().replace("'", "").lower()
            if norm_regel_wert == 'b': norm_regel_wert = 'beidseits'
            elif norm_regel_wert == 'e': norm_regel_wert = 'einseitig' # Vereinfachung für Vergleich
            condition_tuple = (final_cond_type_for_comparison, f"{vergleichsop}{norm_regel_wert}")
        elif typ_original == "GESCHLECHT IN LISTE": # Bereits oben durch PATIENT_GESCHLECHT abgedeckt, wenn Feld gesetzt ist
            final_cond_type_for_comparison = 'GESCHLECHT_LIST_CHECK'
            condition_tuple = (final_cond_type_for_comparison, tuple(sorted([g.strip().lower() for g in wert.split(',') if g.strip()])))
        else:
            # Fallback für unbekannte oder nicht spezifisch behandelte Typen
            # print(f"  WARNUNG: get_simplified_conditions: Unbehandelter Typ '{typ_original}' für Pauschale {pauschale_code}. Verwende Originaltyp und Wert.")
            condition_tuple = (typ_original, wert) # Als Fallback
            
        if condition_tuple:
            simplified_set.add(condition_tuple)
        # else:
            # print(f"  WARNUNG: get_simplified_conditions konnte für Pauschale {pauschale_code} Typ '{typ_original}' mit Wert '{wert}' kein Tupel erzeugen.")
            
    return simplified_set


def generate_condition_detail_html(
    condition_tuple: tuple,
    leistungskatalog_dict: Dict, # Für LKN-Beschreibungen
    tabellen_dict_by_table: Dict,  # Für Tabelleninhalte und ICD-Beschreibungen
    lang: str = 'de'
    ) -> str:
    """
    Generiert HTML für eine einzelne vereinfachte Bedingung (aus get_simplified_conditions)
    im Vergleichsabschnitt der Pauschalenerklärung.
    """
    cond_type_comp, cond_value_comp = condition_tuple # cond_value_comp kann String oder Tuple sein
    condition_html = "<li>"

    try:
        # Formatierung basierend auf dem normalisierten Typ aus get_simplified_conditions
        if cond_type_comp == 'LKN_LIST':
            condition_html += translate('require_lkn_list', lang)
            if not cond_value_comp: # cond_value_comp ist hier ein Tuple von LKNs
                condition_html += f"<i>{translate('no_lkns_spec', lang)}</i>"
            else:
                lkn_details_html_parts = []
                for lkn_code in cond_value_comp: # Iteriere über das Tuple
                    beschreibung = get_beschreibung_fuer_lkn_im_backend(lkn_code, leistungskatalog_dict, lang)
                    lkn_details_html_parts.append(f"<b>{html.escape(lkn_code)}</b> ({html.escape(beschreibung)})")
                condition_html += ", ".join(lkn_details_html_parts)

        elif cond_type_comp == 'LKN_TABLE':
            condition_html += translate('require_lkn_table', lang)
            if not cond_value_comp: # cond_value_comp ist Tuple von Tabellennamen
                condition_html += f"<i>{translate('no_table_name', lang)}</i>"
            else:
                table_links_html_parts = []
                for table_name_norm in cond_value_comp: # Iteriere über Tuple von normalisierten Tabellennamen
                    # Hole Original-Tabellenname, falls möglich (für Anzeige), sonst normalisierten
                    # Dies ist schwierig ohne die Original-Bedingungsdaten hier.
                    # Wir verwenden den normalisierten Namen für get_table_content.
                    table_content_entries = get_table_content(table_name_norm, "service_catalog", tabellen_dict_by_table, lang)
                    entry_count = len(table_content_entries)
                    details_content_html = ""
                    if table_content_entries:
                        details_content_html = "<ul style='margin-top: 5px; font-size: 0.9em; max-height: 150px; overflow-y: auto; border-top: 1px solid #eee; padding-top: 5px; padding-left: 15px; list-style-position: inside;'>"
                        for item in sorted(table_content_entries, key=lambda x: x.get('Code', '')):
                            item_code = item.get('Code', 'N/A'); item_text = get_beschreibung_fuer_lkn_im_backend(item_code, leistungskatalog_dict, lang)
                            details_content_html += f"<li><b>{html.escape(item_code)}</b>: {html.escape(item_text)}</li>"
                        details_content_html += "</ul>"
                    entries_label = translate('entries_label', lang)
                    table_detail_html = (
                        f"<details class='inline-table-details-comparison'>"
                        f"<summary>{html.escape(table_name_norm.upper())}</summary> ({entry_count} {entries_label}){details_content_html}</details>"
                    )
                    table_links_html_parts.append(table_detail_html)
                condition_html += ", ".join(table_links_html_parts)

        elif cond_type_comp == 'ICD_TABLE':
            condition_html += translate('require_icd_table', lang)
            if not cond_value_comp: # Tuple von Tabellennamen
                condition_html += f"<i>{translate('no_table_name', lang)}</i>"
            else:
                table_links_html_parts = []
                for table_name_norm in cond_value_comp:
                    table_content_entries = get_table_content(table_name_norm, "icd", tabellen_dict_by_table, lang)
                    entry_count = len(table_content_entries)
                    details_content_html = ""
                    if table_content_entries:
                        details_content_html = "<ul>"
                        for item in sorted(table_content_entries, key=lambda x: x.get('Code', '')):
                            item_code = item.get('Code', 'N/A'); item_text = item.get('Code_Text', 'N/A')
                            details_content_html += f"<li><b>{html.escape(item_code)}</b>: {html.escape(item_text)}</li>"
                        details_content_html += "</ul>"
                    entries_label = translate('entries_label', lang)
                    table_detail_html = (
                        f"<details class='inline-table-details-comparison'>"
                        f"<summary>{html.escape(table_name_norm.upper())}</summary> ({entry_count} {entries_label}){details_content_html}</details>"
                    )
                    table_links_html_parts.append(table_detail_html)
                condition_html += ", ".join(table_links_html_parts)

        elif cond_type_comp == 'ICD_LIST':
            condition_html += translate('require_icd_list', lang)
            if not cond_value_comp: # Tuple von ICDs
                condition_html += f"<i>{translate('no_icds_spec', lang)}</i>"
            else:
                icd_details_html_parts = []
                for icd_code in cond_value_comp:
                    beschreibung = get_beschreibung_fuer_icd_im_backend(icd_code, tabellen_dict_by_table, lang=lang)
                    icd_details_html_parts.append(f"<b>{html.escape(icd_code)}</b> ({html.escape(beschreibung)})")
                condition_html += ", ".join(icd_details_html_parts)
        
        elif cond_type_comp == 'GTIN_LIST':
            condition_html += translate('require_gtin_list', lang)
            if not cond_value_comp: condition_html += f"<i>{translate('no_gtins_spec', lang)}</i>"
            else: condition_html += html.escape(", ".join(cond_value_comp))
        
        elif cond_type_comp.startswith('PATIENT_'):
            feld_name_raw = cond_type_comp.split('_', 1)[1]
            feld_name = feld_name_raw.replace('_', ' ').capitalize()
            condition_html += translate(
                'patient_condition',
                lang,
                field=html.escape(feld_name),
                value=html.escape(str(cond_value_comp)),
            )
        
        elif cond_type_comp == 'ANZAHL_CHECK':
            condition_html += translate('anzahl_condition', lang, value=html.escape(str(cond_value_comp)))

        elif cond_type_comp == 'SEITIGKEIT_CHECK':
            condition_html += translate('seitigkeit_condition', lang, value=html.escape(str(cond_value_comp)))
        
        elif cond_type_comp == 'GESCHLECHT_LIST_CHECK':
            condition_html += translate('geschlecht_list', lang)
            if not cond_value_comp: condition_html += f"<i>{translate('no_gender_spec', lang)}</i>"
            else: condition_html += html.escape(", ".join(cond_value_comp))

        else: # Allgemeiner Fallback für andere Typen aus get_simplified_conditions
            condition_html += f"{html.escape(cond_type_comp)}: {html.escape(str(cond_value_comp))}"

    except Exception as e_detail_gen:
        logger.error(
            "FEHLER beim Erstellen der Detailansicht für Vergleichs-Bedingung '%s': %s",
            condition_tuple,
            e_detail_gen,
        )
        traceback.print_exc()
        condition_html += f"<i>Fehler bei Detailgenerierung: {html.escape(str(e_detail_gen))}</i>"
    
    condition_html += "</li>"
    return condition_html
