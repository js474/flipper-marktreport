/** ---------- Webhook (Stripe -> Web-App) ---------- */
function doPost(e) {
  if (e.parameter && e.parameter.upload === '1') return handleUpload_(e);
  const raw = e.postData && e.postData.contents ? e.postData.contents : '';
  const sig = headerValue_(e, 'Stripe-Signature');
  let event;
  try {
    if (!verifyStripeSignature_(raw, sig)) {
      logWebhook_('abgelehnt', 'Signatur ungültig', '');
      return json_({ ok: false, error: 'bad signature' }, 400);
    }
    event = JSON.parse(raw);
    handleEvent_(event);
    logWebhook_('ok', event.type, event.id);
    return json_({ ok: true });
  } catch (err) {
    console.error('doPost: ' + err + '\n' + (err.stack || ''));
    logWebhook_('fehler', String(err), event && event.id || '');
    meldeFehler_('Stripe-Webhook ' + (event && event.type || ''), err);
    return json_({ ok: false, error: String(err) }, 500);
  }
}

/** GitHub Actions liefert die fertige Ausgabe ab: JSON {name, data(base64)} mit ?upload=1&key=UPLOAD_SECRET */
function handleUpload_(e) {
  try {
    if (!e.parameter.key || e.parameter.key !== PROPS.getProperty('UPLOAD_SECRET')) return json_({ ok: false, error: 'forbidden' });
    const body = JSON.parse(e.postData.contents);
    if (!ISSUE_RE.test(body.name)) return json_({ ok: false, error: 'bad name' });
    const folder = DriveApp.getFolderById(CONFIG.pdfFolderId);
    const existing = folder.getFilesByName(body.name);
    while (existing.hasNext()) existing.next().setTrashed(true);
    const blob = Utilities.newBlob(Utilities.base64Decode(body.data), MimeType.PDF, body.name);
    const file = folder.createFile(blob);
    console.log('Ausgabe abgelegt: ' + body.name + ' (' + file.getId() + ')');
    return json_({ ok: true, fileId: file.getId() });
  } catch (err) {
    meldeFehler_('Upload Ausgabe', err);
    return json_({ ok: false, error: String(err) });
  }
}

function doGet(e) {
  if (e && e.parameter && e.parameter.bleiben) return bleibSeite_(e);
  return ContentService.createTextOutput('Marktreport-Webhook aktiv').setMimeType(ContentService.MimeType.TEXT);
}

function headerValue_(e, name) {
  const h = (e && e.headers) || {};
  const key = Object.keys(h).find(k => k.toLowerCase() === name.toLowerCase());
  return key ? h[key] : (e.parameter && e.parameter.sig) || '';
}

function verifyStripeSignature_(payload, header) {
  if (!CONFIG.stripeWebhookSecret) throw new Error('STRIPE_WEBHOOK_SECRET fehlt in den Script Properties');
  if (!header) return false;
  const parts = Object.fromEntries(header.split(',').map(p => p.split('=')));
  const t = parts.t, v1 = parts.v1;
  if (!t || !v1) return false;
  if (Math.abs(Date.now() / 1000 - Number(t)) > 600) return false;
  const mac = Utilities.computeHmacSha256Signature(t + '.' + payload, CONFIG.stripeWebhookSecret);
  const hex = mac.map(b => ('0' + (b & 0xff).toString(16)).slice(-2)).join('');
  return hex === v1;
}

function handleEvent_(event) {
  const obj = event.data.object;
  switch (event.type) {
    case 'checkout.session.completed':
      if (obj.mode !== 'subscription') return;
      if (!isReportProduct_(obj.metadata)) return;
      upsertSubscriber_({
        email: obj.customer_details && obj.customer_details.email,
        name: obj.customer_details && obj.customer_details.name,
        customer: obj.customer, subscription: obj.subscription,
        status: 'active', amount: obj.amount_total,
        promo: obj.discounts && obj.discounts[0] ? (obj.discounts[0].promotion_code || obj.discounts[0].coupon || '') : '',
        start: new Date(event.created * 1000)
      });
      sendWelcome_(obj.customer_details.email, obj.customer_details.name, obj.subscription);
      break;
    case 'customer.subscription.updated':
    case 'customer.subscription.deleted':
      if (!isReportProduct_(obj.metadata)) return;
      updateStatus_(obj.id, obj.status, obj.cancel_at_period_end ? new Date(periodEnd_(obj) * 1000) : (obj.ended_at ? new Date(obj.ended_at * 1000) : null));
      const prev = event.data.previous_attributes || {};
      if (event.type === 'customer.subscription.updated' && obj.cancel_at_period_end && prev.cancel_at_period_end === false) {
        sendKuendigungsMail_(obj);
      }
      break;
    default:
      // andere Events ignorieren
  }
}

function isReportProduct_(meta) {
  return meta && String(meta.produkt || '').toLowerCase() === CONFIG.productMarker;
}

