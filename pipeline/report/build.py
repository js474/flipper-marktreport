import json, base64, math, pathlib, os
from playwright.sync_api import sync_playwright

R = pathlib.Path(__file__).resolve().parents[2]   # Repo-Wurzel
MONTH = os.environ.get('REPORT_MONTH', '2026-11')
D = R / 'data' / 'snapshots' / MONTH
P = json.load(open(D/'public.json'))
F = json.load(open(D/'fin.json'))
Z = json.load(open(D/'zg.json'))
G = json.load(open(D/'demo.json'))
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
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')
def sg(x, d=1):
    return ('+' if x > 0 else '') + de(x, d)
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
fk_zins = F['mfi_unternehmen']['bis1mio_var_sep26']
fk_zins_vj = F['mfi_unternehmen']['bis1mio_var_sep25']
notar_pct = 1.5
def flip_cost(grest):
    nk = FX['kauf'] * (grest + notar_pct) / 100
    basis = FX['kauf'] + fx_san
    fk = basis * FX['fk']
    zins = fk * fk_zins / 100 * FX['monate'] / 12
    zins_vj = fk * fk_zins_vj / 100 * FX['monate'] / 12
    ek = basis - fk + nk
    return dict(nk=nk, fk=fk, zins=zins, zins_vj=zins_vj, ek=ek, total=FX['kauf'] + fx_san + nk + zins)
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
    r['spread'] = (s['jung'] - s['san']) if (s.get('jung') and s.get('san')) else None
    r['abschlag'] = (s['san'] / s['qm'] - 1) * 100 if s.get('san') else None
    r['gap'] = s['rend'] - bz
    r['leist_qm'] = darl_med / s['qm']
    rows.append(r)
rows.sort(key=lambda r: -r['qm'])
n_total = sum(r['n'] for r in rows)
robust = [r for r in rows if r['spread'] is not None and r['san_n'] >= 8 and r['jung_n'] >= 8]
top_spread = sorted(robust, key=lambda r: -r['spread'])
top_rend = sorted(rows, key=lambda r: -r['rend'])
over_mw = sum(1 for r in rows if r['disc'] < 0)

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
    lo, hi = 0, max(a + b) * 1.18
    l, bt, top = 40, 40, 30
    cw = (w - l - 10) / len(cats)
    Y = lambda v: top + (hi - v) / (hi - lo) * (h - bt - top)
    o = []
    for g in range(0, int(hi) + 1):
        o.append(f'<line x1="{l}" x2="{w-10}" y1="{Y(g)}" y2="{Y(g)}" stroke="{LINE}"/><text x="{l-8}" y="{Y(g)+4}" font-size="10" text-anchor="end" fill="{MUT}">{g}</text>')
    bw = cw * 0.28
    for i, c in enumerate(cats):
        cx = l + cw * i + cw / 2
        for j, (v, col) in enumerate([(a[i], '#9cc9cc'), (b[i], TD)]):
            x = cx - bw - 3 + j * (bw + 6)
            o.append(f'<rect x="{x}" y="{Y(v)}" width="{bw}" height="{Y(0)-Y(v)}" rx="3" fill="{col}"/>')
            o.append(f'<text x="{x+bw/2}" y="{Y(v)-6}" font-size="10" font-weight="700" text-anchor="middle" fill="{INK}">{de(v,dec)}</text>')
        o.append(f'<text x="{cx}" y="{h-bt+18}" font-size="10.5" text-anchor="middle" fill="{INK}">{c}</text>')
    o.append(f'<rect x="{l}" y="4" width="12" height="12" rx="2" fill="#9cc9cc"/><text x="{l+18}" y="14" font-size="10.5" fill="{MUT}">{la}</text>')
    o.append(f'<rect x="{l+150}" y="4" width="12" height="12" rx="2" fill="{TD}"/><text x="{l+168}" y="14" font-size="10.5" fill="{MUT}">{lb}</text>')
    return svg(w, h, ''.join(o))

def line_chart(pts, lo, hi, w=640, h=180, dec=2, unit=' %'):
    l, b, top = 46, 30, 26
    step = (w - l - 30) / (len(pts) - 1)
    X = lambda i: l + 34 + i * (w - l - 70) / (len(pts) - 1)
    Y = lambda v: top + (hi - v) / (hi - lo) * (h - b - top)
    o = []
    g = lo
    while g <= hi + 1e-9:
        o.append(f'<line x1="{l}" x2="{w-10}" y1="{Y(g)}" y2="{Y(g)}" stroke="{LINE}"/><text x="{l-8}" y="{Y(g)+4}" font-size="10" text-anchor="end" fill="{MUT}">{de(g,1)}</text>')
        g += 0.2
    o.append('<path d="' + ' '.join(f"{'M' if i == 0 else 'L'}{X(i)},{Y(v)}" for i, (_, v) in enumerate(pts)) + f'" fill="none" stroke="{TD}" stroke-width="2.5"/>')
    for i, (k, v) in enumerate(pts):
        o.append(f'<circle cx="{X(i)}" cy="{Y(v)}" r="4.5" fill="{TD}"/>')
        o.append(f'<text x="{X(i)}" y="{Y(v)-12}" font-size="11" font-weight="700" text-anchor="middle" fill="{INK}">{de(v,dec)}{unit}</text>')
        o.append(f'<text x="{X(i)}" y="{h-8}" font-size="10.5" text-anchor="middle" fill="{MUT}">{k}</text>')
    return svg(w, h, ''.join(o))

