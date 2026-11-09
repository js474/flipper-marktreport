"""Verdichtet alle Monats-Snapshots (data/snapshots/JJJJ-MM/) zu einer Langzeitreihe data/historie.json.
Je Monat die Kernkennzahlen (Zinsen, Preise, Stimmung, Leverage je Stadt), damit spätere Ausgaben
Mehrmonats-Vergleiche und Charts bauen können, ohne alte Quellen neu abzurufen. Läuft im Workflow nach dem Build."""
import json, pathlib
R = pathlib.Path(__file__).resolve().parents[2]
S = R / 'data' / 'snapshots'
def lade(d, name):
    p = d / f'{name}.json'
    return json.load(open(p)) if p.exists() else {}
def g(obj, *keys):
    for k in keys:
        if not isinstance(obj, dict) or k not in obj: return None
        obj = obj[k]
    return obj
hist = {'hinweis': 'Automatisch aus data/snapshots/ verdichtet (pipeline/data/historie.py). Quelle je Wert steht im jeweiligen Monats-Snapshot.', 'monate': {}}
for d in sorted(x for x in S.iterdir() if x.is_dir()):
    m = d.name
    F, P, ST, MK, K = lade(d, 'fin'), lade(d, 'public'), lade(d, 'stimmung'), lade(d, 'markt'), lade(d, 'kpi')
    lev = {}
    for f in ('lev_sued', 'lev_west', 'lev_nord', 'lev_ost'):
        for c, v in lade(d, f).items():
            lev[c] = {k: v.get(k) for k in ('n', 'qm', 'alt', 'altsan', 'rend', 'disc', 'unter_n', 'unter_basis', 'r')}
    hist['monate'][m] = {
        'euribor_12m': g(F, 'euribor', 'm12'), 'euribor_3m': g(F, 'euribor', 'm3'), 'euribor_datum': g(F, 'euribor', 'datum'),
        'flipper_zins': [round(g(F, 'euribor', 'm12') + a, 3) for a in (g(F, 'euribor', 'flipper_aufschlag') or [])] if g(F, 'euribor', 'm12') else None,
        'ezb_einlage': g(P, 'ezb', 'einlage'),
        'greix_etw_yoy': g(P, 'greix', 'etw_yoy'), 'greix_etw_qoq': g(P, 'greix', 'etw_qoq'),
        'baupreise_instand_yoy': g(P, 'baupreise', 'instand_yoy'),
        'bop_preiserwartung': g(ST, 'bop_hh', 'preiserwartung_12m_mittel', 'wert'), 'bop_anteil_steigend': g(ST, 'bop_hh', 'anteil_steigend', 'wert'),
        'ifo_klima_wohnungsbau': g(ST, 'ifo', 'klima', 'wert'), 'ifo_storno': g(ST, 'ifo', 'storno', 'wert'),
        'konsumklima': g(ST, 'konsumklima', 'prognose', 'wert'), 'anschaffungsneigung': g(ST, 'konsumklima', 'anschaffung', 'wert'),
        'is24_nachfrage_kauf': g(MK, 'is24', 'nachfrage_kauf_de_pct'), 'zv_h1_letzt': (g(MK, 'zwangsversteigerungen', 'h1') or [[None, None]])[-1][1],
        'epx_etw_yoy': (g(MK, 'epx', 'etw') or [None, None, None])[2], 'vdp_etw_yoy': g(MK, 'vdp', 'etw_yoy'),
        'kaufkraft': g(K, 'kaufkraft'), 'darlehen_median': g(K, 'darl_med'), 'inserate_gesamt': g(K, 'n_total'),
        'leverage': lev,
    }
json.dump(hist, open(R / 'data' / 'historie.json', 'w'), ensure_ascii=False, indent=1)
print('ok', list(hist['monate']))