/** ---------- Sheet ---------- */
function sheet_(name) {
  const ss = SpreadsheetApp.openById(CONFIG.sheetId);
  let sh = ss.getSheetByName(name);
  if (!sh) { sh = ss.insertSheet(name); }
  return sh;
}

function upsertSubscriber_(s) {
  const sh = sheet_(CONFIG.sheetAbos);
  const rows = sh.getDataRange().getValues();
  const idx = rows.findIndex((r, i) => i > 0 && r[4] === s.subscription);
  const row = [new Date(), s.email, s.name || '', s.customer, s.subscription, s.status, (s.amount || 0) / 100, s.promo || '', s.start || '', '', '', ''];
  if (idx > 0) {
    row[0] = rows[idx][0]; row[10] = rows[idx][10]; row[11] = rows[idx][11];
    sh.getRange(idx + 1, 1, 1, COLS.length).setValues([row]);
  } else {
    sh.appendRow(row);
  }
  console.log('Abonnent gespeichert: ' + s.email + ' / ' + s.subscription);
}

function updateStatus_(subscriptionId, status, endDate) {
  const sh = sheet_(CONFIG.sheetAbos);
  const rows = sh.getDataRange().getValues();
  const idx = rows.findIndex((r, i) => i > 0 && r[4] === subscriptionId);
  if (idx < 1) { console.log('Subscription unbekannt: ' + subscriptionId); return; }
  sh.getRange(idx + 1, 6).setValue(status);
  if (endDate) sh.getRange(idx + 1, 10).setValue(endDate);
  console.log('Status: ' + subscriptionId + ' -> ' + status);
}

function activeSubscribers_() {
  const sh = sheet_(CONFIG.sheetAbos);
  const rows = sh.getDataRange().getValues();
  const now = new Date();
  return rows.slice(1).map((r, i) => ({ rowIndex: i + 2, email: r[1], name: r[2], status: r[5], end: r[9], last: r[11] }))
    .filter(x => x.email && CONFIG.activeStatus.indexOf(x.status) >= 0 || (x.status === 'canceled' && x.end && new Date(x.end) > now));
}

function logWebhook_(status, info, eventId) {
  try { sheet_(CONFIG.sheetLog).appendRow([new Date(), status, info, eventId]); } catch (e) { console.error('Log: ' + e); }
}

/** ---------- Ausgaben und Versand ---------- */
/** Alle Ausgaben im Ordner, neueste zuerst. */
function allIssues_() {
  const files = DriveApp.getFolderById(CONFIG.pdfFolderId).getFilesByType(MimeType.PDF);
  const list = [];
  while (files.hasNext()) {
    const f = files.next();
    const m = ISSUE_RE.exec(f.getName());
    if (m) list.push({ f: f, key: m[1] + m[2] + '|' + f.getLastUpdated().toISOString(), y: Number(m[1]), mo: Number(m[2]) });
  }
  list.sort((a, b) => (a.key < b.key ? 1 : -1));
  const seen = {};
  return list.filter(x => { const k = x.y + '-' + x.mo; if (seen[k]) return false; seen[k] = 1; return true; });
}

/** Erschienen = schon an alle verschickt oder Versandtermin (15., 9 Uhr) erreicht. Neue Abos bekommen nichts vor dem offiziellen Termin. */
function publishedIssues_() {
  const now = new Date();
  const all = allIssues_();
  const pub = all.filter(x => issueAlreadySent_(x.f.getName()) || now >= new Date(x.y, x.mo - 1, CONFIG.sendDay, CONFIG.sendHour));
  return (pub.length ? pub : all.slice(0, 1)).map(x => x.f);
}

function latestIssue_() {
  const files = DriveApp.getFolderById(CONFIG.pdfFolderId).getFilesByType(MimeType.PDF);
  let best = null, bestKey = '';
  while (files.hasNext()) {
    const f = files.next();
    const m = ISSUE_RE.exec(f.getName());
    if (!m) continue;
    const key = m[1] + m[2] + '|' + f.getLastUpdated().toISOString();
    if (key > bestKey) { best = f; bestKey = key; }
  }
  return best;
}

function issueAlreadySent_(fileName) {
  const sh = sheet_(CONFIG.sheetAusgaben);
  return sh.getDataRange().getValues().some(r => r[0] === fileName);
}

function sendMonthlyReport() {
  const file = latestIssue_();
  if (!file) { console.log('Keine Ausgabe im Ordner'); return; }
  if (issueAlreadySent_(file.getName())) { console.log('Bereits versendet: ' + file.getName()); return; }
  const subs = activeSubscribers_();
  let sent = 0;
  subs.forEach(s => {
    if (s.last === file.getName()) return;   // hat die Ausgabe schon mit der Willkommensmail bekommen
    try {
      sendIssueMail_(s.email, s.name, file, false);
      const sh = sheet_(CONFIG.sheetAbos);
      sh.getRange(s.rowIndex, 11).setValue(new Date());
      sh.getRange(s.rowIndex, 12).setValue(file.getName());
      sent++;
    } catch (err) { meldeFehler_('Monatsversand an ' + s.email, err); }
  });
  sheet_(CONFIG.sheetAusgaben).appendRow([file.getName(), new Date(), sent, subs.length]);
  console.log('Ausgabe ' + file.getName() + ' an ' + sent + ' von ' + subs.length + ' versendet');
}