GEO = json.load(open(R/'assets/germany.geojson'))
PADX = 70
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
    for x, y, rad, r in dots:
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
    return f'<div class="kpis c{cols or len(k)}">{"".join(k)}</div>'
def note(t, title='Einordnung für Flipper'):
    return f'<div class="note avoid"><b>{title}:</b> {t}</div>'
def src(t):
    return f'<p class="src">{t}</p>'
def block(title, inner):
    return f'<div class="block avoid"><h3>{title}</h3>{inner}</div>'

SRC = []
def cite(name, detail, url):
    SRC.append((name, detail, url))

# ---------- Cover ----------
cover = f'''<section class="cover-page">
<div class="cover"><img class="clogo" src="data:image/png;base64,{LOGO_W}"/>
<div class="kicker">Ausgabe 01 · Stand 7. November 2026</div>
<h1>Immobilienhandel-Marktreport</h1><div class="sub">Fix-und-Flip · Ausgabe November 2026</div>
<p class="lead">Zinsen, Finanzierung, Preise, Angebotsdaten aus {len(rows)} Städten, Baukosten, Zielgruppe und Demografie. Zusammengeführt aus {de(n_total)} aktiven Wohnungsinseraten der Leverage-Datenbank und über 30 amtlichen und institutionellen Quellen.</p></div>
<h2 class="first">Die Lage in sechs Zahlen</h2>
{kpis(
 kpi(de(bz,2)+' %', 'Bauzins 10 Jahre+', f'Sep 2026, Vorjahr {de(bz_vj,2)} %'),
 kpi(de(F['euribor']['m3'],2)+' %', '3-Monats-Euribor', f'05.11.2026, Nov 2025 Ø {de(F["euribor"]["m3_nov25"],2)} %'),
 kpi(de(kaufkraft,1).replace('-', '−')+' %', 'Darlehensbudget Käufer', 'bei gleicher Rate wie vor 12 Monaten'),
 cols=3)}
{kpis(
 kpi(sg(P['greix']['etw_yoy'])+' %', 'Wohnungspreise ggü. Vorjahr', 'GREIX Q3 2026, nominal'),
 kpi(sg(G['mieten']['greix_yoy'])+' %', 'Angebotsmieten ggü. Vorjahr', 'GREIX Q3 2026'),
 kpi(sg(P['baupreise']['instand_yoy'])+' %', 'Instandhaltungspreise', 'Aug 2026 ggü. Vorjahr'),
 cols=3)}
<h2>Kurzfassung</h2>
<ul class="sum">
<li>Der Käufer am Ende hat weniger Budget. Bei gleicher Monatsrate wie vor einem Jahr finanziert ein Haushalt heute {de(abs(kaufkraft),1)} % weniger Darlehen. Ein Haushalt mit Medianeinkommen ({de(ek_med)} € netto) kommt bei 35 % Belastung auf rund {de(darl_med,-3)} € Darlehen, der durchschnittliche Baufinanzierungskredit liegt bei {de(F['dtb']['darlehen'],-3)} €.</li>
<li>Kurzfristiges Geld ist teurer als langfristiges. Variable Wohnungsbaukredite kosten {de(F['mfi_wohnen']['sep26']['var'],2)} %, zehnjährige {de(F['mfi_wohnen']['sep26']['j10'],2)} %. Für die Projektfinanzierung des Flips ist das der teuerste Teil der Zinskurve.</li>
<li>Kaufpreise geben nach, Mieten steigen. Wohnungen sind nominal {de(abs(P['greix']['etw_yoy']),1)} % günstiger als vor einem Jahr, Angebotsmieten {de(G['mieten']['greix_yoy'],1)} % teurer. Das verbessert die Rendite für Kapitalanleger als Käufer.</li>
<li>Sanierung kostet {de(P['baupreise']['instand_yoy'],1)} % mehr. Gleichzeitig sinken die Wohnungspreise, die Marge hängt damit stärker am Einkaufspreis.</li>
<li>Die Flip-Spanne ist regional sehr unterschiedlich. Zwischen sanierungsbedürftigen Wohnungen und Bestand der Baujahre 1995 bis 2020 liegen je nach Stadt {de(min(r['spread'] for r in robust))} bis {de(max(r['spread'] for r in robust))} € je m².</li>
<li>Die Erbengeneration verkauft. 2025 wurden steuerlich {de(G['erbe']['grundvermoegen'],1)} Mrd. € Grundvermögen übertragen, {sg(G['erbe']['grund_yoy'])} % mehr als im Vorjahr. Bis 2039 erreichen {de(G['boomer']['erwerbspersonen_rente_bis_2039'],1)} Mio. Erwerbspersonen das Rentenalter.</li>
</ul>
<div class="toc avoid"><h3>Inhalt</h3><ol>
<li>Zinsen und Finanzierungsumfeld</li><li>Zwei Seiten der Finanzierung: Flipper und Käufer</li><li>Kaufnebenkosten und Förderung</li>
<li>Preise und Mieten</li><li>Angebotsmarkt Deutschland: {len(rows)} Städte</li><li>Leistbarkeit: Was sich der Käufer leisten kann</li>
<li>Baukosten, Energie und Regulierung</li><li>Zielgruppe: Haushalte, Einkommen, Wohnfläche</li><li>Demografie, Ruhestand und Erben</li>
<li>Steuern und Recht für Flipper</li><li>Methodik und Quellen</li></ol></div>
</section>'''

