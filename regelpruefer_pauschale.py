# regelpruefer_pauschale.py (Version mit korrigiertem Import und 9 Argumenten)
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

# Performance/Sicherheitslimits für die Auswertung boolescher Ausdrücke
MAX_BOOLEAN_EVAL_TOKENS = 10000
MAX_SHUNTING_YARD_OPS = 50000 # ca. 5x MAX_BOOLEAN_EVAL_TOKENS
MAX_RPN_EVAL_OPS = 50000      # ca. 5x MAX_BOOLEAN_EVAL_TOKENS
MAX_TOTAL_EVAL_TIME_WARN_SECONDS = 10 # Sekunden, bevor eine Warnung für die Gesamtdauer geloggt wird


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

    try:
        if bedingungstyp == "ICD": # ICD IN LISTE
            if not check_icd_conditions_at_all: return True
            required_icds_in_rule_list = {w.strip().upper() for w in str(werte_str).split(',') if w.strip()}
            if not required_icds_in_rule_list: return True
            return any(req_icd in provided_icds_upper for req_icd in required_icds_in_rule_list)

        elif bedingungstyp == "HAUPTDIAGNOSE IN TABELLE": # ICD IN TABELLE
            if not check_icd_conditions_at_all: return True
            table_ref = werte_str
            icd_codes_in_rule_table = {entry['Code'].upper() for entry in get_table_content(table_ref, "icd", tabellen_dict_by_table) if entry.get('Code')}
            if not icd_codes_in_rule_table:
                 return False if provided_icds_upper else True
            return any(provided_icd in icd_codes_in_rule_table for provided_icd in provided_icds_upper)

        elif bedingungstyp == "GTIN" or bedingungstyp == "MEDIKAMENTE IN LISTE":
            werte_list_gtin = [w.strip() for w in str(werte_str).split(',') if w.strip()]
            if not werte_list_gtin: return True
            return any(req_gtin in provided_gtins for req_gtin in werte_list_gtin)

        elif bedingungstyp == "LKN" or bedingungstyp == "LEISTUNGSPOSITIONEN IN LISTE":
            werte_list_upper_lkn = [w.strip().upper() for w in str(werte_str).split(',') if w.strip()]
            if not werte_list_upper_lkn: return True
            return any(req_lkn in provided_lkns_upper for req_lkn in werte_list_upper_lkn)

        elif bedingungstyp == "GESCHLECHT IN LISTE":
            if werte_str:
                geschlechter_in_regel_lower = {g.strip().lower() for g in str(werte_str).split(',') if g.strip()}
                return provided_geschlecht_str in geschlechter_in_regel_lower
            return True

        elif bedingungstyp == "LEISTUNGSPOSITIONEN IN TABELLE" or bedingungstyp == "TARIFPOSITIONEN IN TABELLE":
            table_ref = werte_str
            lkn_codes_in_rule_table = {entry['Code'].upper() for entry in get_table_content(table_ref, "service_catalog", tabellen_dict_by_table) if entry.get('Code')}
            if not lkn_codes_in_rule_table: return False
            return any(provided_lkn in lkn_codes_in_rule_table for provided_lkn in provided_lkns_upper)

        elif bedingungstyp == "PATIENTENBEDINGUNG":
            if feld_ref == "Alter":
                if provided_alter is None: return False
                try:
                    alter_patient = int(provided_alter); alter_ok = True
                    if min_val_regel is not None and alter_patient < int(min_val_regel): alter_ok = False
                    if max_val_regel is not None and alter_patient > int(max_val_regel): alter_ok = False
                    if min_val_regel is None and max_val_regel is None and wert_regel_explizit is not None:
                        if alter_patient != int(wert_regel_explizit): alter_ok = False
                    return alter_ok
                except (ValueError, TypeError): return False
            elif feld_ref == "Geschlecht":
                 if isinstance(wert_regel_explizit, str):
                     return provided_geschlecht_str == wert_regel_explizit.strip().lower()
                 return False
            else:
                logger.warning( "WARNUNG (check_single PATIENTENBEDINGUNG): Unbekanntes Feld '%s'.", feld_ref)
                return True

        elif bedingungstyp == "ALTER IN JAHREN BEI EINTRITT":
            alter_eintritt = context.get("AlterBeiEintritt")
            if alter_eintritt is None: return False
            try:
                alter_val = int(alter_eintritt)
                regel_wert = int(werte_str)
                vergleichsoperator = condition.get("Vergleichsoperator")
                if vergleichsoperator == ">=": return alter_val >= regel_wert
                elif vergleichsoperator == "<=": return alter_val <= regel_wert
                elif vergleichsoperator == ">": return alter_val > regel_wert
                elif vergleichsoperator == "<": return alter_val < regel_wert
                elif vergleichsoperator == "=": return alter_val == regel_wert
                elif vergleichsoperator == "!=": return alter_val != regel_wert
                else:
                    logger.warning("WARNUNG (check_single ALTER BEI EINTRITT): Unbekannter Vergleichsoperator '%s'.", vergleichsoperator)
                    return False
            except (ValueError, TypeError) as e_alter:
                logger.error("FEHLER (check_single ALTER BEI EINTRITT) Konvertierung: %s. Regelwert: '%s', Kontextwert: '%s'", e_alter, werte_str, alter_eintritt)
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
                    logger.warning("WARNUNG (check_single ANZAHL): Unbekannter Vergleichsoperator '%s'.", vergleichsoperator)
                    return False
            except (ValueError, TypeError) as e_anzahl:
                logger.error("FEHLER (check_single ANZAHL) Konvertierung: %s. Regelwert: '%s', Kontextwert: '%s'", e_anzahl, werte_str, provided_anzahl)
                return False

        elif bedingungstyp == "SEITIGKEIT":
            regel_wert_seitigkeit_norm = werte_str.strip().replace("'", "").lower()
            vergleichsoperator = condition.get('Vergleichsoperator')
            if vergleichsoperator == "=":
                if regel_wert_seitigkeit_norm == 'b': return provided_seitigkeit_str == 'beidseits'
                elif regel_wert_seitigkeit_norm == 'e': return provided_seitigkeit_str in ['einseitig', 'links', 'rechts']
                elif regel_wert_seitigkeit_norm == 'l': return provided_seitigkeit_str == 'links'
                elif regel_wert_seitigkeit_norm == 'r': return provided_seitigkeit_str == 'rechts'
                else: return provided_seitigkeit_str == regel_wert_seitigkeit_norm
            elif vergleichsoperator == "!=":
                if regel_wert_seitigkeit_norm == 'b': return provided_seitigkeit_str != 'beidseits'
                elif regel_wert_seitigkeit_norm == 'e': return provided_seitigkeit_str not in ['einseitig', 'links', 'rechts']
                elif regel_wert_seitigkeit_norm == 'l': return provided_seitigkeit_str != 'links'
                elif regel_wert_seitigkeit_norm == 'r': return provided_seitigkeit_str != 'rechts'
                else: return provided_seitigkeit_str != regel_wert_seitigkeit_norm
            else:
                logger.warning("WARNUNG (check_single SEITIGKEIT): Unbekannter Vergleichsoperator '%s'.", vergleichsoperator)
                return False
        else:
            logger.warning("WARNUNG (check_single): Unbekannter Pauschalen-Bedingungstyp '%s'. Wird als False angenommen.", bedingungstyp)
            return False
    except Exception as e:
        logger.error("FEHLER (check_single) für P: %s G: %s Typ: %s, Werte: %s: %s", pauschale_code_for_debug, gruppe_for_debug, bedingungstyp, werte_str, e)
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
    if spezifische_icd_tabelle:
        icd_entries_specific = get_table_content(spezifische_icd_tabelle, "icd", tabellen_dict_by_table, lang)
        for entry in icd_entries_specific:
            if entry.get('Code', '').upper() == icd_code.upper():
                return entry.get('Code_Text', icd_code)
    haupt_icd_tabelle_name = "icd_hauptkatalog"
    icd_entries_main = get_table_content(haupt_icd_tabelle_name, "icd", tabellen_dict_by_table, lang)
    for entry in icd_entries_main:
        if entry.get('Code', '').upper() == icd_code.upper():
            return entry.get('Code_Text', icd_code)
    return icd_code

