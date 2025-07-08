# --- Prompt-Übersetzungen ---
def get_stage1_prompt(user_input: str, katalog_context: str, lang: str) -> str:
    """Return the Stage 1 prompt in the requested language."""
    if lang == "fr":
        return f"""**Tâche :** Analysez le texte de traitement médical suisse suivant avec la plus grande précision. Votre mission est d'identifier les numéros de catalogue des prestations (LKN) pertinents, de déterminer leur quantité et d'extraire les informations contextuelles. Utilisez principalement le catalogue LKAAT_Leistungskatalog fourni, mais vous pouvez également tenir compte des synonymes médicaux ou des termes courants. Les Pauschales (forfaits) doivent être ignorées lors de l'identification des LKN.

**Contexte : LKAAT_Leistungskatalog (source de référence pour les LKN valides, leurs descriptions et les sections "MedizinischeInterpretation" contenant des termes supplémentaires ; la table des forfaits peut être consultée à titre complémentaire mais les LKN de type Pauschale ne doivent pas être sélectionnées ici.)
--- Leistungskatalog Start ---
{katalog_context}
--- Leistungskatalog Ende ---

**Rôle :** Vous êtes un expert du tarif médical suisse TARDOC. Votre unique tâche est d'identifier et de coder correctement les prestations individuelles (LKN) à partir d'un texte de traitement.

**Instructions :** Suivez précisément les étapes suivantes :

1.  **Analyse du texte et décomposition des tâches :**
    *   Lisez attentivement le "Behandlungstext" (texte de traitement).
    *   **CRITIQUE :** Si le texte décrit plusieurs activités distinctes et séparées (par des signes de ponctuation ou des mots comme "plus", "et", "ainsi que", "suivi de"), traitez chaque activité comme une tâche distincte.
        *   Exemple : "Consultation de médecine générale 15 min plus 10 minutes de conseil à l'enfant"
            *   Tâche 1 : "Consultation de médecine générale 15 min"
            *   Tâche 2 : "10 minutes de conseil à l'enfant"
        *   Attribuez toujours les indications de temps et autres détails à la tâche correcte.

2.  **Identification des LKN (par tâche) :**
    *   **Interprétation médicale :** Comprenez l'intention médicale, pas seulement les mots exacts. Utilisez vos connaissances des synonymes, termes techniques et paraphrases.
        *   Exemples : "Ablation" est synonyme d'"exérèse". Une "verrue" est une "lésion cutanée bénigne". "Cathétérisme cardiaque gauche" correspond à "coronarographie".
        *   Si une anesthésie ou une narcose réalisée par un anesthésiste est mentionnée, sélectionnez explicitement un code du chapitre WA.10 (table ANAST). S'il n'est pas fait mention de la durée, utilisez par défaut `WA.10.0010`. Lorsque la durée précise en minutes est indiquée, employez le code `WA.10.00x0` approprié.
        *   **Instruction Critique pour Enlèvement de Verrue à la Curette/Cuillère Tranchante :** Si le texte de traitement décrit explicitement l'"enlèvement d'une verrue" (ou synonymes directs) ET mentionne l'utilisation d'une "curette" ou "cuillère tranchante" (ou traductions directes) :
            *   Vous **DEVEZ IMPÉRATIVEMENT** donner la priorité aux LKN qui décrivent spécifiquement le "curetage de verrue" ou "l'enlèvement de verrue par curetage".
            *   Recherchez activement des codes comme `MK.05.0070` (si celui-ci correspond au "curetage de verrues" ou similaire et est présent dans le catalogue fourni).
            *   Cette instruction spécifique pour le curetage de verrues **PRIME** sur les codes plus généraux d'exérèse de lésions cutanées.
        *   **IMPORTANT :** Si une procédure n'existe dans le catalogue que sous forme de forfait (par exemple, de nombreuses interventions chirurgicales majeures), vous ne trouverez pas de LKN correspondantes. Dans ce cas, une liste `identified_leistungen` vide est la réponse correcte.
    *   Consultez activement le champ "MedizinischeInterpretation" du catalogue, car il contient souvent des indications importantes sur des désignations alternatives ou des synonymes courants pour une prestation.
    *   **Remarques administratives:** Ignorez les remarques purement administratives ou logistiques (p.ex., "temps de transfert vers la dermatologie", "le patient a attendu") lors de l'identification des LKN cliniques facturables, à moins qu'elles n'informent directement un paramètre facturable (p.ex., durée d'une prestation surveillée).


3.  **RÈGLES SPÉCIFIQUES pour les LKN et le calcul des quantités :**
    *   **A) Logique pour les consultations (Chapitres AA & CA) :**
        *   Cette logique s'applique uniquement aux activités telles que "consultation", "entretien", "consultation de médecine générale/de famille".
        *   Étape 1 : Extrayez la durée totale de cette consultation en minutes (par ex., "15 minutes").
        *   Étape 2 : Choisissez le chapitre :
            *   **CA (Médecin de famille) :** Si le texte contient "médecin de famille", "médecine de famille" ou des termes équivalents (par ex. "hausärztlich" si le contexte l'indique clairement).
            *   **AA (Général) :** Dans TOUS LES AUTRES CAS de consultation générale.
        *   Étape 3 : Appliquez la règle de répartition suivante de manière stricte :
            *   LKN de base : `AA.00.0010` ou `CA.00.0010` ("5 premières min."). La quantité est TOUJOURS 1.
            *   LKN supplémentaire : Uniquement si la durée dépasse 5 minutes, ajoutez `AA.00.0020` ou `CA.00.0020` ("chaque min. supplémentaire").
            *   Quantité de la LKN supplémentaire : La quantité est EXACTEMENT (durée en minutes - 5).
            *   Exemple "Consultation 15 minutes" : -> `AA.00.0010` (quantité 1) + `AA.00.0020` (quantité 10).
    *   **B) Logique pour les autres prestations basées sur le temps :**
        *   Ceci s'applique à toutes les autres LKN avec une indication de temps (par ex., "par 1 min", "par 5 min").
        *   Exemple : "...exérèse verrue... 5 minutes" trouve la LKN `MK.05.0070` ("...par 1 min").
        *   Calcul de la quantité : La quantité est EXACTEMENT (durée de l'activité / unité de temps de la LKN).
            *   Exemple : 5 minutes pour une LKN "par 1 min" -> quantité = 5 / 1 = 5.
            *   Exemple : 10 minutes pour une LKN "par 5 min" -> quantité = 10 / 5 = 2.
    *   **C) Prestations avec "latéralité" :** Si une prestation requiert une "latéralité" (Seitigkeit), alors pour "des deux côtés" (correspondant à "beidseits"), saisissez quantité = 2 ET `seitigkeit` = "beidseits". Pour "unilatéral" (correspondant à "einseitig"), quantité = 1 et la `seitigkeit` spécifiée ("links" ou "rechts").

4.  **Validation stricte :**
    *   Pour CHAQUE LKN identifiée : Vérifiez LETTRE PAR LETTRE et CHIFFRE PAR CHIFFRE que le code existe dans le catalogue.
    *   Seules les LKN qui réussissent cette vérification sont incluses dans la liste finale. Pour chaque LKN validée, ajoutez le `typ` et la `beschreibung` **directement et sans modification** depuis le contexte du catalogue pour cette LKN.


5.  **Extraction des informations contextuelles :**
    *   Extrayez **uniquement** les valeurs explicitement mentionnées dans le "Behandlungstext". Pour `geschlecht` et `seitigkeit`, utilisez les termes allemands spécifiés pour la sortie JSON :
        *   `dauer_minuten` (nombre) : durée de la prestation principale ou durée totale si plusieurs temps sont indiqués.
        *   `menge_allgemein` (nombre)
        *   `alter` (nombre)
        *   `geschlecht` (chaîne: 'weiblich', 'männlich', 'divers', 'unbekannt')
        *   `seitigkeit` (chaîne: 'einseitig', 'beidseits', 'links', 'rechts', 'unbekannt')
        *   `anzahl_prozeduren` (nombre ou `null`)
    *   Si une valeur n'est pas mentionnée, définissez-la sur `null` (sauf `seitigkeit` et `geschlecht` qui doivent être 'unbekannt' si non spécifié).

6.  **Justification (`begruendung_llm`) :**
    *   Indiquez brièvement pourquoi les LKN **validées** ont été choisies et comment les quantités ont été calculées. Référez-vous à votre analyse des étapes précédentes et aux **descriptions du catalogue**.

**Format de sortie :** **UNIQUEMENT** du JSON valide, **AUCUN** autre texte.
```json
{{
  "identified_leistungen": [
    {{
      "lkn": "LKN_VALIDÉE_1",
      "typ": "TYPE_DU_CATALOGUE_1",
      "beschreibung": "DESCRIPTION_DU_CATALOGUE_1",
      "menge": QUANTITÉ_LKN_1
    }}
  ],
  "extracted_info": {{
    "dauer_minuten": null,
    "menge_allgemein": null,
    "alter": null,
    "geschlecht": "unbekannt",
    "seitigkeit": "unbekannt",
    "anzahl_prozeduren": null
  }},
  "begruendung_llm": "<Brève justification>"
}}

Si aucune LKN correspondante du catalogue n'est trouvée, renvoyez un objet JSON avec une liste "identified_leistungen" vide.

Behandlungstext: "{user_input}"

Réponse JSON:"""
    elif lang == "it":
        return f"""**Compito:** Analizzi il seguente testo di trattamento medico svizzero con la massima precisione. Il Suo compito è identificare i numeri di catalogo delle prestazioni (LKN) pertinenti, determinarne la quantità ed estrarre le informazioni contestuali. Utilizzi principalmente il catalogo LKAAT_Leistungskatalog fornito, ma può anche tenere conto di sinonimi medici o termini comuni. Le Pauschal (prestazioni forfettarie) devono essere ignorate durante l'identificazione delle LKN.

**Contesto: LKAAT_Leistungskatalog (fonte di riferimento per le LKN valide, le loro descrizioni e le sezioni "MedizinischeInterpretation" contenenti termini aggiuntivi; la tabella delle Pauschal può essere consultata in via complementare, ma le LKN di tipo Pauschal non devono essere selezionate qui.)
--- Leistungskatalog Start ---
{katalog_context}
--- Leistungskatalog Ende ---

**Ruolo:** Lei è un esperto della tariffa medica svizzera TARDOC. Il Suo unico compito è identificare e codificare correttamente le prestazioni singole (LKN) a partire da un testo di trattamento.

**Istruzioni:** Segua precisamente i seguenti passaggi:

1.  **Analisi del testo e scomposizione dei compiti:**
    *   Legga attentamente il "Behandlungstext" (testo del trattamento).
    *   **CRITICO:** Se il testo descrive più attività distinte e separate (da segni di punteggiatura o parole come "più", "e", "così come", "seguito da"), tratti ogni attività come un compito distinto.
        *   Esempio: "Consultazione di medicina generale 15 min più 10 minuti di consulenza al bambino"
            *   Compito 1: "Consultazione di medicina generale 15 min"
            *   Compito 2: "10 minuti di consulenza al bambino"
        *   Attribuisca sempre le indicazioni di tempo e altri dettagli al compito corretto.

2.  **Identificazione delle LKN (per compito):**
    *   **Interpretazione medica:** Comprenda l'intento medico, non solo le parole esatte. Utilizzi la Sua conoscenza di sinonimi, termini tecnici e parafrasi.
        *   Esempi: "Rimozione" è sinonimo di "asportazione". Una "verruca" è una "lesione cutanea benigna". "Cateterismo cardiaco sinistro" corrisponde a "coronarografia".
        *   Se viene menzionata un'anestesia o narcosi eseguita da un anestesista, selezioni esplicitamente un codice del capitolo WA.10 (tabella ANAST). Se non è indicata la durata, usi di default `WA.10.0010`. Quando viene fornita una durata precisa in minuti, impieghi il corrispondente codice `WA.10.00x0`.
        *   **Nota per cateterismo cardiaco sinistro (potenzialmente legato a Pauschale C05.10B):** Presti particolare attenzione affinché le LKN scelte corrispondano molto precisamente alla descrizione testuale. Se diverse LKN sembrano possibili, e se una LKN è un noto attivatore della Pauschale C05.10B, si assicuri che il testo giustifichi pienamente questa LKN specifica e le condizioni di tale Pauschale prima di selezionarla.
        *   **Istruzione Critica per Rimozione Verruca con Curette/Cucchiaio Tagliente:** Se il testo del trattamento descrive esplicitamente la "rimozione di una verruca" (o sinonimi diretti) E menziona l'uso di una "curette" o "cucchiaio tagliente" (o traduzioni dirette):
            *   **DEVE IMPERATIVAMENTE** dare priorità alle LKN che descrivono specificamente il "curettage di verruca" o la "rimozione di verruca mediante curettage".
            *   Ricerca attivamente codici come `MK.05.0070` (se questo corrisponde a "curettage di verruche" o simile ed è presente nel catalogo fornito).
            *   Questa istruzione specifica per il curettage di verruche **PREVALE** sui codici più generici di rimozione di lesioni cutanee.
        *   **Istruzione specifica per "Frattura dito, Inchiodamento" (potenzialmente legato a Pauschale C08.30F):** Se il testo descrive una frattura di un dito trattata con inchiodamento o osteosintesi con chiodo (o termini molto simili): Sia particolarmente attento nella selezione delle LKN relative sia alla frattura del dito sia alla procedura di inchiodamento/osteosintesi. Se una LKN identificata è un noto attivatore della Pauschale C08.30F e il testo giustifica pienamente tale LKN, la consideri attentamente.
        *   **IMPORTANTE:** Se una procedura esiste nel catalogo solo sotto forma di Pauschal (ad esempio, molti interventi chirurgici maggiori), non troverà LKN corrispondenti. In questo caso, una lista `identified_leistungen` vuota è la risposta corretta.
    *   Consulti attivamente il campo "MedizinischeInterpretation" del catalogo, poiché spesso contiene indicazioni importanti su designazioni alternative o sinonimi comuni per una prestazione.
    *   **Note amministrative:** Ignori le osservazioni puramente amministrative o logistiche (ad es. "tempo di trasferimento alla dermatologia", "il paziente ha aspettato") durante l'identificazione delle LKN cliniche fatturabili, a meno che non informino direttamente un parametro fatturabile (ad es. durata di una prestazione supervisionata).

3.  **REGOLE SPECIFICHE per le LKN e il calcolo delle quantità:**
    *   **A) Logica per le consultazioni (Capitoli AA & CA):**
        *   Questa logica si applica unicamente ad attività come "consultazione", "colloquio", "consultazione di medicina generale/di famiglia".
        *   Passo 1: Estragga la durata totale di questa consultazione in minuti (ad es., "15 minuti").
        *   Passo 2: Scelga il capitolo:
            *   **CA (Medico di famiglia):** Se il testo contiene "medico di famiglia", "medicina di famiglia" o termini equivalenti (es. "hausärztlich" se il contesto lo indica chiaramente).
            *   **AA (Generale):** In TUTTI GLI ALTRI CASI di consultazione generale.
        *   Passo 3: Applichi la seguente regola di ripartizione in modo rigoroso:
            *   LKN di base: `AA.00.0010` o `CA.00.0010` ("primi 5 min."). La quantità è SEMPRE 1.
            *   LKN aggiuntiva: Solo se la durata supera i 5 minuti, aggiunga `AA.00.0020` o `CA.00.0020` ("ogni min. successivo").
            *   Quantità della LKN aggiuntiva: La quantità è ESATTAMENTE (durata in minuti - 5).
            *   Esempio "Consultazione 15 minuti": -> `AA.00.0010` (quantità 1) + `AA.00.0020` (quantità 10).
    *   **B) Logica per le altre prestazioni basate sul tempo:**
        *   Questo si applica a tutte le altre LKN con un'indicazione di tempo (ad es., "per 1 min", "per 5 min").
        *   Esempio: "...asportazione verruca... 5 minuti" trova la LKN `MK.05.0070` ("...per 1 min"). Quantità = 5.
        *   Esempio: "10 minuti consulenza bambino" e LKN `CG.15.0010` ("Consulenza... per bambino... pro 5 min.") -> quantità = 10/5 = 2. (Questo tipo di "consulenza" specifica, se non una consultazione generale AA/CA, segue questa regola).
        *   Calcolo della quantità: La quantità è ESATTAMENTE (durata dell'attività / unità di tempo della LKN).
    *   **C) Prestazioni con "lateralità":** Se una prestazione richiede una "lateralità" (Seitigkeit), allora per "bilaterale" (corrispondente a "beidseits"), inserisca quantità = 2 E `seitigkeit` = "beidseits". Per "unilaterale" (corrispondente a "einseitig"), quantità = 1 e la `seitigkeit` specificata ("links" o "rechts").


4.  **Validazione rigorosa:**
    *   Per OGNI LKN identificata: Verifichi LETTERA PER LETTERA e CIFRA PER CIFRA che il codice esista nel catalogo.
    *   Solo le LKN che superano questa verifica vengono incluse nella lista finale. Per ogni LKN validata, aggiunga il `typ` e la `beschreibung` **direttamente e senza modifiche** dal contesto del catalogo per quella LKN.

5.  **Estrazione delle informazioni contestuali:**
    *   Estragga **unicamente** i valori esplicitamente menzionati nel "Behandlungstext". Per `geschlecht` e `seitigkeit`, utilizzi i termini tedeschi specificati per l'output JSON:
        *   `dauer_minuten` (numero): durata della prestazione principale o durata totale se più tempi sono indicati.
        *   `menge_allgemein` (numero)
        *   `alter` (numero)
        *   `geschlecht` (stringa: 'weiblich', 'männlich', 'divers', 'unbekannt')
        *   `seitigkeit` (stringa: 'einseitig', 'beidseits', 'links', 'rechts', 'unbekannt')
        *   `anzahl_prozeduren` (numero o `null`)
    *   Se un valore non è menzionato, lo imposti su `null` (tranne `seitigkeit` e `geschlecht` che devono essere 'unbekannt' se non specificato).

6.  **Motivazione (`begruendung_llm`):**
    *   Indichi brevemente perché le LKN **validate** sono state scelte e come sono state calcolate le quantità. Faccia riferimento alla Sua analisi dei passaggi precedenti e alle **descrizioni del catalogo**.

**Formato di output:** **SOLO** JSON valido, **NESSUN** altro testo.
```json
{{
  "identified_leistungen": [
    {{
      "lkn": "LKN_VALIDATA_1",
      "typ": "TIPO_DA_CATALOGO_1",
      "beschreibung": "DESCRIZIONE_DA_CATALOGO_1",
      "menge": QUANTITÀ_LKN_1
    }}
  ],
  "extracted_info": {{
    "dauer_minuten": null,
    "menge_allgemein": null,
    "alter": null,
    "geschlecht": "unbekannt",
    "seitigkeit": "unbekannt",
    "anzahl_prozeduren": null
  }},
  "begruendung_llm": "<Breve motivazione>"
}}

Se nessuna LKN corrispondente dal catalogo viene trovata, restituisca un oggetto JSON con una lista "identified_leistungen" vuota.

Behandlungstext: "{user_input}"

Risposta JSON:"""
    else: # German (base)
        return f"""**Aufgabe:** Analysiere den folgenden medizinischen Behandlungstext aus der Schweiz äußerst präzise. Deine Aufgabe ist es, relevante Leistungs-Katalog-Nummern (LKN) samt Menge und Kontextinformationen zu bestimmen. Nutze primär den bereitgestellten LKAAT_Leistungskatalog, darfst aber auch medizinische Synonyme oder übliche Begriffe berücksichtigen und die Pauschalen-Tabelle hinzuziehen.

**Kontext: LKAAT_Leistungskatalog (maßgebliche Quelle für gültige LKNs, deren Beschreibungen und etwaige "MedizinischeInterpretation"-Abschnitte mit zusätzlichen Begriffen; ergänzend kann die Pauschalen-Tabelle verwendet werden.)
--- Leistungskatalog Start ---
{katalog_context}
--- Leistungskatalog Ende ---
Rolle: Du bist ein Experte für den Schweizer Arzttarif TARDOC. Deine einzige Aufgabe ist es, aus einem Behandlungstext die korrekten Einzelleistungen (LKNs) zu identifizieren und zu kodieren. Pauschalen werden ignoriert.

Anweisungen: Führe die folgenden Schritte exakt aus:

1. Textanalyse & Aufgabenzerlegung:
    Lies den Behandlungstext sorgfältig.
    KRITISCH: Wenn der Text mehrere, voneinander getrennte Tätigkeiten beschreibt (getrennt durch  Satzzeichen oder Wörter wie "plus", "und", "sowie", "gefolgt von"), behandle jede Tätigkeit als eigene Aufgabe.
    Beispiel: "Hausärztliche Konsultation 15 Min plus 10 Minuten Beratung Kind"
    Aufgabe 1: "Hausärztliche Konsultation 15 Min"
    Aufgabe 2: "10 Minuten Beratung Kind"
    Weise Zeitangaben und andere Details immer der korrekten Aufgabe zu.
2. LKN-Identifikation (pro Aufgabe):
    Medizinische Interpretation: Verstehe die medizinische Absicht, nicht nur die exakten Worte. Nutze dein Wissen über Synonyme, Fachbegriffe und Umschreibungen.
    Beispiele: "Entfernung" ist gleichbedeutend mit "Abtragen". Eine "Warze" ist eine "benigne Hautläsion". "Linksherzkatheter" ist "Koronarographie".
    WICHTIG: Wenn eine Prozedur im Katalog nur als Pauschale existiert (z.B. viele grosse chirurgische Eingriffe), wirst du keine passenden LKNs finden. In diesem Fall ist eine leere identified_leistungen-Liste die korrekte Antwort.
3. SPEZIALREGELN für LKNs und Mengenberechnung:
    A) Logik für Konsultationen (Kapitel AA & CA):
        Diese Logik gilt nur für Tätigkeiten wie "Konsultation", "Sprechstunde", "hausärztliche Konsultation".
        Schritt 1: Extrahiere die Gesamtdauer dieser Konsultation in Minuten (z.B. "15 Minuten").
        Schritt 2: Wähle das Kapitel:
        CA (Hausarzt): Wenn der Text "Hausarzt" oder "hausärztlich" enthält.
        AA (Allgemein): In ALLEN ANDEREN FÄLLEN von allgemeiner Konsultation.
        Schritt 3: Wende die folgende Aufteilungsregel strikt an:
        Basis-LKN: AA.00.0010 oder CA.00.0010 ("erste 5 Min."). Die Menge ist IMMER 1.
        Zusatz-LKN: Nur wenn die Dauer über 5 Minuten liegt, füge AA.00.0020 oder CA.00.0020 ("jede weitere Min.") hinzu.
        Menge der Zusatz-LKN: Die Menge ist EXAKT (Dauer in Minuten - 5).
        Beispiel "Konsultation 15 Minuten": -> AA.00.0010 (Menge 1) + AA.00.0020 (Menge 10).
    B) Logik für andere zeitbasierte Leistungen:
        Dies gilt für alle anderen LKNs mit Zeitangabe (z.B. "pro 1 Min.", "pro 5 Min.").
        Beispiel: "...Abtragen Warze... 5 Minuten" findet die LKN MK.05.0070 ("...pro 1 Min.").
        Mengenberechnung: Die Menge ist EXAKT (Dauer der Tätigkeit / Zeiteinheit der LKN).
        Beispiel: 5 Minuten für eine "pro 1 Min."-LKN -> menge = 5 / 1 = 5.
        Beispiel: 10 Minuten für eine "pro 5 Min."-LKN -> menge = 10 / 5 = 2.
4. Strikte Validierung:
    Für JEDE identifizierte LKN: Prüfe BUCHSTABE FÜR BUCHSTABE und ZIFFER FÜR ZIFFER, dass der Code im Katalog existiert.
    Nur LKNs, die diese Prüfung bestehen, kommen in die finale Liste.
5. Kontextinformationen extrahieren:
    Extrahiere die im Text genannten Werte (dauer_minuten, menge_allgemein, alter, etc.).
    Wenn es mehrere Zeitangaben gibt, extrahiere die Dauer der Hauptleistung oder die Gesamtdauer.
6. Begründung:
    Fasse kurz zusammen, warum du die LKNs gewählt hast und wie du die Mengen berechnet hast. Beziehe dich dabei auf deine Analyse aus den vorherigen Schritten.

Output-Format: NUR valides JSON, KEIN anderer Text.

```json
{{
  "identified_leistungen": [
    {{
      "lkn": "VALIDIERTE_LKN_1",
      "typ": "TYP_AUS_KATALOG_1",
      "beschreibung": "BESCHREIBUNG_AUS_KATALOG_1",
      "menge": MENGE_ZAHL_LKN_1
    }}
  ],
  "extracted_info": {{
    "dauer_minuten": null,
    "menge_allgemein": null,
    "alter": null,
    "geschlecht": "unbekannt",
    "seitigkeit": "unbekannt",
    "anzahl_prozeduren": null
  }},
  "begruendung_llm": "<Begründung>"
}}

Wenn absolut keine passende LKN aus dem Katalog gefunden wird, gib ein JSON-Objekt mit einer leeren "identified_leistungen"-Liste zurück.

Behandlungstext: "{user_input}"

JSON-Antwort:"""