# ---------- 1 Zinsen ----------
mw, mv = F['mfi_wohnen']['sep26'], F['mfi_wohnen']['sep25']
cite('Deutsche Bundesbank', 'MFI-Zinsstatistik, Wohnungsbaukredite an private Haushalte nach Zinsbindung, Stand 02.11.2026', F['mfi_wohnen']['url'])
cite('Deutsche Bundesbank', 'MFI-Zinsstatistik, Kredite an nichtfinanzielle Kapitalgesellschaften, Stand 02.11.2026', F['mfi_unternehmen']['url'])
cite('Deutsche Bundesbank', 'Geldmarktsätze, Euribor (Quelle EMMI), Stand 06.11.2026', F['euribor']['url'])
cite('Europäische Zentralbank', 'Geldpolitische Beschlüsse vom 29.10.2026', P['ezb']['url'])
s1 = f'''<section class="sec brk"><h2>1 · Zinsen und Finanzierungsumfeld</h2>
<p class="intro">Variable Zinsen bestimmen die Kosten der Projektfinanzierung, Zinsen mit 10 Jahren Bindung das Budget der Käuferinnen und Käufer.</p>
{kpis(kpi(de(bz,2)+' %','Bauzins über 10 Jahre','Sep 2026, Bundesbank'),
      kpi(de(mw['var'],2)+' %','Wohnungsbaukredit variabel','bis 1 Jahr Zinsbindung, Sep 2026'),
      kpi(de(F['mfi_unternehmen']['bis1mio_var_sep26'],2)+' %','Unternehmenskredit variabel','bis 1 Mio. €, Sep 2026'), cols=3)}
{kpis(kpi(de(F['euribor']['m3'],2)+' %','3-Monats-Euribor','Tageswert 05.11.2026'),
      kpi(de(F['euribor']['m6'],2)+' %','6-Monats-Euribor','Tageswert 05.11.2026'),
      kpi(de(P['ezb']['einlage'],2)+' %','EZB-Einlagesatz','zuletzt am 29.10. unverändert'), cols=3)}
{block('Effektivzins Wohnungsbaukredite nach Zinsbindung, Sep 2025 und Sep 2026', grouped(['variabel bis 1 J.','1 bis 5 J.','5 bis 10 J.','über 10 J.'],[mv['var'],mv['j1_5'],mv['j5_10'],mv['j10']],[mw['var'],mw['j1_5'],mw['j5_10'],mw['j10']],'September 2025','September 2026'))}
{src('Quelle: Deutsche Bundesbank, MFI-Zinsstatistik, Neugeschäft, Effektivzinssatz.')}
{block('Bauzins über 10 Jahre im Verlauf', line_chart([('Okt 25',P['bauzins']['okt25']),('Jan 26',P['bauzins']['jan26']),('Jul 26',P['bauzins']['jul26']),('Aug 26',P['bauzins']['aug26']),('Sep 26',P['bauzins']['sep26'])], 3.6, 4.4))}
{src('Quelle: Deutsche Bundesbank. Ausgewiesene Monate, keine durchgehende Reihe.')}
{note(f'Der 3-Monats-Euribor, an dem variable Darlehen und viele Projektfinanzierungen hängen, liegt bei {de(F["euribor"]["m3"],2)} % nach {de(F["euribor"]["m3_nov25"],2)} % im Durchschnitt November 2025. Das sind {de(F["euribor"]["m3"]-F["euribor"]["m3_nov25"],2)} Prozentpunkte mehr. Die EZB hat den Einlagesatz am 10.09.2026 auf {de(P["ezb"]["einlage"],2)} % erhöht. Variable Wohnungsbaukredite sind mit {de(mw["var"],2)} % teurer als Kredite mit 5 bis 10 Jahren Bindung ({de(mw["j5_10"],2)} %). Jeder Monat Projektlaufzeit läuft damit zum höchsten Satz der Zinskurve.')}
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
           (f'Zinskosten {FX["monate"]} Monate bei {de(fk_zins,2)} %', a['zins'], b['zins']),
           (f'Zinskosten vor einem Jahr ({de(fk_zins_vj,2)} %)', a['zins_vj'], b['zins_vj']),
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
s2 = f'''<section class="sec"><h2>2 · Zwei Seiten der Finanzierung: Flipper und Käufer</h2>
<p class="intro">Seite A rechnet eine Projektfinanzierung mit variablem Unternehmenskredit, Seite B eine Eigennutzer-Finanzierung mit 10 Jahren Zinsbindung. Die Annahmen stehen unter der jeweiligen Tabelle.</p>
{block('Seite A: Was der Flipper finanziert (Rechenbeispiel Wohnung)', ftab(flip_by, flip_nw, 'Bayern (3,5 % GrESt)', 'NRW (6,5 % GrESt)'))}
{src(f'Annahmen: Kaufpreis {de(FX["kauf"])} €, {FX["qm"]} m², Sanierung {de(FX["san_qm"])} € je m², Haltedauer {FX["monate"]} Monate, Zins wie Bundesbank-Durchschnitt für variable Unternehmenskredite bis 1 Mio. € (Sep 2026 bzw. Sep 2025). Individuelle Konditionen liegen bei Projektfinanzierungen oft darüber.')}
{note(f'Die Zinskosten des Projekts sind binnen eines Jahres um rund {de(flip_by["zins"]-flip_by["zins_vj"],-1)} € gestiegen. Jeder zusätzliche Monat Haltedauer kostet im Beispiel rund {de(flip_by["zins"]/FX["monate"])} €. Zwischen Bayern und NRW liegen allein bei der Grunderwerbsteuer {de(flip_nw["nk"]-flip_by["nk"])} € Unterschied, die vor Verkauf als Eigenkapital gebunden sind.')}
{block('Seite B: Was der Käufer finanziert (Rechenbeispiel Eigennutzer)', btab(buy_by, buy_nw, 'Bayern', 'NRW'))}
{src(f'Annahmen: Kaufpreis {de(KX["preis"])} €, Beleihungsauslauf {de(KX["bel"],1)} % und Tilgung {de(tilg,2)} % entsprechen dem Durchschnitt laut Dr. Klein Trendindikator (2. Tertial 2026), Zins laut Bundesbank (über 10 Jahre, Sep 2026). Makler nicht berücksichtigt.')}
{kpis(kpi(de(F['dtb']['darlehen'])+' €','Ø Darlehenshöhe','Dr. Klein, Mai bis Aug 2026'),
      kpi(de(F['dtb']['beleihung'],1)+' %','Ø Beleihungsauslauf','Dr. Klein, Mai bis Aug 2026'),
      kpi(de(F['dtb']['tilgung'],2)+' %','Ø anfängliche Tilgung', F['dtb']['zinsbindung']+' Zinsbindung'), cols=3)}
{block('Was sich verändert hat', f'<table class="t"><thead><tr><th></th><th>Sep 2025</th><th>Sep 2026</th><th>Differenz</th></tr></thead><tbody><tr><td class="c">Monatsrate für {de(darl)} € Darlehen</td><td>{de(rate_vj,2)} €</td><td>{de(rate_now,2)} €</td><td class="b neg">{sg(rate_now-rate_vj,2)} €</td></tr><tr><td class="c">Darlehen bei Rate von {de(rate_vj,2)} €</td><td>{de(darl)} €</td><td>{de(darl_gleich)} €</td><td class="b neg">{sg(darl_gleich-darl)} €</td></tr></tbody></table>')}
{note(f'Ein Käufer braucht im Beispiel {de(buy_by["ek"])} € (Bayern) bis {de(buy_nw["ek"])} € (NRW) eigenes Geld. Wer heute dieselbe Rate wie vor einem Jahr tragen kann, bekommt {de(abs(kaufkraft),1)} % weniger Darlehen. Vergleichspreise aus 2025 überschätzen deshalb das heutige Käuferbudget.')}
</section>'''

# ---------- 3 Nebenkosten / Förderung ----------
cite('ImmoScout24', 'Medieninformation Grunderwerbsteuer im Bundesländervergleich, 07.05.2026', F['grest']['url'])
cite('KfW', 'Merkblatt Wohneigentum für Familien Bestandserwerb (308), Stand 08/2026', F['kfw308']['url'])
cite('KfW', 'Merkblatt BEG Wohngebäude Kredit (261), Stand 09/2026', F['kfw261']['url'])
gr = sorted([(k, v) for k, v in F['grest'].items() if k not in ('quelle', 'url')], key=lambda x: -x[1])
s3 = f'''<section class="sec"><h2>3 · Kaufnebenkosten und Förderung</h2>
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
s4 = f'''<section class="sec"><h2>4 · Preise und Mieten</h2>
<p class="intro">Drei Kaufpreisindizes mit unterschiedlicher Methode (Notarverträge, Finanzierungsfälle, amtliche Transaktionsdaten) und zwei Mietindikatoren.</p>
{kpis(kpi(sg(P['greix']['etw_qoq'])+' %','GREIX ETW ggü. Vorquartal','Q3 2026, nominal'),
      kpi(sg(P['greix']['etw_yoy'])+' %','GREIX ETW ggü. Vorjahr',f'real {sg(P["greix"]["etw_real_yoy"])} %'),
      kpi(sg(P['epx']['etw_yoy'],2)+' %','Europace ETW ggü. Vorjahr','Sep 2026'), cols=3)}
{kpis(kpi(sg(P['epx']['neubau_yoy'],2)+' %','Europace Neubauhäuser','Sep 2026 ggü. Vorjahr'),
      kpi(sg(G['mieten']['greix_yoy'])+' %','Angebotsmieten (GREIX)','Q3 2026 ggü. Vorjahr'),
      kpi(sg(G['mieten']['vpi_nettokalt_sep'])+' %','Nettokaltmieten (VPI)','Sep 2026 ggü. Vorjahr'), cols=3)}
{block('Eigentumswohnungen nach Großstadt, Veränderung zum Vorquartal (GREIX Q3 2026)', bars(list(P['greix']['staedte_qoq'].items())))}
{src('Quelle: Kiel Institut, GREIX. Hamburg und München in der Veröffentlichung nicht separat ausgewiesen.')}
{block('Eigentumswohnungen nach Kreistyp, Veränderung zum Vorjahresquartal (Destatis Q2 2026)', bars(list(hpi.items()), lab=300))}
{src('Quelle: Destatis, Häuserpreisindex, Pressemitteilung Nr. 336 vom 24.09.2026.')}
{block('Angebotsmieten nach Großstadt, Veränderung zum Vorjahr (GREIX Q3 2026)', bars(sorted(G['mieten']['staedte'].items(), key=lambda x: -x[1])))}
{src('Quelle: GREIX-Mietpreisindex, Kiel Institut, Meldung vom 15.10.2026, abgerufen über epd. Angebotsmieten, keine Bestandsmieten.')}
{note(f'Wohnungen nominal {sg(P["greix"]["etw_yoy"])} %, Angebotsmieten {sg(G["mieten"]["greix_yoy"])} %. Die Bruttorendite für Kapitalanleger steigt dadurch, am stärksten in Hamburg, Düsseldorf und Köln. Kreisfreie Großstädte außerhalb der Metropolen legen bei Wohnungspreisen zu ({sg(hpi["Kreisfreie Großstädte außerhalb der Metropolen"])} %), dicht besiedelte ländliche Kreise verlieren ({sg(hpi["Dicht besiedelte ländliche Kreise"])} %).')}
</section>'''