def get_group_operator_for_pauschale(
    pauschale_code: str, bedingungen_data: List[Dict], default: str = DEFAULT_GROUP_OPERATOR
) -> str:
    for cond in bedingungen_data:
        if cond.get("Pauschale") == pauschale_code and "GruppenOperator" in cond:
            op = str(cond.get("GruppenOperator", "")).strip().upper()
            if op in ("UND", "ODER"):
                return op
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
    if len(tokens) > MAX_BOOLEAN_EVAL_TOKENS:
        logger.warning(f"Abbruch _evaluate_boolean_tokens: Token-Anzahl ({len(tokens)}) überschreitet Limit ({MAX_BOOLEAN_EVAL_TOKENS}).")
        return False
    precedence = {"AND": 2, "OR": 1}
    output: List[Any] = []
    op_stack: List[str] = []
    shunting_yard_ops_count = 0
    for tok in tokens:
        shunting_yard_ops_count += 1
        if shunting_yard_ops_count > MAX_SHUNTING_YARD_OPS:
            logger.warning(f"Abbruch Shunting-Yard in _evaluate_boolean_tokens: Operationslimit ({MAX_SHUNTING_YARD_OPS}) überschritten.")
            return False
        if isinstance(tok, bool):
            output.append(tok)
        elif tok in ("AND", "OR"):
            while op_stack and op_stack[-1] in ("AND", "OR") and precedence[op_stack[-1]] >= precedence[tok]:
                output.append(op_stack.pop())
                shunting_yard_ops_count +=1
            op_stack.append(tok)
        elif tok == "(":
            op_stack.append(tok)
        elif tok == ")":
            while op_stack and op_stack[-1] != "(":
                output.append(op_stack.pop())
                shunting_yard_ops_count +=1
            if not op_stack:
                logger.error("Fehler in _evaluate_boolean_tokens: Nicht übereinstimmende schließende Klammer.")
                return False
            op_stack.pop()
        else:
            logger.error(f"Fehler in _evaluate_boolean_tokens: Unbekanntes Token {tok}.")
            return False
    while op_stack:
        shunting_yard_ops_count += 1
        if shunting_yard_ops_count > MAX_SHUNTING_YARD_OPS:
            logger.warning(f"Abbruch Shunting-Yard (while op_stack) in _evaluate_boolean_tokens: Operationslimit ({MAX_SHUNTING_YARD_OPS}) überschritten.")
            return False
        op = op_stack.pop()
        if op == "(":
            logger.error("Fehler in _evaluate_boolean_tokens: Nicht übereinstimmende öffnende Klammer.")
            return False
        output.append(op)
    stack: List[bool] = []
    rpn_eval_ops_count = 0
    for tok in output:
        rpn_eval_ops_count += 1
        if rpn_eval_ops_count > MAX_RPN_EVAL_OPS:
            logger.warning(f"Abbruch RPN-Auswertung in _evaluate_boolean_tokens: Operationslimit ({MAX_RPN_EVAL_OPS}) überschritten.")
            return False
        if isinstance(tok, bool):
            stack.append(tok)
        else:
            if len(stack) < 2:
                logger.error("Fehler in _evaluate_boolean_tokens: Unzureichende Operanden für Operator.")
                return False
            b = stack.pop()
            a = stack.pop()
            stack.append(a and b if tok == "AND" else a or b)
    if len(stack) != 1:
        logger.error("Fehler in _evaluate_boolean_tokens: Invalider boolescher Ausdruck nach Auswertung.")
        return False
    return stack[0]

