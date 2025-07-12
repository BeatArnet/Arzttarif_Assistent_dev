# regelpruefer.py

"""
Modul zur Prüfung der Abrechnungsregeln (Regelwerk) für TARDOC-Leistungen
und der Bedingungen für Pauschalen.
"""
import json
import logging
import re  # Importiere Regex für Mengenanpassung
from typing import Dict, List
from utils import get_lang_field

logger = logging.getLogger(__name__)

# --- Konstanten für Regeltypen (zur besseren Lesbarkeit) ---
REGEL_MENGE = "Mengenbeschränkung"
REGEL_ZUSCHLAG_ZU = "Nur als Zuschlag zu"
REGEL_NICHT_KUMULIERBAR = "Nicht kumulierbar mit"
REGEL_PAT_GESCHLECHT = "Patientenbedingung: Geschlecht" # Veraltet, nutze Patientenbedingung
REGEL_PAT_ALTER = "Patientenbedingung: Alter"       # Veraltet, nutze Patientenbedingung
REGEL_PAT_BEDINGUNG = "Patientenbedingung" # Neuer, generischer Typ
REGEL_DIAGNOSE = "Diagnosepflicht"
REGEL_PAUSCHAL_AUSSCHLUSS = "Pauschalenausschluss"
# Fügen Sie hier weitere Typen hinzu, falls Ihr Regelmodell sie enthält

