import re
import json, base64, math, pathlib, os
from playwright.sync_api import sync_playwright

R = pathlib.Path(__file__).resolve().parents[2]   # Repo-Wurzel
MONTH = os.environ.get('REPORT_MONTH', '2026-10')   # Berichtsmonat, Erscheinung am 15. des Folgemonats
_MN = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember']
_y, _m = int(MONTH[:4]), int(MONTH[5:7])
BERICHT = f'{_MN[_m-1]} {_y}'
_ey, _em = (_y + 1, 1) if _m == 12 else (_y, _m + 1)
ERSCHEINT = f'15. {_MN[_em-1]} {_ey}'
AUSGABE_NR = (_y - 2026) * 12 + _m - 9          # Oktober 2026 = Ausgabe 01
D = R / 'data' / 'snapshots' / MONTH
P = json.load(open(D/'public.json'))
F = json.load(open(D/'fin.json'))
Z = json.load(open(D/'zg.json'))
G = json.load(open(D/'demo.json'))
STAND = G.get('stand', '7. November 2026')   # Datenstand der Ausgabe, im Snapshot demo.json als 'stand' pflegen
BBK = json.load(open(D/'bbk.json')) if (D/'bbk.json').exists() else None
MON = ['Jan','Feb','Mrz','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez']
def mlabel(tp):   # '2026-09' -> 'Sep 26'
    y, m = tp.split('-')[:2]
    return f'{MON[int(m)-1]} {y[2:]}'
S = {}
for f in ['lev_sued', 'lev_west', 'lev_nord', 'lev_ost']:
    p = D/f'{f}.json'
    if p.exists():
        S.update(json.load(open(p)))

T, TD, TL, INK, MUT, RED, LINE = '#6fb2b7', '#3e7b80', '#edf6f7', '#1d2b2c', '#5f6e6f', '#c0675a', '#dbe6e7'

def de(x, d=0):
    if d < 0:
        x, d = round(x, d), 0
    s = f"{x:,.{d}f}"
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    if s.startswith('-'):
        s = '−' + s[1:]           # echtes Minuszeichen
    if s in ('−0', '−0,0', '−0,00'):
        s = s[1:]
    return s
def sg(x, d=1):
    return ('+' if round(x, d) > 0 else '') + de(x, d)
def na(x, f=lambda v: de(v)):
    return 'k. A.' if x is None else f(x)

# ======================= Berechnungen =======================
bz, bz_vj = P['bauzins']['sep26'], P['bauzins']['sep25']
tilg = F['dtb']['tilgung']               # Ø anfängliche Tilgung laut Dr. Klein
annu = (bz + tilg) / 100
annu_vj = (bz_vj + tilg) / 100
darl = 300000
rate_now, rate_vj = darl * annu / 12, darl * annu_vj / 12
darl_gleich = rate_vj * 12 / annu
kaufkraft = (darl_gleich / darl - 1) * 100

# Leistbarkeit Median-Haushalt
ek_med = Z['einkommen']['median']
quote = 0.35
rate_med = ek_med * quote
darl_med = rate_med * 12 / annu
darl_med_vj = rate_med * 12 / annu_vj

# Flipper-Rechnung (Beispielannahmen, klar ausgewiesen)
FX = dict(kauf=200000, qm=70, san_qm=1000, monate=12, fk=0.80)
fx_san = FX['qm'] * FX['san_qm']
_EU = F['euribor']; _AUF = _EU['flipper_aufschlag']          # Flipper-Zins: 12-Monats-Euribor + Aufschlag
fk_zins = _EU['m12'] + _AUF[1]                                  # Rechnung mit 2,5 Prozentpunkten (vorsichtig)
fk_zins_lo = _EU['m12'] + _AUF[0]                               # Variante 2,0 Prozentpunkte
fk_zins_vj = _EU['m12_nov25'] + _AUF[1]
notar_pct = 1.5
def flip_cost(grest):
    nk = FX['kauf'] * (grest + notar_pct) / 100
    basis = FX['kauf'] + fx_san
    fk = basis * FX['fk']
    zins = fk * fk_zins / 100 * FX['monate'] / 12
    zins_vj = fk * fk_zins_vj / 100 * FX['monate'] / 12
    zins_lo = fk * fk_zins_lo / 100 * FX['monate'] / 12
    ek = basis - fk + nk
    return dict(nk=nk, fk=fk, zins=zins, zins_vj=zins_vj, zins_lo=zins_lo, ek=ek, total=FX['kauf'] + fx_san + nk + zins)
flip_by = flip_cost(F['grest']['Bayern'])
flip_nw = flip_cost(F['grest']['Nordrhein-Westfalen'])

# Käufer-Rechnung
KX = dict(preis=300000, bel=F['dtb']['beleihung'])
def buyer(grest):
    darl_k = KX['preis'] * KX['bel'] / 100
    nk = KX['preis'] * (grest + notar_pct) / 100
    ek = KX['preis'] - darl_k + nk
    return dict(darl=darl_k, nk=nk, ek=ek, rate=darl_k * annu / 12)
buy_by = buyer(F['grest']['Bayern'])
buy_nw = buyer(F['grest']['Nordrhein-Westfalen'])

# Städte
rows = []
for c, s in S.items():
    r = dict(c=c, **s)
    # Abschlag unsaniert ggü. Bestand gleicher Baujahre (1950 bis 1994), nur ab 50 Inseraten in der Stadt
    ok = s['n'] >= 50 and s.get('alt') and s.get('altsan')
    r['spread'] = (s['alt'] - s['altsan']) if ok else None
    r['abschlag'] = (s['altsan'] / s['alt'] - 1) * 100 if ok else None
    r['dyn'] = s['neu30'] / s['n'] * 100 if s.get('neu30') is not None and s['n'] else None
    r['gap'] = s['rend'] - bz
    r['spread_eur'] = s['rend'] - F['euribor']['m12']          # Bruttorendite minus 12-Monats-Euribor (Prozentpunkte)
    r['unter_pct'] = (s['unter_n'] / s['unter_basis'] * 100) if s.get('unter_basis') and s['unter_basis'] > 0 and s.get('unter_n', -1) >= 0 else None
    r['leist_qm'] = darl_med / s['qm']
    rows.append(r)
rows.sort(key=lambda r: -r['qm'])
# Vormonatsvergleich: automatisch, sobald ein älterer Snapshot existiert
_alle = sorted(x.name for x in (R / 'data' / 'snapshots').iterdir() if x.is_dir() and x.name < MONTH)
PREV = None
if _alle:
    PREV = {}
    for f in ['lev_sued', 'lev_west', 'lev_nord', 'lev_ost']:
        pp = R / 'data' / 'snapshots' / _alle[-1] / f'{f}.json'
        if pp.exists():
            PREV.update(json.load(open(pp)))
for r in rows:
    v = (PREV or {}).get(r['c'])
    r['d_qm'] = (r['qm'] / v['qm'] - 1) * 100 if v and v.get('qm') else None
    r['d_n'] = r['n'] - v['n'] if v and v.get('n') is not None else None
n_total = sum(r['n'] for r in rows)
robust = [r for r in rows if r['spread'] is not None and r['altsan_n'] >= 8 and r['alt_n'] >= 8]
top_spread = sorted(robust, key=lambda r: -r['spread'])
top_rend = sorted(rows, key=lambda r: -r['rend'])
over_mw = sum(1 for r in rows if r['disc'] < 0)
unter50 = sum(1 for r in rows if r['leist_qm'] < 50)
SHOW_TAGE = False   # start_date ist bei einem Teil der Quellen das Importdatum (Cluster 18.10.2026), Wert noch nicht belastbar
tage_rows = [r for r in rows if r.get('tage') is not None] if SHOW_TAGE else []

KPI = dict(kaufkraft=kaufkraft, rate_now=rate_now, rate_vj=rate_vj, darl_med=darl_med, flip_by=flip_by, flip_nw=flip_nw,
           buy_by=buy_by, buy_nw=buy_nw, n_total=n_total, staedte=len(rows))
json.dump(KPI, open(D/'kpi.json', 'w'), ensure_ascii=False, indent=1, default=float)

# ======================= Grafik-Bausteine =======================
def svg(w, h, inner):
    return f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Montserrat">{inner}</svg>'

def bars(items, unit=' %', dec=1, lab=230, w=640, rowh=26, signed=True, vmin=None, colors=None):
    vals = [v for _, v in items]
    lo = min(0, min(vals)) if vmin is None else vmin
    hi = max(0, max(vals))
    plot = w - lab - 90
    span = (hi - lo) or 1
    sc = lambda v: lab + (v - lo) / span * plot
    z = sc(0)
    h = rowh * len(items) + 8
    o = [f'<line x1="{z}" y1="0" x2="{z}" y2="{h-4}" stroke="{LINE}"/>']
    for i, (k, v) in enumerate(items):
        y = i * rowh + 4
        x0, x1 = sorted([z, sc(v)])
        col = (colors[i] if colors else (TD if v >= 0 else RED))
        o.append(f'<text x="{lab-12}" y="{y+rowh/2+4}" text-anchor="end" font-size="11" fill="{INK}">{k}</text>')
        o.append(f'<rect x="{x0}" y="{y+6}" width="{max(x1-x0,2)}" height="{rowh-12}" rx="3" fill="{col}"/>')
        txt = (sg(v, dec) if signed else de(v, dec)) + unit
        o.append(f'<text x="{max(x1, z)+8}" y="{y+rowh/2+4}" font-size="11" font-weight="700" fill="{INK}">{txt}</text>')
    return svg(w, h, ''.join(o))

def grouped(cats, a, b, la, lb, unit=' %', w=640, h=200, dec=2):
    lo, hi = min(0, min(a + b) * 1.25), max(0, max(a + b)) * 1.18
    l, bt, top = 40, 40, 30
    cw = (w - l - 10) / len(cats)
    Y = lambda v: top + (hi - v) / (hi - lo) * (h - bt - top)
    o = []
    for g in range(int(math.floor(lo)), int(hi) + 1):
        o.append(f'<line x1="{l}" x2="{w-10}" y1="{Y(g)}" y2="{Y(g)}" stroke="{LINE}"/><text x="{l-8}" y="{Y(g)+4}" font-size="10" text-anchor="end" fill="{MUT}">{de(g)}</text>')
    bw = cw * 0.28
    for i, c in enumerate(cats):
        cx = l + cw * i + cw / 2
        for j, (v, col) in enumerate([(a[i], '#9cc9cc'), (b[i], TD)]):
            x = cx - bw - 3 + j * (bw + 6)
            y0, y1 = sorted([Y(0), Y(v)])
            o.append(f'<rect x="{x}" y="{y0}" width="{bw}" height="{max(y1-y0,1)}" rx="3" fill="{col}"/>')
            o.append(f'<text x="{x+bw/2}" y="{(Y(v)-6) if v >= 0 else (Y(v)+12)}" font-size="10" font-weight="700" text-anchor="middle" fill="{INK}">{de(v,dec)}</text>')
        o.append(f'<text x="{cx}" y="{h-bt+18}" font-size="10.5" text-anchor="middle" fill="{INK}">{c}</text>')
    o.append(f'<rect x="{l}" y="4" width="12" height="12" rx="2" fill="#9cc9cc"/><text x="{l+18}" y="14" font-size="10.5" fill="{MUT}">{la}</text>')
    o.append(f'<rect x="{l+150}" y="4" width="12" height="12" rx="2" fill="{TD}"/><text x="{l+168}" y="14" font-size="10.5" fill="{MUT}">{lb}</text>')
    return svg(w, h, ''.join(o))

def nice_step(span, n=5):
    raw = span / n; mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag: return m * mag
    return 10 * mag
def auto_range(vals, pad=0.12):
    lo, hi = min(vals), max(vals); span = (hi - lo) or abs(hi) or 1
    st = nice_step(span)
    lo = math.floor((lo - span * pad) / st) * st; hi = math.ceil((hi + span * pad) / st) * st
    return lo, hi, st
def line_chart(pts, lo, hi, w=640, h=180, dec=2, unit=' %', step=0.2, lab=None):
    l, b, top = (lab or 46), 30, 26
    X = lambda i: l + 34 + i * (w - l - 70) / (len(pts) - 1)
    Y = lambda v: top + (hi - v) / (hi - lo) * (h - b - top)
    o = []
    g = lo
    while g <= hi + 1e-9:
        o.append(f'<line x1="{l}" x2="{w-10}" y1="{Y(g)}" y2="{Y(g)}" stroke="{LINE}"/><text x="{l-8}" y="{Y(g)+4}" font-size="10" text-anchor="end" fill="{MUT}">{de(g, 1 if step < 1 else 0)}</text>')
        g += step
    o.append('<path d="' + ' '.join(f"{'M' if i == 0 else 'L'}{X(i)},{Y(v)}" for i, (_, v) in enumerate(pts)) + f'" fill="none" stroke="{TD}" stroke-width="2.5"/>')
    for i, (k, v) in enumerate(pts):
        o.append(f'<circle cx="{X(i)}" cy="{Y(v)}" r="4.5" fill="{TD}"/>')
        o.append(f'<text x="{X(i)}" y="{Y(v)-12}" font-size="11" font-weight="700" text-anchor="middle" fill="{INK}">{de(v,dec)}{unit}</text>')
        o.append(f'<text x="{X(i)}" y="{h-8}" font-size="10.5" text-anchor="middle" fill="{MUT}">{k}</text>')
    return svg(w, h, ''.join(o))

