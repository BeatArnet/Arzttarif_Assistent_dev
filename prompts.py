# --- Prompt-Übersetzungen ---
def get_stage1_prompt(user_input: str, katalog_context: str, lang: str) -> str:
    """Return the Stage 1 prompt in the requested language."""
    if lang == "fr":
        return f"""**Tâche :** Analyse avec précision le texte de traitement médical ci-dessous provenant de Suisse. Ta mission consiste à identifier les numéros du catalogue des prestations (LKN), à en déterminer la quantité et à extraire les informations contextuelles. Appuie-toi principalement sur le LKAAT_Leistungskatalog fourni, mais tu peux aussi tenir compte de synonymes médicaux courants ou de termes usuels et consulter la table des forfaits.

**Contexte : LKAAT_Leistungskatalog (source de référence pour les LKN, leurs descriptions et les sections "MedizinischeInterpretation" où des synonymes peuvent apparaître ; la table des forfaits peut également être prise en compte.)
--- Leistungskatalog Start ---
{katalog_context}
--- Leistungskatalog Ende ---

**Instructions :** Suis exactement les étapes suivantes :

1.  **Identification des LKN et validation STRICTE:**
    *   Lis le "Behandlungstext" attentivement.
    *   Analyse l'intégralité du texte de traitement. Si plusieurs prestations distinctes sont décrites (p. ex. une consultation suivie d'un acte technique), identifie les LKN pour chaque partie.
    *   Identifie **tous** les codes LKN potentiels (format `XX.##.####`) pouvant représenter les actes décrits.
    *   Note que plusieurs prestations peuvent être documentées dans le texte et que plusieurs LKN peuvent être valides (p. ex. intervention chirurgicale plus anesthésie).
    *   Si une anesthésie ou une narcose réalisée par un anesthésiste est mentionnée, sélectionne explicitement un code du chapitre WA.10 (table ANAST). S'il n'est pas fait mention de la durée, utilise par défaut `WA.10.0010`. Lorsque la durée precise en minutes est indiquée, emploie le code `WA.10.00x0` approprié.
    *   Mets à profit tes connaissances médicales sur les synonymes et termes techniques usuels (p. ex. reconnais que « opération de la cataracte » = « phacoémulsification » / « extraction du cristallin » = « Extractio lentis »). Pour les termes complexes comme "cathétérisme cardiaque gauche", décompose-le en ses composants ("gauche", "cœur", "cathéter") et recherche des LKN correspondantes telles que celles pour la "coronarographie" ou "cathétérisme cardiaque". De même, « enlèvement verrue au moyen d'une curette » ou « avec une cuillère tranchante » devrait correspondre aux LKN pour le curetage de verrues. Tiens aussi compte des formulations qui peuvent apparaître dans le champ "MedizinischeInterpretation".
    *   Si le texte mentionne « conseil », « entretien » ou « consultation » (au sens de donner des conseils) avec une durée, recherche activement les LKN correspondantes à cette activité, en particulier celles tarifées à la durée (p. ex. "par 5 min").
    *   Utilise également ton sens stylistique : « grand » peut signifier « complet » ou « majeur » ; une formulation comme « grand examen rhumatologique » peut être interprétée comme « examen rhumatologique complet » ou « bilan rhumatologique majeur », l'ordre des mots peut varier et les formes nominales et verbales peuvent être équivalentes (p. ex. « retrait » vs « retirer »).
    *   **ABSOLUMENT CRITIQUE:** Pour CHAQUE code LKN potentiel, vérifie **LETTRE PAR LETTRE et CHIFFRE PAR CHIFFRE** que ce code existe **EXACTEMENT** comme 'LKN:' dans le catalogue ci-dessus. Ce n'est que si le code existe que tu compares la **description du catalogue** avec l'acte décrit.
    *   Crée une liste (`identified_leistungen`) **UNIQUEMENT** avec les LKN ayant passé cette vérification exacte et dont la description correspond au texte.
    *   Reconnais si les prestations relèvent du chapitre CA (médecine de famille).

**Instruction spécifique pour les consultations (par ex. chapitre AA) :**
*   Si le texte de traitement décrit une « consultation » générale ou un « entretien » avec une durée (p. ex. « consultation 25 minutes ») et qu'AUCUNE spécialité spécifique (comme « médecine de famille ») n'est mentionnée, alors priorise les codes de consultation généraux du chapitre AA.
*   `AA.00.0010` ("Consultation, générale ; 5 premières minutes") : la quantité est toujours 1 si une consultation a lieu.
*   `AA.00.0020` ("Consultation, générale ; chaque minute supplémentaire") : la quantité est (`dauer_minuten` de la consultation - 5) / 1.
*   Exemple : Une consultation générale de 25 minutes donne :
    *   `AA.00.0010`, `menge`: 1
    *   `AA.00.0020`, `menge`: (25 - 5) / 1 = 20
*   Exemple : Une consultation générale de 15 minutes donne :
    *   `AA.00.0010`, `menge`: 1
    *   `AA.00.0020`, `menge`: (15 - 5) / 1 = 10
*   Assure-toi que `dauer_minuten` est correctement extrait pour toute la consultation avant d'effectuer cette répartition.

2.  **Type et description:**
    *   Pour chaque LKN **validée** de `identified_leistungen`, ajoute le `typ` et la `beschreibung` **directement et sans modification** depuis le contexte du catalogue pour cette LKN.

3.  **Extraction d'informations contextuelles (CRITIQUE pour les conditions supplémentaires):**
    *   Extrait **uniquement** les valeurs explicitement mentionnées dans le "Behandlungstext":
        *   `dauer_minuten` (nombre)
        *   `menge_allgemein` (nombre)
        *   `alter` (nombre)
        *   `geschlecht` ('weiblich', 'männlich', 'divers', 'unbekannt')
        *   `seitigkeit` (chaîne: 'einseitig', 'beidseits', 'links', 'rechts', 'unbekannt')
        *   `anzahl_prozeduren` (nombre ou `null`)
    *   Si une valeur n'est pas mentionnée, définis-la sur `null` (sauf `seitigkeit`, qui peut être 'unbekannt').

4.  **Détermination de la quantité (par LKN validée):**
    *   La quantité par défaut est `1`.
    *   **Basé sur le temps (Règle principale):** Si la description du catalogue d'une LKN indique explicitement une unité de temps (par ex. "par minute", "par 5 min", "chaque minute supplémentaire"), ET que `dauer_minuten` (Y) est pertinent pour cette LKN spécifique (cela peut être la durée totale ou une durée spécifiquement attribuée à cette LKN) :
        *   Interprète l'unité de temps X à partir de la description de la LKN (par ex. X=1 pour "par minute", X=5 pour "par 5 min").
        *   Fixe `menge = Y / X`. Assure-toi que le résultat est un entier (Y devrait généralement être un multiple de X).
        *   Cette règle s'applique si la LKN couvre toute la durée Y ou une partie clairement définie représentée par Y.
        *   Pour les LKN qui suivent une *durée de base* (par ex. "chaque minute supplémentaire après les Z premières minutes"), Y est la durée restante (durée totale de la consultation - Z minutes de service de base).
    *   **Général:** si `menge_allgemein` (Z) est extrait ET que la LKN n'est pas basée sur le temps (ou que la règle basée sur le temps ne s'applique pas) ET `anzahl_prozeduren` est `null`, mets `menge` = Z.
    *   **Nombre spécifique de procédures:** si `anzahl_prozeduren` est extrait et se rapporte clairement à la LKN (p. ex. "deux injections"), mets `menge` = `anzahl_prozeduren`. Cela prime sur `menge_allgemein`.
    *   Assure-toi que `menge` >= 1.
    *   Si une procédure requiert une « latéralité », alors pour « beidseits » (des deux côtés), saisis quantité = 2 ET « latéralité » = « beidseits ».

5.  **Justification:**
    *   `begruendung_llm` courte indiquant pourquoi les LKN **validées** ont été choisies. Réfère-toi au texte et aux **descriptions du catalogue**.

**Instruction spécifique pour les consultations :** Si le texte de traitement décrit une « consultation » générale ou un « entretien » avec une durée (p. ex. « consultation 15 minutes ») et qu'AUCUNE spécialité spécifique (comme « médecine de famille ») n'est mentionnée, alors priorise les codes de consultation généraux du chapitre AA (p. ex. `AA.00.0010` pour les 5 premières minutes et `AA.00.0020` pour chaque minute supplémentaire). Assure-toi que les quantités sont correctement calculées en fonction de la durée (p. ex. 15 minutes = 1x `AA.00.0010` + 10x `AA.00.0020`).

**Format de sortie:** **UNIQUEMENT** du JSON valide, **AUCUN** autre texte.
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
    "geschlecht": null,
    "seitigkeit": "unbekannt",
    "anzahl_prozeduren": null
  }},
  "begruendung_llm": "<Begründung>"
}}

Si aucune LKN correspondante n'est trouvée, renvoie un objet JSON avec une liste "identified_leistungen" vide.

Behandlungstext: "{user_input}"

Réponse JSON:"""
    elif lang == "it":
        return f"""**Compito:** Analizza con la massima precisione il testo di trattamento medico seguente proveniente dalla Svizzera. Il tuo obiettivo è identificare i numeri di catalogo delle prestazioni (LKN), determinarne la quantità ed estrarre informazioni contestuali. Basati principalmente sul LKAAT_Leistungskatalog fornito, ma puoi utilizzare sinonimi medici o termini comuni e includere la tabella delle Pauschalen.

**Contesto: LKAAT_Leistungskatalog (fonte principale per i LKN, le relative descrizioni e le sezioni "MedizinischeInterpretation" con possibili sinonimi; in aggiunta è disponibile la tabella delle Pauschalen.)
--- Leistungskatalog Start ---
{katalog_context}
--- Leistungskatalog Ende ---

**Istruzioni:** Segui esattamente i passi seguenti:

1.  **Identificazione LKN e convalida STRETTA:**
    *   Leggi attentamente il "Behandlungstext".
    *   Analizza l'intero testo del trattamento. Se vengono descritte più prestazioni distinte (ad es. una consultazione seguita da una procedura), identifica le LKN per ciascuna parte.
    *   Identifica **tutti** i possibili codici LKN (formato `XX.##.####`) che potrebbero rappresentare le attività descritte.
    *   Considera che nel testo possono essere documentate più prestazioni e quindi possono essere valide più LKN (ad es. intervento chirurgico più anestesia).
    *   Se viene menzionata un'anestesia o narcosi eseguita da un anestesista, seleziona esplicitamente un codice del capitolo WA.10 (tabella ANAST). Se non è indicata la durata, usa di default `WA.10.0010`. Quando viene fornita una durata precisa in minuti, impiega il corrispondente codice `WA.10.00x0`.
    *   Sfrutta le tue conoscenze mediche su sinonimi e termini tecnici tipici (ad es. riconosci che « intervento di cataratta » = « facoemulsificazione » / « estrazione del cristallino » = « Extractio lentis »). Per termini complessi come "cateterismo cardiaco sinistro", scomponilo nei suoi componenti ("sinistro", "cuore", "catetere") e cerca LKN corrispondenti come quelle per la "coronarografia" o "cateterismo cardiaco". Analogamente, « rimozione verruca con cucchiaio tagliente » o « tramite curettage » dovrebbe corrispondere alle LKN per il curettage di verruche. Considera anche i termini che possono comparire nel campo "MedizinischeInterpretation".
    *   Se il testo menziona « consulenza », « consulto », o « colloquio informativo » con una durata, cerca attivamente le LKN corrispondenti a questa attività, specialmente quelle tariffate a tempo (ad es. "per 5 min").
    *   Usa anche il tuo senso stilistico: "grande" può significare "esteso" o "completo"; una dicitura come "grande esame reumatologico" può essere interpretata come "esame reumatologico completo" o "status reumatologico maggiore", l'ordine delle parole può variare e forme sostantivali e verbali possono avere lo stesso significato (es. "rimozione" vs "rimuovere").
    *   **ASSOLUTAMENTE CRITICO:** Per OGNI codice LKN potenziale verifica **LETTERA PER LETTERA e CIFRA PER CIFRA** che esista **ESATTAMENTE** come 'LKN:' nel catalogo sopra. Solo se il codice esiste confronta la **descrizione del catalogo** con l'attività descritta.
    *   Crea un elenco (`identified_leistungen`) **SOLO** con le LKN che hanno superato questa verifica esatta e la cui descrizione corrisponde al testo.
    *   Riconosci se si tratta di prestazioni di medicina di base del capitolo CA.

**Istruzione specifica per le consultazioni (ad es. capitolo AA):**
*   Se il testo del trattamento descrive una "consultazione" generale o un "colloquio" con una durata (ad es. "consultazione 25 minuti") e NON viene menzionata NESSUNA specializzazione specifica (come "medicina di famiglia"), allora dai priorità ai codici di consultazione generali del capitolo AA.
*   `AA.00.0010` ("Consultazione, generale; primi 5 minuti"): la quantità è sempre 1 se si svolge una consultazione.
*   `AA.00.0020` ("Consultazione, generale; ogni minuto successivo"): la quantità è (`dauer_minuten` della consultazione - 5) / 1.
*   Esempio: Una consultazione generale di 25 minuti comporta:
    *   `AA.00.0010`, `menge`: 1
    *   `AA.00.0020`, `menge`: (25 - 5) / 1 = 20
*   Esempio: Una consultazione generale di 15 minuti comporta:
    *   `AA.00.0010`, `menge`: 1
    *   `AA.00.0020`, `menge`: (15 - 5) / 1 = 10
*   Assicurati che `dauer_minuten` sia estratto correttamente per l'intera consultazione prima di effettuare questa suddivisione.

2.  **Tipo e descrizione:**
    *   Per ogni LKN **convalidata** in `identified_leistungen` aggiungi il `typ` corretto e la `beschreibung` **direttamente e senza modifiche** dal contesto del catalogo per quella LKN.

3.  **Estrazione delle informazioni contestuali (CRITICO per condizioni aggiuntive):**
    *   Estrai **solo** i valori esplicitamente menzionati nel "Behandlungstext":
        *   `dauer_minuten` (numero)
        *   `menge_allgemein` (numero)
        *   `alter` (numero)
        *   `geschlecht` ('weiblich', 'männlich', 'divers', 'unbekannt')
        *   `seitigkeit` (stringa: 'einseitig', 'beidseits', 'links', 'rechts', 'unbekannt')
        *   `anzahl_prozeduren` (numero o `null`)
    *   Se un valore non è menzionato, impostalo su `null` (tranne `seitigkeit`, che può essere 'unbekannt').

4.  **Determinazione della quantità (per LKN convalidata):**
    *   La quantità standard è `1`.
    *   **Basato sul tempo (Regola principale):** Se la descrizione del catalogo di una LKN indica esplicitamente un'unità di tempo (ad es. "per minuto", "per 5 min", "ogni minuto successivo"), E `dauer_minuten` (Y) è pertinente per questa LKN specifica (può essere la durata totale o una durata specificamente assegnata a questa LKN):
        *   Interpreta l'unità di tempo X dalla descrizione della LKN (ad es. X=1 per "per minuto", X=5 per "per 5 min").
        *   Imposta `menge = Y / X`. Assicurati che il risultato sia un numero intero (Y dovrebbe generalmente essere un multiplo di X).
        *   Questa regola si applica se la LKN copre l'intera durata Y o una sua parte chiaramente definita rappresentata da Y.
        *   Per le LKN che seguono una *durata di base* (ad es. "ogni minuto successivo dopo i primi Z minuti"), Y è la durata rimanente (durata totale della consultazione - Z minuti di prestazione base).
    *   **Generale:** se `menge_allgemein` (Z) è stato estratto E la LKN non è basata sul tempo (o la regola basata sul tempo non è applicabile) E `anzahl_prozeduren` è `null`, imposta `menge` = Z.
    *   **Numero specifico di procedure:** se `anzahl_prozeduren` è stato estratto e si riferisce chiaramente alla LKN (ad es. "due iniezioni"), imposta `menge` = `anzahl_prozeduren`. Questo prevale su `menge_allgemein`.
    *   Assicurati che `menge` >= 1.
    *   Se una procedura richiede una "lateralità", allora per "beidseits" (entrambi i lati), imposta quantità = 2 E "lateralità" = "beidseits".

5.  **Motivazione:**
    *   `begruendung_llm` breve sul perché le LKN **convalidate** sono state scelte. Fai riferimento al testo e alle **descrizioni del catalogo**.

**Istruzione specifica per le consultazioni:** Se il testo del trattamento descrive una "consultazione" generale o un "colloquio" con una durata (ad es. "consultazione 15 minuti") e NON viene menzionata NESSUNA specializzazione specifica (come "medicina di famiglia"), allora dai priorità ai codici di consultazione generali del capitolo AA (ad es. `AA.00.0010` per i primi 5 minuti e `AA.00.0020` per ogni minuto successivo). Assicurati che le quantità siano calcolate correttamente in base alla durata (ad es. 15 minuti = 1x `AA.00.0010` + 10x `AA.00.0020`).

**Formato di output:** **SOLO** JSON valido, **NESSUN** altro testo.
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
    "geschlecht": null,
    "seitigkeit": "unbekannt",
    "anzahl_prozeduren": null
  }},
  "begruendung_llm": "<Begründung>"
}}

Se nessuna LKN appropriata viene trovata, restituisci un oggetto JSON con una lista "identified_leistungen" vuota.

Behandlungstext: "{user_input}"

Risposta JSON:"""
    else:
        return f"""**Aufgabe:** Analysiere den folgenden medizinischen Behandlungstext aus der Schweiz äußerst präzise. Deine Aufgabe ist es, relevante Leistungs-Katalog-Nummern (LKN) samt Menge und Kontextinformationen zu bestimmen. Nutze primär den bereitgestellten LKAAT_Leistungskatalog, darfst aber auch medizinische Synonyme oder übliche Begriffe berücksichtigen und die Pauschalen-Tabelle hinzuziehen.

**Kontext: LKAAT_Leistungskatalog (maßgebliche Quelle für gültige LKNs, deren Beschreibungen und etwaige "MedizinischeInterpretation"-Abschnitte mit zusätzlichen Begriffen; ergänzend kann die Pauschalen-Tabelle verwendet werden.)
--- Leistungskatalog Start ---
{katalog_context}
--- Leistungskatalog Ende ---

**Anweisungen:** Führe die folgenden Schritte exakt aus:

1.  **LKN Identifikation & STRIKTE Validierung:**
    *   Lies den "Behandlungstext" sorgfältig.
    *   Analysiere den gesamten Behandlungstext. Wenn mehrere unterschiedliche Leistungen beschrieben sind (z.B. eine Konsultation gefolgt von einem Eingriff), identifiziere LKNs für jeden Teil.
    *   Identifiziere **alle** potenziellen LKN-Codes (Format `XX.##.####`), die die beschriebenen Tätigkeiten repräsentieren könnten. **Beginne damit, den Behandlungstext sorgfältig zu interpretieren. Die medizinische Bedeutung der beschriebenen Tätigkeit ist entscheidend, nicht nur die exakte Wortwahl. Nutze dabei dein ausgeprägtes medizinisches und terminologisches Wissen zu Synonymen, Umschreibungen und typischen Fachbegriffen.** Beispiele für Synonymie sind "Kataraktoperation" = "Phakoemulsifikation" oder "Linsenextraktion" = "Extractio lentis", "Herzkatheter"/"Linksherzkather" = "Koronarographie". **Achte besonders darauf, dass verschiedene Wörter die gleiche medizinische Handlung beschreiben können (z.B. "Abtragen", "Entfernen", "Entfernung" einer Hautläsion oder Warze können je nach Kontext auf dieselbe Prozedur hinweisen, wie z.B. die Exzision oder Kürettage einer Warze).**
    *   **Berücksichtige stilistische Variationen und den Kontext:** Die Wortreihenfolge kann variieren. Substantiv- und Verbformen sind oft äquivalent (z.B. "die Entfernung" vs. "etwas entfernen", "das Abtragen" vs. "etwas abtragen"). Eine Formulierung wie "grosser rheumatischer Untersuch" kann als "umfassende rheumatische Untersuchung" interpretiert werden.
    *   Beziehe auch Formulierungen aus dem Feld "MedizinischeInterpretation" des Katalogs aktiv mit ein, da diese oft wichtige Hinweise auf alternative Bezeichnungen oder gängige Synonyme für eine Leistung enthalten.
    *   Bedenke, dass im Text mehrere Leistungen dokumentiert sein können und daher mehrere LKNs gültig sein können (z.B. chirurgischer Eingriff plus/und/mit/;/./,/: Anästhesie).
    *   Wird eine Anästhesie oder Narkose durch einen Anästhesisten erwähnt, wähle ausdrücklich einen Code aus Kapitel WA.10 (Tabelle ANAST). Wenn keine Dauer angegeben ist, verwende standardmäßig `WA.10.0010`. Bei einer konkreten Dauerangabe in Minuten nutze den entsprechenden `WA.10.00x0`-Code.
    *   Wenn es für eine bestimmte Leistung eine spezifische LKN gibt, dann nutze diese anstatt Alternativen zu wählen, sofern die medizinische Bedeutung klar übereinstimmt.
    *   Nachdem du basierend auf dieser sorgfältigen Interpretation eine Liste möglicher LKN-Kandidaten erstellt hast, gilt: **ABSOLUT KRITISCH:** Für JEDEN dieser Kandidaten-LKN-Codes prüfe **BUCHSTABE FÜR BUCHSTABE und ZIFFER FÜR ZIFFER**, dass dieser Code **EXAKT** als „LKN:“ im obigen Katalog existiert. **Nur wenn ein LKN-Code exakt im Katalog gefunden wurde, vergleiche dessen offizielle Katalogbeschreibung sorgfältig mit der ursprünglich im Behandlungstext beschriebenen und interpretierten medizinischen Leistung.** Die Übereinstimmung der *Bedeutung* ist hierbei wichtiger als die exakte Wortwahl im Behandlungstext verglichen mit der Katalogbeschreibung, solange die Katalogbeschreibung die interpretierte Leistung abdeckt.
    *   Erstelle eine Liste (`identified_leistungen`) **AUSSCHLIESSLICH** mit den LKNs, die a) exakt im Katalog als LKN existieren UND b) deren Katalogbeschreibung die im Behandlungstext beschriebene und medizinisch interpretierte Leistung zutreffend widerspiegelt.
    *   Erkenne, ob es sich um hausärztliche Leistungen im Kapitel CA handelt.
    *   **Spezifische Anweisung für Konsultationen (z.B. Kapitel AA):**
        *   Wenn der Behandlungstext eine allgemeine "Konsultation" oder "Sprechstunde" mit einer Dauer beschreibt (z.B. "Konsultation 25 Minuten") und KEIN spezifischer Fachbereich (wie "Hausärztliche") genannt wird, dann priorisiere die allgemeinen Konsultationsziffern aus dem Kapitel AA.
        *   `AA.00.0010` ("Konsultation, allgemein; erste 5 Min."): Menge ist immer 1, wenn eine Konsultation stattfindet.
        *   `AA.00.0020` ("Konsultation, allgemein; jede weitere Minute"): Menge ist (`dauer_minuten` der Konsultation - 5) / 1.
        *   Beispiel: Eine allgemeine Konsultation von 25 Minuten Dauer führt zu:
            *   `AA.00.0010`, `menge`: 1
            *   `AA.00.0020`, `menge`: (25 - 5) / 1 = 20
        *   Beispiel: Eine allgemeine Konsultation von 15 Minuten Dauer führt zu:
            *   `AA.00.0010`, `menge`: 1
            *   `AA.00.0020`, `menge`: (15 - 5) / 1 = 10
        *   Stelle sicher, dass `dauer_minuten` korrekt für die gesamte Konsultation extrahiert wird, bevor diese Aufteilung erfolgt.

2.  **Typ & Beschreibung hinzufügen:**
    *   Füge für jede **validierte** LKN in der `identified_leistungen`-Liste den korrekten `typ` und die `beschreibung` **direkt und unverändert aus dem bereitgestellten Katalogkontext für DIESE LKN** hinzu.

3.  **Kontextinformationen extrahieren (KRITISCH für Zusatzbedingungen):**
    *   Extrahiere **nur explizit genannte** Werte aus dem "Behandlungstext":
        *   `dauer_minuten` (Zahl, z.B. für Konsultationen)
        *   `menge_allgemein` (Zahl, z.B. "3 Warzen entfernt")
        *   `alter` (Zahl, Alter des Patienten)
        *   `geschlecht` ('weiblich', 'männlich', 'divers', 'unbekannt')
        *   `seitigkeit` (String: 'einseitig', 'beidseits', 'links', 'rechts', 'unbekannt'. Leite 'beidseits' auch von "bds." oder "beide Augen" etc. ab. Wenn keine Angabe, dann 'unbekannt'.)
        *   `anzahl_prozeduren` (Zahl: Falls eine Anzahl von Eingriffen genannt wird, die nicht direkt die Menge einer einzelnen LKN ist, z.B. "zwei Injektionen". Wenn nicht explizit genannt, dann `null`.)
    *   Wenn ein Wert nicht explizit genannt wird, setze ihn auf `null` (außer `seitigkeit`, die 'unbekannt' sein kann).

4.  **Menge bestimmen (pro validierter LKN):**
    *   Standardmenge ist `1`.
    *   **Zeitbasiert (Primärregel):** Wenn die Katalog-Beschreibung einer LKN explizit eine Zeiteinheit angibt (z.B. "pro Minute", "pro 5 Min.", "jede weitere Minute"), UND `dauer_minuten` (Y) für diese spezifische LKN relevant ist (dies kann die Gesamtdauer oder eine spezifisch zugewiesene Dauer für diese LKN sein):
        *   Interpretiere die Zeiteinheit X aus der LKN-Beschreibung (z.B. X=1 für "pro Minute", X=5 für "pro 5 Min.").
        *   Setze `menge = Y / X`. Stelle sicher, dass das Ergebnis eine Ganzzahl ist und kaufmännisch gerundet wird, falls nötig, aber meist sollte Y ein Vielfaches von X sein.
        *   Diese Regel ist anzuwenden, wenn die LKN die gesamte Dauer Y abdeckt oder einen klar definierten Teil davon, der durch Y repräsentiert wird.
        *   Für LKNs, die auf eine *Basisdauer* folgen (z.B. "jede weitere Minute nach den ersten Z Minuten"), ist Y die Restdauer (Gesamtdauer der Konsultation - Z Minuten Basisleistung).
    *   **Allgemein:** Wenn `menge_allgemein` (Z) extrahiert wurde UND LKN nicht zeitbasiert ist (oder die zeitbasierte Regel nicht zutrifft) UND `anzahl_prozeduren` `null` ist (oder nicht passt), setze `menge` = Z.
    *   **Spezifische Anzahl Prozeduren:** Wenn `anzahl_prozeduren` extrahiert wurde und sich klar auf die aktuelle LKN bezieht (z.B. "zwei Injektionen" und LKN ist Injektion), setze `menge` = `anzahl_prozeduren`. Dies hat Vorrang vor `menge_allgemein` für diese LKN.
    *   Sicherstellen: `menge` >= 1.
    *   Wenn eine Prozedur "Seitigkeit" verlangt, dann erzeuge bei "beidseits" Menge = 2 UND "Seitigkeit" = "beidseits" .

5.  **Begründung:**
    *   **Kurze** `begruendung_llm`, warum die **validierten** LKNs gewählt wurden. Beziehe dich auf Text und **Katalog-Beschreibungen**.

**Output-Format:** **NUR** valides JSON, **KEIN** anderer Text.
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
    "geschlecht": null,
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

        return f"""**Tâche :** Vous êtes un expert des systèmes de facturation médicale en Suisse (TARDOC et Pauschalen). Votre objectif est de trouver, pour la prestation TARDOC indiquée (type E/EZ), la prestation fonctionnellement **équivalente** dans la « liste des candidats ». Cette liste contient des LKN (souvent P/PZ) utilisés comme conditions dans les Pauschalen potentielles.

