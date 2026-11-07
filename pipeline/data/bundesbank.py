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
def hole(s):
    fehler = []
    for fmt in ('sdmx_csv', 'csv'):
        u = f'https://api.statistiken.bundesbank.de/rest/data/BBIM1/{s}?format={fmt}&lastNObservations=13&lang=en'
        try:
            txt = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'marktreport/1.0'}), timeout=60).read().decode('utf-8-sig')
        except Exception as e:
            fehler.append(f'{fmt}: {e}'); continue
        sep = ';' if txt.count(';') > txt.count(',') else ','
        rows = list(csv.reader(io.StringIO(txt), delimiter=sep))
        pts = []
        for r in rows:
            if len(r) >= 2 and len(r[0]) == 7 and r[0][4] == '-':
                try: pts.append((r[0], float(r[1].replace(',', '.'))))
                except ValueError: pass
        if not pts and rows:
            hdr = rows[0]
            if 'TIME_PERIOD' in hdr and 'OBS_VALUE' in hdr:
                ti, vi = hdr.index('TIME_PERIOD'), hdr.index('OBS_VALUE')
                pts = [(r[ti], float(r[vi])) for r in rows[1:] if len(r) > vi and r[vi] not in ('', '.')]
        if pts:
            return pts[-13:]
        fehler.append(f'{fmt}: keine Werte, Anfang: {txt[:200]!r}')
    raise RuntimeError(' | '.join(fehler))

for k, s in SERIES.items():
    pts = hole(s)
    if len(pts) < 6:
        sys.exit(f'Bundesbank-Reihe {k} zu kurz: {len(pts)} Werte')
    out['reihen'][k] = pts
    out['reihen_id_' + k] = 'BBIM1.' + s
d = R / 'data' / 'snapshots' / MONTH
json.dump(out, open(d / 'bbk.json', 'w'), ensure_ascii=False, indent=1)
print('ok', {k: v[-1] for k, v in out['reihen'].items()})
