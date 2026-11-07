/** ---------- Fehler-Log ----------
 * Fehler landen im Tab "Fehler" des Abonnenten-Sheets. Der Fehler-Wächter (geplante Aufgabe, täglich 12 Uhr)
 * liest den Tab, postet eine Sammelmeldung in Slack #automation-fehler, behebt und setzt den Status.
 * Gleicher Fehler am selben Tag: nur Zähler hoch.
 */
function meldeFehler_(wo, err) {
  const text = String(err && err.message || err);
  const stack = err && err.stack ? String(err.stack).split('\n').slice(0, 6).join('\n') : '';
  console.error('[' + wo + '] ' + text);
  try {
    const sh = sheet_('Fehler');
    if (sh.getLastRow() === 0) sh.appendRow(['Zeit', 'Tag', 'Quelle', 'Meldung', 'Stack', 'Anzahl', 'Status', 'Notiz']);
    const tag = Utilities.formatDate(new Date(), 'Europe/Berlin', 'yyyy-MM-dd');
    const rows = sh.getDataRange().getValues();
    const i = rows.findIndex((r, k) => k > 0 && r[1] === tag && r[2] === wo && r[3] === text);
    if (i > 0) { sh.getRange(i + 1, 6).setValue(Number(rows[i][5] || 1) + 1); return; }
    sh.appendRow([new Date(), tag, wo, text, stack, 1, 'offen', '']);
  } catch (e) {
    try { MailApp.sendEmail(CONFIG.errorMail, 'Marktreport Fehler: ' + wo, text + '\n\nFehler-Log nicht schreibbar: ' + e); } catch (x) {}
  }
}

function test_fehlerLog() {
  meldeFehler_('Test', new Error('Testeintrag, bitte ignorieren'));
}
