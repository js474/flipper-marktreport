# Runbook: Monatsausgabe Immobilienhandel-Marktreport (Fix-und-Flip)

Ausgeführt vom Monats-Agenten (geplante Aufgabe in der Claude-Cloud, am 12. jedes Monats). Ziel: Am 15. um 9 Uhr verschickt das Apps Script automatisch die neue Ausgabe an alle Abonnentinnen und Abonnenten.

**MONAT** = Erscheinungsmonat im Format JJJJ-MM (Lauf am 12.12.2026 → `2026-12`, Label "Dezember 2026"). **VORMONAT** = neuester Ordner unter `data/snapshots/`.

## Arbeitsteilung
- Agent: Daten holen, Snapshot schreiben, `pipeline/report/build.py` auf den neuen Monat anpassen (Labels, Datumsangaben, Schlüssel, Texte), lokal bauen und prüfen, pushen.
- GitHub Workflow "Report bauen und ausliefern": baut bei jedem Push auf `data/snapshots/**` oder `pipeline/report/**` das PDF, prüft Quellen, Stil und Seitenzahl, legt es in `ausgaben/` ab und übergibt es an den Versand. Kein Agent-Schritt nötig.

## Schritt 1: Snapshot anlegen
`cp -r data/snapshots/VORMONAT data/snapshots/MONAT`, dann jeden Block mit dem neuesten veröffentlichten Wert aktualisieren. Regeln:
- Nur Werte aus der Quelle selbst (Pressemitteilung, Tabelle, Datenbank). Nichts schätzen, nichts aus Erinnerung.
- Jeder Block behält bzw. bekommt eine `url` auf die konkrete Quelle. `pipeline/qa/quellencheck.py MONAT` muss 0 melden.
- Gibt es seit dem Vormonat keine neue Veröffentlichung, bleibt der Wert, Quelle und Stand bleiben unverändert (im Text dann den alten Stand nennen).
- Schlüssel mit Monatsnamen (z. B. `sep26`) dürfen umbenannt werden, `build.py` dann mit anpassen. Vormonatswerte für Vergleiche behalten (z. B. `vm_*`).

