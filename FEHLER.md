# Fehlerbehandlung

Alle Fehler landen in Slack **#automation-fehler** (C0CFVKQEJ81).

- Apps Script (`apps-script/Fehler.gs`, `meldeFehler_`): Webhook, Upload, Monatsversand, Bleib-Angebot. Gleiche Meldung max. 1x pro Stunde.
- GitHub Actions: Der Fehler-Wächter liest fehlgeschlagene Läufe über die Check-Runs-API.

## Fehler-Wächter (geplante Aufgabe, stündlich 7 bis 22 Uhr)
1. Neue Nachrichten in #automation-fehler ohne Reaktion lesen, plus fehlgeschlagene Check-Runs auf `main`.
2. 👀 setzen, Ursache im Repo suchen, beheben, Commit auf `main`.
3. Im Thread antworten: Ursache, Fix, Commit. ✅ setzen.
4. Nicht selbst lösbar (fehlender Key, Zugang, Geld- oder Kundentexte betroffen): Im Thread benennen, was Johannes tun muss, ❗ setzen.

Grenzen: Keine Änderungen an Preisen, Coupons, Stripe-Objekten oder Mailtexten ohne Freigabe. Keine Secrets in Code oder Slack.