def get_stage2_mapping_prompt(tardoc_lkn: str, tardoc_desc: str, candidates_text: str, lang: str) -> str:
    """Return the Stage 2 mapping prompt in the requested language."""
    if lang == "fr":
        return f"""**Tâche :** Vous êtes un expert des systèmes de facturation médicale en Suisse (TARDOC et Pauschalen). Votre objectif est de trouver, pour la prestation TARDOC individuelle indiquée (type E/EZ), la prestation fonctionnellement **équivalente** dans la « liste des candidats ». Cette liste contient des LKN (de tous types, souvent P/PZ) utilisés comme conditions dans les Pauschalen potentiellement pertinentes.

**Prestation TARDOC fournie (type E/EZ) :**
*   LKN : {tardoc_lkn}
*   Description : {tardoc_desc}
*   Contexte : Cette prestation a été réalisée dans le cadre d'un traitement pour lequel une facturation par Pauschalen est examinée.

**Équivalents possibles (liste des candidats - LKN pour les conditions des Pauschalen) :**
Trouvez dans CETTE liste la LKN candidate décrivant **le même type d'acte médical**.
--- Kandidaten Start ---
{candidates_text}
--- Kandidaten Ende ---

**Analyse et décision :**
1.  Comprenez la **fonction médicale principale** de la prestation TARDOC donnée.
2.  Identifiez la LKN candidate qui représente le mieux cette fonction principale et priorisez selon la pertinence.

**Réponse :**
*   Donnez une **liste simple séparée par des virgules** des codes LKN retenus.
*   Si aucun candidat ne convient, renvoyez exactement `NONE`.
*   Aucune autre explication.

Liste priorisée (uniquement la liste ou NONE) :"""
    elif lang == "it":
        return f"""**Compito:** Lei è un esperto dei sistemi di fatturazione medica in Svizzera (TARDOC e Pauschalen). Il Suo obiettivo è individuare, per la prestazione singola TARDOC indicata (tipo E/EZ), la prestazione funzionalmente **equivalente** nella "lista dei candidati". Questa lista contiene LKN (di tutti i tipi, spesso P/PZ) utilizzati come condizioni nelle Pauschal potenzialmente rilevanti.

**Prestazione TARDOC fornita (tipo E/EZ):**
*   LKN: {tardoc_lkn}
*   Descrizione: {tardoc_desc}
*   Contesto: Questa prestazione è stata eseguita nell'ambito di un trattamento per il quale si sta valutando una fatturazione a forfait (Pauschal).

**Possibili equivalenti (lista dei candidati - LKN per le condizioni delle Pauschal):**
Trovi in QUESTA lista la LKN candidata che descrive **lo stesso type di atto medico**.
--- Kandidaten Start ---
{candidates_text}
--- Kandidaten Ende ---

**Analisi e decisione:**
1.  Comprenda la **funzione medica principale** della prestazione TARDOC data.
2.  Identifichi la LKN candidata che meglio rappresenta questa funzione principale e la prioritizzi in base alla pertinenza.

**Risposta:**
*   Fornisca un **elenco semplice separato da virgole** dei codici LKN trovati.
*   Se nessun candidato è adatto, restituisca esattamente `NONE`.
*   Nessun'altra spiegazione.

Elenco prioritario (solo elenco o NONE):"""
    else: # German (base)
        return f"""**Aufgabe:** Du bist ein Experte für medizinische Abrechnungssysteme in der Schweiz (TARDOC und Pauschalen). Deine Aufgabe ist es, für die gegebene TARDOC-Einzelleistung (Typ E/EZ) die funktional **äquivalente** Leistung aus der \"Kandidatenliste\" zu finden. Die Kandidatenliste enthält LKNs (aller Typen, oft P/PZ), die als Bedingungen in potenziell relevanten Pauschalen vorkommen.

**Gegebene TARDOC-Leistung (Typ E/EZ):**
*   LKN: {tardoc_lkn}
*   Beschreibung: {tardoc_desc}
*   Kontext: Diese Leistung wurde im Rahmen einer Behandlung erbracht, für die eine Pauschalenabrechnung geprüft wird.

**Mögliche Äquivalente (Kandidatenliste - LKNs für Pauschalen-Bedingungen):**
Finde aus DIESER Liste die Kandidaten-LKN, die die **gleiche Art von medizinischer Tätigkeit** beschreibt.
--- Kandidaten Start ---
{candidates_text}
--- Kandidaten Ende ---

**Analyse & Entscheidung:**
1.  Verstehe die **medizinische Kernfunktion** der gegebenen TARDOC-Leistung.
2.  Identifiziere die Kandidaten-LKN, die diese Kernfunktion am besten repräsentiert, und priorisiere nach Passgenauigkeit.

**Antwort:**
*   Gib eine **reine, kommagetrennte Liste** der LKN-Codes zurück.
*   Wenn keine passt, gib exakt `NONE` aus.
*   Keine weiteren Erklärungen.

Priorisierte Liste (nur Liste oder NONE):"""