def evaluate_structured_conditions(
    pauschale_code: str,
    context: Dict,
    pauschale_bedingungen_data: List[Dict],
    tabellen_dict_by_table: Dict[str, List[Dict]],
    debug: bool = False,
) -> bool:
    func_start_time = time.time()
    # PAUSCHALE_KEY = 'Pauschale' # Not needed if conditions are pre-filtered
    GRUPPE_KEY = 'Gruppe'
    OPERATOR_KEY = 'Operator'
    EBENE_KEY = 'Ebene'
    BED_ID_KEY = 'BedingungsID'
    BED_TYP_KEY = 'Bedingungstyp'
    AST_VERBINDUNGSOPERATOR_TYPE = "AST VERBINDUNGSOPERATOR"

    def _evaluate_intra_block_logic(
        conditions_in_block: List[Dict],
        block_debug_id: Any,
        pauschale_code_debug: str
        ) -> bool:
        if not conditions_in_block:
            if debug: logger.info("DEBUG Intra-Block %s (Pauschale %s): Leer, evaluiert zu True", block_debug_id, pauschale_code_debug)
            return True

        start_sort_intra = time.time()
        sorted_conditions_for_block = sorted(
            conditions_in_block,
            key=lambda c: (c.get(EBENE_KEY, 1), c.get(BED_ID_KEY, 0)) 
        )
        if debug: logger.debug("DEBUG Intra-Block %s (Pauschale %s): Interne Sortierung dauerte %.4fs", block_debug_id, pauschale_code_debug, time.time() - start_sort_intra)

        baseline_level_block = 1 
        first_level_block = sorted_conditions_for_block[0].get(EBENE_KEY, 1)

        start_single_check = time.time()
        first_res_block = check_single_condition(
            sorted_conditions_for_block[0], context, tabellen_dict_by_table
        )
        if debug: logger.debug("DEBUG Intra-Block %s (Pauschale %s): Erste Bed. ID %s geprüft in %.4fs", block_debug_id, pauschale_code_debug, sorted_conditions_for_block[0].get(BED_ID_KEY), time.time() - start_single_check)

        tokens_block: List[Any] = ["("] * (first_level_block - baseline_level_block)
        tokens_block.append(bool(first_res_block))
        prev_level_block = first_level_block

        time_spent_in_check_single_total = time.time() - start_single_check # Inklusive der ersten Prüfung
        time_spent_in_token_generation_loop = 0

        start_token_loop = time.time()
        for cond_idx in range(1, len(sorted_conditions_for_block)):
            current_cond = sorted_conditions_for_block[cond_idx]
            linking_op = sorted_conditions_for_block[cond_idx -1].get(OPERATOR_KEY, "UND").upper()
            cur_level_block = current_cond.get(EBENE_KEY, baseline_level_block)

            if cur_level_block < prev_level_block:
                tokens_block.extend(")" for _ in range(prev_level_block - cur_level_block))
            
            tokens_block.append("AND" if linking_op == "UND" else "OR")

            if cur_level_block > prev_level_block:
                tokens_block.extend("(" for _ in range(cur_level_block - prev_level_block))

            start_single_check_loop = time.time()
            cur_res_block = check_single_condition(current_cond, context, tabellen_dict_by_table)
            loop_check_time = time.time() - start_single_check_loop
            time_spent_in_check_single_total += loop_check_time
            if debug: logger.debug("DEBUG Intra-Block %s (Pauschale %s): Bed. ID %s geprüft in %.4fs", block_debug_id, pauschale_code_debug, current_cond.get(BED_ID_KEY), loop_check_time)

            tokens_block.append(bool(cur_res_block))
            prev_level_block = cur_level_block
        time_spent_in_token_generation_loop = time.time() - start_token_loop - (time_spent_in_check_single_total - (time.time() - start_single_check)) # Subtrahiere die erste Prüfung nicht doppelt

        tokens_block.extend(")" for _ in range(prev_level_block - baseline_level_block))

        if debug:
            logger.info("DEBUG Intra-Block %s (Pauschale %s): Zeit für check_single_condition Summe: %.4fs", block_debug_id, pauschale_code_debug, time_spent_in_check_single_total)
            logger.info("DEBUG Intra-Block %s (Pauschale %s): Zeit für Token-Generierung (Schleife): %.4fs", block_debug_id, pauschale_code_debug, time_spent_in_token_generation_loop)
            logger.info("DEBUG Intra-Block %s (Pauschale %s): Anzahl Bedingungen: %s, Token-Liste Länge: %s", block_debug_id, pauschale_code_debug, len(sorted_conditions_for_block), len(tokens_block))

        expr_str_block = "".join(
            str(t).lower() if isinstance(t, bool) else (" and " if t == "AND" else " or " if t == "OR" else t)
            for t in tokens_block
        )
        try:
            start_eval_tokens = time.time()
            block_result = _evaluate_boolean_tokens(tokens_block)
            if debug:
                logger.info("DEBUG Intra-Block %s (Pauschale %s): _evaluate_boolean_tokens dauerte %.4fs", block_debug_id, pauschale_code_debug, time.time() - start_eval_tokens)
                logger.info("DEBUG Intra-Block %s (Pauschale %s): Ausdruck '%s' => %s",
                            block_debug_id, pauschale_code_debug,
                            expr_str_block,
                            block_result)
            return block_result
        except Exception as e_eval_intra_block:
            logger.error(
                "FEHLER bei Intra-Block-Logik (Pauschale: %s, Block beginnend mit Gruppe ca. %s) '%s': %s",
                pauschale_code_debug, block_debug_id, expr_str_block, e_eval_intra_block,
            )
            traceback.print_exc()
            return False

    # Die Variable 'pauschale_bedingungen_data' enthält jetzt die bereits
    # spezifischen und vorsortierten (nach Gruppe, BedID) Bedingungen für 'pauschale_code'.
    # Daher ist die Filterung und Hauptsortierung hier nicht mehr nötig.
    all_conditions_for_pauschale = pauschale_bedingungen_data # Direkte Zuweisung

    if debug:
        logger.info("DEBUG Pauschale %s: Erhielt %s bereits gefilterte/sortierte Bedingungen.", pauschale_code, len(all_conditions_for_pauschale))

    if not all_conditions_for_pauschale:
        if debug: logger.info("DEBUG Pauschale %s: Keine Bedingungen für diese Pauschale vorhanden (oder übergeben), Ergebnis True. Dauer: %.4fs", pauschale_code, time.time() - func_start_time)
        return True

    evaluated_block_results: List[bool] = []
    inter_block_operators: List[str] = []
    current_block_sub_conditions: List[Dict] = []
    current_block_first_gruppe_id_for_debug = None 

    start_main_loop = time.time()
    for i, condition in enumerate(all_conditions_for_pauschale):
        cond_type = str(condition.get(BED_TYP_KEY, "")).upper()

        if cond_type == AST_VERBINDUNGSOPERATOR_TYPE:
            if current_block_sub_conditions:
                start_intra_eval = time.time()
                block_res = _evaluate_intra_block_logic(current_block_sub_conditions, current_block_first_gruppe_id_for_debug, pauschale_code)
                if debug: logger.info("DEBUG Pauschale %s: _evaluate_intra_block_logic für Block (start G: %s) dauerte %.4fs", pauschale_code, current_block_first_gruppe_id_for_debug, time.time() - start_intra_eval)
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

    if debug: logger.info("DEBUG Pauschale %s: Hauptschleife (Blockbildung) dauerte %.4fs", pauschale_code, time.time() - start_main_loop)

    if current_block_sub_conditions:
        start_intra_eval_final = time.time()
        block_res = _evaluate_intra_block_logic(current_block_sub_conditions, current_block_first_gruppe_id_for_debug, pauschale_code)
        if debug: logger.info("DEBUG Pauschale %s: _evaluate_intra_block_logic für letzten Block (start G: %s) dauerte %.4fs", pauschale_code, current_block_first_gruppe_id_for_debug, time.time() - start_intra_eval_final)
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

    start_final_link = time.time()
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
    if debug: logger.info("DEBUG Pauschale %s: Finale Verknüpfung dauerte %.4fs", pauschale_code, time.time() - start_final_link)

    total_duration = time.time() - func_start_time
    if debug:
        logger.info(
            "DEBUG Finales Ergebnis Pauschale %s: %s. Gesamtdauer evaluate_structured_conditions: %.4fs",
            pauschale_code,
            final_pauschale_result,
            total_duration
        )
    if total_duration > MAX_TOTAL_EVAL_TIME_WARN_SECONDS:
        logger.warning(
            "PERFORMANCE WARNUNG: evaluate_structured_conditions für Pauschale %s dauerte %.4fs, was das Limit von %s Sekunden überschreitet.",
            pauschale_code, total_duration, MAX_TOTAL_EVAL_TIME_WARN_SECONDS
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
        original_werte = str(cond_data.get(BED_WERTE_KEY, ""))

        if cond_type_upper in ["LEISTUNGSPOSITIONEN IN LISTE", "LKN"]:
            lkn_codes = [l.strip().upper() for l in original_werte.split(',') if l.strip()]
            lkn_details_parts = []
            if lkn_codes:
                for lkn_c in lkn_codes:
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
                werte_display = "".join(table_links_parts)
            else:
                werte_display = f"<i>{translate('no_table_name', lang)}</i>"

        elif cond_type_upper in ["HAUPTDIAGNOSE IN TABELLE", "ICD IN TABELLE"]:
            table_names_icd = [t.strip() for t in original_werte.split(',') if t.strip()]
            table_links_icd_parts = []
            if table_names_icd:
                for table_name_i in table_names_icd:
                    table_content_entries_icd = get_table_content(table_name_i, "icd", tabellen_dict_by_table, lang)
                    entry_count_icd = len(table_content_entries_icd)
                    details_content_html_icd = ""
                    if table_content_entries_icd:
                        details_content_html_icd = "<ul class='table-content-list'>"
                        for item_icd in sorted(table_content_entries_icd, key=lambda x: x.get('Code', '')):
                            item_code_icd = item_icd.get('Code', 'N/A')
                            item_text_icd = item_icd.get('Code_Text', get_beschreibung_fuer_icd_im_backend(item_code_icd, tabellen_dict_by_table, spezifische_icd_tabelle=table_name_i, lang=lang))
                            details_content_html_icd += f"<li><b>{escape(item_code_icd)}</b>: {escape(item_text_icd)}</li>"
                        details_content_html_icd += "</ul>"
                    
                    table_links_icd_parts.append(
                        f"<details class='inline-table-details'>"
                        f"<summary><i>{escape(table_name_i)}</i> ({entry_count_icd} {translate('entries_label', lang)})</summary>{details_content_html_icd}</details>"
                    )
                werte_display = "".join(table_links_icd_parts)
            else:
                werte_display = f"<i>{translate('no_table_name', lang)}</i>"

        elif cond_type_upper in ["ICD", "HAUPTDIAGNOSE IN LISTE"]:
            icd_codes_list = [icd.strip().upper() for icd in original_werte.split(',') if icd.strip()]
            icd_details_parts = []
            if icd_codes_list:
                for icd_c in icd_codes_list:
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
            else:
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

        else:
            werte_display = escape(original_werte)

        context_match_info_html = ""
        if condition_met:
            match_details = []
            if cond_type_upper == "ICD" or cond_type_upper == "HAUPTDIAGNOSE IN LISTE":
                provided_icds_upper = {p_icd.upper() for p_icd in context.get("ICD", []) if p_icd}
                required_icds_in_rule_list = {w.strip().upper() for w in str(cond_data.get(BED_WERTE_KEY, "")).split(',') if w.strip()}
                matching_icds = list(provided_icds_upper.intersection(required_icds_in_rule_list))
                if matching_icds:
                    match_details.append(f"{translate('fulfilled_by_icd', lang)}: {', '.join(matching_icds)}")
            elif cond_type_upper in ["LKN", "LEISTUNGSPOSITIONEN IN LISTE"]:
                provided_lkns_upper = {p_lkn.upper() for p_lkn in context.get("LKN", []) if p_lkn}
                required_lkns_in_rule_list = {w.strip().upper() for w in str(cond_data.get(BED_WERTE_KEY, "")).split(',') if w.strip()}
                matching_lkns = list(provided_lkns_upper.intersection(required_lkns_in_rule_list))
                if matching_lkns:
                    match_details.append(f"{translate('fulfilled_by_lkn', lang)}: {', '.join(matching_lkns)}")
            elif cond_type_upper in ["LEISTUNGSPOSITIONEN IN TABELLE", "TARIFPOSITIONEN IN TABELLE"]:
                provided_lkns_upper = {p_lkn.upper() for p_lkn in context.get("LKN", []) if p_lkn}
                table_ref = cond_data.get(BED_WERTE_KEY, "")
                lkn_codes_in_rule_table = {entry['Code'].upper() for entry in get_table_content(table_ref, "service_catalog", tabellen_dict_by_table) if entry.get('Code')}
                matching_lkns = list(provided_lkns_upper.intersection(lkn_codes_in_rule_table))
                if matching_lkns:
                    match_details.append(f"{translate('fulfilled_by_lkn_in_table', lang, table=escape(table_ref))}: {', '.join(matching_lkns)}")
            elif cond_type_upper == "HAUPTDIAGNOSE IN TABELLE":
                if context.get("useIcd", True):
                    provided_icds_upper = {p_icd.upper() for p_icd in context.get("ICD", []) if p_icd}
                    table_ref_icd = cond_data.get(BED_WERTE_KEY, "")
                    icd_codes_in_rule_table = {entry['Code'].upper() for entry in get_table_content(table_ref_icd, "icd", tabellen_dict_by_table) if entry.get('Code')}
                    matching_icds = list(provided_icds_upper.intersection(icd_codes_in_rule_table))
                    if matching_icds:
                        match_details.append(f"{translate('fulfilled_by_icd_in_table', lang, table=escape(table_ref_icd))}: {', '.join(matching_icds)}")
                else:
                    match_details.append(f"({translate('icd_check_disabled', lang)})")
            elif cond_type_upper in ["GTIN", "MEDIKAMENTE IN LISTE"]:
                provided_gtins = set(context.get("GTIN", []))
                required_gtins_in_rule_list = {w.strip() for w in str(cond_data.get(BED_WERTE_KEY, "")).split(',') if w.strip()}
                matching_gtins = list(provided_gtins.intersection(required_gtins_in_rule_list))
                if matching_gtins:
                    match_details.append(f"{translate('fulfilled_by_gtin', lang)}: {', '.join(matching_gtins)}")
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
            else:
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

    if current_group is not None:
        html_parts.append("</div>")

    return {
        "html": "".join(html_parts),
        "errors": [],
        "trigger_lkn_condition_met": trigger_lkn_condition_overall_met
    }

def render_condition_results_html(
    results: List[Dict[str, Any]],
    lang: str = "de"
) -> str:
    logger.warning("render_condition_results_html wird aufgerufen, ist aber für die neue HTML-Struktur veraltet.")
    html_parts = ["<ul class='legacy-condition-list'>"]
    for item in results:
        icon_text = "&#10003;" if item.get("erfuellt") else "&#10007;"
        typ_text = escape(str(item.get("Bedingungstyp", "")))
        wert_text = escape(str(item.get("Werte", "")))
        html_parts.append(f"<li>{icon_text} {typ_text}: {wert_text}</li>")
    html_parts.append("</ul>")
    return "".join(html_parts)

def determine_applicable_pauschale(
    user_input: str,
    rule_checked_leistungen: list[dict],
    context: dict,
    pauschale_lp_data: List[Dict],
    # Ersetzt durch pauschale_bedingungen_indexed
    # pauschale_bedingungen_data: List[Dict],
    pauschale_bedingungen_indexed: Dict[str, List[Dict[str, Any]]], # NEUER PARAMETER
    pauschalen_dict: Dict[str, Dict],
    leistungskatalog_dict: Dict[str, Dict],
    tabellen_dict_by_table: Dict[str, List[Dict]],
    potential_pauschale_codes_input: Set[str] | None = None,
    lang: str = 'de'
) -> dict:
    logger.info("INFO: Starte Pauschalenermittlung mit strukturierter Bedingungsprüfung (optimiert)...")
    PAUSCHALE_ERKLAERUNG_KEY = 'pauschale_erklaerung_html'; POTENTIAL_ICDS_KEY = 'potential_icds'
    LKN_KEY_IN_RULE_CHECKED = 'lkn'; PAUSCHALE_KEY_IN_PAUSCHALEN = 'Pauschale'
    PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN = 'Pauschale_Text'
    LP_LKN_KEY = 'Leistungsposition'; LP_PAUSCHALE_KEY = 'Pauschale'
    BED_PAUSCHALE_KEY = 'Pauschale'; BED_TYP_KEY = 'Bedingungstyp'
    BED_WERTE_KEY = 'Werte'

    current_debug_status = logger.isEnabledFor(logging.DEBUG) # Für konsistente Debug-Ausgaben

    potential_pauschale_codes: Set[str] = set()
    if potential_pauschale_codes_input is not None:
        potential_pauschale_codes = potential_pauschale_codes_input
        if current_debug_status: logger.info("DEBUG: Verwende übergebene potenzielle Pauschalen: %s", potential_pauschale_codes)
    else:
        if current_debug_status: logger.info("DEBUG: Suche potenzielle Pauschalen (da nicht übergeben)...")
        # This internal search logic is simplified as potential_pauschale_codes_input
        # is expected to be comprehensive from server.py.
        # However, keeping a minimal LKN-based search from pauschale_lp_data if nothing is passed.
        context_lkns_for_search = {str(lkn).upper() for lkn in context.get("LKN", []) if lkn}
        for item in pauschale_lp_data:
            lkn_in_lp = item.get(LP_LKN_KEY)
            if lkn_in_lp and lkn_in_lp.upper() in context_lkns_for_search:
                pc = item.get(LP_PAUSCHALE_KEY)
                if pc and pc in pauschalen_dict: potential_pauschale_codes.add(pc)
        if current_debug_status: logger.info("DEBUG: Potenzielle Pauschalen nach initialer interner LP-Suche: %s", potential_pauschale_codes)
        # The more complex search through all conditions (pauschale_bedingungen_data) to find
        # potential Pauschalen is removed here, as server.py should now provide a more
        # complete set via potential_pauschale_codes_input, leveraging the indexed conditions.

    if not potential_pauschale_codes:
        # This message might need adjustment if potential_pauschale_codes_input was specifically empty.
        return {"type": "Error", "message": "Keine potenziellen Pauschalen zur Prüfung identifiziert.", "evaluated_pauschalen": []}

    evaluated_candidates = []
    for code in sorted(list(potential_pauschale_codes)):
        if code not in pauschalen_dict:
            logger.warning("WARNUNG: Potenzielle Pauschale %s nicht in pauschalen_dict gefunden. Übersprungen.", code)
            continue
        
        conditions_for_this_pauschale = pauschale_bedingungen_indexed.get(str(code), []) # str(code) für Konsistenz
        if not conditions_for_this_pauschale and current_debug_status:
            logger.info("DEBUG: Keine Bedingungen im Index für Pauschale %s gefunden. Wird als erfüllbar ohne Bedingungen behandelt.", code)
            # evaluate_structured_conditions wird dies als True zurückgeben, wenn die Liste leer ist.

        is_pauschale_valid_structured = False
        bedingungs_html = "" # Wird später für die UI gefüllt

        if current_debug_status: logger.info("DEBUG: Prüfe Pauschale %s mit Kontext %s. Anzahl Bedingungen aus Index: %s", code, context, len(conditions_for_this_pauschale))
        start_time_eval = time.time()

        try:
            # Rufe evaluate_structured_conditions mit der spezifischen, bereits sortierten Liste auf
            is_pauschale_valid_structured = evaluate_structured_conditions(
                code, context, conditions_for_this_pauschale, tabellen_dict_by_table, debug=current_debug_status
            )
            end_time_eval = time.time()
            if current_debug_status:
                logger.info("DEBUG: Pauschale %s geprüft in %.4f Sekunden. Ergebnis: %s", code, end_time_eval - start_time_eval, is_pauschale_valid_structured)

            # HTML-Generierung für UI - verwendet auch die indizierten/gefilterten Bedingungen
            # check_pauschale_conditions muss ebenfalls die spezifische Liste erhalten
            check_res = check_pauschale_conditions(
                code, context, conditions_for_this_pauschale, tabellen_dict_by_table, leistungskatalog_dict, lang
            )
            bedingungs_html = check_res.get("html", "")
        except Exception as e_eval:
            logger.error("FEHLER bei der Auswertung/HTML-Generierung für Pauschale %s: %s", code, e_eval)
            traceback.print_exc()

        tp_raw = pauschalen_dict[code].get("Taxpunkte")
        try:
            tp_val = float(tp_raw) if tp_raw is not None else 0.0
        except (ValueError, TypeError):
            tp_val = 0.0

        evaluated_candidates.append({
            "code": code, "details": pauschalen_dict[code],
            "is_valid_structured": is_pauschale_valid_structured,
            "bedingungs_pruef_html": bedingungs_html, "taxpunkte": tp_val,
        })

    valid_candidates = [cand for cand in evaluated_candidates if cand["is_valid_structured"]]
    if current_debug_status: logger.info("DEBUG: Struktur-gültige Kandidaten nach Prüfung: %s", [c["code"] for c in valid_candidates])

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
        elif fallback_valid_candidates:
            chosen_list_for_selection = fallback_valid_candidates
            selection_type_message = "Fallback (C9x)"
        
        if chosen_list_for_selection:
            if current_debug_status: logger.info("INFO: Auswahl aus %s struktur-gültigen %s Kandidaten.", len(chosen_list_for_selection), selection_type_message)
            for cand in chosen_list_for_selection: cand["score"] = cand.get("taxpunkte", 0)
            def sort_key_score_suffix(candidate):
                code_str = str(candidate['code'])
                match = re.search(r"([A-Z])$", code_str)
                suffix_ord = ord(match.group(1)) if match else ord('Z') + 1
                return (-candidate.get("score", 0), suffix_ord)
            chosen_list_for_selection.sort(key=sort_key_score_suffix)
            selected_candidate_info = chosen_list_for_selection[0]
            if current_debug_status: logger.info("INFO: Gewählte Pauschale nach Score-Sortierung: %s",selected_candidate_info["code"])
        else:
             return {"type": "Error", "message": "Interner Fehler bei der Pauschalenauswahl (Kategorisierung fehlgeschlagen).", "evaluated_pauschalen": evaluated_candidates}
    else:
        logger.info("INFO: Keine Pauschale erfüllt die strukturierten Bedingungen.")
        if potential_pauschale_codes:
            gepruefte_codes_namen = [f"{c['code']} ({get_lang_field(c['details'], PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A'})"
                                     for c in evaluated_candidates if not c['is_valid_structured']]
            msg_details = ""
            if gepruefte_codes_namen:
                msg_details = " Folgende potenziellen Pauschalen wurden geprüft, aber deren Bedingungen waren nicht erfüllt: " + ", ".join(gepruefte_codes_namen)
            return {"type": "Error", "message": f"Keine der potenziellen Pauschalen erfüllte die detaillierten UND/ODER-Bedingungen.{msg_details}", "evaluated_pauschalen": evaluated_candidates}
        else:
            return {"type": "Error", "message": "Keine passende Pauschale gefunden (keine potenziellen Kandidaten).", "evaluated_pauschalen": evaluated_candidates}

    if not selected_candidate_info:
        return {"type": "Error", "message": "Interner Fehler: Keine Pauschale nach Auswahlprozess selektiert.", "evaluated_pauschalen": evaluated_candidates}

    best_pauschale_code = selected_candidate_info["code"]
    best_pauschale_details = selected_candidate_info["details"].copy()
    # HTML für die ausgewählte Pauschale wurde bereits im Loop generiert und in selected_candidate_info["bedingungs_pruef_html"] gespeichert.
    bedingungs_pruef_html_result = selected_candidate_info.get("bedingungs_pruef_html", "<p class='error'>Bedingungs-HTML nicht gefunden.</p>")
    condition_errors_html_gen = [] # Fehler bei der HTML-Generierung selbst, nicht bei der Bedingungsprüfung

    # Die Notwendigkeit, check_pauschale_conditions hier erneut aufzurufen, entfällt,
    # da die Ergebnisse (inkl. HTML) bereits in evaluated_candidates -> selected_candidate_info gespeichert sind.
    # try:
    #     # Hole die spezifischen Bedingungen für die beste Pauschale aus dem Index
    #     conditions_for_best_pauschale = pauschale_bedingungen_indexed.get(str(best_pauschale_code), [])
    #     condition_result_html_dict = check_pauschale_conditions(
    #         best_pauschale_code, context, conditions_for_best_pauschale, # Verwende indizierte Liste
    #         tabellen_dict_by_table, leistungskatalog_dict, lang
    #     )
    #     bedingungs_pruef_html_result = condition_result_html_dict.get("html", "<p class='error'>Fehler bei HTML-Generierung der Bedingungen.</p>")
    #     condition_errors_html_gen.extend(condition_result_html_dict.get("errors", []))
    # except Exception as e_html_gen: # This was part of the commented out block, ensure it's properly handled or removed if selected_candidate_info always has the HTML
    #     logger.error("FEHLER bei Aufruf von check_pauschale_conditions (HTML-Generierung) für %s: %s", best_pauschale_code, e_html_gen)
    #     traceback.print_exc()
    #     bedingungs_pruef_html_result = (f"<p class='error'>Schwerwiegender Fehler bei HTML-Generierung der Bedingungen: {escape(str(e_html_gen))}</p>")
        # condition_errors_html_gen = [f"Fehler HTML-Generierung: {e_html_gen}"] # This line is also part of the commented logic

    lkns_fuer_erklaerung = [str(lkn) for lkn in context.get('LKN', []) if lkn]
    if lang == 'fr':
        pauschale_erklaerung_html = (f"<p>Sur la base du contexte (p.ex. LKN : {escape(', '.join(lkns_fuer_erklaerung) or 'aucun')}, lateralité : {escape(str(context.get('Seitigkeit')))}, nombre : {escape(str(context.get('Anzahl')))}, vérification ICD active : {context.get('useIcd', True)}) les forfaits suivants ont été vérifiés :</p>")
    elif lang == 'it':
        pauschale_erklaerung_html = (f"<p>Sulla base del contesto (ad es. LKN: {escape(', '.join(lkns_fuer_erklaerung) or 'nessuna')}, lateralità: {escape(str(context.get('Seitigkeit')))}, numero: {escape(str(context.get('Anzahl')))}, verifica ICD activa: {context.get('useIcd', True)}) sono stati verificati i seguenti forfait:</p>")
    else:
        pauschale_erklaerung_html = (f"<p>Basierend auf dem Kontext (u.a. LKNs: {escape(', '.join(lkns_fuer_erklaerung) or 'keine')}, Seitigkeit: {escape(str(context.get('Seitigkeit')))}, Anzahl: {escape(str(context.get('Anzahl')))}, ICD-Prüfung aktiv: {context.get('useIcd', True)}) wurden folgende Pauschalen geprüft:</p>")
    
    pauschale_erklaerung_html += "<ul>"
    for cand_eval in sorted(evaluated_candidates, key=lambda x: x['code']):
        status_text = f"<span style=\"color:green;\">{translate('conditions_met', lang)}</span>" if cand_eval['is_valid_structured'] else f"<span style=\"color:red;\">{translate('conditions_not_met', lang)}</span>"
        code_str = escape(cand_eval['code'])
        link = f"<a href='#' class='pauschale-exp-link' data-code='{code_str}'>{code_str}</a>"
        pauschale_erklaerung_html += (f"<li><b>{link}</b>: {escape(get_lang_field(cand_eval['details'], PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A')} {status_text}</li>")
    pauschale_erklaerung_html += "</ul>"
    
    if lang == 'fr':
        pauschale_erklaerung_html += (f"<p><b>Choix : {escape(best_pauschale_code)}</b> ({escape(get_lang_field(best_pauschale_details, PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A')}) - comme forfait avec la lettre suffixe la plus basse (p. ex. A avant B) parmi les candidats valides de la catégorie privilégiée (forfaits spécifiques avant forfaits de secours C9x).</p>")
    elif lang == 'it':
        pauschale_erklaerung_html += (f"<p><b>Selezionato: {escape(best_pauschale_code)}</b> ({escape(get_lang_field(best_pauschale_details, PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A')}) - come forfait con la lettera suffisso più bassa (es. A prima di B) tra i candidati validi della categoria preferita (forfait specifici prima dei forfait di fallback C9x).</p>")
    else:
        pauschale_erklaerung_html += (f"<p><b>Ausgewählt wurde: {escape(best_pauschale_code)}</b> ({escape(get_lang_field(best_pauschale_details, PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A')}) - als die Pauschale mit dem niedrigsten Suffix-Buchstaben (z.B. A vor B) unter den gültigen Kandidaten der bevorzugten Kategorie (spezifische Pauschalen vor Fallback-Pauschalen C9x).</p>")

    match_stamm = re.match(r"([A-Z0-9.]+)([A-Z])$", str(best_pauschale_code))
    pauschalen_stamm_code = match_stamm.group(1) if match_stamm else None
    if pauschalen_stamm_code:
        other_evaluated_codes_in_group = [cand for cand in evaluated_candidates if str(cand['code']).startswith(pauschalen_stamm_code) and str(cand['code']) != best_pauschale_code]
        if other_evaluated_codes_in_group:
            if lang == 'fr': pauschale_erklaerung_html += f"<hr><p><b>Comparaison avec d'autres forfaits du groupe '{escape(pauschalen_stamm_code)}':</b></p>"
            elif lang == 'it': pauschale_erklaerung_html += f"<hr><p><b>Confronto con altri forfait del gruppo '{escape(pauschalen_stamm_code)}':</b></p>"
            else: pauschale_erklaerung_html += f"<hr><p><b>Vergleich mit anderen Pauschalen der Gruppe '{escape(pauschalen_stamm_code)}':</b></p>"
            # Verwende pauschale_bedingungen_indexed für get_simplified_conditions
            conditions_for_selected_pauschale = pauschale_bedingungen_indexed.get(str(best_pauschale_code), [])
            selected_conditions_repr_set = get_simplified_conditions(best_pauschale_code, conditions_for_selected_pauschale)
            for other_cand in sorted(other_evaluated_codes_in_group, key=lambda x: x['code']):
                other_code_str = str(other_cand['code']); other_details_dict = other_cand['details']
                validity_info_html = f"<span style=\"color:green;\">{translate('conditions_also_met', lang)}</span>" if other_cand['is_valid_structured'] else f"<span style=\"color:red;\">{translate('conditions_not_met', lang)}</span>"
                conditions_for_other_pauschale = pauschale_bedingungen_indexed.get(str(other_code_str), [])
                other_conditions_repr_set = get_simplified_conditions(other_code_str, conditions_for_other_pauschale)
                additional_conditions_for_other = other_conditions_repr_set - selected_conditions_repr_set
                missing_conditions_in_other = selected_conditions_repr_set - other_conditions_repr_set
                diff_label = translate('diff_to', lang)
                pauschale_erklaerung_html += (f"<details style='margin-left: 15px; font-size: 0.9em;'><summary>{diff_label} <b>{escape(other_code_str)}</b> ({escape(get_lang_field(other_details_dict, PAUSCHALE_TEXT_KEY_IN_PAUSCHALEN, lang) or 'N/A')}) {validity_info_html}</summary>")
                if additional_conditions_for_other:
                    if lang == 'fr': pauschale_erklaerung_html += f"<p>Exigences supplémentaires / autres pour {escape(other_code_str)}:</p><ul>"
                    elif lang == 'it': pauschale_erklaerung_html += f"<p>Requisiti supplementari / altri per {escape(other_code_str)}:</p><ul>"
                    else: pauschale_erklaerung_html += f"<p>Zusätzliche/Andere Anforderungen für {escape(other_code_str)}:</p><ul>"
                    for cond_tuple_item in sorted(list(additional_conditions_for_other)): pauschale_erklaerung_html += generate_condition_detail_html(cond_tuple_item, leistungskatalog_dict, tabellen_dict_by_table, lang)
                    pauschale_erklaerung_html += "</ul>"
                if missing_conditions_in_other:
                    if lang == 'fr': pauschale_erklaerung_html += f"<p>Les exigences suivantes de {escape(best_pauschale_code)} manquent pour {escape(other_code_str)}:</p><ul>"
                    elif lang == 'it': pauschale_erklaerung_html += f"<p>I seguenti requisiti di {escape(best_pauschale_code)} mancano in {escape(other_code_str)}:</p><ul>"
                    else: pauschale_erklaerung_html += f"<p>Folgende Anforderungen von {escape(best_pauschale_code)} fehlen bei {escape(other_code_str)}:</p><ul>"
                    for cond_tuple_item in sorted(list(missing_conditions_in_other)): pauschale_erklaerung_html += generate_condition_detail_html(cond_tuple_item, leistungskatalog_dict, tabellen_dict_by_table, lang)
                    pauschale_erklaerung_html += "</ul>"
                if not additional_conditions_for_other and not missing_conditions_in_other:
                    if lang == 'fr': pauschale_erklaerung_html += "<p><i>Aucune différence de conditions essentielles trouvée (basé sur un contrôle simplifié type/valeur). Des différences détaillées peuvent exister au niveau du nombre ou de groupes logiques spécifiques.</i></p>"
                    elif lang == 'it': pauschale_erklaerung_html += "<p><i>Nessuna differenza nelle condizioni principali trovata (basato su un confronto semplificato tipo/valore). Differenze dettagliate possibili nel numero o in gruppi logici specifici.</i></p>"
                    else: pauschale_erklaerung_html += "<p><i>Keine unterschiedlichen Kernbedingungen gefunden (basierend auf vereinfachter Typ/Wert-Prüfung). Detaillierte Unterschiede können in der Anzahl oder spezifischen Logikgruppen liegen.</i></p>"
                pauschale_erklaerung_html += "</details>"
    
    best_pauschale_details[PAUSCHALE_ERKLAERUNG_KEY] = pauschale_erklaerung_html
    potential_icds_list = []
    # Hole die spezifischen, bereits gefilterten und sortierten Bedingungen für die beste Pauschale
    conditions_for_best_pauschale_final = pauschale_bedingungen_indexed.get(str(best_pauschale_code), [])
    for cond_item_icd in conditions_for_best_pauschale_final:
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
        "type": "Pauschale", "details": best_pauschale_details,
        "bedingungs_pruef_html": bedingungs_pruef_html_result,
        "bedingungs_fehler": condition_errors_html_gen,
        "conditions_met": True,
        "evaluated_pauschalen": evaluated_candidates
    }
    return final_result_dict

