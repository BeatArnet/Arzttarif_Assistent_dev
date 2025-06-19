# utils.py
import html
from typing import Dict, List, Any

def escape(text: Any) -> str:
    """Escapes HTML special characters in a string."""
    return html.escape(str(text))

def get_table_content(table_ref: str, table_type: str, tabellen_dict_by_table: dict) -> list[dict]:
    """Holt Einträge für eine Tabelle und einen Typ (Case-Insensitive)."""
    content = []
    # Schlüssel für PAUSCHALEN_Tabellen - anpassen falls nötig!
    TAB_CODE_KEY = 'Code'; TAB_TEXT_KEY = 'Code_Text'; TAB_TYP_KEY = 'Tabelle_Typ'

    table_names = [t.strip() for t in table_ref.split(',') if t.strip()]
    all_entries_for_type = []

    for name in table_names:
        normalized_key = name.lower() # Suche immer mit kleinem Schlüssel
        # print(f"DEBUG (get_table_content): Suche normalisierten Schlüssel '{normalized_key}' für Typ '{table_type}'") # Optional

        if normalized_key in tabellen_dict_by_table:
            # print(f"DEBUG (get_table_content): Schlüssel '{normalized_key}' gefunden.") # Optional
            for entry in tabellen_dict_by_table[normalized_key]: # Greife direkt auf die Liste zu
                entry_typ = entry.get(TAB_TYP_KEY)
                if entry_typ and entry_typ.lower() == table_type.lower():
                    code = entry.get(TAB_CODE_KEY); text = entry.get(TAB_TEXT_KEY)
                    if code: all_entries_for_type.append({"Code": code, "Code_Text": text or "N/A"})
        else:
             print(f"WARNUNG (get_table_content): Normalisierter Schlüssel '{normalized_key}' (Original: '{name}') nicht in tabellen_dict_by_table gefunden.")

    unique_content = {item['Code']: item for item in all_entries_for_type}.values()
    return sorted(unique_content, key=lambda x: x.get('Code', ''))

def get_lang_field(entry: Dict[str, Any], base_key: str, lang: str) -> Any:
    """Returns the value for a language-aware key if available."""
    if not isinstance(entry, dict):
        return None
    suffix = {'de': '', 'fr': '_f', 'it': '_i'}.get(str(lang).lower(), '')
    return entry.get(f"{base_key}{suffix}") or entry.get(base_key)


