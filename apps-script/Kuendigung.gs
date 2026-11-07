/** ---------- Kündigung: Bestätigung + Bleib-Angebot 9 € ---------- */

const BLEIB_COUPON = 'Et8OIoxs';   // Flipper 50 % dauerhaft, 19 € -> 9,50 € (gleich wie Partner-Code)
const BLEIB_PREIS = '9,50 €';

function bleibSecret_() {
  let s = PROPS.getProperty('BLEIB_SECRET');
  if (!s) { s = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, ''); PROPS.setProperty('BLEIB_SECRET', s); }
  return s;
}

function bleibToken_(subId) {
  const mac = Utilities.computeHmacSha256Signature(subId, bleibSecret_());
  return mac.map(b => ('0' + (b & 0xff).toString(16)).slice(-2)).join('').slice(0, 32);
}

function bleibLink_(subId) {
  return ScriptApp.getService().getUrl() + '?bleiben=' + encodeURIComponent(subId) + '&t=' + bleibToken_(subId);
}

/** Normales Abo = kein Rabatt aktiv. Nur dann gibt es das Angebot. */
function hatRabatt_(sub) {
  return !!(sub.discount || (sub.discounts && sub.discounts.length));
}

function subscriberBySub_(subId) {
  const rows = sheet_(CONFIG.sheetAbos).getDataRange().getValues();
  const r = rows.find((x, i) => i > 0 && x[4] === subId);
  return r ? { email: r[1], name: r[2] } : null;
}

function datumDe_(unix) {
  return Utilities.formatDate(new Date(unix * 1000), 'Europe/Berlin', 'dd.MM.yyyy');
}

function sendKuendigungsMail_(sub) {
  const s = subscriberBySub_(sub.id);
  if (!s || !s.email) { meldeFehler_('Kündigungsmail', 'Kein Abonnent im Sheet für ' + sub.id); return; }
  const vorname = s.name ? String(s.name).trim().split(' ')[0] : '';
  const anrede = vorname ? 'Hallo ' + vorname + ',' : 'Hallo,';
  const ende = datumDe_(periodEnd_(sub));
  const angebot = !hatRabatt_(sub);
  const BTN = 'display:inline-block;background:#3e7b80;color:#ffffff;text-decoration:none;font-weight:bold;padding:12px 22px;border-radius:6px';

  let body = '<p>' + anrede + '</p>' +
    '<p>schade, dass du keine Marktdaten rund um den Immobilienhandel mehr bekommen möchtest. Dein Abo läuft noch bis zum ' + ende + ', bis dahin bekommst du jede Ausgabe wie gewohnt.</p>';
  if (angebot) {
    body +=
      '<p>Sprichst du in Zukunft nicht mehr mit Banken, Maklerinnen und Maklern oder anderen Leuten aus der Branche? In genau diesen Gesprächen bringt dir der Report am meisten. Wer die aktuellen Zinsen und Preise der eigenen Region kennt, wird vom Gegenüber als Profi wahrgenommen.</p>' +
      '<p>Wir machen dir deshalb einen einmaligen Vorschlag: Bleib für ' + BLEIB_PREIS + ' statt 19 € im Monat dabei.</p>' +
      '<p style="margin:24px 0"><a href="' + bleibLink_(sub.id) + '" style="' + BTN + '">Für ' + BLEIB_PREIS + ' im Monat dabeibleiben</a></p>' +
      '<p>Ein Klick nimmt die Kündigung zurück. Ab der nächsten Abrechnung zahlst du ' + BLEIB_PREIS + ', alles andere bleibt gleich.</p>';
  }
  body += '<p>Viele Grüße</p><p>Johannes &amp; Team Flipper<br><a href="' + CONFIG.website + '" style="' + LINK + '">www.flipperimmo.com</a></p>';

  const html = '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:#1d2b2c;max-width:620px">' + body + mailFooter_() + '</div>';
  const subject = 'Dein Marktreport-Abo endet am ' + ende;
  const opts = { htmlBody: html, name: CONFIG.senderName, replyTo: CONFIG.replyTo };
  if (aliasAvailable_()) opts.from = CONFIG.fromAlias;
  const plain = 'Dein Abo endet am ' + ende + '.' + (angebot ? ' Für ' + BLEIB_PREIS + ' im Monat dabeibleiben: ' + bleibLink_(sub.id) : '');
  GmailApp.sendEmail(s.email, subject, plain, opts);
  console.log('Kündigungsmail an ' + s.email + (angebot ? ' mit Angebot' : ''));
}

/** ---------- Bleib-Seite (doGet ?bleiben=) ---------- */
function bleibSeite_(e) {
  const sub = e.parameter.bleiben, t = e.parameter.t;
  const ok = sub && t && t === bleibToken_(sub);
  const tpl = HtmlService.createTemplateFromFile('Bleiben');
  tpl.sub = ok ? sub : '';
  tpl.t = ok ? t : '';
  tpl.preis = BLEIB_PREIS;
  return tpl.evaluate().setTitle('Immobilienhandel-Marktreport').addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/** Wird per google.script.run vom Button aufgerufen. Kein GET-Klick löst etwas aus. */
function bleibenBestaetigen(subId, t) {
  try {
    if (!subId || t !== bleibToken_(subId)) return { ok: false, msg: 'Der Link ist ungültig.' };
    const sub = stripe_('get', '/v1/subscriptions/' + encodeURIComponent(subId));
    if (sub.status === 'canceled') return { ok: false, msg: 'Dein Abo ist bereits beendet. Schreib uns kurz an report@flipperimmo.com, dann richten wir es für dich wieder ein.' };
    if (hatRabatt_(sub) && !sub.cancel_at_period_end) return { ok: true, msg: 'Du bist schon dabei. Es ist nichts weiter zu tun.' };
    if (hatRabatt_(sub)) return { ok: false, msg: 'Für dein Abo gilt bereits ein Rabatt. Schreib uns an report@flipperimmo.com.' };
    stripe_('post', '/v1/subscriptions/' + encodeURIComponent(subId), {
      'cancel_at_period_end': 'false',
      'discounts[0][coupon]': BLEIB_COUPON
    });
    logWebhook_('bleiben', 'Kündigung zurückgenommen, ' + BLEIB_PREIS, subId);
    return { ok: true, msg: 'Erledigt: Deine Kündigung ist zurückgenommen. Ab der nächsten Abrechnung zahlst du ' + BLEIB_PREIS + ' im Monat.' };
  } catch (err) {
    meldeFehler_('Bleib-Angebot ' + subId, err);
    return { ok: false, msg: 'Das hat nicht geklappt. Schreib uns an report@flipperimmo.com, wir erledigen das für dich.' };
  }
}

function stripe_(method, path, payload) {
  const key = PROPS.getProperty('STRIPE_API_KEY');
  if (!key) throw new Error('STRIPE_API_KEY fehlt in den Script Properties');
  const opts = { method: method, headers: { Authorization: 'Bearer ' + key }, muteHttpExceptions: true };
  if (payload) opts.payload = payload;
  const res = UrlFetchApp.fetch('https://api.stripe.com' + path, opts);
  const data = JSON.parse(res.getContentText());
  if (res.getResponseCode() >= 300) throw new Error('Stripe ' + res.getResponseCode() + ': ' + (data.error && data.error.message));
  return data;
}