def get_stage2_ranking_prompt(user_input: str, potential_pauschalen_text: str, lang: str) -> str:
    """Return the Stage 2 ranking prompt in the requested language."""
    if lang == "fr":
        return f"""Sur la base du texte de traitement suivant, quelle Pauschale (forfait) listée ci-dessous correspond le mieux au contenu ?
Prenez en compte la description de la Pauschale ('Pauschale_Text').
Fournissez une liste priorisée des codes de Pauschale en commençant par la meilleure correspondance.
Donnez UNIQUEMENT les codes de Pauschale sous forme de liste séparée par des virgules (par ex. "CODE1,CODE2"). AUCUNE justification.

Texte de traitement : "{user_input}"

Pauschales potentielles :
--- Pauschalen Start ---
{potential_pauschalen_text}
--- Pauschalen Ende ---

Codes de Pauschale par ordre de pertinence (uniquement la liste séparée par des virgules) :"""
    elif lang == "it":
        return f"""In base al seguente testo di trattamento, quale delle Pauschal (prestazioni forfettarie) elencate di seguito corrisponde meglio al contenuto?
Tenga conto della descrizione della Pauschal ('Pauschale_Text').
Fornisca un elenco prioritario dei codici Pauschal iniziando dalla corrispondenza migliore.
Fornisca SOLO i codici Pauschal sotto forma di elenco separato da virgole (ad es. "CODE1,CODE2"). NESSUNA giustificazione.

Testo di trattamento: "{user_input}"

Pauschal potenziali:
--- Pauschalen Start ---
{potential_pauschalen_text}
--- Pauschalen Ende ---

Codici Pauschal in ordine di rilevanza (solo elenco separato da virgole):"""
    else: # German (base)
        return f"""Basierend auf dem folgenden Behandlungstext, welche der unten aufgeführten Pauschalen passt inhaltlich am besten?
Berücksichtige die Beschreibung der Pauschale ('Pauschale_Text').
Gib eine priorisierte Liste der Pauschalen-Codes zurück, beginnend mit der besten Übereinstimmung.
Gib NUR die Pauschalen-Codes als kommagetrennte Liste zurück (z.B. \"CODE1,CODE2\"). KEINE Begründung.

Behandlungstext: \"{user_input}\"

Potenzielle Pauschalen:
--- Pauschalen Start ---
{potential_pauschalen_text}
--- Pauschalen Ende ---

Priorisierte Pauschalen-Codes (nur kommagetrennte Liste):"""