GEO = json.load(open(R/'assets/germany.geojson'))
PADX = 70
RUHR = ['Duisburg', 'Essen', 'Gelsenkirchen', 'Bochum', 'Wuppertal']
def de_map(rows, key, fmt, legend_title, breaks, w=520):
    lat0 = math.radians(51.2)
    lon_min, lon_max, lat_min, lat_max = 5.6, 15.3, 47.1, 55.2
    sx = w / ((lon_max - lon_min) * math.cos(lat0))
    h = (lat_max - lat_min) * sx
    P2 = lambda lon, lat: ((lon - lon_min) * math.cos(lat0) * sx, (lat_max - lat) * sx)
    paths = []
    for poly in GEO['geometry']['coordinates']:
        ring = poly[0]
        pts = [P2(lo, la) for lo, la in ring]
        if len(pts) < 8:
            continue
        paths.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in pts) + 'Z')
    o = [f'<path d="{" ".join(paths)}" fill="#f3f8f8" stroke="#a9c5c7" stroke-width="1.2"/>']
    shades = ['#d4e9ea', '#9fcdd0', '#6fb2b7', '#3e7b80', '#234a4d']
    def col(v):
        for i, b in enumerate(breaks):
            if v < b:
                return shades[i]
        return shades[-1]
    placed = []
    dots = []
    for r in sorted(rows, key=lambda r: -r['n']):
        x, y = P2(r['lon'], r['lat'])
        rad = 4 + min(r['n'], 900) ** 0.5 * 0.28
        dots.append((x, y, rad, r))
    for x, y, rad, r in dots:
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{col(r[key])}" stroke="#fff" stroke-width="1.2"/>')
        placed.append((x - rad, y - rad, x + rad, y + rad))
    def hit(b):
        return any(not (b[2] < q[0] or b[0] > q[2] or b[3] < q[1] or b[1] > q[3]) for q in placed)
    ruhr = [(x, y, rad, r) for x, y, rad, r in dots if r['c'] in RUHR]
    if ruhr:
        cx = sum(d[0] for d in ruhr) / len(ruhr); cy = sum(d[1] for d in ruhr) / len(ruhr)
        o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="30" fill="none" stroke="#8aa9ab" stroke-width="0.8" stroke-dasharray="3 2"/>')
        bx, by = -PADX + 4, cy - 70
        o.append(f'<line x1="{cx-30:.1f}" y1="{cy:.1f}" x2="{bx+92:.1f}" y2="{by+8:.1f}" stroke="#8aa9ab" stroke-width="0.7"/>')
        o.append(f'<text x="{bx}" y="{by}" font-size="9" font-weight="700" fill="{INK}">Rhein-Ruhr</text>')
        for i, (_, _, _, rr) in enumerate(sorted(ruhr, key=lambda d: d[3]['c'])):
            o.append(f'<text x="{bx}" y="{by+13+i*12}" font-size="9" fill="{INK}">{rr["c"]} {fmt(rr[key])}</text>')
        placed.append((bx, by - 10, bx + 95, by + 13 + len(ruhr) * 12))
        placed.append((cx - 31, cy - 31, cx + 31, cy + 31))
    for x, y, rad, r in dots:
        if r['c'] in RUHR:
            continue
        txt = f"{r['c']} {fmt(r[key])}"
        tw = len(txt) * 5.3
        cands = []
        for dist in (rad + 4, rad + 16, rad + 30, rad + 46):
            for ux, uy in [(1, 0), (-1, 0), (0, -1), (0, 1), (0.8, -0.7), (0.8, 0.7), (-0.8, -0.7), (-0.8, 0.7)]:
                anc = 'start' if ux > 0.3 else ('end' if ux < -0.3 else 'middle')
                cands.append((ux * dist, uy * dist + (4 if uy == 0 else (0 if uy < 0 else 9)), anc, dist > rad + 5))
        for dx, dy, anc, lead in cands:
            if anc == 'start':
                b = (x + dx, y + dy - 9, x + dx + tw, y + dy + 2)
            elif anc == 'end':
                b = (x + dx - tw, y + dy - 9, x + dx, y + dy + 2)
            else:
                b = (x + dx - tw / 2, y + dy - 9, x + dx + tw / 2, y + dy + 2)
            if b[0] < -PADX or b[2] > w + PADX or hit(b):
                continue
            placed.append(b)
            if lead:
                ly = y + dy - 3
                lx = b[0] if anc == 'start' else (b[2] if anc == 'end' else x + dx)
                o.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{lx:.1f}" y2="{ly:.1f}" stroke="#8aa9ab" stroke-width="0.7"/>')
            o.append(f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" text-anchor="{anc}" font-size="9" fill="{INK}" stroke="#fff" stroke-width="2.5" paint-order="stroke">{txt}</text>')
            break
    lx, ly = 8, h - 26 - 18 * len(shades)
    o.append(f'<text x="{lx}" y="{ly}" font-size="10" font-weight="700" fill="{INK}">{legend_title}</text>')
    labs = [f'unter {fmt(breaks[0])}'] + [f'{fmt(breaks[i])} bis {fmt(breaks[i+1])}' for i in range(len(breaks) - 1)] + [f'ab {fmt(breaks[-1])}']
    for i, (s_, t) in enumerate(zip(shades, labs)):
        o.append(f'<circle cx="{lx+7}" cy="{ly+16+i*18}" r="6" fill="{s_}" stroke="#fff"/><text x="{lx+20}" y="{ly+20+i*18}" font-size="9.5" fill="{MUT}">{t}</text>')
    return f'<svg viewBox="{-PADX} 0 {w+2*PADX} {h+4}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Montserrat">' + ''.join(o) + '</svg>'

# ======================= HTML =======================
def font(wt):
    b = base64.b64encode((R/f'node_modules/@fontsource/montserrat/files/montserrat-latin-{wt}-normal.woff2').read_bytes()).decode()
    return f"@font-face{{font-family:Montserrat;font-weight:{wt};src:url(data:font/woff2;base64,{b}) format('woff2');}}"
LOGO_T = base64.b64encode((R/'assets/logo_teal.png').read_bytes()).decode()
LOGO_W = base64.b64encode((R/'assets/logo_white.png').read_bytes()).decode()

def kpi(v, l, s=''):
    return f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div><div class="s">{s}</div></div>'
def kpis(*k, cols=None):
    return f'<div class="kpis c{cols or len(k)}">{"".join(k)}</div><!--/kpis-->'
def note(t, title='Einordnung für Flipper'):
    return f'<div class="note avoid"><b>{title}:</b> {t}</div>'
def src(t):
    return f'<p class="src">{t}</p>'
def block(title, inner):
    return f'<div class="block avoid"><h3>{title}</h3>{inner}</div>'

SRC = []
def cite(name, detail, url):
    SRC.append((name, detail, url))

kurz_leverage = ''
if robust:
    _pos = [x for x in robust if x['spread'] > 0]
    _top = max(robust, key=lambda x: x['spread'])
    kurz_leverage += f"<li>In {len(_pos)} von {len(robust)} Städten mit genug Inseraten werden unsanierte Wohnungen der Baujahre 1950 bis 1994 günstiger angeboten als der Bestand gleicher Baujahre. Der größte Abschlag liegt in {_top['c']} bei {de(_top['spread'])} € je m².</li>"
if tage_rows:
    kurz_leverage += f"<li>Die Hälfte der Inserate ist je nach Stadt seit {de(min(r['tage'] for r in tage_rows))} bis {de(max(r['tage'] for r in tage_rows))} Tagen online. Am längsten stehen Inserate in {', '.join(f"{x['c']} ({de(x['tage'])} Tage)" for x in sorted(tage_rows, key=lambda x: -x['tage'])[:3])}.</li>"
_unter = sorted([r for r in rows if r['unter_pct'] is not None and (r.get('unter_basis') or 0) >= 50], key=lambda r: -r['unter_pct'])
unter_block = (block('Anteil der Angebote unter Leverage-Marktwert (Inserate mit Bewertung, ab 50 je Stadt)', bars([(r['c'], r['unter_pct']) for r in _unter[:10]] + [(r['c'], r['unter_pct']) for r in _unter[-6:]], ' %', dec=0, lab=200, signed=False, vmin=0, rowh=22))
               + src(f'Anteil der Inserate, deren Angebotspreis auf oder unter dem Leverage-Marktwert liegt. Oben die 10 Städte mit dem höchsten Anteil, unten die 6 mit dem niedrigsten. Über alle {len(rows)} Städte: {de(sum(r["unter_n"] for r in rows if r.get("unter_n", -1) >= 0) / max(1, sum(r["unter_basis"] for r in rows if r.get("unter_basis"))) * 100)} %.')) if _unter else ''
GX = json.load(open(D/'greix_staedte.json')) if (D/'greix_staedte.json').exists() else None
ZS = json.load(open(D/'zensus.json')) if (D/'zensus.json').exists() else None
greix_block = ''; alt_block = ''
if GX:
    cite('Kiel Institut für Weltwirtschaft', 'GREIX Q3 2026, Städtewerte (Transaktionspreise je m², hedonischer Index) aus der GREIX-Datenschnittstelle, abgerufen 09.11.2026', GX['url'])
    _gx = []
    for r in rows:
        g_ = GX['staedte'].get(r['c'])
        if g_ and g_['qm'] and g_['q'] in ('Q3 2026', 'Q2 2026'):
            r['greix_qm'] = g_['qm']; r['greix_q'] = g_['q']; r['greix_yoy'] = g_['yoy']
            r['gap_greix'] = (r['qm'] / g_['qm'] - 1) * 100
            _gx.append(r)
    _gx.sort(key=lambda r: -r['gap_greix'])
    if _gx:
        greix_block = (block('Angebotspreis (Leverage, Median) gegenüber Transaktionspreis (GREIX, Durchschnitt), Abweichung in %',
                             bars([(f"{r['c']} ({de(r['qm'])} vs. {de(r['greix_qm'])} €)", r['gap_greix']) for r in _gx], ' %', dec=0, lab=250, rowh=22))
                       + src('GREIX: Durchschnittspreis je m² aller notariell beurkundeten Wohnungskäufe (Neubau und Bestand), auf 100 € gerundet, Q3 2026 (München, Bonn: Q2 2026). Leverage: Median der aktiven Angebote im Stadtkreis. Positiver Wert: Angebote liegen über den zuletzt gezahlten Preisen. Nur Städte, für die GREIX aktuelle Werte liefert.'))
if ZS:
    cite('Statistische Ämter des Bundes und der Länder', 'Zensus 2022, Tabelle 3000G-1002, Gebäude mit Wohnraum nach Baujahr, Gemeindeebene', ZS['url'])
    for r in rows:
        r['vor1979'] = ZS['vor1979'].get(r['c'])
    _za = sorted([r for r in rows if r.get('vor1979') is not None], key=lambda r: -r['vor1979'])
    alt_block = (block('Anteil der Wohngebäude mit Baujahr bis 1979 (Zensus 2022), %', bars([(r['c'], r['vor1979']) for r in _za[:10]] + [(r['c'], r['vor1979']) for r in _za[-6:]], ' %', dec=0, lab=200, signed=False, vmin=0, rowh=22))
                 + src(f'Quelle: Zensus 2022, Stichtag 15.05.2022, Gebäude mit Wohnraum je Gemeinde. Oben die 10 ältesten Bestände, unten die 6 jüngsten. Gebäude bis 1979 fallen vor die erste Wärmeschutzverordnung und sind der typische Sanierungsbestand. Spanne über alle {len(_za)} Städte: {de(_za[-1]["vor1979"],1)} % ({_za[-1]["c"]}) bis {de(_za[0]["vor1979"],1)} % ({_za[0]["c"]}).'))
_sp = sorted(rows, key=lambda r: -r['spread_eur'])
spread_block = (block(f'Bruttorendite minus 12-Monats-Euribor ({de(F["euribor"]["m12"],2)} %), Prozentpunkte', bars([(r['c'], r['spread_eur']) for r in _sp[:10]] + [(r['c'], r['spread_eur']) for r in _sp[-6:]], ' Pp', dec=1, lab=200, rowh=22))
                + src(f'Median-Bruttorendite der Stadt abzüglich 12-Monats-Euribor. Unter 2,0 bis 2,5 Prozentpunkten trägt die Miete den Flipper-Zins nicht; Halten statt Verkaufen rechnet sich dann nicht. {sum(1 for r in rows if r["spread_eur"] < 2.5)} von {len(rows)} Städten liegen unter 2,5 Prozentpunkten.'))
unter_gesamt = sum(r["unter_n"] for r in rows if r.get("unter_n", -1) >= 0) / max(1, sum(r["unter_basis"] for r in rows if r.get("unter_basis"))) * 100
kurz_stimmung = ''
if (D/'stimmung.json').exists() and (D/'markt.json').exists():
    _st, _mk = json.load(open(D/'stimmung.json')), json.load(open(D/'markt.json'))
    kurz_stimmung = (f"<li>Die Stimmung dreht vor den Zahlen: {de(_st['bop_hh']['anteil_steigend']['wert'])} % der Haushalte erwarten steigende Preise (Juli: {de(_st['bop_hh']['anteil_steigend']['reihe'][0][1])} %), das Konsumklima liegt bei {sg(_st['konsumklima']['prognose']['wert'],1)} Punkten (Vorjahr {sg(_st['konsumklima']['prognose']['vorjahr'],1)}), {de(_st['ifo']['storno']['wert'],1)} % der Wohnungsbaufirmen melden Stornierungen (Vorjahr {de(_st['ifo']['storno']['vorjahr'],1)} %).</li>"
                     f"<li>Die Kaufnachfrage je Inserat ist seit Mai um {de(abs(_mk['is24']['nachfrage_kauf_de_pct']))} % gesunken, am stärksten unter 3.000 € je m² ({sg(_mk['is24']['nachfrage_segment']['unter 3.000 €/m²'],0)} %). Zwangsversteigerungen: {de(_mk['zwangsversteigerungen']['h1'][-1][1])} Termine im ersten Halbjahr 2026, {sg(_mk['zwangsversteigerungen']['h1_2026_yoy'])} %.</li>")
# ---------- Cover ----------
cover = f'''<section class="cover-page">
<div class="cover"><img class="clogo" src="data:image/png;base64,{LOGO_W}"/>
<div class="kicker">Ausgabe {AUSGABE_NR:02d} · Erscheint am {ERSCHEINT} · Datenstand {STAND}</div>
<h1>Immobilienhandel-Marktreport</h1><div class="sub">Fix-und-Flip · Berichtsmonat {BERICHT}</div>
<p class="lead">Zinsen, Finanzierung, Preise, Angebotsdaten aus {len(rows)} Städten, Baukosten, Zielgruppe und Demografie. Zusammengeführt aus {de(n_total)} aktiven Wohnungsinseraten der Leverage-Datenbank und über 60 amtlichen, institutionellen und Markt-Quellen.</p></div>
<h2 class="first">Die Lage in sechs Zahlen</h2>
{kpis(
 kpi(de(bz,2)+' %', 'Bauzins über 10 Jahre', f'Sep 2026, Vorjahr {de(bz_vj,2)} %'),
 kpi(de(F['euribor']['m12'],2)+' %', '12-Monats-Euribor', f'{F["euribor"]["datum"]}, Nov 2025 Ø {de(F["euribor"]["m12_nov25"],2)} %'),
 kpi(de(kaufkraft,1)+' %', 'Darlehensbudget Käufer', 'bei gleicher Rate wie vor 12 Monaten'),
 cols=3)}
{kpis(
 kpi(sg(P['greix']['etw_yoy'])+' %', 'Wohnungspreise ggü. Vorjahr', 'GREIX Q3 2026, nominal'),
 kpi(sg(G['mieten']['greix_yoy'])+' %', 'Angebotsmieten ggü. Vorjahr', 'GREIX Q3 2026'),
 kpi(sg(P['baupreise']['instand_yoy'])+' %', 'Instandhaltungspreise', 'Aug 2026 ggü. Vorjahr'),
 cols=3)}
<h2>Kurzfassung</h2>
<ul class="sum">
<li>Der Käufer am Ende hat weniger Budget. Bei gleicher Monatsrate wie vor einem Jahr finanziert ein Haushalt heute {de(abs(kaufkraft),1)} % weniger Darlehen. Ein Haushalt mit Medianeinkommen ({de(ek_med)} € netto) kommt bei 35 % Belastung auf rund {de(darl_med,-3)} € Darlehen, der durchschnittliche Baufinanzierungskredit liegt bei {de(F['dtb']['darlehen'],-3)} €.</li>
<li>Variable Wohnungsbaukredite kosten {de(F['mfi_wohnen']['sep26']['var'],2)} %, Kredite mit über 10 Jahren Bindung {de(F['mfi_wohnen']['sep26']['j10'],2)} %. Kurzfristiges Geld ist teurer als langfristiges.</li>
<li>Kaufpreise geben nach, Mieten steigen. Wohnungen sind nominal {de(abs(P['greix']['etw_yoy']),1)} % günstiger als vor einem Jahr, Angebotsmieten {de(G['mieten']['greix_yoy'],1)} % teurer. Das verbessert die Rendite für Kapitalanleger als Käufer.</li>
<li>Sanierung kostet {de(P['baupreise']['instand_yoy'],1)} % mehr. Gleichzeitig sinken die Wohnungspreise, die Marge hängt damit stärker am Einkaufspreis.</li>
{kurz_leverage}
<li>{de(unter_gesamt)} % der bewerteten Inserate in den {len(rows)} Städten sind auf oder unter Leverage-Marktwert angeboten, am häufigsten in {', '.join(f"{r['c']} ({de(r['unter_pct'])} %)" for r in _unter[:3])}. Die Bruttorendite liegt in {sum(1 for r in rows if r["spread_eur"] < 2.5)} von {len(rows)} Städten weniger als 2,5 Prozentpunkte über dem 12-Monats-Euribor.</li>
{kurz_stimmung}
<li>2025 wurde steuerlich Grundvermögen von {de(G['erbe']['grundvermoegen'],1)} Mrd. € vererbt oder verschenkt, {de(G['erbe']['grund_yoy'],1)} % mehr als im Vorjahr. Bis 2039 erreichen {de(G['boomer']['erwerbspersonen_rente_bis_2039'],1)} Mio. Erwerbspersonen das Rentenalter.</li>
</ul>
<div class="toc avoid"><h3>Inhalt</h3><ol>__TOC__</ol></div>
</section>'''

# ---------- 1 Zinsen ----------
zins_verlauf = ''; euribor_verlauf = ''
if BBK:
    _pts = [(mlabel(t), v) for t, v in BBK['reihen']['j10']]
    _lo = math.floor(min(v for _, v in _pts) * 5) / 5 - 0.2; _hi = math.ceil(max(v for _, v in _pts) * 5) / 5 + 0.2
    zins_verlauf = block(f'Bauzins über 10 Jahre, letzte {len(_pts)} Monate', line_chart(_pts, _lo, _hi, dec=2)) + src('Quelle: Deutsche Bundesbank, MFI-Zinsstatistik, Zeitreihe ' + BBK['reihen_id_j10'] + ', Monatswerte.')
    if 'eur12' in BBK['reihen']:
        _ep = [(mlabel(t), v) for t, v in BBK['reihen']['eur12']]
        _lo = math.floor(min(v for _, v in _ep) * 5) / 5 - 0.2; _hi = math.ceil(max(v for _, v in _ep) * 5) / 5 + 0.2
        euribor_verlauf = block(f'12-Monats-Euribor, Monatsdurchschnitte, letzte {len(_ep)} Monate', line_chart(_ep, _lo, _hi, dec=2)) + src('Quelle: Deutsche Bundesbank, Geldmarktsätze (EMMI), Zeitreihe ' + BBK['reihen_id_eur12'] + '.')
EU = F['euribor']
fz = [EU['m12'] + a for a in EU['flipper_aufschlag']]
fz_vj = [EU['m12_nov25'] + a for a in EU['flipper_aufschlag']]
mw, mv = F['mfi_wohnen']['sep26'], F['mfi_wohnen']['sep25']
cite('Deutsche Bundesbank', 'MFI-Zinsstatistik, Wohnungsbaukredite an private Haushalte nach Zinsbindung, Stand 02.11.2026', F['mfi_wohnen']['url'])
cite('Deutsche Bundesbank', 'MFI-Zinsstatistik, Kredite an nichtfinanzielle Kapitalgesellschaften, Stand 02.11.2026', F['mfi_unternehmen']['url'])
cite('Deutsche Bundesbank', 'Geldmarktsätze, Euribor (Quelle EMMI), Tageswerte 05.11.2026 und Monatsdurchschnitte', F['euribor']['url'])
cite('Europäische Zentralbank', 'Geldpolitische Beschlüsse vom 29.10.2026', P['ezb']['url'])
s1 = f'''<section class="sec brk"><h2>§ · Zinsen und Finanzierungsumfeld</h2>
<p class="intro">Variable Zinsen bestimmen die Kosten der Projektfinanzierung, Zinsen mit 10 Jahren Bindung das Budget der Käuferinnen und Käufer.</p>
{kpis(kpi(de(bz,2)+' %','Bauzins über 10 Jahre','Sep 2026, Bundesbank'),
      kpi(de(mw['var'],2)+' %','Wohnungsbaukredit variabel','bis 1 Jahr Zinsbindung, Sep 2026'),
      kpi(de(F['mfi_unternehmen']['bis1mio_var_sep26'],2)+' %','Unternehmenskredit variabel','bis 1 Mio. €, Sep 2026'), cols=3)}
{kpis(kpi(de(EU['m12'],2)+' %','12-Monats-Euribor','Referenz für variable Flipper-Darlehen, '+EU['datum']),
      kpi(de(fz[0],2)+' %','Flipper-Zins bei 2,0 % Aufschlag','12-Monats-Euribor + 2,0 Prozentpunkte'),
      kpi(de(fz[1],2)+' %','Flipper-Zins bei 2,5 % Aufschlag','12-Monats-Euribor + 2,5 Prozentpunkte'), cols=3)}
{kpis(kpi(de(EU['m3'],2)+' %','3-Monats-Euribor','Tageswert '+EU['datum']),
      kpi(de(EU['m6'],2)+' %','6-Monats-Euribor','Tageswert '+EU['datum']),
      kpi(de(P['ezb']['einlage'],2)+' %','EZB-Einlagesatz','zuletzt am 29.10. unverändert'), cols=3)}
{euribor_verlauf}
{block('Flipper-Zins (Rechenbeispiel): 12-Monats-Euribor plus Bankaufschlag', f'<p>Variable Projektfinanzierungen für Fix-und-Flip-Vorhaben werden in der Praxis am 12-Monats-Euribor ausgerichtet, die Bank schlägt je nach Bonität, Eigenkapital und Objekt meist 2,0 bis 2,5 Prozentpunkte auf. Beim Stand vom {EU["datum"]} ergibt das {de(fz[0],2)} % bis {de(fz[1],2)} % Zins. Vor einem Jahr (Monatsdurchschnitt November 2025: {de(EU["m12_nov25"],2)} %) lag dieselbe Rechnung bei {de(fz_vj[0],2)} % bis {de(fz_vj[1],2)} %. Je 100.000 € Fremdkapital und Monat Haltedauer kostet das heute {de(round(fz[0]*1000/12))} € bis {de(round(fz[1]*1000/12))} € Zins.</p>')}
{src('Quelle: Deutsche Bundesbank, Geldmarktsätze (Euribor, Quelle EMMI). Aufschlag 2,0 bis 2,5 Prozentpunkte: Erfahrungswert Team Flippɘr aus Finanzierungen, kein Marktdurchschnitt. Das konkrete Angebot der Bank weicht ab.')}
{block('Effektivzins Wohnungsbaukredite nach Zinsbindung, Sep 2025 und Sep 2026', grouped(['variabel bis 1 J.','1 bis 5 J.','5 bis 10 J.','über 10 J.'],[mv['var'],mv['j1_5'],mv['j5_10'],mv['j10']],[mw['var'],mw['j1_5'],mw['j5_10'],mw['j10']],'September 2025','September 2026'))}
{src('Quelle: Deutsche Bundesbank, MFI-Zinsstatistik, Neugeschäft, Effektivzinssatz.')}
{zins_verlauf}
{note(f'Der 12-Monats-Euribor, Referenz für variable Flipper-Darlehen, liegt bei {de(EU["m12"],2)} % nach {de(EU["m12_nov25"],2)} % im Durchschnitt November 2025. Das sind {de(EU["m12"]-EU["m12_nov25"],2)} Prozentpunkte mehr. Der 3-Monats-Euribor steht bei {de(EU["m3"],2)} % (November 2025 Ø {de(EU["m3_nov25"],2)} %). Die EZB hat den Einlagesatz am 10.09.2026 auf {de(P["ezb"]["einlage"],2)} % erhöht. Variable Wohnungsbaukredite sind mit {de(mw["var"],2)} % teurer als Kredite mit 5 bis 10 Jahren Bindung ({de(mw["j5_10"],2)} %).')}
{block('Kreditvergabe der Banken (Bank Lending Survey, Q3 2026)', f'<p>Die Banken haben ihre Kreditstandards für private Wohnungsbaukredite im dritten Quartal leicht gelockert (Nettoanteil {de(F["bls"]["standards_q3"])} %, nach {sg(F["bls"]["standards_q2"],0)} % im Vorquartal). Die Nachfrage ist das zweite Quartal in Folge deutlich gesunken, die Ablehnungsraten sind weiter gestiegen. Für das vierte Quartal erwarten die Banken unveränderte Standards und einen weiter sinkenden Finanzierungsbedarf.</p>')}
{src('Quelle: Deutsche Bundesbank, Bank Lending Survey, veröffentlicht 27.10.2026.')}
</section>'''
cite('Deutsche Bundesbank', 'Bank Lending Survey Deutschland, Oktober-Ergebnisse, 27.10.2026', F['bls']['url'])

# ---------- 2 Zwei Seiten ----------
cite('Dr. Klein Privatkunden AG', 'Trendindikator Baufinanzierung, 2. Tertial 2026, 16.09.2026', F['dtb']['url'])
cite('Verbraucherzentrale Bundesverband', 'Notar- und Grundbuchkosten beim Immobilienkauf', F['notar']['url'])
def ftab(a, b, la, lb):
    rws = [('Kaufpreis', FX['kauf'], FX['kauf']), (f'Sanierung ({FX["qm"]} m² × {de(FX["san_qm"])} €)', fx_san, fx_san),
           ('Kaufnebenkosten (Grunderwerbsteuer + 1,5 % Notar/Grundbuch)', a['nk'], b['nk']),
           (f'Fremdkapital ({de(FX["fk"]*100)} % auf Kauf + Sanierung)', a['fk'], b['fk']),
           (f'Zinskosten {FX["monate"]} Monate bei {de(fk_zins,2)} % (Euribor 12 M + 2,5 Pp)', a['zins'], b['zins']),
           (f'Zinskosten bei {de(fk_zins_lo,2)} % (Euribor 12 M + 2,0 Pp)', a['zins_lo'], b['zins_lo']),
           (f'Zinskosten vor einem Jahr ({de(fk_zins_vj,2)} %, Euribor Nov 2025 + 2,5 Pp)', a['zins_vj'], b['zins_vj']),
           ('Eigenkapitalbedarf inkl. Nebenkosten', a['ek'], b['ek']),
           ('Gesamtkosten bis Verkauf (ohne Makler, Gebühren, Steuern)', a['total'], b['total'])]
    body = ''.join(f'<tr><td class="c">{k}</td><td>{de(x)} €</td><td>{de(y)} €</td></tr>' for k, x, y in rws)
    return f'<table class="t"><thead><tr><th>Position</th><th>{la}</th><th>{lb}</th></tr></thead><tbody>{body}</tbody></table>'
def btab(a, b, la, lb):
    rws = [('Kaufpreis', KX['preis'], KX['preis']), (f'Darlehen ({de(KX["bel"],1)} % Beleihung)', a['darl'], b['darl']),
           ('Kaufnebenkosten (Grunderwerbsteuer + 1,5 % Notar/Grundbuch)', a['nk'], b['nk']),
           ('Eigenkapitalbedarf', a['ek'], b['ek']),
           (f'Monatsrate ({de(bz,2)} % Zins, {de(tilg,2)} % Tilgung)', a['rate'], b['rate'])]
    body = ''.join(f'<tr><td class="c">{k}</td><td>{de(x)} €</td><td>{de(y)} €</td></tr>' for k, x, y in rws)
    return f'<table class="t"><thead><tr><th>Position</th><th>{la}</th><th>{lb}</th></tr></thead><tbody>{body}</tbody></table>'
s2 = f'''<section class="sec"><h2>§ · Zwei Seiten der Finanzierung: Flipper und Käufer</h2>
<p class="intro">Seite A rechnet eine Projektfinanzierung mit variablem Flipper-Darlehen (12-Monats-Euribor plus Aufschlag), Seite B eine Eigennutzer-Finanzierung mit 10 Jahren Zinsbindung. Die Annahmen stehen unter der jeweiligen Tabelle.</p>
{block('Seite A: Was der Flipper finanziert (Rechenbeispiel Wohnung)', ftab(flip_by, flip_nw, 'Bayern (3,5 % GrESt)', 'NRW (6,5 % GrESt)'))}
{src(f'Annahmen: Kaufpreis {de(FX["kauf"])} €, {FX["qm"]} m², Sanierung {de(FX["san_qm"])} € je m², Haltedauer {FX["monate"]} Monate, Zins = 12-Monats-Euribor ({de(_EU["m12"],2)} % am {_EU["datum"]}, Bundesbank) plus 2,5 Prozentpunkte Bankaufschlag (Erfahrungswert Team Flippɘr, Variante 2,0 Prozentpunkte als eigene Zeile). Vorjahr: Monatsdurchschnitt November 2025 plus 2,5 Prozentpunkte. Der Bundesbank-Durchschnitt für variable Unternehmenskredite bis 1 Mio. € liegt bei {de(F["mfi_unternehmen"]["bis1mio_var_sep26"],2)} % (Sep 2026) und ist für Projektfinanzierungen meist nicht erreichbar.')}
{note(f'Die Zinskosten des Projekts sind binnen eines Jahres um rund {de(flip_by["zins"]-flip_by["zins_vj"],-1)} € gestiegen. Jeder zusätzliche Monat Haltedauer kostet im Beispiel rund {de(flip_by["zins"]/FX["monate"])} €. Zwischen Bayern und NRW liegen allein bei der Grunderwerbsteuer {de(flip_nw["nk"]-flip_by["nk"])} € Unterschied, die vor Verkauf als Eigenkapital gebunden sind.')}
<div class="avoid">{block('Seite B: Was der Käufer finanziert (Rechenbeispiel Eigennutzer)', btab(buy_by, buy_nw, 'Bayern', 'NRW'))}
{src(f'Annahmen: Kaufpreis {de(KX["preis"])} €, Beleihungsauslauf {de(KX["bel"],1)} % und Tilgung {de(tilg,2)} % entsprechen dem Durchschnitt laut Dr. Klein Trendindikator (2. Tertial 2026), Zins laut Bundesbank (über 10 Jahre, Sep 2026). Makler nicht berücksichtigt.')}
{kpis(kpi(de(F['dtb']['darlehen'])+' €','Ø Darlehenshöhe','Dr. Klein, Mai bis Aug 2026'),
      kpi(de(F['dtb']['beleihung'],1)+' %','Ø Beleihungsauslauf','Dr. Klein, Mai bis Aug 2026'),
      kpi(de(F['dtb']['tilgung'],2)+' %','Ø anfängliche Tilgung', F['dtb']['zinsbindung']+' Zinsbindung'), cols=3)}</div>
{block('Was sich verändert hat', f'<table class="t"><thead><tr><th></th><th>Sep 2025</th><th>Sep 2026</th><th>Differenz</th></tr></thead><tbody><tr><td class="c">Monatsrate für {de(darl)} € Darlehen</td><td>{de(rate_vj)} €</td><td>{de(rate_now)} €</td><td class="b neg">{sg(rate_now-rate_vj,0)} €</td></tr><tr><td class="c">Darlehen bei Rate von {de(rate_vj)} €</td><td>{de(darl)} €</td><td>{de(darl_gleich)} €</td><td class="b neg">{sg(darl_gleich-darl,0)} €</td></tr></tbody></table>')}
{note(f'Ein Käufer braucht im Beispiel {de(buy_by["ek"])} € (Bayern) bis {de(buy_nw["ek"])} € (NRW) eigenes Geld. Wer heute dieselbe Rate wie vor einem Jahr tragen kann, bekommt {de(abs(kaufkraft),1)} % weniger Darlehen. Vergleichspreise aus 2025 überschätzen deshalb das heutige Käuferbudget.')}
</section>'''

# ---------- 3 Nebenkosten / Förderung ----------
cite('ImmoScout24', 'Medieninformation Grunderwerbsteuer im Bundesländervergleich, 07.05.2026', F['grest']['url'])
cite('KfW', 'Merkblatt Wohneigentum für Familien Bestandserwerb (308), Stand 08/2026', F['kfw308']['url'])
cite('KfW', 'Merkblatt BEG Wohngebäude Kredit (261), Stand 09/2026', F['kfw261']['url'])
gr = sorted([(k, v) for k, v in F['grest'].items() if k not in ('quelle', 'url')], key=lambda x: -x[1])
s3 = f'''<section class="sec"><h2>§ · Kaufnebenkosten und Förderung</h2>
{block('Grunderwerbsteuer nach Bundesland, 2026', bars(gr, ' %', dec=1, signed=False, lab=200, rowh=26))}
{src('Quelle: ImmoScout24, Medieninformation vom 07.05.2026. Notar und Grundbuch zusätzlich rund 1 bis 1,5 % des Kaufpreises (Verbraucherzentrale).')}
{note(f'Beim Flip fällt die Grunderwerbsteuer zweimal an, beim eigenen Einkauf und beim Käufer, dessen Budget sie schmälert. Auf {de(FX["kauf"])} € Kaufpreis sind das zwischen {de(FX["kauf"]*gr[-1][1]/100)} € ({gr[-1][0]}) und {de(FX["kauf"]*gr[0][1]/100)} € ({", ".join(k for k,v in gr if v==gr[0][1])}).')}
{block('KfW-Förderung für Käufer von Bestandsimmobilien', f"""<table class="t"><tbody>
<tr><td class="c">Wohneigentum für Familien, Bestandserwerb (308, „Jung kauft Alt“)</td><td>Kredit {F['kfw308']['betrag']}; Einkommensgrenze {F['kfw308']['einkommen']}; nur für Gebäude der Energieklasse {F['kfw308']['energieklasse']}; Sanierung auf {F['kfw308']['sanierung']}.</td></tr>
<tr><td class="c">BEG Wohngebäude Kredit (261)</td><td>Kredit {F['kfw261']['betrag']}; {F['kfw261']['zuschuss']}.</td></tr></tbody></table>""")}
{src('Quelle: KfW Merkblätter 308 (Stand 08/2026) und 261 (Stand 09/2026). Zinssätze tagesaktuell auf kfw.de, hier nicht ausgewiesen.')}
{note('Familien mit KfW 308 suchen gezielt Häuser der Energieklassen F bis H und konkurrieren damit beim Einkauf unsanierter Objekte mit Flippern. Gleichzeitig ist ein energetisch sanierter Flip für diese Käufergruppe nicht förderfähig. Wer an Familien verkauft, sollte das in der Objektauswahl berücksichtigen.')}
</section>'''

# ---------- 4 Preise & Mieten ----------
cite('Kiel Institut für Weltwirtschaft', 'GREIX Kaufpreisindex Q3 2026, 05.11.2026', P['greix']['url'])
cite('Kiel Institut für Weltwirtschaft (über epd)', 'GREIX Mietpreisindex Q3 2026, 15.10.2026', G['mieten']['greix_url'])
cite('Europace AG', 'EPX 9/26, 08.10.2026', P['epx']['url'])
cite('Statistisches Bundesamt', 'Häuserpreisindex Q2 2026, PM Nr. 336 vom 24.09.2026', P['hpi']['url'])
cite('Statistisches Bundesamt', 'Verbraucherpreisindex September 2026, PM Nr. 364', G['mieten']['vpi_url'])
hpi = P['hpi']['etw_yoy']
s4 = f'''<section class="sec"><h2>§ · Preise und Mieten</h2>
<p class="intro">Drei Kaufpreisindizes mit unterschiedlicher Methode (Notarverträge, Finanzierungsfälle, amtliche Transaktionsdaten) und zwei Mietindikatoren.</p>
{kpis(kpi(sg(P['greix']['etw_qoq'])+' %','GREIX ETW ggü. Vorquartal','Q3 2026, nominal'),
      kpi(sg(P['greix']['etw_yoy'])+' %','GREIX ETW ggü. Vorjahr',f'real {sg(P["greix"]["etw_real_yoy"])} %'),
      kpi(sg(P['epx']['etw_yoy'],1)+' %','Europace ETW ggü. Vorjahr','Sep 2026'), cols=3)}
{kpis(kpi(sg(P['epx']['neubau_yoy'],1)+' %','Europace Neubauhäuser','Sep 2026 ggü. Vorjahr'),
      kpi(sg(G['mieten']['greix_yoy'])+' %','Angebotsmieten (GREIX)','Q3 2026 ggü. Vorjahr'),
      kpi(sg(G['mieten']['vpi_nettokalt_sep'])+' %','Nettokaltmieten (VPI)','Sep 2026 ggü. Vorjahr'), cols=3)}
{block('Eigentumswohnungen nach Großstadt, Veränderung zum Vorquartal (GREIX Q3 2026)', bars(list(P['greix']['staedte_qoq'].items())))}
{src('Quelle: Kiel Institut, GREIX. Hamburg und München in der Veröffentlichung nicht separat ausgewiesen.')}
{block('Eigentumswohnungen nach Kreistyp, Veränderung zum Vorjahresquartal (Destatis Q2 2026)', bars(list(hpi.items()), lab=300))}
{src('Quelle: Destatis, Häuserpreisindex, Pressemitteilung Nr. 336 vom 24.09.2026.')}
{block('Angebotsmieten nach Großstadt, Veränderung zum Vorjahr (GREIX Q3 2026)', bars(sorted(G['mieten']['staedte'].items(), key=lambda x: -x[1])))}
{src('Quelle: GREIX-Mietpreisindex, Kiel Institut, Meldung vom 15.10.2026, abgerufen über epd. Angebotsmieten, keine Bestandsmieten.')}
{note(f'Wohnungen nominal {sg(P["greix"]["etw_yoy"])} %, Angebotsmieten {sg(G["mieten"]["greix_yoy"])} %. Bei sinkenden Preisen und steigenden Mieten steigt die rechnerische Bruttorendite für Kapitalanleger. Die stärksten Mietanstiege meldet GREIX für {", ".join(f"{k} ({sg(v)} %)" for k, v in sorted(G["mieten"]["staedte"].items(), key=lambda x: -x[1])[:3])}. Kreisfreie Großstädte außerhalb der Metropolen legen bei Wohnungspreisen zu ({sg(hpi["Kreisfreie Großstädte außerhalb der Metropolen"])} %), dicht besiedelte ländliche Kreise verlieren ({sg(hpi["Dicht besiedelte ländliche Kreise"])} %).')}
</section>'''


# ---------- Stimmung und Erwartung ----------
ST = json.load(open(D/'stimmung.json')) if (D/'stimmung.json').exists() else None
s_stimmung = ''
if ST:
    _b, _i, _k, _z, _e, _u = ST['bop_hh'], ST['ifo'], ST['konsumklima'], ST['zinserwartung'], ST['ezb_ces'], ST['umfragen']
    cite('Deutsche Bundesbank', 'Studie zu Erwartungen von Privatpersonen (BOP-HH), Immobilienpreiserwartungen September 2026, veröffentlicht 13.10.2026', _b['url'])
    cite('ifo Institut', 'Konjunkturumfrage Wohnungsbau September 2026 (16.10.2026), Werte wiedergegeben im SHK-Journal; Reihe aus Architekturblatt, cash-online, Börsen-Zeitung, DHZ', _i['url'])
    cite('NIM Nürnberg Institut für Marktentscheidungen', 'Konsumklima powered by GfK, Pressemitteilung vom 28.10.2026', _k['url'])
    cite('Interhyp AG', 'Zins-Update Oktober 2026 mit Bankenpanel, 15.10.2026; Vorjahrespanel November 2025 via cash-online', _z['url'])
    cite('Europäische Zentralbank', 'Consumer Expectations Survey September 2026, Pressemitteilung vom 23.10.2026', _e['url'])
    cite('Interhyp AG', 'Wohntraumstudie 2026, 21.10.2026', _u['interhyp_mieter_wunsch']['url'])
    cite('Interhyp AG', 'Leistbarkeitsstudie 2026, 10.06.2026', _u['interhyp_leistbarkeit']['url'])
    cite('Postbank / YouGov', 'Mieterumfrage Juli 2026, wiedergegeben bei fundresearch.de (dpa), 27.07.2026', _u['postbank_mieter_wunsch']['url'])
    cite('DSGV', 'Vermögensbarometer 2026, wiedergegeben bei fundresearch.de (dpa), 27.10.2026', _u['dsgv']['url'])
    _ip = [(mlabel(t), v) for t, v in _i['klima']['reihe']]; _lo, _hi, _st = auto_range([v for _, v in _ip])
    _kp = [(mlabel(t), v) for t, v in _k['anschaffung']['reihe']]; _lo2, _hi2, _st2 = auto_range([v for _, v in _kp])
    _zb = [('Nächste 1 bis 2 Monate gleichbleibend', _z['kurz']['gleich']), ('Nächste 1 bis 2 Monate fallend', _z['kurz']['fallend']), ('Nächste 1 bis 2 Monate steigend', _z['kurz']['steigend']),
           ('Langfristig fallend', _z['lang']['fallend']), ('Langfristig steigend', _z['lang']['steigend']), ('Vorjahrespanel, Erwartung für 2026 steigend', _z['lang_vorjahr']['steigend'])]
    s_stimmung = f'''<section class="sec"><h2>§ · Stimmung und Erwartung</h2>
<p class="intro">Umfragen laufen den amtlichen Zahlen um Monate voraus. Haushalte, Baufirmen und Banken sagen hier, womit sie rechnen.</p>
{kpis(kpi(sg(_b['preiserwartung_12m_mittel']['wert'])+' %','Erwartete Immobilienpreise in 12 Monaten',f'Haushalte, Mittelwert, Sep 2026 (Aug: {sg(_b["preiserwartung_12m_mittel"]["vormonat"])} %)'),
      kpi(de(_b['anteil_steigend']['wert'])+' %','Haushalte erwarten steigende Preise',f'Sep 2026, Juli: {de(_b["anteil_steigend"]["reihe"][0][1])} %. Fallend: {de(_b["anteil_fallend"]["wert"])} %'),
      kpi(sg(_e['hauspreis_12m']['wert'])+' %','Hauspreiserwartung Euroraum',f'EZB-Umfrage Sep 2026, Vorjahr {sg(_e["hauspreis_12m"]["vorjahr"])} %'), cols=3)}
{kpis(kpi(sg(_i['klima']['wert'],1),'ifo Geschäftsklima Wohnungsbau',f'Saldo Sep 2026, Vorjahr {sg(_i["klima"]["vorjahr"],1)}'),
      kpi(de(_i['storno']['wert'],1)+' %','Baufirmen mit Stornierungen',f'Wohnungsbau Sep 2026, Vorjahr {de(_i["storno"]["vorjahr"],1)} %'),
      kpi(de(_i['auftragsmangel']['wert'],1)+' %','Baufirmen mit Auftragsmangel',f'Wohnungsbau Sep 2026, Vorjahr {de(_i["auftragsmangel"]["vorjahr"],1)} %'), cols=3)}
{kpis(kpi(sg(_k['prognose']['wert'],1),'Konsumklima (Prognose Nov 2026)',f'Vorjahr {sg(_k["prognose"]["vorjahr"],1)} Punkte'),
      kpi(sg(_k['anschaffung']['wert'],1),'Anschaffungsneigung Okt 2026',f'Vorjahr {sg(_k["anschaffung"]["vorjahr"],1)} Punkte'),
      kpi(sg(_k['einkommen']['wert'],1),'Einkommenserwartung Okt 2026',f'Vorjahr {sg(_k["einkommen"]["vorjahr"],1)} Punkte'), cols=3)}
{block(f'ifo Geschäftsklima Wohnungsbau, Saldo, letzte {len(_ip)} Monate', line_chart(_ip, _lo, _hi, dec=1, unit='', step=_st))}
{src('Quelle: Konjunkturumfragen des ifo Instituts. Saldo aus positiven und negativen Antworten zu Lage und Erwartung. Oktoberwert erscheint Mitte November.')}
{block(f'Anschaffungsneigung der Verbraucher, Punkte, letzte {len(_kp)} Monate', line_chart(_kp, _lo2, _hi2, dec=1, unit='', step=_st2))}
{src('Quelle: NIM Konsumklima powered by GfK, rund 2.000 Interviews je Monat.')}
{block('Zinserwartung der Banken (Interhyp-Bankenpanel, Anteil der Institute in %)', bars(_zb, ' %', dec=0, lab=300, signed=False, vmin=0))}
{src(f'Quelle: Interhyp Zins-Update Oktober 2026. Bauzins 10 Jahre laut Interhyp rund {de(_z["bauzins10"],1)} %. Vorjahr: Interhyp-Panel November 2025, Erwartung für 2026 (60 % steigend, 20 % gleich, 20 % fallend).')}
{block('Wunsch nach Wohneigentum und Leistbarkeit (Umfragen 2026)', f'<table class="t sm"><thead><tr><th>Kennzahl</th><th>Wert</th><th>Erhebung</th></tr></thead><tbody>'
 f'<tr><td class="c">Mieterinnen und Mieter mit Wunsch nach Wohneigentum</td><td class="b">{de(_u["interhyp_mieter_wunsch"]["wert"])} %</td><td>Interhyp Wohntraumstudie, {_u["interhyp_mieter_wunsch"]["zeitraum"]}</td></tr>'
 f'<tr><td class="c">Davon 23- bis 30-Jährige mit Kaufinteresse</td><td class="b">80 %</td><td>Interhyp Wohntraumstudie 2026</td></tr>'
 f'<tr><td class="c">Mieter, die lieber im Eigentum wohnen würden</td><td class="b">{de(_u["postbank_mieter_wunsch"]["wert"],1)} %</td><td>Postbank/YouGov, {_u["postbank_mieter_wunsch"]["zeitraum"]}</td></tr>'
 f'<tr><td class="c">Sehen Eigentum am ehesten über Erbschaft erreichbar</td><td class="b">45,8 %</td><td>Postbank/YouGov, Juli 2026</td></tr>'
 f'<tr><td class="c">Sehen Immobilien in der Wunschregion als kaum leistbar</td><td class="b">{de(_u["interhyp_leistbarkeit"]["wert"])} %</td><td>Interhyp Leistbarkeitsstudie, {_u["interhyp_leistbarkeit"]["zeitraum"]} (2025: {de(_u["interhyp_leistbarkeit"]["vorjahr"])} %)</td></tr>'
 f'<tr><td class="c">Halten den Markt für überdreht</td><td class="b">39 %</td><td>Interhyp Leistbarkeitsstudie 2026 (2025: 35 %)</td></tr>'
 f'<tr><td class="c">Eigentümer, die mit dem Kauf zufrieden sind</td><td class="b">97 %</td><td>Interhyp Wohntraumstudie 2026</td></tr>'
 f'<tr><td class="c">Besitzen Aktien oder Wertpapiere</td><td class="b">{de(_u["dsgv"]["aktien"])} %</td><td>DSGV Vermögensbarometer 2026, über 4.800 Befragte</td></tr></tbody></table>')}
{note(f'{de(_b["anteil_steigend"]["wert"])} % der Haushalte erwarten steigende Preise, im Juli waren es {de(_b["anteil_steigend"]["reihe"][0][1])} %. Die Baufirmen melden mit {de(_i["storno"]["wert"],1)} % so viele Stornierungen wie seit Beginn der Reihe nicht (Vorjahr {de(_i["storno"]["vorjahr"],1)} %), das Klima im Wohnungsbau liegt mit {sg(_i["klima"]["wert"],1)} unter dem Vorjahr ({sg(_i["klima"]["vorjahr"],1)}). Konsumklima und Einkommenserwartung sind binnen eines Jahres von {sg(_k["prognose"]["vorjahr"],1)} auf {sg(_k["prognose"]["wert"],1)} und von {sg(_k["einkommen"]["vorjahr"],1)} auf {sg(_k["einkommen"]["wert"],1)} Punkte gefallen. {de(_u["interhyp_mieter_wunsch"]["wert"])} % der Mieterinnen und Mieter wollen Eigentum, {de(_u["interhyp_leistbarkeit"]["wert"])} % halten es in ihrer Region für kaum leistbar: Die Nachfrage ist da, das Budget fehlt. 80 % der Banken im Interhyp-Panel erwarten kurzfristig stabile Zinsen, langfristig rechnen 60 % mit fallenden.')}
</section>'''

# ---------- 5 Angebotsmarkt ----------
cite('Leverage Immo GmbH', f'Eigene Auswertung von {de(n_total)} aktiven Wohnungsinseraten in {len(rows)} Städten, Abruf 07.11.2026', 'https://leverage.immo')
qm_breaks = [2500, 3500, 4500, 6000]
rend_breaks = [4.0, 4.5, 5.0, 6.0]
def city_table(rs):
    body = ''
    for r in rs:
        klein = r['n'] < 50
        def grp(v, n):
            if klein:
                return 'k. A.'
            return na(v, lambda x: de(x)+' €') + f'<span class="r">n={n}{" ⚠" if (v is not None and n < 10) else ""}</span>'
        body += (f'<tr><td class="c">{r["c"]}<span class="r">{r["r"]} km</span></td><td>{de(r["n"])}</td><td class="b">{de(r["qm"])} €</td>'
                 f'<td>{grp(r.get("altsan"), r.get("altsan_n", 0))}</td><td>{grp(r.get("alt"), r.get("alt_n", 0))}</td>'
                 f'<td class="b">{na(r["spread"], lambda v: de(v)+" €") if not klein else "k. A."}</td><td>{de(r["rend"],1)} %</td><td>{sg(-r["disc"],1)} %</td><td>{na(r["unter_pct"], lambda v: de(v)+" %")}</td>'
                 + (f'<td>{na(r.get("tage"), lambda v: de(v))}</td>' if SHOW_TAGE else '')
                 + (f'<td>{na(r["d_qm"], lambda v: sg(v,1)+" %")}</td>' if PREV else '') + '</tr>')
    return ('<table class="t sm"><thead><tr><th>Stadt</th><th>Inserate</th><th>Median €/m²</th><th>Unsaniert 1950 bis 1994</th><th>Bestand 1950 bis 1994</th>'
            f'<th>Abschlag unsaniert</th><th>Brutto&shy;rendite</th><th>Angebot ggü. Marktwert</th><th>Anteil unter Marktwert</th>' + ('<th>Tage online</th>' if SHOW_TAGE else '') + ('<th>Preis Δ Vormonat</th>' if PREV else '') + f'</tr></thead><tbody>{body}</tbody></table>')
half = (len(rows) + 1) // 2
spread_top3 = ', '.join(f"{x['c']} ({de(x['spread'])} €)" for x in top_spread[:3])
tage_sorted = sorted(tage_rows, key=lambda r: -r['tage'])
tage_block = (block('Wie lange Wohnungen online sind (Median der aktiven Inserate, Tage)', bars([(r['c'], r['tage']) for r in tage_sorted[:10]] + [(r['c'], r['tage']) for r in tage_sorted[-6:]], ' Tage', dec=0, signed=False, lab=200, rowh=22, vmin=0))
              + src('Gemessen ab Erstveröffentlichung des Inserats.')) if tage_rows else ''
s5 = f'''<section class="sec"><h2>§ · Angebotsmarkt Deutschland: {len(rows)} Städte</h2>
<p class="intro">Auswertung aus der Leverage-Datenbank: {de(n_total)} aktive Wohnungsinserate, abgerufen am 07.11.2026. Medianwerte im Umkreis um die Stadtmitte.</p>
{kpis(kpi(de(n_total),'Ausgewertete Inserate',f'{len(rows)} Städte, alle Bundesländer'),
      kpi(f'{over_mw} von {len(rows)}','Städte mit Angeboten über Marktwert','Median Angebot ggü. Leverage-Bewertung'),
      kpi(de(top_rend[0]['rend'],1)+' %',f'Höchste Bruttorendite',top_rend[0]['c']), cols=3)}
{block('Größter Abschlag unsaniert ggü. Bestand gleicher Baujahre (1950 bis 1994), € je m²', bars([(r['c'], r['spread']) for r in top_spread[:12]], ' €', dec=0, signed=False, lab=200))}
{src('Nur Städte mit mindestens 8 Inseraten je Gruppe.')}
{block('Höchste Bruttomietrenditen (Median)', bars([(r['c'], r['rend']) for r in top_rend[:12]], ' %', dec=1, signed=False, lab=200, vmin=0))}
{tage_block}
{unter_block}
{spread_block}
{greix_block}
{alt_block}
{note(f'Die größten Abschläge für unsanierte Wohnungen gegenüber dem Bestand gleicher Baujahre zeigen {spread_top3}. Die höchsten Bruttorenditen liegen in {", ".join(r["c"] for r in top_rend[:3])} bei Preisen von {de(min(r["qm"] for r in top_rend[:3]))} bis {de(max(r["qm"] for r in top_rend[:3]))} € je m² und {de(min(r["n"] for r in top_rend[:3]))} bis {de(max(r["n"] for r in top_rend[:3]))} Inseraten je Stadt. In {over_mw} von {len(rows)} Städten liegt der Median der Angebote über der Leverage-Bewertung.')}

<div class="block avoid"><h3>Median-Angebotspreis Eigentumswohnungen, € je m²</h3><div class="mapw">{de_map(rows,'qm',lambda v: de(v),'€ je m²',qm_breaks)}</div></div>
{src('Kreisgröße nach Anzahl der Inserate. Alle Werte stehen zusätzlich in der Tabelle.')}
<div class="block avoid"><h3>Bruttomietrendite (Median), %</h3><div class="mapw">{de_map(rows,'rend',lambda v: de(v,1)+" %",'Bruttorendite',rend_breaks)}</div></div>
{src('Bruttorendite: Leverage-Mietschätzung (Jahreskaltmiete) geteilt durch Angebotspreis, Median der Inserate mit Bewertung.')}
<div class="block"><h3>Alle Städte im Überblick (sortiert nach Preis je m²)</h3>{city_table(rows)}</div>
{src('Unsaniert: Zustand laut Inserat sanierungsbedürftig. Bestand: Alle Inserate derselben Baujahre 1950 bis 1994. Abschlag: Median Bestand minus Median unsaniert, € je m². Werte nur ab 5 Inseraten je Gruppe und 50 Inseraten je Stadt (sonst k. A.). ⚠ = unter 10 Inserate. Angebot ggü. Marktwert: Positiver Wert heißt teurer angeboten als die Leverage-Bewertung. Radius siehe Methodik. Angebotspreise sind keine Kaufpreise.')}
</section>'''


# ---------- Marktdruck: Nachfrage, Genehmigungen, Zwangsversteigerungen, Suchinteresse ----------
MK = json.load(open(D/'markt.json')) if (D/'markt.json').exists() else None
TR = json.load(open(D/'trends.json')) if (D/'trends.json').exists() else None
s_markt = ''
if MK:
    _is, _iw, _zv, _bg, _ex, _vd = MK['is24'], MK['immowelt'], MK['zwangsversteigerungen'], MK['baugenehmigungen'], MK['epx'], MK['vdp']
    cite('ImmoScout24', 'WohnBarometer Q3 2026, 02.10.2026', _is['url'])
    cite('immowelt', 'Pressemitteilung zum 3. Quartal 2026, 30.09.2026', _iw['url'])
    cite('HAUSGOLD', 'Auswertung Anzeigendauer Q1 2025 bis Q1 2026', MK['hausgold']['url'])
    cite('Argetra GmbH', 'Halbjahresbericht Zwangsversteigerungen 1/2026 (Juli 2026, via Haufe) und Jahresbericht 2025', _zv['url'])
    cite('Statistisches Bundesamt', 'Baugenehmigungen, Konjunkturindikator buw110 (Stand 16.10.2026) und PM Nr. 370 vom 16.10.2026', _bg['url'])
    cite('Europace AG', 'Hauspreisindex EPX September 2026, 08.10.2026', _ex['url'])
    cite('Hypoport SE', 'Operative Kennziffern Q3 2026, 15.10.2026 (Transaktionsvolumen Europace)', _ex['transaktion']['url'])
    cite('vdp Verband deutscher Pfandbriefbanken', 'Immobilienpreisindex Q2 2026, 10.08.2026', _vd['url'])
    _bgp = [(mlabel(t), n) for t, n, _ in _bg['reihe']]; _lo, _hi, _st = auto_range([n for _, n in _bgp])
    _bgb = block(f'Genehmigte Wohnungen je Monat, letzte {len(_bgp)} Monate', line_chart(_bgp, _lo, _hi, dec=0, unit='', step=_st, lab=60)) + src(f'Quelle: Destatis, Originalwerte, Wohn- und Nichtwohngebäude inkl. Baumaßnahmen im Bestand. Januar bis August 2026: {de(_bg["jan_aug_2026"])} Wohnungen, {sg(_bg["jan_aug_yoy"])} % ggü. Vorjahr. September erscheint Mitte November.')
    _zvb = block('Zwangsversteigerungstermine Deutschland', bars([(k, n) for k, n, _ in _zv['jahre']] + [(k, n) for k, n, _ in _zv['h1']], '', dec=0, lab=150, signed=False, vmin=0)) + src(f'Quelle: Argetra. 1. Halbjahr 2026: {de(_zv["h1"][-1][1])} Termine ({sg(_zv["h1_2026_yoy"])} %), Verkehrswerte {de(_zv["h1"][-1][2],2)} Mrd. € ({sg(_zv["h1_2026_vw_yoy"])} %), Prognose 2026 rund {de(_zv["prognose_2026"])} Termine. Objektarten 2025: {de(_zv["objekte_2025"]["Ein- und Zweifamilienhäuser"],1)} % Ein- und Zweifamilienhäuser, {de(_zv["objekte_2025"]["Eigentumswohnungen"],1)} % Eigentumswohnungen.')
    _segb = block('Kaufnachfrage nach Preissegment, Mai bis September 2026 ggü. Vorperiode (ImmoScout24)', bars(list(_is['nachfrage_segment'].items()), ' %', dec=0, lab=200)) + src('Quelle: ImmoScout24 WohnBarometer Q3 2026, Kontaktanfragen je Inserat, Bestandswohnungen.')
    _trb = ''
    if TR and TR.get('reihen'):
        _mon = {}
        for b_, pts in TR['reihen'].items():
            for d_, v in pts:
                _mon.setdefault(b_, {}).setdefault(d_[:7], []).append(v)
        _beg = [b_ for b_ in ('Wohnung kaufen', 'Haus verkaufen', 'Zwangsversteigerung', 'Baufinanzierung') if b_ in _mon]
        _mths = sorted(set.intersection(*(set(_mon[b_]) for b_ in _beg)))[-12:]
        _rowsT = ''.join(f'<tr><td class="c">{b_}</td>' + ''.join(f'<td>{de(sum(_mon[b_][m])/len(_mon[b_][m]))}</td>' for m in _mths) + '</tr>' for b_ in _beg)
        _trb = block('Suchinteresse bei Google (Deutschland, Monatsmittel, 100 = Höchstwert je Begriff im Zeitraum)', f'<table class="t sm"><thead><tr><th>Begriff</th>' + ''.join(f'<th>{mlabel(m)}</th>' for m in _mths) + f'</tr></thead><tbody>{_rowsT}</tbody></table>') + src('Quelle: Google Trends, wöchentliche Werte zu Monatsmitteln verdichtet. Relativ je Begriff, nicht zwischen Begriffen vergleichbar.')
        cite('Google', 'Google Trends, Suchinteresse Deutschland, letzte 12 Monate', TR['url'])
    s_markt = f'''<section class="sec"><h2>§ · Marktdruck: Nachfrage und Verkaufsdruck</h2>
<p class="intro">Wie viel Nachfrage trifft auf wie viel Angebot, und wo entsteht Verkaufsdruck.</p>
{kpis(kpi(sg(_is['nachfrage_kauf_de_pct'],0)+' %','Kaufnachfrage je Inserat',f'ImmoScout24, Mai bis Sep 2026 ggü. Vorperiode; Metropolen {sg(_is["nachfrage_metropolen_pct"],0)} %'),
      kpi(sg(_is['nachfrage_miete_pct'],0)+' %','Mietnachfrage je Inserat','ImmoScout24, gleicher Zeitraum'),
      kpi(de(_iw['kaufanfragen_anteil'],1)+' %','Anteil Kaufanfragen an allen Anfragen',f'immowelt Jan bis Aug 2026, Vorjahr {de(_iw["kaufanfragen_anteil_vj"],1)} %'), cols=3)}
{kpis(kpi(de(_zv['h1'][-1][1]),'Zwangsversteigerungen 1. Hj. 2026',f'{sg(_zv["h1_2026_yoy"])} % ggü. Vorjahr, Ø Verkehrswert {de(_zv["h1_2026_vw_mittel"],-3)} €'),
      kpi(sg(_bg['jan_aug_yoy'])+' %','Baugenehmigungen Jan bis Aug 2026',f'{de(_bg["jan_aug_2026"])} Wohnungen, Neubau Aug {sg(_bg["aug_neubau_yoy"])} %'),
      kpi(de(_ex['transaktion']['q3_2026'],2)+' Mrd. €','Finanzierungsvolumen Europace Q3',f'Vorjahr {de(_ex["transaktion"]["q3_2025"],2)} Mrd. €'), cols=3)}
{kpis(kpi(de(GX['bund_q3']['vermarktungsdauer_etw_tage'])+' Tage','Vermarktungsdauer Eigentumswohnungen','GREIX Q3 2026, Median bis Beurkundung') if GX else '',
      kpi(de(GX['bund_q3']['anteil_preissenkung_etw'],1)+' %','Verkäufe mit vorheriger Preissenkung','GREIX Q3 2026, Eigentumswohnungen') if GX else '',
      kpi(sg(GX['bund_q3']['transaktionen_etw_q2_yoy'],1)+' %','Zahl der Wohnungskäufe','GREIX Q2 2026 ggü. Vorjahr') if GX else '', cols=3) if GX else ''}
{kpis(kpi(sg(_is['bestand_etw']['yoy'])+' %','Angebotspreise Bestandswohnungen',f'ImmoScout24 Q3 2026 ggü. Vorjahr, {de(_is["bestand_etw"]["qm"])} €/m²'),
      kpi(sg(_vd['etw_yoy'])+' %','Transaktionspreise Eigentumswohnungen',f'vdp {_vd["quartal"]} ggü. Vorjahr (Pfandbriefbanken)'),
      kpi(sg(_ex['etw'][2],2)+' %','Europace EPX Eigentumswohnungen',f'{_ex["monat"]} ggü. Vorjahr, Monat {sg(_ex["etw"][1],2)} %'), cols=3)}
{_segb}
{_bgb}
{_zvb}
{_trb}
{note(f'Die Kaufnachfrage je Inserat ist seit Mai um {de(abs(_is["nachfrage_kauf_de_pct"]))} % gesunken, die Mietnachfrage um {de(_is["nachfrage_miete_pct"])} % gestiegen. Am stärksten fehlt die Nachfrage im günstigsten Segment unter 3.000 € je m² ({sg(_is["nachfrage_segment"]["unter 3.000 €/m²"],0)} %), also dort, wo Fix-und-Flip-Objekte eingekauft werden. Angebotspreise (ImmoScout24 {sg(_is["bestand_etw"]["yoy"])} %) laufen den Transaktionspreisen (vdp {sg(_vd["etw_yoy"])} %, GREIX {sg(P["greix"]["etw_yoy"])} %, EPX {sg(_ex["etw"][2],2)} %) davon. Zwangsversteigerungen steigen das dritte Jahr in Folge ({sg(_zv["h1_2026_yoy"])} % im ersten Halbjahr), die Verkehrswerte je Termin liegen bei rund {de(_zv["h1_2026_vw_mittel"],-3)} €. Laut HAUSGOLD standen Anzeigen im ersten Quartal 2026 in Hamburg rund 44 % und in Bayern rund 40 % länger online als ein Jahr zuvor.')}
</section>'''

# ---------- 6 Leistbarkeit ----------
EG = json.load(open(D/'eigentum.json')) if (D/'eigentum.json').exists() else None
reallohn_block = ''; eigentum_blocks = ''; insolvenz_block = ''; insolvenz_kpis = ''
if EG:
    _rl = EG['reallohn']
    cite('Statistisches Bundesamt', 'Reallohnindex (zuletzt PM Nr. 308 vom 27.08.2026) und Häuserpreisindex, Basis 2025 = 100, Tabelle Stand 24.09.2026', _rl['url'])
    reallohn_block = (block('Reallöhne und Wohnimmobilienpreise, Veränderung zum Vorjahresquartal in %', grouped([q for q, _, _ in _rl['reihe']], [a for _, a, _ in _rl['reihe']], [b for _, _, b in _rl['reihe']], 'Reallohnindex', 'Häuserpreisindex', dec=1, h=230))
                      + src(f'Quelle: Destatis. Reallohn: Nominallohn ({sg(_rl["nominal_q2_26"])} % im 2. Quartal 2026) abzüglich Verbraucherpreise ({sg(_rl["vpi_q2_26"])} %). Häuserpreisindex Q4 2025 und Q1 2026 nach Basisumstellung revidiert. 3. Quartal 2026 erscheint Ende November (Löhne) bzw. Ende Dezember (Preise).'))
    _mz, _ph, _ev, _zb = EG['mikrozensus'], EG['phf'], EG['evs'], EG['zensus_bund']
    cite('Statistisches Bundesamt', 'Mikrozensus-Zusatzerhebung Wohnen, Eigentumsquote 2006 bis 2022 nach Ländern; West/Ost aus Datenreport 2024, Kapitel 6.1', _mz['url'])
    cite('Deutsche Bundesbank', 'Monatsbericht April 2025, Vermögensbefragung PHF 2023; Anteil mit weiterem Immobilienvermögen aus Monatsbericht April 2023 (Welle 2021)', _ph['url'])
    cite('Statistisches Bundesamt', 'Einkommens- und Verbrauchsstichprobe 2023, Haus- und Grundbesitz, Geld- und Immobilienvermögen, veröffentlicht 06.03.2026', _ev['url'])
    cite('Eurostat', 'EU-SILC, Bevölkerung nach Wohnstatus (ilc_lvho02), News vom 05.02.2026', EG['eurostat']['url'])
    cite('Statistische Ämter des Bundes und der Länder', 'Zensus 2022, Wohnungen nach Baujahr (Tabelle 4000X-1002) und Leerstand (PM Zensus Nr. 46)', _zb['url'])
    _l18, _l22 = _mz['laender_2018'], _mz['laender_2022']
    _lk = sorted(_l22, key=lambda k: -_l22[k])
    eigentum_blocks = (block('Eigentumsquote Deutschland, Anteil der Haushalte im eigenen Wohneigentum (Mikrozensus)', bars(_mz['de'], ' %', dec=1, signed=False, lab=120, vmin=0, rowh=24))
        + src(f'Quelle: Destatis, Mikrozensus-Zusatzerhebung Wohnen. Ab 2020 neue Methodik, 2022 nur eingeschränkt mit den Vorjahren vergleichbar. West {de(_mz["west_2022"],1)} % (2006: {de(_mz["west_2006"],1)} %), Ost inkl. Berlin {de(_mz["ost_2022"],1)} % (2006: {de(_mz["ost_2006"],1)} %). Eurostat zählt Personen statt Haushalte: {de(100-EG["eurostat"]["de_mieter_2024"])} % der Menschen in Deutschland wohnen im Eigentum, im EU-Schnitt {de(EG["eurostat"]["eu_eigentuemer_2024"],1)} % (2024).')
        + block('Vermögen von Eigentümern und Mietern (Bundesbank-Vermögensbefragung 2023, Median je Haushalt)', bars([('Eigentümer ohne Hypothek', _ph['median_eigentuemer_ohne_hyp']), ('Eigentümer mit Hypothek', _ph['median_eigentuemer_mit_hyp']), ('Alle Haushalte', _ph['median_alle']), ('Mieterhaushalte', _ph['median_mieter'])], ' €', dec=0, signed=False, lab=220, vmin=0))
        + src(f'Quelle: Deutsche Bundesbank, PHF 2023. {de(_ph["eigentum_hauptwohnsitz"][-1][1])} % der Haushalte besitzen ihren Hauptwohnsitz (2021: {de(_ph["eigentum_hauptwohnsitz"][-2][1])} %), {de(_ph["sonstiges_immobilienvermoegen_2021"])} % halten weiteres Immobilienvermögen, etwa vermietete Wohnungen (Welle 2021). Wert des Hauptwohnsitzes im Mittel {de(_ph["wert_hauptwohnsitz"],-3)} € (2021: {de(_ph["wert_hauptwohnsitz_2021"],-3)} €).')
        + block('Haus- und Grundbesitz der Haushalte nach Art (EVS 2023, Anteil der Haushalte, Mehrfachnennung)', bars(list(_ev['arten'].items()), ' %', dec=1, signed=False, lab=260, vmin=0, rowh=24))
        + src(f'Quelle: Destatis, EVS 2023, Stichtag 01.01.2023. {de(_ev["haus_grundbesitz"],1)} % aller Haushalte besitzen Haus- oder Grundbesitz (West {de(_ev["west"],1)} %, Ost {de(_ev["ost"],1)} %). Immobilienvermögen je Haushalt im Schnitt {de(_ev["immobilienvermoegen"][-1][1],-3)} € (2018: {de(_ev["immobilienvermoegen"][-2][1],-3)} €, 2008: {de(_ev["immobilienvermoegen"][0][1],-3)} €).')
        + block('Wohnungsbestand Deutschland nach Baujahr (Zensus 2022, Anteil der Wohnungen in %)', bars(list(_zb['baujahr'].items()), ' %', dec=1, signed=False, lab=160, vmin=0, rowh=22))
        + src(f'Quelle: Zensus 2022, {de(_zb["wohnungen"])} Wohnungen, Stichtag 15.05.2022. {de(sum(v for k, v in _zb["baujahr"].items() if k in ("vor 1919","1919 bis 1949","1950 bis 1959","1960 bis 1969","1970 bis 1979")),1)} % der Wohnungen sind vor 1980 gebaut. Leerstand {de(_zb["leerstand"],1)} %.'))
    _in = EG['insolvenzen']
    cite('Statistisches Bundesamt', 'Unternehmensinsolvenzen, PM Nr. 85 (13.03.2026), Nr. 325 (11.09.2026), Nr. 362 (09.10.2026), Tabelle nach Monaten', _in['url'])
    cite('Creditreform', 'Insolvenzen in Deutschland, 1. Halbjahr 2026, 23.06.2026', _in['url2'])
    insolvenz_kpis = kpis(kpi(de(_in['h1_2026']), 'Unternehmensinsolvenzen 1. Hj. 2026', f'{sg(_in["h1_2026_yoy"])} % ggü. Vorjahr, Juli {sg(_in["jul_2026_yoy"])} %'),
                          kpi(de(_in['bau_je10k_h1_2026'],1), 'Insolvenzen je 10.000 Baufirmen', f'1. Hj. 2026, alle Branchen 36,2; Vorjahr {de(_in["bau_je10k_h1_2025"],1)}'),
                          kpi(sg(_in['bau_yoy_h1_2026_creditreform'])+' %', 'Bauinsolvenzen ggü. Vorjahr', 'Creditreform, 1. Hj. 2026 (2025: ' + sg(_in['bau_yoy_2025_creditreform']) + ' %)'), cols=3)
    insolvenz_block = (block('Unternehmensinsolvenzen je Monat, alle Branchen', bars(_in['monate_2025'] + _in['monate_2026'], '', dec=0, signed=False, lab=90, vmin=0, rowh=20))
                       + src(f'Quelle: Destatis, beantragte Unternehmensinsolvenzen nach Monaten, Stand 09.10.2026. 2025 gesamt {de(_in["gesamt_2025"])} ({sg(_in["gesamt_2025_yoy"])} %). Das Baugewerbe liegt mit {de(_in["bau_je10k_2025"])} Insolvenzen je 10.000 Unternehmen (2025) deutlich über dem Durchschnitt von {de(_in["gesamt_je10k_2025"])}.'))
leist = sorted(rows, key=lambda r: -r['leist_qm'])
s6 = f'''<section class="sec"><h2>§ · Leistbarkeit: Was sich der Käufer leisten kann</h2>
<p class="intro">Der erzielbare Verkaufspreis hängt am Darlehen, das ein typischer Haushalt bekommt. Die Rechnung geht vom Median-Haushaltsnettoeinkommen aus.</p>
{kpis(kpi(de(ek_med)+' €','Median-Haushaltsnettoeinkommen','pro Monat, EU-SILC 2025'),
      kpi(de(rate_med)+' €','Rate bei 35 % Belastung','Annahme für die Rechnung'),
      kpi(de(darl_med,-3)+' €','Darlehen daraus',f'{de(bz,2)} % Zins, {de(tilg,2)} % Tilgung'), cols=3)}
{block('Wie viele m² ein Median-Haushalt allein mit Darlehen finanzieren kann', bars([(r['c'], r['leist_qm']) for r in leist[:12]] + [(r['c'], r['leist_qm']) for r in leist[-8:]], ' m²', dec=0, signed=False, lab=200, rowh=24))}
{src(f'Rechnung: Darlehen von {de(darl_med,-3)} € geteilt durch Median-Angebotspreis je m² der Stadt. Ohne Eigenkapital und Kaufnebenkosten. Oben die 12 günstigsten, unten die 8 teuersten Märkte der Auswertung. Zum Vergleich: Eine durchschnittliche Wohnung in Deutschland hat {de(Z["flaeche"]["je_wohnung"],1)} m².')}
{note(f'Ein Haushalt mit Medianeinkommen finanziert in München rund {de(S["München"]["qm"] and darl_med/S["München"]["qm"])} m², in Leipzig rund {de(darl_med/S["Leipzig"]["qm"])} m². Ohne Eigenkapital reicht das Darlehen in {unter50} von {len(rows)} Städten für weniger als 50 m².')}
{reallohn_block}
{block('Anteil der Wohnkosten am verfügbaren Haushaltseinkommen (EU-SILC 2025)', bars([('Alle Haushalte',Z['wohnkosten']['anteil25']),('Alleinlebende',Z['wohnkosten']['allein']),('Alleinerziehende',Z['wohnkosten']['alleinerz'])], ' %', signed=False, lab=200, vmin=0))}
{src('Quelle: Destatis, Anteil der Wohnkosten am verfügbaren Haushaltseinkommen, EU-SILC 2025.')}
{block(f'Mietbelastung nach Haushaltsnettoeinkommen (Mikrozensus 2022, Durchschnitt {de(Z["mietbelastung"]["schnitt"],1)} %)', bars(list(Z['mietbelastung']['nach_einkommen'].items()), ' %', signed=False, lab=200, vmin=0))}
{note(f'Im Schnitt geben Haushalte {de(Z["wohnkosten"]["anteil25"],1)} % ihres verfügbaren Einkommens für Wohnen aus, {de(Z["wohnkosten"]["ueber40_25"],1)} % der Bevölkerung mehr als 40 %. Mieterhaushalte mit unter 1.500 € Einkommen zahlen {de(Z["mietbelastung"]["nach_einkommen"]["unter 1.500 €"],1)} %. Bei Verkauf an Kapitalanleger sollte die angesetzte Miete im Zielquartier tragbar bleiben.')}
</section>'''
cite('Statistisches Bundesamt', 'Einkommen und Einkommensverteilung, EU-SILC 2025, Tabellenstand 09.04.2026', Z['einkommen']['url'])
cite('Statistisches Bundesamt', 'Anteil der Wohnkosten am verfügbaren Haushaltseinkommen, Tabellenstand 09.04.2026', Z['wohnkosten']['url'])
cite('Statistisches Bundesamt', 'Mieten und Mietbelastung, Mikrozensus 2022, Tabelle WO6', Z['mietbelastung']['url'])

# ---------- 7 Kosten, Energie, Regulierung ----------
cite('Statistisches Bundesamt', 'Baupreisindex August 2026, PM Nr. 360 vom 09.10.2026', P['baupreise']['url'])
cite('Statistisches Bundesamt', 'Baugenehmigungen August 2026, PM Nr. 370 vom 16.10.2026', P['baugen']['url'])
cite('Statistisches Bundesamt', 'Baufertigstellungen 2025, PM Nr. 174 vom 22.05.2026', Z['fertig']['url'])
cite('Statistisches Bundesamt', 'Zensus 2022, Heizungsart, PM Zensus 45', Z['heizung']['url'])
cite('Bundesregierung', 'Neues Gebäudemodernisierungsgesetz, 29.07.2026', G['geg']['url'])
cite('Deutscher Bundestag', 'Drittes Gesetz zur Änderung des BEHG, Beschluss 15.10.2026', G['co2']['url'])
heiz = [(k, v) for k, v in Z['heizung'].items() if k != 'url']
s7 = f'''<section class="sec"><h2>§ · Baukosten, Energie und Regulierung</h2>
{kpis(kpi(sg(P['baupreise']['instand_yoy'])+' %','Instandhaltung Wohngebäude','Aug 2026 ggü. Vorjahr'),
      kpi(de(Z['fertig']['2025']),'Fertiggestellte Wohnungen 2025',f'{sg(Z["fertig"]["yoy"])} % ggü. 2024'),
      kpi(de(P['baugen']['jan_aug']),'Genehmigte Wohnungen',f'Jan bis Aug 2026, {sg(P["baugen"]["jan_aug_yoy"])} %'), cols=3)}
{block('Preisanstieg einzelner Gewerke, Aug 2026 ggü. Vorjahr', bars([('Dachdeckerarbeiten',P['baupreise']['dach']),('Zimmer- und Holzbau',P['baupreise']['zimmer']),('Elektro, Sicherheit, IT',P['baupreise']['elektro']),('Erdarbeiten',P['baupreise']['erd']),('Instandhaltung gesamt',P['baupreise']['instand_yoy']),('Neubau Wohngebäude gesamt',P['baupreise']['wohn_yoy']),('Heizung inkl. Wärmepumpe',P['baupreise']['heizung'])], vmin=0, lab=220))}
{src('Quelle: Destatis, Baupreisindex, PM Nr. 360 vom 09.10.2026.')}
{insolvenz_kpis}
{insolvenz_block}
{block('Womit Deutschlands Wohnungen heizen (Zensus 2022)', bars(heiz, ' %', dec=0, signed=False, lab=260, vmin=0))}
{src('Quelle: Destatis, Zensus 2022, Anteil der Wohnungen nach überwiegendem Energieträger. Stichtag 15.05.2022.')}
{block('Was sich bei Heizung und CO2 geändert hat', f"""<table class="t"><tbody>
<tr><td class="c">Gebäudemodernisierungsgesetz</td><td>{G['geg']['status']}. {G['geg']['kern']}.</td></tr>
<tr><td class="c">Nationaler CO2-Preis</td><td>Preiskorridor {G['co2']['2026']} € je Tonne für 2026, für 2027 laut Bundestagsbeschluss vom 15.10.2026 ebenfalls {G['co2']['2027']} €.</td></tr>
<tr><td class="c">EU-Emissionshandel für Gebäude (ETS 2)</td><td>Start um ein Jahr auf {G['co2']['ets2']} verschoben.</td></tr></tbody></table>""")}
{note(f'Drei Viertel aller Wohnungen heizen mit Gas oder Öl. Mit dem neuen Gesetz entfällt die Pflicht zu 65 % erneuerbarer Wärme bei neuen Heizungen, der Druck kommt künftig über den CO2-Preis und die Grüngasquote ab 2028. Für die Kalkulation: Den Heizungstausch nicht pauschal einplanen, sondern nach Käufergruppe entscheiden. Dach und Elektro sind die Gewerke mit dem stärksten Preisanstieg und sollten früh festgepreist werden.')}
{block('Rechenbeispiel Baukosten', f'<p>Eine {FX["qm"]}-m²-Wohnung mit {de(FX["san_qm"])} € Sanierungsbudget je m² kostet bei {sg(P["baupreise"]["instand_yoy"])} % Preissteigerung rund <b>{de(fx_san*P["baupreise"]["instand_yoy"]/100)} € mehr</b> als vor einem Jahr. Wohnungspreise sind laut GREIX im selben Zeitraum um {de(abs(P["greix"]["etw_yoy"]),1)} % gesunken. Gleichzeitig wurden 2025 nur {de(Z["fertig"]["2025"])} Wohnungen fertiggestellt, {de(Z["fertig"]["genehmigt_nicht_fertig"])} genehmigte Wohnungen sind noch nicht gebaut.</p>')}
{src(f'Rechenbeispiel mit angenommenem Budget von {de(FX["san_qm"])} € je m², eigene Berechnung.')}
</section>'''

# ---------- 8 Zielgruppe ----------
cite('Statistisches Bundesamt', 'Wohnungsbestand Ende 2025, PM Nr. 250 vom 16.07.2026', Z['flaeche']['url'])
cite('Statistisches Bundesamt', 'Wohnfläche nach Eigentümern und Mietern, Tabelle WO4', Z['flaeche']['url2'])
cite('Statistisches Bundesamt', 'Eigentumsquote, Mikrozensus 2022', Z['eigentum']['url'])
cite('Statistisches Bundesamt', 'Privathaushalte nach Haushaltsgröße, Tabellenstand 13.04.2026', Z['haushalte']['url'])
cite('Statistisches Bundesamt', 'Reallöhne 2. Quartal 2026, PM Nr. 308 vom 27.08.2026', Z['loehne']['url'])
cite('Bundesagentur für Arbeit', 'Arbeitsmarkt im Oktober 2026, 30.10.2026', Z['alq']['url'])
eig = sorted(Z['eigentum']['laender'].items(), key=lambda x: -x[1])
s8 = f'''<section class="sec"><h2>§ · Zielgruppe: Haushalte, Einkommen, Wohnfläche</h2>
{kpis(kpi(de(Z['flaeche']['je_wohnung'],1)+' m²','Ø Wohnfläche je Wohnung','Bestand Ende 2025'),
      kpi(de(Z['flaeche']['je_person'],1)+' m²','Ø Wohnfläche je Person','Bestand Ende 2025'),
      kpi(de(Z['flaeche']['neubau25'],1)+' m²','Ø Neubauwohnung 2025',f'2007: {de(Z["flaeche"]["neubau07"],1)} m²'), cols=3)}
{kpis(kpi(de(Z['haushalte']['single'],1)+' %','Einpersonenhaushalte','2025, Anteil aller Haushalte'),
      kpi(sg(Z['loehne']['real'])+' %','Reallöhne','Q2 2026 ggü. Vorjahr'),
      kpi(de(Z['alq']['okt26'],1)+' %','Arbeitslosenquote',f'Okt 2026, Vorjahr {de(Z["alq"]["okt25"],1)} %'), cols=3)}
{block('Wohnfläche Eigentümer und Mieter (Mikrozensus 2022)', f'<table class="t"><thead><tr><th></th><th>je Wohnung</th><th>je Person</th></tr></thead><tbody><tr><td class="c">Eigentümerhaushalte</td><td>{de(Z["flaeche"]["eig_wohnung"],1)} m²</td><td>{de(Z["flaeche"]["eig_person"],1)} m²</td></tr><tr><td class="c">Mieterhaushalte</td><td>{de(Z["flaeche"]["miet_wohnung"],1)} m²</td><td>{de(Z["flaeche"]["miet_person"],1)} m²</td></tr></tbody></table>')}
{block('Eigentumsquote nach Bundesland (Mikrozensus 2022, Anteil Eigentümerhaushalte)', bars(eig, ' %', signed=False, lab=200, rowh=24, vmin=0))}
{src('Quelle: Destatis, Eigentumsquote, Mikrozensus Zusatzprogramm Wohnen 2022. Deutschland gesamt '+de(Z['eigentum']['de'],1)+' %.')}
{eigentum_blocks}
{note(f'{de(Z["haushalte"]["single"],1)} % aller Haushalte sind Einpersonenhaushalte, weitere {de(Z["haushalte"]["zwei"],1)} % Zweipersonenhaushalte. Eigentümer wohnen auf {de(Z["flaeche"]["eig_wohnung"],1)} m², Mieter auf {de(Z["flaeche"]["miet_wohnung"],1)} m². Die niedrigsten Eigentumsquoten haben {", ".join(f"{k} ({de(v,1)} %)" for k, v in eig[-3:][::-1])}, dort wohnt die große Mehrheit zur Miete.')}
</section>'''

# ---------- 9 Demografie ----------
cite('Statistisches Bundesamt', 'Erwerbspersonen erreichen in den nächsten 15 Jahren das Rentenalter, PM 03.09.2025', G['boomer']['url'])
cite('Statistisches Bundesamt', '16. koordinierte Bevölkerungsvorausberechnung, PM vom 11.12.2025', G['alter']['url'])
cite('Statistisches Bundesamt', 'Erbschaft- und Schenkungsteuer 2025, PM Nr. 306 vom 26.08.2026', G['erbe']['url'])
cite('DIW Berlin', 'Wochenbericht 5/2021, Erbschaften und Schenkungen', G['diw']['url'])
cite('Statistisches Bundesamt', 'Haushaltsvorausberechnung, PM vom 05.11.2026', G['haushalte']['url'])
cite('Statistisches Bundesamt', 'Wanderungen 2025, PM Nr. 184 vom 01.06.2026', G['binnen']['url'])
cite('Statistisches Bundesamt', 'Bevölkerung 2025, PM Nr. 203 vom 16.06.2026', G['bev25']['url'])
cite('Argetra GmbH', 'Jahresbericht Zwangsversteigerungen 2025, Januar 2026', G['zv']['url'])
binnen = sorted(list(G['binnen']['gewinner'].items()) + list(G['binnen']['verlierer'].items()), key=lambda x: -x[1])
s9 = f'''<section class="sec"><h2>§ · Demografie, Ruhestand und Erben</h2>
<p class="intro">Die geburtenstarken Jahrgänge 1955 bis 1969 erreichen bis 2039 das Rentenalter.</p>
{kpis(kpi(de(G['boomer']['erwerbspersonen_rente_bis_2039'],1)+' Mio.','Erreichen bis 2039 das Rentenalter',f'{G["boomer"]["anteil"]} % aller Erwerbspersonen'),
      kpi(de(G['alter']['ab67_2024'],1)+' Mio.','Menschen ab 67 (2024)',f'bis 2038: {de(G["alter"]["ab67_2038_von"],1)} bis {de(G["alter"]["ab67_2038_bis"],1)} Mio.'),
      kpi(de(G['erbe']['grundvermoegen'],1)+' Mrd. €','Übertragenes Grundvermögen 2025',f'{sg(G["erbe"]["grund_yoy"])} % ggü. 2024'), cols=3)}
{kpis(kpi(de(G['erbe']['vermoegen25'],1)+' Mrd. €','Steuerlich erfasste Erbschaften und Schenkungen',f'2025, {sg(G["erbe"]["vermoegen_yoy"])} % ggü. Vorjahr'),
      kpi(de(P['wanderung']['netto25']),'Nettozuwanderung 2025',f'2024: {de(P["wanderung"]["netto24"])}'),
      kpi(de(G['zv']['2025']),'Zwangsversteigerungstermine 2025',f'{sg((G["zv"]["2025"]/G["zv"]["2024"]-1)*100)} % ggü. 2024'), cols=3)}
{block('Wanderungssaldo zwischen Bundesländern 2025 (größte Gewinner und Verlierer)', bars(binnen, '', dec=0, lab=220))}
{src('Quelle: Destatis, PM Nr. 184 vom 01.06.2026. Insgesamt 996.000 Umzüge zwischen Bundesländern.')}
{block('Bevölkerungsentwicklung 2025 nach Region', bars([('Berlin',G['bev25']['berlin']),('Hamburg',G['bev25']['hamburg']),('Westdeutschland',G['bev25']['west']),('Ostdeutschland',G['bev25']['ost']),('Sachsen-Anhalt',G['bev25']['sachsen_anhalt']),('Thüringen',G['bev25']['thueringen'])], lab=220))}
{src('Quelle: Destatis, PM Nr. 203 vom 16.06.2026.')}
{note(f'Die Erbschaftsteuerstatistik erfasst nur Fälle oberhalb der Freibeträge, das tatsächliche Volumen ist deutlich höher. Das DIW schätzt für 2002 bis 2017 im Schnitt {de(G["diw"]["wert"])} Mrd. € pro Jahr und hält das für eher unterschätzt. 2025 verlieren Thüringen und Sachsen-Anhalt Einwohner, Brandenburg, Bayern und Schleswig-Holstein gewinnen. Die Zahl der Haushalte sinkt laut Destatis bis 2050 auf {de(G["haushalte"]["2050_von"],1)} bis {de(G["haushalte"]["2050_bis"],1)} Mio. (2024: {de(G["haushalte"]["2024"],1)} Mio.).')}
</section>'''

# ---------- Meldungen des Monats (RSS-Feeds) ----------
s_feeds = ''
FEEDS = json.load(open(D/'feeds.json')) if (D/'feeds.json').exists() else None
if FEEDS and FEEDS.get('meldungen'):
    _prio = ['Bundesbank', 'Destatis', 'EZB', 'ifo', 'DIW', 'IW Köln', 'KfW', 'vdp', 'GdW', 'ZIA', 'BBSR', 'bulwiengesa', 'empirica', 'Europace', 'Interhyp', 'Dr. Klein', 'ImmoScout', 'immowelt']
    def _rang(m):
        q = m['quelle']
        return next((i for i, p_ in enumerate(_prio) if p_.lower() in q.lower()), len(_prio))
    _ml = [m for m in FEEDS['meldungen'] if m.get('datum') and m.get('titel_treffer', True)]
    _auswahl = sorted(_ml, key=lambda m: (_rang(m), m['datum']), reverse=False)
    # je Quelle höchstens 2, insgesamt 14, dann nach Datum absteigend
    _seen = {}; _pick = []
    for m in sorted(_auswahl, key=lambda m: (_rang(m), -int(m['datum'].replace('-', '')))):
        if _seen.get(m['quelle'], 0) >= 2: continue
        _seen[m['quelle']] = _seen.get(m['quelle'], 0) + 1; _pick.append(m)
        if len(_pick) >= 16: break
    _pick.sort(key=lambda m: m['datum'], reverse=True)
    def _tt(t): return re.sub(r'\s+[–—]\s+', ', ', t).replace('–', '-').replace('—', '-')
    _li = ''.join(f'<li><span class="fd">{m["datum"][8:10]}.{m["datum"][5:7]}.</span> <b>{m["quelle"]}:</b> {_tt(m["titel"])}<br><span class="url">{m["link"]}</span></li>' for m in _pick)
    _fq = ', '.join(f['quelle'] for f in FEEDS['feeds_ok'])
    s_feeds = f'''<section class="sec"><h2>§ · Meldungen des Monats</h2>
<p class="intro">Automatisch gelesen aus {len(FEEDS['feeds_ok'])} Nachrichten-Feeds seit dem {FEEDS['zeitraum_ab'][8:10]}.{FEEDS['zeitraum_ab'][5:7]}.{FEEDS['zeitraum_ab'][:4]}, gefiltert auf Immobilien, Zinsen, Bau und Haushalte. {len(FEEDS['meldungen'])} relevante Meldungen, hier die wichtigsten {len(_pick)}.</p>
<ol class="srcl feeds">{_li}</ol>
{src('Gelesene Feeds: ' + _fq + '. Stand ' + FEEDS['stand'][8:10] + '.' + FEEDS['stand'][5:7] + '.' + FEEDS['stand'][:4] + '. Überschriften der Herausgeber, Gedankenstriche durch Kommas ersetzt.')}
</section>'''
    cite('Diverse Herausgeber', f'Pressemitteilungen und Meldungen aus {len(FEEDS["feeds_ok"])} RSS-Feeds, Zeitraum ab {FEEDS["zeitraum_ab"]}, siehe Kapitel Meldungen des Monats', 'siehe Einzellinks im Kapitel')

# ---------- Methodik / Quellen ----------
seen, src_items = set(), []
for a, b, c in SRC:
    if (a, b) in seen:
        continue
    seen.add((a, b)); src_items.append((a, b, c))
src_html = ''.join(f'<li>{a} · {b}<br><span class="url">{c}</span></li>' for a, b, c in src_items)
s11 = f'''<section class="sec brk"><h2>§ · Methodik und Quellen</h2>
<p>Jede Zahl in diesem Report stammt aus einer der unten genannten Quellen oder ist eine nachvollziehbare Berechnung daraus. Annahmen in Rechenbeispielen sind direkt beim Beispiel genannt. Amtliche Daten erscheinen mit Verzögerung, deshalb steht bei jeder Kennzahl der Bezugszeitraum.</p>
<p><b>Leverage-Angebotsdaten:</b> Aktive Inserate für Eigentumswohnungen zum Kauf aus mehreren Portalen, ohne Fremddatenbanken, Abruf 07.11.2026. Medianwerte je Stadt im Umkreis von 5 km um die Stadtmitte. In großen Städten 2 bis 3 km, weil eine Abfrage höchstens 1.000 Inserate zählt. In Städten mit weniger als 150 Inseraten im 5-km-Umkreis 10 km, dieser Umkreis kann Nachbarorte einschließen (z. B. Mainz und Wiesbaden, Potsdam und Berlin-Wannsee). Der verwendete Radius steht in der Tabelle unter dem Stadtnamen. Der Zustand stammt aus der Inseratsangabe, das Baujahr aus dem Inserat. Mieten und Marktwerte sind Schätzungen des Leverage-Bewertungsmodells, keine Angebotsmieten. Angebotspreise sind keine Kaufpreise.</p>
<p><b>Grenzen dieser Ausgabe:</b> Kreisgenaue amtliche Daten zu Wanderung, Alter und Eigentum folgen im Quartalsreport. Für einige Kennzahlen lagen nur Sekundärquellen mit Verweis auf den Herausgeber vor (GREIX-Mietindex, Grunderwerbsteuersätze). Sie sind im Quellenverzeichnis so gekennzeichnet.</p>
<h3>Quellenverzeichnis</h3><ol class="srcl">{src_html}</ol>
<div class="block avoid"><h3>Rechtlicher Hinweis</h3>
<p class="legal">Dieser Report dient ausschließlich der allgemeinen Information. Er stellt keine Anlageberatung, Steuerberatung, Rechtsberatung oder Aufforderung zum Kauf oder Verkauf von Immobilien dar. Die Daten wurden sorgfältig aus den genannten Quellen zusammengestellt. Eine Gewähr für Richtigkeit, Vollständigkeit und Aktualität wird nicht übernommen. Vergangene Entwicklungen sind kein verlässlicher Indikator für künftige Entwicklungen. Investitionsentscheidungen triffst du eigenverantwortlich, idealerweise nach individueller Prüfung durch Fachleute. Daten der Deutschen Bundesbank und des Statistischen Bundesamts unterliegen der Datenlizenz Deutschland, Namensnennung, Version 2.0.</p>
<p class="legal">Herausgeber: Flipper Consulting GmbH. Weitergabe und Vervielfältigung nur mit schriftlicher Zustimmung.</p></div>
</section>'''

css = ''.join(font(w) for w in (400, 600, 700, 800)) + f'''
@page{{size:A4;margin:24mm 17mm 20mm 17mm}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:Montserrat;color:{INK};font-size:10.5px;line-height:1.62;-webkit-print-color-adjust:exact}}
.cover-page{{break-after:page}}
.sec{{margin-top:34px}}.brk{{break-before:page;margin-top:0}}h2{{break-after:avoid}}.mapw{{width:88%;margin:0 auto}}
.cover{{background:{TD};color:#fff;border-radius:14px;padding:28px 28px 26px;margin-bottom:22px}}
.clogo{{height:26px;display:block;margin-bottom:22px}}
.sub{{font-size:13px;font-weight:600;opacity:.9;margin-top:-4px}}.kicker{{font-size:9.5px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;opacity:.9}}
h1{{font-size:32px;font-weight:800;margin:8px 0 10px;line-height:1.15}}
.lead{{font-size:12px;margin:0;line-height:1.6}}
h2{{font-size:18px;font-weight:800;color:{TD};margin:0 0 12px;line-height:1.3}}
h2.first{{margin-top:4px}}
h3{{font-size:11.5px;font-weight:700;margin:0 0 10px;line-height:1.4}}
.intro{{font-size:11px;color:#3a4a4b;margin:0 0 16px}}
.block{{margin:18px 0 6px}}
.avoid{{break-inside:avoid}}
.kpis{{display:grid;gap:10px;margin:0 0 12px;break-inside:avoid}}
.kpis.c3{{grid-template-columns:repeat(3,1fr)}}
.kpi{{background:{TL};border-radius:10px;padding:12px 14px;min-height:74px}}
.kpi .v{{font-size:19px;font-weight:800;color:{TD};line-height:1.15;white-space:nowrap}}
.kpi .l{{font-size:9.5px;font-weight:700;margin-top:6px;line-height:1.35}}
.kpi .s{{font-size:8.5px;color:{MUT};margin-top:3px;line-height:1.35}}
.sum{{padding-left:16px;margin:0 0 10px}}.sum li{{margin-bottom:6px;font-size:10.3px}}
.toc ol{{columns:2;column-gap:28px;padding-left:18px;margin:0}}.toc li{{margin-bottom:5px}}
.t{{width:100%;border-collapse:collapse;font-size:10px}}
.t th{{text-align:left;font-size:8.5px;text-transform:uppercase;letter-spacing:.4px;color:{MUT};border-bottom:1.5px solid {T};padding:7px 8px;vertical-align:bottom;line-height:1.35}}
.t td{{padding:8px;border-bottom:1px solid #e6eeef;vertical-align:top;line-height:1.45}}
.t td.c{{font-weight:700;width:38%}}.t td.b{{font-weight:800}}
.t.sm td{{padding:6px 7px;font-size:9.5px}}.t.sm td.c{{width:auto}}
.t tr{{break-inside:avoid}}
.r{{display:block;font-size:8px;color:{MUT};font-weight:400;margin-top:1px}}
.neg{{color:{RED}}}
.note{{border-left:4px solid {T};background:{TL};padding:12px 14px;border-radius:0 8px 8px 0;margin:14px 0;font-size:10.5px;line-height:1.6}}
.src{{font-size:8.3px;color:{MUT};margin:6px 0 4px;line-height:1.45}}
.srcl{{padding-left:18px}}.srcl li{{margin-bottom:7px;break-inside:avoid}}.url{{font-size:8px;color:{MUT};word-break:break-all}}
.legal{{font-size:9px;color:#3a4a4b}}
svg{{display:block}}
'''

HEADER = f'''<div style="width:100%;padding:0 17mm;font-family:Arial;font-size:7.5px;color:{MUT};display:flex;justify-content:space-between;align-items:center;-webkit-print-color-adjust:exact">
<img src="data:image/png;base64,{LOGO_T}" style="height:13px"/><span style="letter-spacing:1px;text-transform:uppercase">Immobilienhandel-Marktreport (Fix-und-Flip) · {BERICHT}</span></div>'''
FOOTER = f'''<div style="width:100%;padding:0 17mm;font-family:Arial;font-size:7px;color:{MUT};display:flex;justify-content:space-between;align-items:center;-webkit-print-color-adjust:exact">
<img src="data:image/png;base64,{LOGO_T}" style="height:9px"/><span>Keine Anlage-, Steuer- oder Rechtsberatung. Alle Angaben ohne Gewähr.</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'''

def feinschliff(h):
    import re
    h = re.sub(r'(?<=\d) (?=(%|€|m²|Mrd\.|Mio\.|Tage|km)(?![\w]))', '\u00a0', h)
    h = re.sub(r'(?<=\d) (?=Prozentpunkte)', '\u00a0', h)
    h = h.replace('CO2', 'CO₂')
    return h
SECS = [x for x in [s1, s2, s3, s4, s_stimmung, s5, s_markt, s6, s7, s8, s9, s_feeds, s11] if x]
_titel = []
def _kopf(sec):
    m = re.search(r'(<h2>.*?</h2>\s*(?:<p class="intro">.*?</p>\s*)?(?:<div class="kpis[^"]*">.*?<!--/kpis-->\s*)?)', sec, re.S)
    return sec.replace(m.group(1), '<div class="avoid">' + m.group(1) + '</div>', 1) if m else sec
for i, sec in enumerate(SECS, 1):
    SECS[i-1] = _kopf(sec.replace('<h2>§ · ', f'<h2>{i} · ', 1))
    _titel.append(re.search(r'<h2>\d+ · (.*?)</h2>', SECS[i-1]).group(1))
cover = cover.replace('__TOC__', ''.join(f'<li>{t}</li>' for t in _titel))
html = f'<!doctype html><html lang="de"><head><meta charset="utf-8"><style>{css}</style></head><body>{cover}{"".join(SECS)}</body></html>'
html = feinschliff(html)
(R/'out').mkdir(exist_ok=True)
(R/'out'/f'report_{MONTH}.html').write_text(html)
out = R/'out'/f'Immobilienhandel-Marktreport-{MONTH}.pdf'
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.set_content(html, wait_until='networkidle')
    pg.pdf(path=str(out), format='A4', print_background=True, display_header_footer=True,
           header_template=HEADER, footer_template=FOOTER,
           margin=dict(top='24mm', bottom='20mm', left='17mm', right='17mm'))
    b.close()
import pymupdf
_d = pymupdf.open(str(out))
_p = _d[0]
_p.draw_rect(pymupdf.Rect(0, 0, _p.rect.width, 24 * 72 / 25.4 - 2), color=None, fill=(1, 1, 1), overlay=True)
_d.saveIncr()
_d.close()
print('ok', len(rows), n_total, round(kaufkraft, 2), round(darl_med), [(r['c'], r['spread']) for r in top_spread[:5]])