# Einfache Übersetzungsfunktion für Backend-Strings
_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    'conditions_met': {
        'de': '(Bedingungen erfüllt)',
        'fr': '(Conditions remplies)',
        'it': '(Condizioni soddisfatte)'
    },
    'conditions_not_met': {
        'de': '(Bedingungen NICHT erfüllt)',
        'fr': '(Conditions NON remplies)',
        'it': '(Condizioni NON soddisfatte)'
    },
    'conditions_also_met': {
        'de': '(Bedingungen auch erfüllt)',
        'fr': '(Conditions aussi remplies)',
        'it': '(Condizioni pure soddisfatte)'
    },
    'group_conditions': {
        'de': 'Bedingungen (Alle müssen erfüllt sein):',
        'fr': 'Conditions (toutes doivent être remplies) :',
        'it': 'Condizioni (tutte devono essere soddisfatte):'
    },
    'group_additional': {
        'de': 'Zusätzliche Bedingungen (Alle müssen erfüllt sein):',
        'fr': 'Conditions supplémentaires (toutes doivent être remplies) :',
        'it': 'Condizioni supplementari (tutte devono essere soddisfatte):'
    },
    'group_logic': {
        'de': 'Logik-Gruppe {id} (Alle Bedingungen dieser Gruppe müssen erfüllt sein):',
        'fr': 'Groupe logique {id} (toutes les conditions de ce groupe doivent être remplies) :',
        'it': 'Gruppo logico {id} (tutte le condizioni di questo gruppo devono essere soddisfatte):'
    },
    'no_valid_groups': {
        'de': 'Keine gültigen Bedingungsgruppen gefunden.',
        'fr': 'Aucun groupe de conditions valide trouvé.',
        'it': 'Nessun gruppo di condizioni valido trovato.'
    },
    'detail_html_not_generated': {
        'de': 'Detail-HTML für Bedingungen nicht generiert.',
        'fr': "HTML détaillé pour les conditions non généré.",
        'it': 'HTML dettagliato per le condizioni non generato.'
    },
    'require_lkn_list': {
        'de': 'Erfordert LKN aus Liste: ',
        'fr': 'NPL requis depuis une liste : ',
        'it': 'NPL richiesti da una lista: '
    },
    'require_lkn_table': {
        'de': 'Erfordert LKN aus Tabelle(n): ',
        'fr': 'NPL requis depuis table(s) : ',
        'it': 'NPL richiesti da tabella/e: '
    },
    'no_lkns_spec': {
        'de': '(Keine LKNs spezifiziert)',
        'fr': '(Aucun NPL spécifié)',
        'it': '(Nessun NPL specificato)'
    },
    'no_table_name': {
        'de': '(Kein Tabellenname spezifiziert)',
        'fr': '(Aucun nom de table spécifié)',
        'it': '(Nessun nome tabella specificato)'
    },
    'require_icd_table': {
        'de': 'Erfordert ICD aus Tabelle(n): ',
        'fr': 'ICD requis depuis table(s) : ',
        'it': 'ICD richiesti da tabella/e: '
    },
    'require_icd_list': {
        'de': 'Erfordert ICD aus Liste: ',
        'fr': 'ICD requis depuis une liste : ',
        'it': 'ICD richiesti da una lista: '
    },
    'no_icds_spec': {
        'de': '(Keine ICDs spezifiziert)',
        'fr': '(Aucun ICD spécifié)',
        'it': '(Nessun ICD specificato)'
    },
    'require_gtin_list': {
        'de': 'Erfordert GTIN aus Liste: ',
        'fr': 'GTIN requis depuis une liste : ',
        'it': 'GTIN richiesti da una lista: '
    },
    'no_gtins_spec': {
        'de': '(Keine GTINs spezifiziert)',
        'fr': '(Aucune GTIN spécifiée)',
        'it': '(Nessuna GTIN specificata)'
    },
    'patient_condition': {
        'de': 'Patientenbedingung ({field}): {value}',
        'fr': 'Condition patient ({field}) : {value}',
        'it': 'Condizione paziente ({field}) : {value}'
    },
    'anzahl_condition': {
        'de': 'Anzahlbedingung: {value}',
        'fr': 'Condition sur la quantité : {value}',
        'it': 'Condizione sul numero: {value}'
    },
    'seitigkeit_condition': {
        'de': 'Seitigkeitsbedingung: {value}',
        'fr': 'Condition de latéralité : {value}',
        'it': 'Condizione di lateralità: {value}'
    },
    'geschlecht_list': {
        'de': 'Geschlecht aus Liste: ',
        'fr': 'Sexe dans la liste : ',
        'it': 'Sesso in elenco: '
    },
    'no_gender_spec': {
        'de': '(Keine Geschlechter spezifiziert)',
        'fr': '(Aucun sexe spécifié)',
        'it': '(Nessun sesso specificato)'
    },
    'fulfilled_by': {
        'de': '(Erfüllt durch: {items})',
        'fr': '(Rempli par : {items})',
        'it': '(Soddisfatto da: {items})'
    },
    'context_items_not_in_table': {
        'de': '(Kontext-Element(e) {items} nicht in Regel-Tabelle(n) gefunden)',
        'fr': '(Élément(s) du contexte {items} non trouvé(s) dans la/les table(s) de règle)',
        'it': '(Elemento/i di contesto {items} non trovato/i nelle tabelle delle regole)'
    },
    'tables_empty': {
        'de': '(Regel-Tabelle(n) leer oder nicht gefunden)',
        'fr': '(Table(s) de règle vide(s) ou non trouvée(s))',
        'it': '(Tabella/e delle regole vuota/e o non trovata/e)'
    },
    'context_items_not_in_list': {
        'de': '(Kontext-Element(e) {items} nicht in Regel-Liste)',
        'fr': '(Élément(s) du contexte {items} absent(s) de la liste de règle)',
        'it': '(Elemento/i di contesto {items} non presente/i nell\'elenco della regola)'
    },
    'no_context_in_list': {
        'de': '(Kein Kontext-Element in Regel-Liste)',
        'fr': '(Aucun élément du contexte dans la liste de règle)',
        'it': '(Nessun elemento di contesto nell\'elenco della regola)'
    },
    'rule_list_empty': {
        'de': '(Regel-Liste leer)',
        'fr': '(Liste de règle vide)',
        'it': '(Elenco della regola vuoto)'
    },
    'entries_label': {
        'de': 'Einträge',
        'fr': 'entrées',
        'it': 'voci'
    },
    'context_value': {
        'de': '(Kontext: {value})',
        'fr': '(Contexte : {value})',
        'it': '(Contesto: {value})'
    },
    'diff_to': {
        'de': 'Unterschiede zu',
        'fr': 'Différences avec',
        'it': 'Differenze rispetto a'
    },
    'or_separator': {
        'de': 'ODER',
        'fr': 'OU',
        'it': 'OPPURE'
    }
}


def translate(key: str, lang: str = 'de', **kwargs) -> str:
    """Einfache Übersetzung bestimmter Texte mit Platzhaltern."""
    lang = str(lang).lower()
    template = _TRANSLATIONS.get(key, {}).get(lang) or _TRANSLATIONS.get(key, {}).get('de') or key
    return template.format(**kwargs)
