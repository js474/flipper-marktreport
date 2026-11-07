/** Legt Sheet und PDF-Ordner an und speichert die IDs in den Script Properties. Einmalig. */
function setup_createSheet() {
  if (!PROPS.getProperty('SHEET_ID')) {
    const ss = SpreadsheetApp.create('Fix & Flip Marktreport Abonnenten');
    const sh = ss.getSheets()[0]; sh.setName(CONFIG.sheetAbos);
    sh.appendRow(COLS); sh.setFrozenRows(1);
    ss.insertSheet(CONFIG.sheetAusgaben).appendRow(['Datei', 'Versendet am', 'Versendet an', 'Abonnenten gesamt']);
    ss.insertSheet(CONFIG.sheetLog).appendRow(['Zeit', 'Status', 'Info', 'Event-ID']);
    PROPS.setProperty('SHEET_ID', ss.getId());
    console.log('Sheet: ' + ss.getUrl());
  }
  if (!PROPS.getProperty('PDF_FOLDER_ID')) {
    const folder = DriveApp.createFolder('Fix & Flip Marktreport Ausgaben');
    PROPS.setProperty('PDF_FOLDER_ID', folder.getId());
    console.log('Ordner: ' + folder.getUrl());
  }
  if (!PROPS.getProperty('UPLOAD_SECRET')) PROPS.setProperty('UPLOAD_SECRET', Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, ''));
  ['SHEET_ID', 'PDF_FOLDER_ID'].forEach(k => {
    try { DriveApp.getFileById(PROPS.getProperty(k)).addEditor(CONFIG.errorMail); } catch (e) { console.log('Freigabe ' + k + ': ' + e); }
  });
  console.log('SHEET_ID=' + PROPS.getProperty('SHEET_ID') + ' PDF_FOLDER_ID=' + PROPS.getProperty('PDF_FOLDER_ID'));
  console.log('UPLOAD_SECRET (als GitHub-Secret REPORT_UPLOAD_SECRET eintragen): ' + PROPS.getProperty('UPLOAD_SECRET'));
}

function test_readSheet() {
  const rows = sheet_(CONFIG.sheetAbos).getDataRange().getValues();
  console.log('Zeilen: ' + rows.length + ' / Kopf: ' + rows[0].join(' | '));
  console.log('Aktive: ' + activeSubscribers_().length);
}

function test_latestIssue() {
  const f = latestIssue_();
  console.log(f ? 'Neueste Ausgabe: ' + f.getName() + ' (' + issueLabel_(f.getName()) + ')' : 'Keine PDF im Ordner');
}

function test_signature() {
  const secret = 'whsec_test';
  const payload = '{"id":"evt_1"}';
  const t = Math.floor(Date.now() / 1000);
  const mac = Utilities.computeHmacSha256Signature(t + '.' + payload, secret)
    .map(b => ('0' + (b & 0xff).toString(16)).slice(-2)).join('');
  const old = CONFIG.stripeWebhookSecret; CONFIG.stripeWebhookSecret = secret;
  console.log('gültig: ' + verifyStripeSignature_(payload, 't=' + t + ',v1=' + mac) + ' / manipuliert: ' + verifyStripeSignature_(payload + 'x', 't=' + t + ',v1=' + mac));
  CONFIG.stripeWebhookSecret = old;
}

/** Simuliert ein checkout.session.completed ohne Stripe, schreibt eine Testzeile und schickt die Willkommensmail an Johannes. */
function test_send_welcome() {
  handleEvent_({ id: 'evt_test', type: 'checkout.session.completed', created: Math.floor(Date.now() / 1000), data: { object: {
    mode: 'subscription', metadata: { produkt: 'marktreport' }, customer: 'cus_test', subscription: 'sub_test',
    amount_total: 1900, customer_details: { email: CONFIG.errorMail, name: 'Johannes Test' }, discounts: [] } } });
  console.log('Willkommensmail an ' + CONFIG.errorMail + ' gesendet');
}

function test_cleanupTestRows() {
  const sh = sheet_(CONFIG.sheetAbos);
  const rows = sh.getDataRange().getValues();
  for (let i = rows.length - 1; i > 0; i--) if (rows[i][4] === 'sub_test') sh.deleteRow(i + 1);
  console.log('Testzeilen entfernt');
}

function test_alias() {
  console.log('Aliase im Postfach: ' + GmailApp.getAliases().join(', ') + ' / report@ verfügbar: ' + aliasAvailable_());
}

/** Einmalig im Editor ausführen: Trigger setzen, Status und Upload-Secret ins Log schreiben. */
function einrichtenAbschliessen() {
  installTriggers();
  console.log('Trigger: ' + ScriptApp.getProjectTriggers().map(t => t.getHandlerFunction()).join(', '));
  console.log('Aliase: ' + GmailApp.getAliases().join(', ') + ' / report@ als Absender: ' + aliasAvailable_());
  console.log('REPORT_UPLOAD_SECRET für GitHub: ' + PROPS.getProperty('UPLOAD_SECRET'));
}

/** Schickt die Willkommensmail mit aktueller Ausgabe an js@, ohne Eintrag im Sheet. */
function testmailAnJs() {
  sendWelcome_(CONFIG.errorMail, 'Johannes');
  console.log('Testmail an ' + CONFIG.errorMail + ' / Absender: ' + (aliasAvailable_() ? CONFIG.fromAlias : 'johannes@') + ' / Ausgabe: ' + (latestIssue_() ? latestIssue_().getName() : 'keine'));
}

/** Kündigungsmail-Vorschau an js@ (ohne Sheet-Eintrag, Link ist nicht einlösbar). */
function test_kuendigungsmail() {
  const fake = { id: 'sub_TEST', current_period_end: Math.floor(Date.now() / 1000) + 20 * 86400 };
  const orig = subscriberBySub_;
  subscriberBySub_ = function () { return { email: CONFIG.errorMail, name: 'Johannes' }; };
  try { sendKuendigungsMail_(fake); } finally { subscriberBySub_ = orig; }
}
