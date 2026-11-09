"""Liest RSS/Atom-Feeds von Instituten, Verbänden und Datenanbietern, filtert auf Immobilien-, Zins- und Bauthemen
der letzten 35 Tage und schreibt data/snapshots/<MONAT>/feeds.json. Läuft im GitHub-Workflow (Runner hat Internet).
Der Monats-Agent liest feeds.json vor dem Schreiben der Kurzfassung (RUNBOOK Schritt 0). Nur Titel, Datum, Link,
Teaser; keine Volltexte. Zitiert wird im Report nur, was der Agent gelesen und mit Quelle versehen hat."""
import json, os, pathlib, re, sys, html, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

R = pathlib.Path(__file__).resolve().parents[2]
MONTH = os.environ.get('REPORT_MONTH') or sys.argv[1]
TAGE = int(os.environ.get('FEED_TAGE', '35'))

FEEDS = [
    ('Deutsche Bundesbank, Pressenotizen', 'https://www.bundesbank.de/action/de/rss/pressenotizen'),
    ('Deutsche Bundesbank, Statistiken', 'https://www.bundesbank.de/action/de/rss/statistiken'),
    ('Destatis, Pressemitteilungen', 'https://www.destatis.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/Pressemitteilungen.xml'),
    ('EZB, Pressemitteilungen', 'https://www.ecb.europa.eu/rss/press.html'),
    ('ifo Institut, Pressemitteilungen', 'https://www.ifo.de/rss/pressemitteilungen'),
    ('DIW Berlin, Pressemitteilungen', 'https://www.diw.de/de/diw_01.c.619586.de/rss_pressemitteilungen.xml'),
    ('IW Köln', 'https://www.iwkoeln.de/rss.xml'),
    ('KfW Research', 'https://www.kfw.de/%C3%9Cber-die-KfW/Newsroom/RSS-Feeds/RSS-Feed-Research.xml'),
    ('vdp Verband deutscher Pfandbriefbanken', 'https://www.pfandbrief.de/site/de/vdp/presse/rss.xml'),
    ('ZIA Zentraler Immobilien Ausschuss', 'https://zia-deutschland.de/feed/'),
    ('GdW Bundesverband Wohnungswirtschaft', 'https://www.gdw.de/feed/'),
    ('Haus & Grund Deutschland', 'https://www.hausundgrund.de/rss.xml'),
    ('bulwiengesa', 'https://www.bulwiengesa.de/feed/'),
    ('empirica', 'https://www.empirica-institut.de/feed/'),
    ('Europace / Hypoport', 'https://report.europace.de/feed/'),
    ('Interhyp Presse', 'https://www.interhyp.de/ueber-interhyp/presse/rss.xml'),
    ('Dr. Klein Presse', 'https://www.drklein.de/feed.xml'),
    ('ImmoScout24 Presse', 'https://www.immobilienscout24.de/unternehmen/presse/rss.xml'),
    ('immowelt Presse', 'https://www.immowelt.de/presse/feed'),
    ('Sparkassen-Finanzgruppe (DSGV) Presse', 'https://www.dsgv.de/rss.xml'),
    ('Bundesinstitut BBSR', 'https://www.bbsr.bund.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed.xml'),
    ('Bundesagentur für Arbeit Presse', 'https://www.arbeitsagentur.de/rss/presse'),
    ('Haufe Immobilien', 'https://www.haufe.de/xml/rss_132442.xml'),
    ('Immobilien Zeitung', 'https://www.iz.de/rss'),
    ('Handelsblatt Immobilien', 'https://www.handelsblatt.com/contentexport/feed/finanzen/immobilien'),
    ('Tagesschau Wirtschaft', 'https://www.tagesschau.de/wirtschaft/index~rss2.xml'),
]

WORTE = re.compile(r'immobil|wohnung|wohnungsbau|baugenehm|baupreis|bauzins|baufinanz|hypothek|zins|euribor|leitzins|einlagesatz|'
                   r'miete|mietpreis|kaufpreis|hauspreis|häuserpreis|eigentum|eigenheim|grunderwerb|grundsteuer|zwangsversteig|'
                   r'insolvenz|baukosten|sanier|energieausweis|gebäudeenergie|wärmepumpe|konsumklima|geschäftsklima|'
                   r'kredit|darlehen|inflation|verbraucherpreis|reallohn|einkommen|haushalt|bevölkerung|zuwander|wanderung|'
                   r'erbschaft|vermögen|kfw|förder', re.I)

def text(el, *names):
    for n in names:
        x = el.find(n)
        if x is not None and (x.text or '').strip():
            return html.unescape(re.sub(r'<[^>]+>', ' ', x.text)).strip()
        if x is not None and x.get('href'):
            return x.get('href')
    return ''

def datum(s):
    s = (s or '').strip()
    try:
        d = parsedate_to_datetime(s); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception: pass
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None

def hole(name, url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 marktreport-feedreader/1.0'})
    raw = urllib.request.urlopen(req, timeout=40).read()
    root = ET.fromstring(raw)
    ns = {'a': 'http://www.w3.org/2005/Atom', 'dc': 'http://purl.org/dc/elements/1.1/'}
    items = root.findall('.//item') or root.findall('.//a:entry', ns)
    out = []
    for it in items:
        t = text(it, 'title', '{http://www.w3.org/2005/Atom}title')
        l = text(it, 'link', '{http://www.w3.org/2005/Atom}link')
        d = datum(text(it, 'pubDate', '{http://purl.org/dc/elements/1.1/}date', '{http://www.w3.org/2005/Atom}updated', '{http://www.w3.org/2005/Atom}published'))
        z = text(it, 'description', '{http://www.w3.org/2005/Atom}summary', '{http://www.w3.org/2005/Atom}content')[:400]
        if t and l:
            out.append({'quelle': name, 'titel': t, 'link': l, 'datum': d.date().isoformat() if d else None, 'teaser': z})
    return out

grenze = (datetime.now(timezone.utc) - timedelta(days=TAGE)).date().isoformat()
ergebnis = {'stand': datetime.now(timezone.utc).date().isoformat(), 'zeitraum_ab': grenze, 'feeds_ok': [], 'feeds_fehler': {}, 'meldungen': []}
for name, url in FEEDS:
    try:
        eintraege = hole(name, url)
    except Exception as e:
        ergebnis['feeds_fehler'][name] = f'{url}: {type(e).__name__}: {str(e)[:120]}'
        continue
    ergebnis['feeds_ok'].append({'quelle': name, 'url': url, 'eintraege': len(eintraege)})
    for e in eintraege:
        if e['datum'] and e['datum'] < grenze:
            continue
        if WORTE.search(e['titel'] + ' ' + e['teaser']):
            ergebnis['meldungen'].append(e)

ergebnis['meldungen'].sort(key=lambda x: x['datum'] or '', reverse=True)
d = R / 'data' / 'snapshots' / MONTH
d.mkdir(parents=True, exist_ok=True)
json.dump(ergebnis, open(d / 'feeds.json', 'w'), ensure_ascii=False, indent=1)
print(f"Feeds ok: {len(ergebnis['feeds_ok'])}, Fehler: {len(ergebnis['feeds_fehler'])}, relevante Meldungen seit {grenze}: {len(ergebnis['meldungen'])}")
for k, v in ergebnis['feeds_fehler'].items():
    print('  FEHLER', k, v)
if len(ergebnis['feeds_ok']) < 8:
    sys.exit('Zu wenige Feeds erreichbar')
