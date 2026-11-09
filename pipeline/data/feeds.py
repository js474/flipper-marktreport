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

FEEDS = [   # alle am 09.11.2026 geprüft (XML mit Einträgen aus 2026)
    ('Deutsche Bundesbank', 'https://www.bundesbank.de/service/rss/de/633290/feed.rss'),
    ('Deutsche Bundesbank, Pressenotizen', 'https://www.bundesbank.de/service/rss/de/633286/feed.rss'),
    ('Destatis', 'https://www.destatis.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/Aktuell.xml'),
    ('EZB', 'https://www.ecb.europa.eu/rss/press.html'),
    ('ifo Institut', 'https://www.ifo.de/rss'),
    ('DIW Berlin', 'https://www.diw.de/de/rss_press.xml'),
    ('IW Köln', 'https://www.iwkoeln.de/rss/iw-pressemitteilungen.xml'),
    ('IW Köln, Immobilienmärkte', 'https://www.iwkoeln.de/rss/immobilienmaerkte.xml'),
    ('vdp Pfandbriefbanken', 'https://www.pfandbrief.de/feed/'),
    ('vdp Pfandbriefbanken, Presseportal', 'https://www.presseportal.de/rss/pm_29608.rss2?langid=1'),
    ('GdW', 'https://www.gdw.de/feed/'),
    ('Haus & Grund', 'https://www.hausundgrund.de/rss/rss.xml'),
    ('bulwiengesa', 'https://bulwiengesa.de/de/feed'),
    ('Europace', 'https://europace.de/feed/'),
    ('Interhyp', 'https://www.presseportal.de/rss/pm_12620.rss2?langid=1'),
    ('ImmoScout24', 'https://www.presseportal.de/rss/pm_31321.rss2?langid=1'),
    ('immowelt', 'https://www.presseportal.de/rss/pm_24964.rss2?langid=1'),
    ('Bundesagentur für Arbeit', 'https://www.presseportal.de/rss/pm_6776.rss2?langid=1'),
    ('Haufe Immobilien', 'https://www.haufe.de/xml/rss_129130.xml'),
    ('Sprengnetter', 'https://www.sprengnetter.de/feed/'),
    ('BFW Bundesverband', 'https://www.bfw-bund.de/feed/'),
    ('IVD Immobilienverband', 'https://ivd.net/feed/'),
    ('Bundesgerichtshof', 'https://www.bundesgerichtshof.de/DE/Service/RSSFeed/Function/RSS_PM.xml?nn=373238'),
    ('Bundesfinanzministerium', 'https://www.bundesfinanzministerium.de/SiteGlobals/Functions/RSSFeed/DE/Pressemitteilungen/RSSPressemitteilungen.xml'),
    ('Tagesschau Wirtschaft', 'https://www.tagesschau.de/wirtschaft/index~rss2.xml'),
    ('Spiegel Wirtschaft', 'https://www.spiegel.de/wirtschaft/index.rss'),
    ('FAZ Wirtschaft', 'https://www.faz.net/rss/aktuell/wirtschaft/'),
]

WORTE = re.compile(r'immobil|wohnung|wohnungsbau|baugenehm|baupreis|bauzins|baufinanz|hypothek|zins|euribor|leitzins|einlagesatz|'
                   r'miete|mietpreis|kaufpreis|hauspreis|häuserpreis|eigentum|eigenheim|grunderwerb|grundsteuer|zwangsversteig|'
                   r'insolvenz|baukosten|sanier|energieausweis|gebäudeenergie|wärmepumpe|konsumklima|geschäftsklima|'
                   r'kredit|darlehen|inflation|verbraucherpreis|reallohn|einkommen|haushalte|privathaushalt|bevölkerung|zuwander|wanderung|'
                   r'erbschaft|vermögen|kfw|förder', re.I)

