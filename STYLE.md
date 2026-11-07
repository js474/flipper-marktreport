# Stilregeln Immobilienhandel-Marktreport (Fix-und-Flip)

Gilt für jeden Text im Report, jede Mail und jeden von Claude generierten Abschnitt. `pipeline/qa/stilcheck.py` prüft das automatisch, der Build bricht bei Funden ab.

## Name
- Titel: Immobilienhandel-Marktreport (Fix-und-Flip)
- Dateiname: `Immobilienhandel-Marktreport-JJJJ-MM.pdf`

## Ton
- Zahl, Quelle, Folge für die Kalkulation. Keine Erklärsätze, die der Leser selbst ziehen kann.
- Ein Satz sagt eine Sache. Keine Gegenüberstellungs-Formeln ("X macht A, Y macht B").
- Keine Begründungsketten mit "weil" am Satzende, wenn die Zahl für sich spricht.
- Wir-Form, Absender Team Flippɘr. Gendergerecht ("Käuferinnen und Käufer").

## Belegpflicht
- Jede Aussage im Text braucht eine Zahl aus dem Report im selben Abschnitt oder eine Quelle im Quellenverzeichnis. Keine Schlussfolgerungen über Käufergruppen, Zimmerzahlen, Erben, Abwanderung oder Nachfrage ohne Zahl.
- Keine Werbung für Leverage oder andere Produkte im Analyseteil.
- Eine Aussage, eine Zahl: Dieselbe Tatsache nicht mit zwei verschiedenen Prozentwerten ausdrücken (z. B. nur „5,6 % weniger Darlehen“, nicht zusätzlich „6,0 % mehr vor einem Jahr“).
- Werte aus verschiedenen Erhebungen (z. B. EU-SILC und Mikrozensus) nie im selben Diagramm.
- „Flip-Spanne“ nicht verwenden. Der Vergleich heißt „Abschlag unsaniert gegenüber Bestand gleicher Baujahre“.

## Zahlenformat
- Euro ganzzahlig (1.425 €), Prozent mit einer Nachkommastelle, Zinssätze mit zwei.
- Echtes Minuszeichen (−), Pluszeichen bei Veränderungen.
- Zwischen Zahl und Einheit ein geschütztes Leerzeichen (macht `feinschliff()` in build.py automatisch).
- CO₂ mit tiefgestellter 2.

## Verboten
- Gedankenstriche (– und —). Komma, Punkt oder Klammer nutzen.
- "nicht nur … sondern", "Die Frage ist nicht", "zahlt sich aus", "spielt eine Rolle", "heißt das:", "nur so gut wie"
- Floskeln: Kurz gesagt, Unterm Strich, Fakt ist, Wichtig ist, Am Ende des Tages, Lass uns
- KI-Vokabular: entscheidend, essenziell, maßgeblich, nahtlos, ganzheitlich
- Fett gesetzte Stichpunkt-Anfänge
- Dreierlisten als Stilmittel
- Coaching, Coach, Flipperversum
- Slogans und Ratgebersätze: „lohnt die …“, „die jeder Flipper kennen muss“, „ist die Alternative“, „bleibt knapp“, „in der Hand“, „sehr unterschiedlich“
- Doppelt gemoppelt: „+11,2 % mehr“
- Kleinschreibung nach Doppelpunkt (nach Doppelpunkt immer groß)

## Beispiel
Schlecht: "Der Flipper finanziert kurz und variabel, der Käufer lang und fest. Beide Rechnungen gehören in jede Kalkulation, weil der Verkaufspreis davon abhängt, was der Käufer finanzieren kann."

Gut: "Seite A rechnet eine Projektfinanzierung mit variablem Unternehmenskredit, Seite B eine Eigennutzer-Finanzierung mit 10 Jahren Zinsbindung."