# ---------- 5 Angebotsmarkt ----------
cite('Leverage Immo GmbH', f'Eigene Auswertung von {de(n_total)} aktiven Wohnungsinseraten in {len(rows)} Städten, Abruf 07.11.2026', 'https://leverage.immo')
qm_breaks = [2500, 3500, 4500, 6000]
rend_breaks = [4.0, 4.5, 5.0, 6.0]
def city_table(rs):
    body = ''
    for r in rs:
        warn_s = ' ⚠' if r['san'] is not None and r['san_n'] < 10 else ''
        warn_j = ' ⚠' if r['jung'] is not None and r['jung_n'] < 10 else ''
        body += (f'<tr><td class="c">{r["c"]}<span class="r">{r["r"]} km</span></td><td>{de(r["n"])}</td><td class="b">{de(r["qm"])} €</td>'
                 f'<td>{na(r["san"], lambda v: de(v)+" €")}<span class="r">n={r["san_n"]}{warn_s}</span></td>'
                 f'<td>{na(r["jung"], lambda v: de(v)+" €")}<span class="r">n={r["jung_n"]}{warn_j}</span></td>'
                 f'<td class="b">{na(r["spread"], lambda v: de(v)+" €")}</td><td>{de(r["rend"],2)} %</td><td>{sg(-r["disc"],1)} %</td></tr>')
    return ('<table class="t sm"><thead><tr><th>Stadt</th><th>Inserate</th><th>Median €/m²</th><th>Sanierungs&shy;bedürftig</th><th>Baujahr 1995 bis 2020</th>'
            f'<th>Spread</th><th>Brutto&shy;rendite</th><th>Angebot ggü. Marktwert</th></tr></thead><tbody>{body}</tbody></table>')