def get_simplified_conditions(pauschale_code: str, bedingungen_data: list[dict]) -> set:
    simplified_set = set()
    PAUSCHALE_KEY = 'Pauschale'; BED_TYP_KEY = 'Bedingungstyp'; BED_WERTE_KEY = 'Werte'
    BED_FELD_KEY = 'Feld'; BED_MIN_KEY = 'MinWert'; BED_MAX_KEY = 'MaxWert'
    BED_VERGLEICHSOP_KEY = 'Vergleichsoperator'
    # Die übergebenen bedingungen_data sind bereits spezifisch für die Pauschale.
    # Die Filterung nach pauschale_code ist hier nicht mehr notwendig, wenn der Aufrufer dies sicherstellt.
    # pauschale_conditions = [cond for cond in bedingungen_data if cond.get(PAUSCHALE_KEY) == pauschale_code]
    # Stattdessen direkt bedingungen_data verwenden:
    for cond in bedingungen_data: # Annahme: bedingungen_data ist bereits die korrekte, gefilterte Liste
        typ_original = cond.get(BED_TYP_KEY, "").upper()
        wert = str(cond.get(BED_WERTE_KEY, "")).strip()
        feld = str(cond.get(BED_FELD_KEY, "")).strip()
        vergleichsop = str(cond.get(BED_VERGLEICHSOP_KEY, "=")).strip()
        condition_tuple = None
        final_cond_type_for_comparison = typ_original
        if typ_original in ["LEISTUNGSPOSITIONEN IN TABELLE", "TARIFPOSITIONEN IN TABELLE", "LKN IN TABELLE"]:
            final_cond_type_for_comparison = 'LKN_TABLE'
            condition_tuple = (final_cond_type_for_comparison, tuple(sorted([t.strip().lower() for t in wert.split(',') if t.strip()])))
        elif typ_original in ["HAUPTDIAGNOSE IN TABELLE", "ICD IN TABELLE"]:
            final_cond_type_for_comparison = 'ICD_TABLE'
            condition_tuple = (final_cond_type_for_comparison, tuple(sorted([t.strip().lower() for t in wert.split(',') if t.strip()])))
        elif typ_original in ["LEISTUNGSPOSITIONEN IN LISTE", "LKN"]:
            final_cond_type_for_comparison = 'LKN_LIST'
            condition_tuple = (final_cond_type_for_comparison, tuple(sorted([lkn.strip().upper() for lkn in wert.split(',') if lkn.strip()])))
        elif typ_original in ["HAUPTDIAGNOSE IN LISTE", "ICD"]:
             final_cond_type_for_comparison = 'ICD_LIST'
             condition_tuple = (final_cond_type_for_comparison, tuple(sorted([icd.strip().upper() for icd in wert.split(',') if icd.strip()])))
        elif typ_original in ["MEDIKAMENTE IN LISTE", "GTIN"]:
            final_cond_type_for_comparison = 'GTIN_LIST'
            condition_tuple = (final_cond_type_for_comparison, tuple(sorted([gtin.strip() for gtin in wert.split(',') if gtin.strip()])))
        elif typ_original == "PATIENTENBEDINGUNG" and feld:
            final_cond_type_for_comparison = f'PATIENT_{feld.upper()}'
            if feld.lower() == "alter":
                min_w = cond.get(BED_MIN_KEY); max_w = cond.get(BED_MAX_KEY)
                wert_repr = f"min:{min_w or '-'}_max:{max_w or '-'}" if min_w is not None or max_w is not None else f"exact:{wert}"
                condition_tuple = (final_cond_type_for_comparison, wert_repr)
            else:
                condition_tuple = (final_cond_type_for_comparison, wert.lower())
        elif typ_original == "ALTER IN JAHREN BEI EINTRITT":
            final_cond_type_for_comparison = 'PATIENT_ALTER_EINTRITT'
            condition_tuple = (final_cond_type_for_comparison, f"{vergleichsop}{wert}")
        elif typ_original == "ANZAHL":
            final_cond_type_for_comparison = 'ANZAHL_CHECK'
            condition_tuple = (final_cond_type_for_comparison, f"{vergleichsop}{wert}")
        elif typ_original == "SEITIGKEIT":
            final_cond_type_for_comparison = 'SEITIGKEIT_CHECK'
            norm_regel_wert = wert.strip().replace("'", "").lower()
            if norm_regel_wert == 'b': norm_regel_wert = 'beidseits'
            elif norm_regel_wert == 'e': norm_regel_wert = 'einseitig'
            condition_tuple = (final_cond_type_for_comparison, f"{vergleichsop}{norm_regel_wert}")
        elif typ_original == "GESCHLECHT IN LISTE":
            final_cond_type_for_comparison = 'GESCHLECHT_LIST_CHECK'
            condition_tuple = (final_cond_type_for_comparison, tuple(sorted([g.strip().lower() for g in wert.split(',') if g.strip()])))
        else:
            condition_tuple = (typ_original, wert)
        if condition_tuple: simplified_set.add(condition_tuple)
    return simplified_set