Quellen je Datei (erste Wahl, jeweils neueste Veröffentlichung):
- `public.json`: Bundesbank MFI-Zinsstatistik (Bauzins >10 J., Neugeschäft), EZB-Beschlüsse, Bundesbank Rendite Bund 10 J., GREIX (Kiel Institut), Europace EPX, Destatis Häuserpreisindex, Baupreisindex, Baugenehmigungen, Wanderung, VPI, Zensus-Leerstand.
- `fin.json`: Bundesbank Geldmarktsätze (Euribor 3M/6M, €STR), MFI-Zinsstatistik Wohnungsbau nach Zinsbindung und Unternehmenskredite, Bank Lending Survey, Dr. Klein Trendindikator Baufinanzierung, KfW-Merkblätter 308 und 261, Grunderwerbsteuer je Land, Notarkosten (Verbraucherzentrale).
- `zg.json`: Destatis Wohnkostenanteil, Mietbelastung, Einkommen (EU-SILC), Reallöhne, BA Arbeitsmarkt, Eigentumsquote, Wohnfläche, Baufertigstellungen, Haushalte, Heizungsart.
- `demo.json`: Demografie, Erbschaften, DIW, Bevölkerungsprognose, Binnenwanderung, Mieten (GREIX-Miete, VPI Nettokalt), CO2-Preis, GEG, Zwangsversteigerungen, Steuerregeln.
- Zusätzlich lesen (für Kurzfassung und Einordnung, nur mit Quelle zitieren): bulwiengesa (https://www.bulwiengesa.de/feed/), Bundesbank- und Destatis-Pressemitteilungen, ifo, vdp-Index.

## Schritt 2: Leverage-Angebotsdaten (Leverage-MCP)
Tools: `deals_search_count`, `deals_search` (bei deals_search immer `limit: 1`). Nur Werte aus Tool-Outputs. Eine Region je Subagent.

Städte (je Datei 12):
- `lev_sued.json`: München, Augsburg, Kempten, Nürnberg, Regensburg, Ingolstadt, Würzburg, Stuttgart, Karlsruhe, Freiburg, Ulm, Mannheim
- `lev_west.json`: Köln, Düsseldorf, Dortmund, Essen, Duisburg, Bochum, Münster, Bielefeld, Aachen, Bonn, Wuppertal, Gelsenkirchen
- `lev_nord.json`: Hamburg, Bremen, Hannover, Kiel, Lübeck, Osnabrück, Braunschweig, Kassel, Frankfurt, Wiesbaden, Mainz, Saarbrücken
- `lev_ost.json`: Berlin, Leipzig, Dresden, Chemnitz, Magdeburg, Halle (Abfrage als "Halle (Saale)"), Erfurt, Rostock, Potsdam, Jena, Zwickau, Görlitz

Feste Parameter: `property_types ["apartment"]`, `deal_type "sale"`, `sources ["market_feed","direct","levi","immowelt","kleinanzeigen","is24","immobilo","seller_direct"]`, `location {"city": STADT, "country": "DE", "radius_km": R}`.
Radius R: 5. Gesamt-Count `capped` (≥1000) → 3, weiter capped → 2. Bei R=5 unter 150 Inseraten → 10 (falls dort nicht capped). Möglichst denselben Radius wie im Vormonat (steht als `r` im Snapshot).

Median-Methode: `deals_search_count` → n. Dann `deals_search` mit gleichen Filtern, `order_by` Kennzahl, `order_direction asc`, `offset floor(n/2)`, `limit 1`. Median nur ab n ≥ 5, sonst null.

Kriterien: SAN = `{"check_type":"condition_allowlist","params":{"values":["renovation_needed"]}}`, ALT = `[{"check_type":"building_year_min","threshold":1950},{"check_type":"building_year_max","threshold":1994}]`, REND = `{"check_type":"rental_yield_gross_market_min","threshold":0.0001}`.

Je Stadt (Schlüssel im JSON):
1. `n`, `qm`: alle Inserate, Median `sale_price_per_sqm`.
2. `san_n`, `san`: [SAN].
3. `alt_n`, `alt`: ALT.
4. `altsan_n`, `altsan`: ALT + [SAN].
5. `rend_n`, `rend`, `disc`: [REND], Median `rental_yield_gross_market` in % (2 NK); auf derselben Teilmenge Median `market_discount_pct` in % (positiv = unter Marktwert).
6. `neu30`: Count mit `crawled_since` = Abrufdatum minus 30 Tage.
7. `tage`: Median `days_online` (order_by `start_date`, offset floor(n/2)).
8. `lat`, `lon` aus `resolved_location`, `r` = Radius.
€/m² ganzzahlig.

## Schritt 3: build.py anpassen
- Alle Datums- und Monatsangaben (Titelseite "Ausgabe NN · Stand", Header, KPI-Untertitel, Quellen-Zitate mit Stand, Abrufdatum Leverage) auf den neuen Stand. Ausgabenummer hochzählen.
- Abschnitt „Neu in Recht und Steuern“: Nur wenn es seit dem Vormonat neue Urteile (BFH, BGH), BMF-Schreiben oder Gesetze mit Bezug zu Immobilienhandel, Grunderwerbsteuer, gewerblichem Grundstückshandel oder Förderung gibt. Dann als `recht_neu` (Liste mit titel, datum, kern, url) in `demo.json` und als eigenes Kapitel vor Methodik einbauen. Sonst entfällt das Kapitel.
- Vormonatsvergleich: Für jede Stadt Preis, Inserate, Rendite und Tage online gegen den Vormonats-Snapshot rechnen und in Tabelle (Spalte Δ Vormonat) und Kurzfassung zeigen.
- Texte (Kurzfassung, Intros, Notizen) neu schreiben, wo sich Zahlen oder Aussagen geändert haben. Wenn möglich Vormonatsvergleich nennen ("nach X im Vormonat").
- Jede Zahl im Text kommt aus dem Snapshot (f-String), nie fest eingetippt.
- Stil: `STYLE.md` ist verbindlich. Keine Erklärsätze, keine Gegenüberstellungs-Formeln, keine Gedankenstriche, nach Doppelpunkt groß, gendergerecht.

## Schritt 4: Lokal prüfen
```
npm i --silent && pip install -q playwright pymupdf
REPORT_MONTH=MONAT python3 pipeline/report/build.py
python3 pipeline/qa/quellencheck.py MONAT
python3 pipeline/qa/stilcheck.py out/Immobilienhandel-Marktreport-MONAT.pdf
```
Dann jede Seite als PNG rendern (pymupdf, 1x) und ansehen: keine überlappenden Texte, keine leeren Seiten, Karten und Grafiken vollständig, Seitenzahl 14 bis 30. Fehler beheben, erneut prüfen.

## Schritt 5: Ausliefern
Commit von `data/snapshots/MONAT/` und `pipeline/report/build.py` auf `main`, pushen. Danach den Check-Run "Report bauen und ausliefern" des Commits abwarten (`gh api repos/js474/flipper-marktreport/commits/<sha>/check-runs`, Annotations lesen). Erfolg = Notice "Versand übernommen".

## Schritt 6: Fehler
Wenn ein Schritt nicht lösbar ist oder der Workflow nach zwei Fix-Versuchen scheitert: Zeile im Google Sheet 1IN_aYyqlkumBD5FFXdLk72JU2-PTOFoeqMi9-BQ2csc, Tab "Fehler" anhängen: Zeit, Tag (JJJJ-MM-TT), Quelle "Monats-Agent", Meldung, Stack leer, Anzahl 1, Status "offen", Notiz. Der Fehler-Wächter meldet das um 12 Uhr in Slack.

## Grenzen
Keine Änderungen an Stripe, Preisen, Abonnentendaten, Mailtexten oder Apps Script. Keine Testmails. Keine Secrets in Code oder Commits.
