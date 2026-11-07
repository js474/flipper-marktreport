"""Jeder Datenblock in data/snapshots/<MONAT>/*.json braucht eine Quelle (url, url2 oder *_url). Exit 1 bei Lücken."""
import json, sys, pathlib
month = sys.argv[1]
d = pathlib.Path(__file__).resolve().parents[2] / 'data' / 'snapshots' / month
fehl = []
for f in sorted(d.glob('*.json')):
    if f.name in ('kpi.json',) or f.name.startswith('lev_'):
        continue
    for k, v in json.load(open(f)).items():
        if isinstance(v, dict) and not any(isinstance(y, str) and y.startswith('http') for y in v.values()):
            fehl.append(f'{f.name}:{k}')
print(f'{len(fehl)} Block/Blöcke ohne Quelle' + (': ' + ', '.join(fehl) if fehl else ''))
sys.exit(1 if fehl else 0)