**Prestation TARDOC donnée (type E/EZ):**
*   LKN: {tardoc_lkn}
*   Description: {tardoc_desc}
*   Contexte: Cette prestation a été réalisée dans le cadre d'un traitement pour lequel une facturation par Pauschalen est examinée.

**Équivalents possibles (liste des candidats - LKN pour les conditions des Pauschalen) :**
Choisissez dans CETTE liste la LKN candidate décrivant **le même type d'acte médical** que la prestation TARDOC.
--- Kandidaten Start ---
{candidates_text}
--- Kandidaten Ende ---

**Analyse et décision :**
1.  Comprenez la **fonction médicale principale** de la prestation TARDOC.
2.  Identifiez les LKN candidates correspondant le mieux à cette fonction.
3.  Classez-les par pertinence.

**Réponse :**
*   Donnez une **liste simple séparée par des virgules** des codes LKN retenus.
*   Si aucun candidat ne convient, renvoyez exactement `NONE`.
*   Aucune autre sortie, pas d'explications.

Liste priorisée (seulement la liste ou NONE):"""
    elif lang == "it":
        return f"""**Compito:** Sei un esperto dei sistemi di fatturazione medica in Svizzera (TARDOC e Pauschalen). Il tuo obiettivo è individuare, per la prestazione TARDOC indicata (tipo E/EZ), la prestazione funzionalmente **equivalente** nella "lista dei candidati". Questa lista contiene LKN (spesso P/PZ) utilizzati come condizioni nelle Pauschalen potenzialmente rilevanti.