# --- Ladefunktion für das Regelwerk ---
def lade_regelwerk(path: str) -> dict:
    """
    Lädt das Regelwerk aus einer JSON-Datei und gibt ein Mapping von LKN zu Regeln zurück.

    Args:
        path: Pfad zur JSON-Datei mit strukturierten Regeln.
    Returns:
        Dict[str, list]: Schlüssel sind LKN-Codes, Werte sind Listen von Regel-Definitionsdicts.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        mapping: dict = {}
        # Annahme: data ist eine Liste von Objekten, jedes mit "LKN" und "Regeln"
        for entry in data:
            lkn = entry.get("LKN")
            if not lkn:
                logger.warning("WARNUNG: Regelobjekt ohne LKN gefunden: %s", entry)
                continue
            rules = entry.get("Regeln") or []
            mapping[lkn] = rules
        return mapping
    except FileNotFoundError:
        logger.error("FEHLER: Regelwerk-Datei nicht gefunden: %s", path)
        return {}
    except json.JSONDecodeError as e:
        logger.error(
            "FEHLER: Fehler beim Parsen der Regelwerk-JSON-Datei '%s': %s",
            path,
            e,
        )
        return {}
    except Exception as e:
        logger.error(
            "FEHLER: Unerwarteter Fehler beim Laden des Regelwerks '%s': %s",
            path,
            e,
        )
        return {}

# --- Hauptfunktion zur Regelprüfung für LKNs ---
def pruefe_abrechnungsfaehigkeit(fall: dict, regelwerk: dict) -> dict:
    """
    Prüft, ob eine gegebene Leistungsposition abrechnungsfähig ist.

    Args:
        fall: Dict mit Kontext zur Leistung (LKN, Menge, ICD, Begleit-LKNs, Pauschalen,
              optional Alter, Geschlecht, GTIN).
        regelwerk: Mapping von LKN zu Regel-Definitionen aus lade_regelwerk.
    Returns:
        Dict mit Schlüsseln:
          - abrechnungsfaehig (bool): True, wenn alle Regeln erfüllt sind.
          - fehler (list): Liste der Regelverstöße (Fehlermeldungen).
    """
    lkn = fall.get("LKN")
    menge = fall.get("Menge", 0) or 0
    begleit = fall.get("Begleit_LKNs") or []
    # Kontextdaten
    alter = fall.get("Alter")
    geschlecht = fall.get("Geschlecht")
    gtins = fall.get("GTIN") or [] # Stelle sicher, dass GTIN hier ankommt
    if isinstance(gtins, str): gtins = [gtins] # Mache zur Liste, falls String

    # Eindeutige ID für Logging, falls 'fall' sie nicht enthält
    request_id = fall.get("request_id", "regelpruefer_standalone")
    logger.info(f"[{request_id}] Starte Regelprüfung für LKN {lkn} mit Menge {menge}.")
    logger.debug(f"[{request_id}] Fall-Kontext für {lkn}: {json.dumps(fall, ensure_ascii=False)}")


    errors: list = []
    allowed = True

    # Hole die Regeln für diese LKN
    rules = regelwerk.get(lkn) or []
    if not rules:
        # Keine Regeln definiert -> gilt als OK
        logger.info(f"[{request_id}] Keine Regeln für LKN {lkn} gefunden. Abrechnungsfähig: True.")
        return {"abrechnungsfaehig": True, "fehler": []}

    logger.info(f"[{request_id}] Prüfe {len(rules)} Regel(n) für LKN {lkn}.")
    for i, rule in enumerate(rules):
        typ = rule.get("Typ")
        if not typ:
            logger.warning(f"[{request_id}] Regel {i+1} für LKN {lkn} hat keinen Typ. Wird ignoriert.")
            continue # Regel ohne Typ ignorieren

        rule_passed = True
        error_msg = ""
        logger.debug(f"[{request_id}] LKN {lkn}, Regel {i+1}: Typ='{typ}', Regel='{rule}'")

        # --- Mengenbesschränkung ---
        if typ == REGEL_MENGE:
            max_menge = rule.get("MaxMenge")
            if isinstance(max_menge, (int, float)) and menge > max_menge:
                rule_passed = False
                error_msg = f"Mengenbeschränkung überschritten (max. {max_menge}, angefragt {menge})"

        # --- Nur als Zuschlag zu ---
        elif typ == REGEL_ZUSCHLAG_ZU:
            parent = rule.get("LKN")
            if parent and parent not in begleit:
                rule_passed = False
                error_msg = f"Nur als Zuschlag zu {parent} zulässig (Basis fehlt)"

        # --- Nicht kumulierbar mit ---
        elif typ == REGEL_NICHT_KUMULIERBAR:
            not_with = rule.get("LKNs") or rule.get("LKN") or []
            if isinstance(not_with, str): not_with = [not_with]
            konflikt = [code for code in begleit if code in not_with]
            if konflikt:
                rule_passed = False
                codes = ", ".join(konflikt)
                error_msg = f"Nicht kumulierbar mit: {codes}"

        # --- Patientenbedingung (Generisch) ---
        elif typ == REGEL_PAT_BEDINGUNG:
            field = rule.get("Feld") # z.B. "Alter", "Geschlecht", "GTIN"
            wert_regel = rule.get("Wert") # Wert aus der Regel
            min_val = rule.get("MinWert") # Für Bereiche (z.B. Alter)
            max_val = rule.get("MaxWert") # Für Bereiche (z.B. Alter)
            wert_fall = fall.get(field) # Wert aus dem Abrechnungsfall

            bedingung_text = f"Patientenbedingung ({field})"
            condition_met = True # Start with True, set to False on failure

            if wert_fall is None:
                condition_met = False # Bedingung nicht prüfbar/erfüllt, wenn Wert fehlt
                error_msg = f"{bedingung_text} nicht erfüllt: Kontextwert fehlt"
            elif field == "Alter":
                try:
                    alter_patient = int(wert_fall)
                    alter_ok = True
                    range_parts = []
                    if min_val is not None and alter_patient < int(min_val): alter_ok = False; range_parts.append(f"min. {min_val}")
                    if max_val is not None and alter_patient > int(max_val): alter_ok = False; range_parts.append(f"max. {max_val}")
                    if wert_regel is not None and alter_patient != int(wert_regel): alter_ok = False; range_parts.append(f"exakt {wert_regel}") # Exakter Wert?
                    condition_met = alter_ok
                    if not condition_met: error_msg = f"{bedingung_text} ({' '.join(range_parts)}) nicht erfüllt (Patient: {alter_patient})"
                except (ValueError, TypeError):
                    condition_met = False; error_msg = f"{bedingung_text}: Ungültiger Alterswert im Fall ({wert_fall})"
            elif field == "Geschlecht":
                if isinstance(wert_regel, str) and isinstance(wert_fall, str):
                    condition_met = wert_fall.lower() == wert_regel.lower()
                    if not condition_met: error_msg = f"{bedingung_text}: erwartet '{wert_regel}', gefunden '{wert_fall}'"
                else: condition_met = False; error_msg = f"{bedingung_text}: Ungültige Werte für Geschlechtsprüfung"
            elif field == "GTIN":
                 # Prüfe, ob mindestens ein benötigter GTIN im Fall vorhanden ist
                 required_gtins = [str(wert_regel)] if isinstance(wert_regel, (str, int)) else [str(w) for w in (wert_regel or [])]
                 provided_gtins_str = [str(g) for g in (gtins or [])] # Nutze gtins Variable
                 condition_met = any(req in provided_gtins_str for req in required_gtins)
                 if not condition_met: error_msg = f"{bedingung_text}: Erwartet einen von {required_gtins}, nicht gefunden"
            else:
                logger.warning(
                    "[%s] WARNUNG: Unbekanntes Feld '%s' für Patientenbedingung bei LKN %s.",
                    request_id,
                    field,
                    lkn,
                )
                condition_met = True  # Unbekannte Felder ignorieren? Oder Fehler? Hier: Ignorieren

            if not condition_met: rule_passed = False

        # --- Diagnosepflicht ---
        elif typ == REGEL_DIAGNOSE:
            required_icds = rule.get("ICD") or rule.get("ICDs", [])
            if isinstance(required_icds, str): required_icds = [required_icds]
            provided_icds = fall.get("ICD", [])
            if isinstance(provided_icds, str): provided_icds = [provided_icds]

            if required_icds and not any(req_icd.upper() in (p_icd.upper() for p_icd in provided_icds) for req_icd in required_icds):
                 rule_passed = False
                 error_msg = f"Erforderliche Diagnose(n) nicht vorhanden (Benötigt: {', '.join(required_icds)})"

        # --- Pauschalenausschluss ---
        elif typ == REGEL_PAUSCHAL_AUSSCHLUSS:
             verbotene_pauschalen = rule.get("Pauschale") or rule.get("Pauschalen", [])
             if isinstance(verbotene_pauschalen, str): verbotene_pauschalen = [verbotene_pauschalen]
             abgerechnete_pauschalen = fall.get("Pauschalen", [])
             if isinstance(abgerechnete_pauschalen, str): abgerechnete_pauschalen = [abgerechnete_pauschalen]

             if any(verb in abgerechnete_pauschalen for verb in verbotene_pauschalen):
                  rule_passed = False
                  error_msg = f"Leistung nicht zulässig bei gleichzeitiger Abrechnung der Pauschale(n): {', '.join(verbotene_pauschalen)}"

        # --- Unbekannter Regeltyp ---
        else:
            logger.warning(
                "[%s] WARNUNG: Unbekannter Regeltyp '%s' für LKN %s ignoriert.",
                request_id,
                typ,
                lkn,
            )
            continue

        if not rule_passed:
            allowed = False
            if error_msg: errors.append(error_msg)
            logger.info(f"[{request_id}] LKN {lkn}, Regel {i+1} ('{typ}') NICHT ERFÜLLT. Grund: {error_msg}")
        else:
            logger.debug(f"[{request_id}] LKN {lkn}, Regel {i+1} ('{typ}') ERFÜLLT.")

    logger.info(f"[{request_id}] Regelprüfung für LKN {lkn} abgeschlossen. Abrechnungsfähig: {allowed}, Fehler: {errors}")
    return {"abrechnungsfaehig": allowed, "fehler": errors}


def prepare_tardoc_abrechnung(
    regel_ergebnisse_liste: list[dict], leistungskatalog_dict: dict, lang: str = 'de'
) -> dict:
    """
    Filtert regelkonforme TARDOC-Leistungen (Typ E/EZ) aus den Regelergebnissen
    und bereitet die Liste für die Frontend-Antwort vor.
    """
    logger.info("INFO (regelpruefer): TARDOC-Abrechnung wird vorbereitet...")
    tardoc_leistungen_final = []
    LKN_KEY = 'lkn'; MENGE_KEY = 'finale_menge'

    for res in regel_ergebnisse_liste:
        lkn = res.get(LKN_KEY)
        menge = res.get(MENGE_KEY, 0)
        abrechnungsfaehig = res.get("regelpruefung", {}).get("abrechnungsfaehig", False)

        if not lkn or not abrechnungsfaehig or menge <= 0: continue

        # Hole Details aus dem übergebenen Leistungskatalog
        lkn_info = leistungskatalog_dict.get(str(lkn).upper()) # Suche Case-Insensitive

        if lkn_info and lkn_info.get("Typ") in ['E', 'EZ']:
            tardoc_leistungen_final.append({
                "lkn": lkn,
                "menge": menge,
                "typ": lkn_info.get("Typ"),
                "beschreibung": get_lang_field(lkn_info, "Beschreibung", lang) or ""
            })
        elif not lkn_info:
            logger.warning(
                "WARNUNG (prepare_tardoc): Details für LKN %s nicht im Leistungskatalog gefunden.",
                lkn,
            )

    if not tardoc_leistungen_final:
        return {"type": "Error", "message": "Keine abrechenbaren TARDOC-Leistungen nach Regelprüfung gefunden."}
    else:
        logger.info(
            "INFO (regelpruefer): %s TARDOC-Positionen zur Abrechnung vorbereitet.",
            len(tardoc_leistungen_final),
        )
        return { "type": "TARDOC", "leistungen": tardoc_leistungen_final }    