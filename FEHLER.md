# Fehlerbehandlung

Eine Sammelmeldung pro Tag, 12 Uhr, in Slack **#automation-fehler** (C0CFVKQEJ81). Keine Fehlermails.

## Quellen
- Apps Script: `meldeFehler_` schreibt in den Tab **Fehler** im Sheet "Fix & Flip Marktreport Abonnenten" (1IN_aYyqlkumBD5FFXdLk72JU2-PTOFoeqMi9-BQ2csc). Spalten: Zeit, Tag, Quelle, Meldung, Stack, Anzahl, Status (offen/erledigt/Johannes), Notiz.
- GitHub Actions: fehlgeschlagene Check-Runs auf `main` der letzten 24 Stunden.

## Fehler-Wächter (geplante Aufgabe in der Claude-Cloud, täglich 12 Uhr, kein PC nötig)
1. Offene Zeilen im Tab Fehler plus fehlgeschlagene Check-Runs sammeln. Nichts offen: Ende, keine Slack-Nachricht.
2. Ursache im Repo suchen, beheben, Commit auf `main`.
3. Eine Slack-Nachricht mit allen Punkten: Ursache, Fix, Commit. Status im Sheet auf erledigt.
4. Nicht selbst lösbar oder Preise, Coupons, Stripe-Objekte, Abonnentendaten, Kundenmail-Texte betroffen: nichts ändern, in der Nachricht klar sagen, was Johannes tun muss, Status Johannes.

Apps-Script-Fixes: Deploy über Workflow "Apps Script deployen" braucht das Secret CLASPRC_JSON. Ohne Secret: Fix liegt im Repo, Deploy macht Claude in der nächsten Sitzung.
