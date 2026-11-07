"""Holt Monatsreihen der Bundesbank (Effektivzinsen Wohnungsbaukredite, Neugeschäft) für die letzten 13 Monate.
Schreibt data/snapshots/<MONAT>/bbk.json. Läuft im GitHub-Workflow (Runner hat freien Internetzugang)."""
import csv, io, json, os, pathlib, sys, urllib.request
R = pathlib.Path(__file__).resolve().parents[2]
MONTH = os.environ.get('REPORT_MONTH') or sys.argv[1]
SERIES = {
    'j10':  'M.DE.B.A2C.P.R.A.2250.EUR.N',
    'j5_10': 'M.DE.B.A2C.O.R.A.2250.EUR.N',
    'j1_5': 'M.DE.B.A2C.I.R.A.2250.EUR.N',
    'var':  'M.DE.B.A2C.F.R.A.2250.EUR.N',
}
out = {'quelle': 'Deutsche Bundesbank, MFI-Zinsstatistik, Effektivzinssätze Neugeschäft, Wohnungsbaukredite an private Haushalte',
       'url': 'https://www.bundesbank.de/de/statistiken/geld-und-kapitalmaerkte/zinssaetze-und-renditen/wohnungsbaukredite-an-private-haushalte-hypothekarkredite-615036',
       'reihen': {}}
for k, s in SERIES.items():
    u = f'https://api.statistiken.bundesbank.de/rest/data/BBIM1/{s}?format=sdmx_csv&lastNObservations=13'
    txt = urllib.request.urlopen(urllib.request.Request(u, headers={'Accept': 'text/csv'}), timeout=60).read().decode('utf-8')
    rows = list(csv.DictReader(io.StringIO(txt)))
    pts = [(r['TIME_PERIOD'], float(r['OBS_VALUE'])) for r in rows if r.get('OBS_VALUE') not in (None, '', '.')]
    if len(pts) < 6:
        sys.exit(f'Bundesbank-Reihe {k} zu kurz: {len(pts)} Werte')
    out['reihen'][k] = pts
    out['reihen_id_' + k] = 'BBIM1.' + s
d = R / 'data' / 'snapshots' / MONTH
json.dump(out, open(d / 'bbk.json', 'w'), ensure_ascii=False, indent=1)
print('ok', {k: v[-1] for k, v in out['reihen'].items()})