/** Willkommensmail mit den letzten zwei erschienenen Ausgaben (Goodie), damit niemand bis zum nächsten 15. wartet. */
function sendWelcome_(email, name, subscriptionId) {
  const files = publishedIssues_().slice(0, 2);
  sendIssueMail_(email, name, files, true);
  if (subscriptionId && files.length) {
    const sh = sheet_(CONFIG.sheetAbos);
    const rows = sh.getDataRange().getValues();
    const i = rows.findIndex((x, k) => k > 0 && x[4] === subscriptionId);
    if (i > 0) { sh.getRange(i + 1, 11).setValue(new Date()); sh.getRange(i + 1, 12).setValue(files[0].getName()); }
  }
}

function issueLabel_(fileName) {
  const m = /(\d{4})-(\d{2})/.exec(fileName || '');
  if (!m) return '';
  const monate = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
  return monate[Number(m[2]) - 1] + ' ' + m[1];
}

const LINK = 'color:#3e7b80';

function mailFooter_() {
  return '<hr style="border:none;border-top:1px solid #dbe6e7;margin:28px 0 16px">' +
    '<p style="font-size:12px;color:#5f6e6f;line-height:1.6">Du erhältst diese E-Mail, weil du den Marktreport für Immobilienhandel abonniert hast.<br><br>' +
    '<a href="' + CONFIG.portalUrl + '" style="' + LINK + '">Abo beenden oder verwalten</a>: Du wirst zu Stripe weitergeleitet, gibst deine E-Mail-Adresse ein, bekommst einen Anmeldelink und kannst das Abo dort mit einem Klick ändern und anpassen.<br>' +
    'Keine Anlage-, Steuer- oder Rechtsberatung. Alle Angaben ohne Gewähr.<br>' +
    '<a href="' + CONFIG.website + '/impressum" style="' + LINK + '">Impressum</a> · <a href="' + CONFIG.website + '/datenschutz" style="' + LINK + '">Datenschutz</a></p>';
}

function mailSignatur_() {
  return '<p>Viel Spass damit,</p><p>Johannes &amp; Team Flipper<br><a href="' + CONFIG.website + '" style="' + LINK + '">www.flipperimmo.com</a></p>';
}

function sendIssueMail_(email, name, fileOrFiles, welcome) {
  const files = Array.isArray(fileOrFiles) ? fileOrFiles : (fileOrFiles ? [fileOrFiles] : []);
  const file = files[0] || null;
  const label = file ? issueLabel_(file.getName()) : '';
  const vorname = name ? String(name).trim().split(' ')[0] : '';
  const anrede = vorname ? 'Hallo ' + vorname + ',' : 'Hallo,';
  const subject = welcome
    ? 'dein Immobilienhandel Marktreport: Ausgabe ' + label
    : 'dein Immobilienhandel Marktreport: Ausgabe ' + label;
  const body = welcome
    ? '<p>' + anrede + '<br>danke für dein Abo und dein Vertrauen.</p>' +
      (files.length > 1
        ? '<p>Im Anhang liegen die aktuelle Ausgabe (' + label + ') und als Extra die Ausgabe ' + issueLabel_(files[1].getName()) + ' des Immobilienhandel-Marktreports. Jede neue Ausgabe kommt automatisch an diese Adresse, sobald sie erscheint.<br>'
        : '<p>Im Anhang liegt die aktuelle Ausgabe des Immobilienhandel-Marktreports. Jede neue Ausgabe kommt automatisch an diese Adresse, sobald sie erscheint.<br>') +
      '(Da wir auf viele wichtige Daten warten, meistens am 15. des Folgemonats.)</p>'
    : '<p>' + anrede + '</p>' +
      '<p>im Anhang liegt die neue Ausgabe des Immobilienhandel-Marktreports für ' + label + '.</p>';
  const html = '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:#1d2b2c;max-width:620px">' +
    body + mailSignatur_() + mailFooter_() + '</div>';
  const opts = { htmlBody: html, name: CONFIG.senderName, replyTo: CONFIG.replyTo };
  if (aliasAvailable_()) opts.from = CONFIG.fromAlias;
  if (files.length) opts.attachments = files.map(f => f.getAs(MimeType.PDF));
  GmailApp.sendEmail(email, subject, 'Im Anhang liegt der Immobilienhandel-Marktreport. Abo beenden oder verwalten: ' + CONFIG.portalUrl, opts);
}

function aliasAvailable_() {
  try { return GmailApp.getAliases().indexOf(CONFIG.fromAlias) >= 0; } catch (e) { return false; }
}

function json_(obj, code) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function periodEnd_(sub) {
  return sub.current_period_end || (sub.items && sub.items.data && sub.items.data[0] && sub.items.data[0].current_period_end) || 0;
}
