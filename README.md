# Fix & Flip Marktreport

Pipeline für den monatlichen Marktreport von Flippɘr.

- `ausgaben/`: fertige PDFs. Jeder Push einer neuen Ausgabe übergibt sie automatisch an den Versand (Apps Script "Fix & Flip Marktreport Abo", Drive-Ordner, Versand am 15.).
- `pipeline/`: Datenabruf, Kennzahlen, Rendering (im Aufbau).
- `data/snapshots/JJJJ-MM/`: Rohdaten je Ausgabe, Basis für Vormonatsvergleiche.

Secrets (Settings, Secrets and variables, Actions): `REPORT_UPLOAD_SECRET`, `LEVERAGE_API_KEY`, `ANTHROPIC_API_KEY`.
