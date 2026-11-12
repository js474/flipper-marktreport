"""Fehler-Waechter. Nur harte Fakten aus der GitHub-API, keine Annahmen.
Aufruf: python pipeline/wachter/wachter.py [woche]
Env: GH_READ_TOKEN (optional, noetig fuer private Repos), GITHUB_TOKEN
Keine Nachricht an Johannes. Befunde landen als Zeilen "BEFUND {json}" im Log und als Warnung im Lauf.
Die Claude-Aufgabe "Fehler-Waechter Automationen" liest sie und behebt sie. Exit 0, damit GitHub keine Fehlermail schickt."""
import base64, json, os, sys, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

REPOS = ["js474/flipper-marktreport", "js474/flipper-linkedin-kommentare", "js474/flipper-reel-remix"]
TOKEN = os.environ.get("GH_READ_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
NOW = datetime.now(timezone.utc)

def get(path):
    req = urllib.request.Request("https://api.github.com/" + path,
        headers={"Accept": "application/vnd.github+json", **({"Authorization": "Bearer " + TOKEN} if TOKEN else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, str(e)

def finding(was, warum, versucht, aktion):
    return {"was": was, "warum": warum, "versucht": versucht, "johannes": aktion}

def pruefe_repo(repo, f):
    s, d = get(f"repos/{repo}")
    if s != 200:
        wo = "GH_READ_TOKEN fehlt" if not os.environ.get("GH_READ_TOKEN") else "GH_READ_TOKEN ohne Zugriff"
        f.append(finding(f"{repo} nicht prüfbar",
            f"GitHub-API antwortet HTTP {s} auf repos/{repo} ({wo}). Bei 404 ist das Repo privat oder der Name falsch.",
            "Abruf mit vorhandenem Token, ohne Ergebnis.",
            "Repo-Setting Secrets: Secret GH_READ_TOKEN in js474/flipper-marktreport anlegen (Fine-grained Token, Repo-Zugriff auf alle drei Repos, Rechte Actions: Read, Contents: Read, Metadata: Read)."))
        return
    since = (NOW - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    s, d = get(f"repos/{repo}/actions/runs?status=failure&created=%3E%3D{since}&per_page=20")
    if s != 200:
        f.append(finding(f"{repo}: Workflow-Läufe nicht lesbar", f"HTTP {s} auf actions/runs.", "Abruf, kein Ergebnis.", "Token-Rechte Actions: Read prüfen."))
        return
    for r in d.get("workflow_runs", []):
        s2, j = get(f"repos/{repo}/actions/runs/{r['id']}/jobs")
        schritte = []
        if s2 == 200:
            for job in j.get("jobs", []):
                for st in job.get("steps", []):
                    if st.get("conclusion") == "failure":
                        schritte.append(f"{job['name']} / {st['name']}")
        f.append(finding(f"{repo}: Workflow '{r['name']}' fehlgeschlagen ({r['event']}, {r['created_at']})",
            "Fehlgeschlagener Schritt: " + ("; ".join(schritte) or "nicht lesbar"),
            "Job-Liste über API gelesen.",
            f"Log öffnen: {r['html_url']}"))

def pruefe_remix(f):
    tag = NOW.day
    if not (2 <= tag <= 10):
        return
    s, d = get("repos/js474/flipper-reel-remix/contents/state.json")
    if s != 200:
        return  # Nicht lesbar ist oben schon als Befund gemeldet
    state = json.loads(base64.b64decode(d["content"]))
    monat = NOW.strftime("%Y-%m")
    if state.get("last_run") != monat:
        f.append(finding(f"Trial-Reel-Remix {monat} nicht eingeplant",
            f"state.json: last_run={state.get('last_run')}, last_attempt={state.get('last_attempt')}. "
            + ("Lauf wurde in diesem Monat nie gestartet." if not str(state.get('last_attempt','')).startswith(monat) else "Lauf wurde gestartet, aber nichts eingeplant."),
            "state.json gelesen.",
            "Aufgabe Trial-Reel-Remix in Claude Code einmal von Hand starten" + (", Remix manuell anstoßen." if tag >= 8 else ", der Tageslauf holt bis zum 7. nach.")))

def selbstpruefung(f):
    """Woechentlich: prueft, ob der Waechter selbst alles erreicht, was er braucht."""
    for name in ["GH_READ_TOKEN"]:
        if not os.environ.get(name):
            f.append(finding(f"Wächter unvollständig: Secret {name} fehlt",
                f"Umgebungsvariable {name} ist im Lauf leer.",
                "Prüfung im wöchentlichen Selbsttest.",
                f"In js474/flipper-marktreport unter Settings, Secrets and variables, Actions das Secret {name} anlegen."))
    s, d = get("repos/js474/flipper-marktreport/actions/workflows/wachter.yml/runs?per_page=7")
    if s == 200:
        rot = [r for r in d.get("workflow_runs", []) if r.get("conclusion") == "failure"]
        print(f"Selbsttest: {len(d.get('workflow_runs', []))} Läufe, davon {len(rot)} mit Befund.")

def main():
    f = []
    for r in REPOS:
        pruefe_repo(r, f)
    pruefe_remix(f)
    if "woche" in sys.argv:
        selbstpruefung(f)
    if not f:
        print("Keine Befunde.")
        return 0
    for x in f:
        print("BEFUND " + json.dumps(x, ensure_ascii=False))
        print("::warning::" + x["was"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
