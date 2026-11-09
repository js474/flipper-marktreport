"""Google Trends (Deutschland, letzte 12 Monate, wöchentlich) für Suchbegriffe rund um Kauf, Verkauf und Zwangsversteigerung.
Schreibt data/snapshots/<MONAT>/trends.json. Läuft im GitHub-Workflow, nicht blockierend (Google drosselt gelegentlich).
Index 0 bis 100 relativ zum Höchstwert im Zeitraum je Begriff; Monatsmittel werden in build.py gebildet."""
import json, os, pathlib, sys, time
R = pathlib.Path(__file__).resolve().parents[2]
MONTH = os.environ.get('REPORT_MONTH') or sys.argv[1]
BEGRIFFE = ['Wohnung kaufen', 'Haus verkaufen', 'Zwangsversteigerung', 'Baufinanzierung', 'Wohnung mieten']
from pytrends.request import TrendReq
out = {'quelle': 'Google Trends, Suchinteresse Deutschland, wöchentlich, Index 0 bis 100 je Begriff (100 = Höchstwert im Zeitraum)',
       'url': 'https://trends.google.de/trends/explore?geo=DE&q=' + ','.join(b.replace(' ', '%20') for b in BEGRIFFE),
       'zeitraum': 'today 12-m', 'reihen': {}}
pt = TrendReq(hl='de-DE', tz=60, timeout=(10, 30), retries=3, backoff_factor=2)
for b in BEGRIFFE:
    for versuch in range(3):
        try:
            pt.build_payload([b], geo='DE', timeframe='today 12-m')
            df = pt.interest_over_time()
            if df.empty:
                raise RuntimeError('leer')
            out['reihen'][b] = [(d.strftime('%Y-%m-%d'), int(v)) for d, v in df[b].items()]
            break
        except Exception as e:
            print('Trends', b, 'Versuch', versuch + 1, type(e).__name__, str(e)[:100])
            time.sleep(20 * (versuch + 1))
if len(out['reihen']) < 3:
    sys.exit('Google Trends: zu wenige Reihen')
d = R / 'data' / 'snapshots' / MONTH
json.dump(out, open(d / 'trends.json', 'w'), ensure_ascii=False, indent=1)
print('ok', {k: v[-1] for k, v in out['reihen'].items()})