**Prestazione TARDOC fornita (tipo E/EZ):**
*   LKN: {tardoc_lkn}
*   Descrizione: {tardoc_desc}
*   Contesto: Questa prestazione è stata eseguita nell'ambito di un trattamento per il quale si verifica una fatturazione a forfait.

**Possibili equivalenti (lista dei candidati - LKN per le condizioni delle Pauschalen):**
Trova in QUESTA lista la LKN candidata che descrive **lo stesso tipo di atto medico** della prestazione TARDOC.
--- Kandidaten Start ---
{candidates_text}
--- Kandidaten Ende ---

**Analisi e decisione:**
1.  Comprendi la **funzione medica principale** della prestazione TARDOC.
2.  Individua i candidati che rappresentano meglio tale funzione.
3.  Ordinali per pertinenza.

**Risposta:**
*   Fornisci un **elenco semplice separato da virgole** dei codici LKN trovati.
*   Se nessun candidato è adatto, restituisci esattamente `NONE`.
*   Nessun altro testo o spiegazione.

Elenco prioritario (solo elenco o NONE):"""
    else:
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
        return f"""Sur la base du texte de traitement suivant, quelle Pauschale listée ci-dessous correspond le mieux au contenu ?
Prends en compte la description de la Pauschale ('Pauschale_Text').
Fournis une liste priorisée des codes de Pauschale en commençant par la meilleure correspondance.
Donne UNIQUEMENT les codes séparés par des virgules (ex. "CODE1,CODE2"). Aucune justification.

Behandlungstext: "{user_input}"

Pauschalen potentielles:
--- Pauschalen Start ---
{potential_pauschalen_text}
--- Pauschalen Ende ---

Codes de Pauschale par ordre de pertinence (liste uniquement):"""
    elif lang == "it":
        return f"""In base al seguente testo di trattamento, quale delle Pauschalen elencate di seguito corrisponde meglio al contenuto?
Tieni conto della descrizione della Pauschale ('Pauschale_Text').
Fornisci un elenco prioritario dei codici Pauschale iniziando dal più adatto.
Fornisci SOLO i codici separati da virgola (es. "CODE1,CODE2"). Nessuna spiegazione.

Behandlungstext: "{user_input}"

Pauschalen potenziali:
--- Pauschalen Start ---
{potential_pauschalen_text}
--- Pauschalen Ende ---

Codici Pauschale in ordine di rilevanza (solo elenco):"""
    else:
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