KERN = re.compile(r'immobil|wohn|\bbau|miet|kaufpreis|hauspreis|häuserpreis|eigentum|eigenheim|grunderwerb|grundsteuer|zins|euribor|hypothek|'
                  r'zwangsversteig|insolvenz|sanier|gebäude|wärmepumpe|heizung|erbschaft|haushalte|bevölkerung|zuwander|konsumklima|'
                  r'kredit|darlehen|inflation|verbraucherpreis|reallohn|makler|notar|grundbuch|baugenehm|fertigstell', re.I)
AUSSCHLUSS = re.compile(r'tender|bubill|schatzanweisung|bundesanleihe|aufstockung|podcast|webinar|veranstaltung|stellenangebot|smart city|'
                        r'jobs?\b|karriere|gewinnspiel|newsletter|sommerfest|jubiläum|plastiksteuer|fußball', re.I)

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

UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 marktreport-feedreader/1.0',
      'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.8, */*;q=0.5'}

def lade(url):
    import gzip
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read()
        if r.headers.get('Content-Encoding') == 'gzip' or raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
    return raw

def entdecke(url):
    """Wenn url eine HTML-Seite ist: <link rel="alternate" type="application/rss+xml|atom+xml" href=...> auslesen."""
    raw = lade(url)
    kopf = raw[:200000].decode('utf-8', 'ignore')
    m = re.search(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', kopf, re.I)
    if not m:
        return None
    h = re.search(r'href=["\']([^"\']+)', m.group(0))
    if not h:
        return None
    from urllib.parse import urljoin
    return urljoin(url, html.unescape(h.group(1)))

def hole(name, url):
    raw = lade(url)
    if raw.lstrip()[:1] != b'<' or b'<html' in raw[:2000].lower():
        alt = entdecke(url)
        if not alt:
            raise ValueError('kein XML und kein Feed-Link auf der Seite')
        raw = lade(alt); url = alt
    raw = re.sub(rb'^[^<]*', b'', raw, count=1)
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
            from urllib.parse import urljoin
            out.append({'quelle': name, 'titel': t, 'link': urljoin(url, l), 'datum': d.date().isoformat() if d else None, 'teaser': z})
    return out

_titel_gesehen = set()
grenze = (datetime.now(timezone.utc) - timedelta(days=TAGE)).date().isoformat()
ergebnis = {'stand': datetime.now(timezone.utc).date().isoformat(), 'zeitraum_ab': grenze, 'feeds_ok': [], 'feeds_fehler': {}, 'meldungen': []}
for name, url in FEEDS:
    try:
        eintraege = hole(name, url)
    except Exception as e:
        ergebnis['feeds_fehler'][name] = f'{url}: {type(e).__name__}: {str(e)[:120]}'
        continue
    ergebnis['feeds_ok'].append({'quelle': name, 'url': url, 'eintraege': len(eintraege), 'neuester': max((e['datum'] or '' for e in eintraege), default=None)})
    for e in eintraege:
        if e['datum'] and e['datum'] < grenze:
            continue
        if AUSSCHLUSS.search(e['titel']):
            continue
        if WORTE.search(e['titel'] + ' ' + e['teaser']) and e['titel'] not in _titel_gesehen:
            e['titel_treffer'] = bool(KERN.search(e['titel']))
            _titel_gesehen.add(e['titel']); ergebnis['meldungen'].append(e)

ergebnis['meldungen'].sort(key=lambda x: x['datum'] or '', reverse=True)
d = R / 'data' / 'snapshots' / MONTH
d.mkdir(parents=True, exist_ok=True)
json.dump(ergebnis, open(d / 'feeds.json', 'w'), ensure_ascii=False, indent=1)
print(f"Feeds ok: {len(ergebnis['feeds_ok'])}, Fehler: {len(ergebnis['feeds_fehler'])}, relevante Meldungen seit {grenze}: {len(ergebnis['meldungen'])}")
for k, v in ergebnis['feeds_fehler'].items():
    print('  FEHLER', k, v)
if len(ergebnis['feeds_ok']) < 12:
    sys.exit('Zu wenige Feeds erreichbar')