def generate_condition_detail_html(
    condition_tuple: tuple,
    leistungskatalog_dict: Dict,
    tabellen_dict_by_table: Dict,
    lang: str = 'de'
    ) -> str:
    cond_type_comp, cond_value_comp = condition_tuple
    condition_html = "<li>"
    try:
        if cond_type_comp == 'LKN_LIST':
            condition_html += translate('require_lkn_list', lang)
            if not cond_value_comp:
                condition_html += f"<i>{translate('no_lkns_spec', lang)}</i>"
            else:
                lkn_details_html_parts = []
                for lkn_code in cond_value_comp:
                    beschreibung = get_beschreibung_fuer_lkn_im_backend(lkn_code, leistungskatalog_dict, lang)
                    lkn_details_html_parts.append(f"<b>{html.escape(lkn_code)}</b> ({html.escape(beschreibung)})")
                condition_html += ", ".join(lkn_details_html_parts)
        elif cond_type_comp == 'LKN_TABLE':
            condition_html += translate('require_lkn_table', lang)
            if not cond_value_comp:
                condition_html += f"<i>{translate('no_table_name', lang)}</i>"
            else:
                table_links_html_parts = []
                for table_name_norm in cond_value_comp:
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
                    table_detail_html = (f"<details class='inline-table-details-comparison'><summary>{html.escape(table_name_norm.upper())}</summary> ({entry_count} {entries_label}){details_content_html}</details>")
                    table_links_html_parts.append(table_detail_html)
                condition_html += ", ".join(table_links_html_parts)
        elif cond_type_comp == 'ICD_TABLE':
            condition_html += translate('require_icd_table', lang)
            if not cond_value_comp:
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
                    table_detail_html = (f"<details class='inline-table-details-comparison'><summary>{html.escape(table_name_norm.upper())}</summary> ({entry_count} {entries_label}){details_content_html}</details>")
                    table_links_html_parts.append(table_detail_html)
                condition_html += ", ".join(table_links_html_parts)
        elif cond_type_comp == 'ICD_LIST':
            condition_html += translate('require_icd_list', lang)
            if not cond_value_comp:
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
            condition_html += translate('patient_condition', lang, field=html.escape(feld_name), value=html.escape(str(cond_value_comp)))
        elif cond_type_comp == 'ANZAHL_CHECK':
            condition_html += translate('anzahl_condition', lang, value=html.escape(str(cond_value_comp)))
        elif cond_type_comp == 'SEITIGKEIT_CHECK':
            condition_html += translate('seitigkeit_condition', lang, value=html.escape(str(cond_value_comp)))
        elif cond_type_comp == 'GESCHLECHT_LIST_CHECK':
            condition_html += translate('geschlecht_list', lang)
            if not cond_value_comp: condition_html += f"<i>{translate('no_gender_spec', lang)}</i>"
            else: condition_html += html.escape(", ".join(cond_value_comp))
        else:
            condition_html += f"{html.escape(cond_type_comp)}: {html.escape(str(cond_value_comp))}"
    except Exception as e_detail_gen:
        logger.error("FEHLER beim Erstellen der Detailansicht für Vergleichs-Bedingung '%s': %s", condition_tuple, e_detail_gen)
        traceback.print_exc()
        condition_html += f"<i>Fehler bei Detailgenerierung: {html.escape(str(e_detail_gen))}</i>"
    condition_html += "</li>"
    return condition_html
