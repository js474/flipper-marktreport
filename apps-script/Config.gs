/** Fix & Flip Marktreport: Abo-Liste und Versand. Keys liegen in den Script Properties. */
const PROPS = PropertiesService.getScriptProperties();

const CONFIG = {
  sheetId: PROPS.getProperty('SHEET_ID'),            // wird von setup_createSheet gesetzt
  pdfFolderId: '1aYiXY3tXvNctfYM8cqGddapuivZUOW5t',  // Ausgabenordner (Eigentümer js@, Schreibrecht johannes@)
  stripeWebhookSecret: PROPS.getProperty('STRIPE_WEBHOOK_SECRET'),
  stripeApiKey: PROPS.getProperty('STRIPE_API_KEY'), // optional, nur für Nachladen von Kundendaten

  sheetAbos: 'Abonnenten',
  sheetAusgaben: 'Ausgaben',
  sheetLog: 'Webhook-Log',

  senderName: 'Johannes Flipper',
  fromAlias: 'report@flipperimmo.com',   // Alias im Postfach johannes@, muss unter Gmail 'Senden als' eingerichtet sein
  replyTo: 'report@flipperimmo.com',
  errorMail: 'js@flipperimmo.com',
  portalUrl: 'https://billing.stripe.com/p/login/00w4gz5y15gWc2R0wU7g400',
  checkoutUrl: 'https://buy.stripe.com/dRmdR90dHbFk8QF6Vi7g41E',
  website: 'https://www.flipperimmo.com',

  sendDay: 15,          // Versandtag im Monat
  sendHour: 9,
  activeStatus: ['active', 'trialing', 'past_due'],
  productMarker: 'marktreport'   // metadata.produkt auf Payment Link / Subscription
};

const ISSUE_RE = /^(?:Immobilienhandel|Fix-und-Flip)-Marktreport-(\d{4})-(\d{2})\.pdf$/;

const COLS = ['Angelegt', 'E-Mail', 'Name', 'Customer-ID', 'Subscription-ID', 'Status', 'Preis brutto', 'Rabattcode', 'Start', 'Ende', 'Letzter Versand', 'Letzte Ausgabe'];