half = (len(rows) + 1) // 2
s5 = f'''<section class="sec brk"><h2>5 · Angebotsmarkt Deutschland: {len(rows)} Städte</h2>
<p class="intro">Exklusive Auswertung aus der Leverage-Datenbank: {de(n_total)} aktive Wohnungsinserate, abgerufen am 07.11.2026. Medianwerte im Umkreis um das jeweilige Stadtzentrum.</p>
{kpis(kpi(de(n_total),'Ausgewertete Inserate',f'{len(rows)} Städte, alle Bundesländer'),
      kpi(f'{over_mw} von {len(rows)}','Städte mit Angeboten über Marktwert','Median Angebot ggü. Leverage-Bewertung'),
      kpi(de(top_rend[0]['rend'],1)+' %',f'Höchste Bruttorendite',top_rend[0]['c']), cols=3)}
<div class="block avoid"><h3>Median-Angebotspreis Eigentumswohnungen, € je m²</h3><div class="mapw">{de_map(rows,'qm',lambda v: de(v),'€ je m²',qm_breaks)}</div></div>
{src('Kreisgröße nach Anzahl der Inserate. Alle Werte stehen zusätzlich in der Tabelle.')}
<div class="block avoid"><h3>Bruttomietrendite (Median), %</h3><div class="mapw">{de_map(rows,'rend',lambda v: de(v,1)+" %",'Bruttorendite',rend_breaks)}</div></div>
{src('Bruttorendite: Leverage-Mietschätzung (Jahreskaltmiete) geteilt durch Angebotspreis, Median der Inserate mit Bewertung.')}
<div class="block"><h3>Alle Städte im Überblick (sortiert nach Preis je m²)</h3>{city_table(rows)}</div>
{src('Spread: Median Baujahr 1995 bis 2020 minus Median sanierungsbedürftig, nur wo beide Werte vorliegen (mindestens 5 Inserate). ⚠ = unter 10 Inserate, Wert schwankt stärker. Angebot ggü. Marktwert: Positiver Wert heißt teurer angeboten als die Leverage-Bewertung. Radius 5 km, in sehr großen Märkten 2 bis 3 km (Kernstadt). Angebotspreise sind keine Kaufpreise.')}
{block('Größte Flip-Spanne je m² (mindestens 8 Inserate je Gruppe)', bars([(r['c'], r['spread']) for r in top_spread[:12]], ' €', dec=0, signed=False, lab=200))}
{block('Höchste Bruttomietrenditen (Median)', bars([(r['c'], r['rend']) for r in top_rend[:12]], ' %', dec=2, signed=False, lab=200, vmin=0))}
{note(f'Die größten Spannen zwischen sanierungsbedürftigem und gutem Bestand finden sich in {", ".join(r["c"] for r in top_spread[:3])}. Die höchsten Renditen liegen in ostdeutschen Märkten mit niedrigen Preisen je m² wie {", ".join(r["c"] for r in top_rend[:3])}. Dort sind die Inseratszahlen allerdings klein und die Nachfrage durch Abwanderung belastet. In {over_mw} von {len(rows)} Städten liegt der Median der Angebote über der Leverage-Bewertung. Dort lohnt die Preisverhandlung mit dem Bewertungsergebnis in der Hand.')}
</section>'''

