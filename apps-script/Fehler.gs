/** ---------- Fehler nach Slack (#automation-fehler) ----------
 * Script Properties: SLACK_BOT_TOKEN (Flipper Automation Hub), SLACK_FEHLER_CHANNEL (Channel-ID).
 * Gleiche Meldung höchstens einmal pro Stunde. Ohne Token: Mail an js@ als Rückfall.
 */
function meldeFehler_(wo, err) {
  const text = String(err && err.message || err);
  const stack = err && err.stack ? String(err.stack).split('\n').slice(0, 6).join('\n') : '';
  console.error('[' + wo + '] ' + text);
  try {
    const cache = CacheService.getScriptCache();
    const key = 'f_' + Utilities.base64Encode(Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, wo + text));
    if (cache.get(key)) return;
    cache.put(key, '1', 3600);
  } catch (e) {}
  const msg = ':rotating_light: *Marktreport · Apps Script* · ' + wo + '\n```' + text + (stack ? '\n' + stack : '') + '```\n' +
    'Quelle: Apps Script `marktreport-abo` (Repo js474/flipper-marktreport, Ordner apps-script/)';
  const token = PROPS.getProperty('SLACK_BOT_TOKEN');
  const channel = PROPS.getProperty('SLACK_FEHLER_CHANNEL') || 'C0CFVKQEJ81';  // #automation-fehler
  if (token && channel) {
    try {
      const res = UrlFetchApp.fetch('https://slack.com/api/chat.postMessage', {
        method: 'post', contentType: 'application/json; charset=utf-8',
        headers: { Authorization: 'Bearer ' + token },
        payload: JSON.stringify({ channel: channel, text: msg }), muteHttpExceptions: true
      });
      if (JSON.parse(res.getContentText()).ok) return;
    } catch (e) {}
  }
  try { MailApp.sendEmail(CONFIG.errorMail, 'Marktreport Fehler: ' + wo, text + '\n\n' + stack); } catch (e) {}
}

function test_fehlerSlack() {
  meldeFehler_('Test', new Error('Testmeldung, bitte ignorieren ' + new Date().toISOString()));
}
