"""Holt Monatsreihen der Bundesbank (Effektivzinsen Wohnungsbaukredite, Neugeschäft) für die letzten 13 Monate.
Schreibt data/snapshots/<MONAT>/bbk.json. Läuft im GitHub-Workflow (Runner hat freien Internetzugang)."""
import csv, io, json, os, pathlib, sys, urllib.request
R = pathlib.Path(__file__).resolve().parents[2]
MONTH = os.environ.get('REPORT_MONTH') or sys.argv[1]
SERIES = {   # (Datenfluss, Schlüssel)
    'j10':  ('BBIM1', 'M.DE.B.A2C.P.R.A.2250.EUR.N'),
    'j5_10': ('BBIM1', 'M.DE.B.A2C.O.R.A.2250.EUR.N'),
    'j1_5': ('BBIM1', 'M.DE.B.A2C.I.R.A.2250.EUR.N'),
    'var':  ('BBIM1', 'M.DE.B.A2C.F.R.A.2250.EUR.N'),
    'eur12': ('BBIG1', 'M.D0.EUR.MMKT.EURIBOR.M12.AVE.MA'),   # 12-Monats-Euribor, Monatsdurchschnitt
    'eur3':  ('BBIG1', 'M.D0.EUR.MMKT.EURIBOR.M03.AVE.MA'),
}
out = {'quelle': 'Deutsche Bundesbank, MFI-Zinsstatistik, Effektivzinssätze Neugeschäft, Wohnungsbaukredite an private Haushalte',
       'url': 'https://www.bundesbank.de/de/statistiken/geld-und-kapitalmaerkte/zinssaetze-und-renditen/wohnungsbaukredite-an-private-haushalte-hypothekarkredite-615036',
       'reihen': {}}
def hole(flow, s):
    fehler = []
    for fmt in ('sdmx_csv', 'csv', 'json'):
        u = f'https://api.statistiken.bundesbank.de/rest/data/{flow}/{s}?format={fmt}&lastNObservations=13&lang=en'
        try:
            txt = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'marktreport/1.0'}), timeout=60).read().decode('utf-8-sig')
        except Exception as e:
            fehler.append(f'{fmt}: {e}'); continue
        if fmt == 'json':
            try:
                j = json.loads(txt)
                ds = j['data']['dataSets'][0]['series']; ser = ds[next(iter(ds))]['observations']
                tps = j['data']['structure']['dimensions']['observation'][0]['values']
                pts = [(tps[int(i)]['id'], float(v[0])) for i, v in sorted(ser.items(), key=lambda x: int(x[0])) if v[0] is not None]
                if pts: return pts[-13:]
            except Exception as e:
                fehler.append(f'json: {e}')
            continue
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

for k, (flow, s) in SERIES.items():
    pts = hole(flow, s)
    if len(pts) < 6:
        sys.exit(f'Bundesbank-Reihe {k} zu kurz: {len(pts)} Werte')
    out['reihen'][k] = pts
    out['reihen_id_' + k] = flow + '.' + s
d = R / 'data' / 'snapshots' / MONTH
json.dump(out, open(d / 'bbk.json', 'w'), ensure_ascii=False, indent=1)
print('ok', {k: v[-1] for k, v in out['reihen'].items()})