# ---------- 6 Leistbarkeit ----------
leist = sorted(rows, key=lambda r: -r['leist_qm'])
s6 = f'''<section class="sec"><h2>6 · Leistbarkeit: Was sich der Käufer leisten kann</h2>
<p class="intro">Der erzielbare Verkaufspreis hängt am Darlehen, das ein typischer Haushalt bekommt. Die Rechnung geht vom Median-Haushaltsnettoeinkommen aus.</p>
{kpis(kpi(de(ek_med)+' €','Median-Haushaltsnettoeinkommen','pro Monat, EU-SILC 2025'),
      kpi(de(rate_med)+' €','Rate bei 35 % Belastung','Annahme für die Rechnung'),
      kpi(de(darl_med,-3)+' €','Darlehen daraus',f'{de(bz,2)} % Zins, {de(tilg,2)} % Tilgung'), cols=3)}
{block('Wie viele m² ein Median-Haushalt allein mit Darlehen finanzieren kann', bars([(r['c'], r['leist_qm']) for r in leist[:12]] + [(r['c'], r['leist_qm']) for r in leist[-8:]], ' m²', dec=0, signed=False, lab=200, rowh=24))}
{src(f'Rechnung: Darlehen von {de(darl_med,-3)} € geteilt durch Median-Angebotspreis je m² der Stadt. Ohne Eigenkapital und Kaufnebenkosten. Oben die 12 günstigsten, unten die 8 teuersten Märkte der Auswertung. Zum Vergleich: Eine durchschnittliche Wohnung in Deutschland hat {de(Z["flaeche"]["je_wohnung"],1)} m².')}
{note(f'Ein Haushalt mit Medianeinkommen finanziert in München rund {de(S["München"]["qm"] and darl_med/S["München"]["qm"])} m², in Leipzig rund {de(darl_med/S["Leipzig"]["qm"])} m². Vor einem Jahr wären es bei gleicher Rate {de((darl_med_vj/darl_med-1)*100,1)} % mehr gewesen. In teuren Märkten erreichen deshalb Wohnungen mit 1 bis 2 Zimmern die meisten zahlungsfähigen Haushalte. In günstigen Märkten reicht das Budget für Familienwohnungen.')}
{block('Wohnkostenbelastung der Haushalte', bars([('Alle Haushalte 2025',Z['wohnkosten']['anteil25']),('Alleinlebende',Z['wohnkosten']['allein']),('Alleinerziehende',Z['wohnkosten']['alleinerz']),('Mieterhaushalte 2022 (Bruttokaltmiete)',Z['mietbelastung']['schnitt'])], ' %', signed=False, lab=280, vmin=0))}
{src('Quellen: Destatis, Anteil der Wohnkosten am verfügbaren Haushaltseinkommen (EU-SILC 2025); Mietbelastungsquote Mikrozensus 2022.')}
{block('Mietbelastung nach Haushaltsnettoeinkommen (Mikrozensus 2022)', bars(list(Z['mietbelastung']['nach_einkommen'].items()), ' %', signed=False, lab=200, vmin=0))}
{note(f'Im Schnitt geben Haushalte {de(Z["wohnkosten"]["anteil25"],1)} % ihres verfügbaren Einkommens für Wohnen aus, {de(Z["wohnkosten"]["ueber40_25"],1)} % der Bevölkerung mehr als 40 %. Mieterhaushalte mit unter 1.500 € Einkommen zahlen {de(Z["mietbelastung"]["nach_einkommen"]["unter 1.500 €"],1)} %. Eigennutzer als Käufer kommen damit überwiegend aus der oberen Einkommenshälfte. Bei Verkauf an Kapitalanleger sollte die angesetzte Miete im Zielquartier tragbar bleiben.')}
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
s7 = f'''<section class="sec"><h2>7 · Baukosten, Energie und Regulierung</h2>
{kpis(kpi(sg(P['baupreise']['instand_yoy'])+' %','Instandhaltung Wohngebäude','Aug 2026 ggü. Vorjahr'),
      kpi(de(Z['fertig']['2025']),'Fertiggestellte Wohnungen 2025',f'{sg(Z["fertig"]["yoy"])} % ggü. 2024'),
      kpi(de(P['baugen']['jan_aug']),'Genehmigte Wohnungen',f'Jan bis Aug 2026, {sg(P["baugen"]["jan_aug_yoy"])} %'), cols=3)}
{block('Preisanstieg einzelner Gewerke, Aug 2026 ggü. Vorjahr', bars([('Dachdeckerarbeiten',P['baupreise']['dach']),('Zimmer- und Holzbau',P['baupreise']['zimmer']),('Elektro, Sicherheit, IT',P['baupreise']['elektro']),('Erdarbeiten',P['baupreise']['erd']),('Instandhaltung gesamt',P['baupreise']['instand_yoy']),('Neubau Wohngebäude gesamt',P['baupreise']['wohn_yoy']),('Heizung inkl. Wärmepumpe',P['baupreise']['heizung'])], vmin=0, lab=220))}
{src('Quelle: Destatis, Baupreisindex, PM Nr. 360 vom 09.10.2026.')}
{block('Womit Deutschlands Wohnungen heizen (Zensus 2022)', bars(heiz, ' %', dec=0, signed=False, lab=260, vmin=0))}
{src('Quelle: Destatis, Zensus 2022, Anteil der Wohnungen nach überwiegendem Energieträger. Stichtag 15.05.2022.')}
{block('Was sich bei Heizung und CO2 geändert hat', f"""<table class="t"><tbody>
<tr><td class="c">Gebäudemodernisierungsgesetz</td><td>{G['geg']['status']}. {G['geg']['kern']}.</td></tr>
<tr><td class="c">Nationaler CO2-Preis</td><td>Preiskorridor {G['co2']['2026']} € je Tonne für 2026, für 2027 laut Bundestagsbeschluss vom 15.10.2026 ebenfalls {G['co2']['2027']} €.</td></tr>
<tr><td class="c">EU-Emissionshandel für Gebäude (ETS 2)</td><td>Start um ein Jahr auf {G['co2']['ets2']} verschoben.</td></tr></tbody></table>""")}
{note(f'Drei Viertel aller Wohnungen heizen mit Gas oder Öl. Mit dem neuen Gesetz entfällt die Pflicht zu 65 % erneuerbarer Wärme bei neuen Heizungen, der Druck kommt künftig über den CO2-Preis und die Grüngasquote ab 2028. Für die Kalkulation: Den Heizungstausch nicht pauschal einplanen, sondern nach Käufergruppe entscheiden. Dach und Elektro sind die Gewerke mit dem stärksten Preisanstieg und sollten früh festgepreist werden.')}
{block('Rechenbeispiel Baukosten', f'<p>Eine {FX["qm"]}-m²-Wohnung mit {de(FX["san_qm"])} € Sanierungsbudget je m² kostet bei {sg(P["baupreise"]["instand_yoy"])} % Preissteigerung rund <b>{de(fx_san*P["baupreise"]["instand_yoy"]/100)} € mehr</b> als vor einem Jahr. Wohnungspreise sind laut GREIX im selben Zeitraum um {de(abs(P["greix"]["etw_yoy"]),1)} % gesunken. Gleichzeitig wurden 2025 nur {de(Z["fertig"]["2025"])} Wohnungen fertiggestellt, {de(Z["fertig"]["genehmigt_nicht_fertig"])} genehmigte Wohnungen sind noch nicht gebaut. Das Neubauangebot bleibt knapp, sanierter Bestand ist die Alternative.</p>')}
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
s8 = f'''<section class="sec"><h2>8 · Zielgruppe: Haushalte, Einkommen, Wohnfläche</h2>
{kpis(kpi(de(Z['flaeche']['je_wohnung'],1)+' m²','Ø Wohnfläche je Wohnung','Bestand Ende 2025'),
      kpi(de(Z['flaeche']['je_person'],1)+' m²','Ø Wohnfläche je Person','Bestand Ende 2025'),
      kpi(de(Z['flaeche']['neubau25'],1)+' m²','Ø Neubauwohnung 2025',f'2007: {de(Z["flaeche"]["neubau07"],1)} m²'), cols=3)}
{kpis(kpi(de(Z['haushalte']['single'],1)+' %','Einpersonenhaushalte','2025, Anteil aller Haushalte'),
      kpi(sg(Z['loehne']['real'])+' %','Reallöhne','Q2 2026 ggü. Vorjahr'),
      kpi(de(Z['alq']['okt26'],1)+' %','Arbeitslosenquote',f'Okt 2026, Vorjahr {de(Z["alq"]["okt25"],1)} %'), cols=3)}
{block('Wohnfläche Eigentümer und Mieter (Mikrozensus 2022)', f'<table class="t"><thead><tr><th></th><th>je Wohnung</th><th>je Person</th></tr></thead><tbody><tr><td class="c">Eigentümerhaushalte</td><td>{de(Z["flaeche"]["eig_wohnung"],1)} m²</td><td>{de(Z["flaeche"]["eig_person"],1)} m²</td></tr><tr><td class="c">Mieterhaushalte</td><td>{de(Z["flaeche"]["miet_wohnung"],1)} m²</td><td>{de(Z["flaeche"]["miet_person"],1)} m²</td></tr></tbody></table>')}
{block('Eigentumsquote nach Bundesland (Mikrozensus 2022, Anteil Eigentümerhaushalte)', bars(eig, ' %', signed=False, lab=200, rowh=24, vmin=0))}
{src('Quelle: Destatis, Eigentumsquote, Mikrozensus Zusatzprogramm Wohnen 2022. Deutschland gesamt '+de(Z['eigentum']['de'],1)+' %.')}
{note(f'{de(Z["haushalte"]["single"],1)} % aller Haushalte sind Einpersonenhaushalte, weitere {de(Z["haushalte"]["zwei"],1)} % Zweipersonenhaushalte. Eigentümer wohnen auf {de(Z["flaeche"]["eig_wohnung"],1)} m², Mieter auf {de(Z["flaeche"]["miet_wohnung"],1)} m². Wer Eigentumswohnungen für Eigennutzer flippt, trifft mit 2 bis 3 Zimmern und 55 bis 80 m² die größte Käufergruppe, wenn das Budget aus Abschnitt 6 reicht. In Ländern mit niedriger Eigentumsquote wie Berlin, Hamburg und Sachsen ist der Kapitalanleger häufiger der Käufer.')}
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
s9 = f'''<section class="sec"><h2>9 · Demografie, Ruhestand und Erben</h2>
<p class="intro">Die geburtenstarken Jahrgänge 1955 bis 1969 gehen in den Ruhestand. Daraus folgen mehr Verkäufe und mehr Erbfälle mit unsanierten Objekten.</p>
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
{note(f'Die Erbschaftsteuerstatistik erfasst nur Fälle oberhalb der Freibeträge, das tatsächliche Volumen ist deutlich höher. Das DIW schätzt für 2002 bis 2017 im Schnitt {de(G["diw"]["wert"])} Mrd. € pro Jahr und hält das für eher unterschätzt. Erbimmobilien sind häufig unsaniert, und die Erben wohnen oft nicht vor Ort. Gleichzeitig verlieren Thüringen und Sachsen-Anhalt Einwohner, Brandenburg, Bayern und Schleswig-Holstein gewinnen. Hohe Renditen in schrumpfenden Regionen gehen mit Leerstandsrisiko beim Exit einher. Die Zahl der Haushalte sinkt laut Destatis bis 2050 auf {de(G["haushalte"]["2050_von"],1)} bis {de(G["haushalte"]["2050_bis"],1)} Mio. (2024: {de(G["haushalte"]["2024"],1)} Mio.).')}
</section>'''

# ---------- 10 Steuer & Recht ----------
cite('Bundesministerium der Justiz', '§ 23 EStG, Private Veräußerungsgeschäfte, gesetze-im-internet.de', G['steuer']['p23'])
cite('Bundesministerium der Finanzen', G['steuer']['bmf'] + ' (Abgrenzung private Vermögensverwaltung und gewerblicher Grundstückshandel)', 'https://datenbank.nwb.de/Dokument/129733/')
s10 = f'''<section class="sec"><h2>10 · Steuern und Recht für Flipper</h2>
{block('Die zwei Regeln, die jeder Flipper kennen muss', f"""<table class="t"><tbody>
<tr><td class="c">Spekulationsfrist (§ 23 EStG)</td><td>Gewinne aus dem Verkauf privater Immobilien sind steuerpflichtig, wenn zwischen Kauf und Verkauf nicht mehr als zehn Jahre liegen. Ausnahme: Ausschließliche Eigennutzung zwischen Kauf und Verkauf oder im Verkaufsjahr und den beiden Jahren davor.</td></tr>
<tr><td class="c">Drei-Objekt-Grenze</td><td>Wer innerhalb von etwa fünf Jahren mehr als drei Objekte kauft und wieder verkauft, gilt in der Regel als gewerblicher Grundstückshändler. Dann fällt Gewerbesteuer an, und auch die ersten drei Verkäufe zählen mit. Die Grenze ist ein Indiz, keine starre Regel ({G['steuer']['bmf']}).</td></tr></tbody></table>""")}
{note('Wer regelmäßig flippt, plant von Anfang an mit gewerblichem Grundstückshandel und klärt mit der Steuerberatung, ob die Flips in einer GmbH laufen sollten. Dieser Abschnitt ersetzt keine steuerliche Beratung im Einzelfall.', 'Hinweis')}
</section>'''

# ---------- Methodik / Quellen ----------
seen, src_items = set(), []
for a, b, c in SRC:
    if (a, b) in seen:
        continue
    seen.add((a, b)); src_items.append((a, b, c))
src_html = ''.join(f'<li>{a} · {b}<br><span class="url">{c}</span></li>' for a, b, c in src_items)
s11 = f'''<section class="sec brk"><h2>11 · Methodik und Quellen</h2>
<p>Jede Zahl in diesem Report stammt aus einer der unten genannten Quellen oder ist eine nachvollziehbare Berechnung daraus. Annahmen in Rechenbeispielen sind direkt beim Beispiel genannt. Amtliche Daten erscheinen mit Verzögerung, deshalb steht bei jeder Kennzahl der Bezugszeitraum.</p>
<p><b>Leverage-Angebotsdaten:</b> Aktive Inserate für Eigentumswohnungen zum Kauf aus mehreren Portalen, ohne Fremddatenbanken, Abruf 07.11.2026. Medianwerte je Stadt im Umkreis von 5 km um das Stadtzentrum, in sehr großen Märkten 2 bis 3 km (Kernstadt), damit jede Auswertung auf allen Inseraten des Kreises beruht. Der Zustand stammt aus der Inseratsangabe, das Baujahr aus dem Inserat. Mieten und Marktwerte sind Schätzungen des Leverage-Bewertungsmodells, keine Angebotsmieten. Angebotspreise sind keine Kaufpreise.</p>
<p><b>Grenzen dieser Ausgabe:</b> Kreisgenaue amtliche Daten zu Wanderung, Alter und Eigentum folgen im Quartalsreport. Für einige Kennzahlen lagen nur Sekundärquellen mit Verweis auf den Herausgeber vor (GREIX-Mietindex, Grunderwerbsteuersätze, Drei-Objekt-Grenze). Sie sind im Quellenverzeichnis so gekennzeichnet.</p>
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
.sum{{padding-left:16px;margin:0 0 10px}}.sum li{{margin-bottom:9px;font-size:10.8px}}
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
<img src="data:image/png;base64,{LOGO_T}" style="height:13px"/><span style="letter-spacing:1px;text-transform:uppercase">Immobilienhandel-Marktreport (Fix-und-Flip) · November 2026</span></div>'''
FOOTER = f'''<div style="width:100%;padding:0 17mm;font-family:Arial;font-size:7px;color:{MUT};display:flex;justify-content:space-between;align-items:center;-webkit-print-color-adjust:exact">
<img src="data:image/png;base64,{LOGO_T}" style="height:9px"/><span>Keine Anlage-, Steuer- oder Rechtsberatung. Alle Angaben ohne Gewähr.</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'''

html = f'<!doctype html><html lang="de"><head><meta charset="utf-8"><style>{css}</style></head><body>{cover}{s1}{s2}{s3}{s4}{s5}{s6}{s7}{s8}{s9}{s10}{s11}</body></html>'
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
print('ok', len(rows), n_total, round(kaufkraft, 2), round(darl_med), [(r['c'], r['spread']) for r in top_spread[:5]])
