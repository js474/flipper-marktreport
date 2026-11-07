"""Stilprüfung für den Immobilienhandel-Marktreport.
Bricht den Build ab, wenn der Text Muster enthält, die nach KI-Formulierung klingen
oder gegen die Hausregeln verstoßen (siehe STYLE.md). Aufruf: python stilcheck.py report.pdf|report.html"""
import re, sys, pathlib

REGELN = [
    (r"[—–]", "Gedankenstrich (Em/En Dash)"),
    (r"\bnicht nur\b.*\bsondern\b", "Negativer Parallelismus (nicht nur ... sondern)"),
    (r"\bDie Frage ist (deshalb )?nicht\b", "Rhetorische Setzung"),
    (r"\bnur so gut wie\b", "Aphorismus"),
    (r"\bheißt das:\s", "Erklär-Floskel (heißt das:)"),
    (r"\bzahlt sich (doppelt )?aus\b", "Redewendung"),
    (r"\b(spielt|spielen) eine (wichtige |entscheidende |zentrale )?Rolle\b", "Floskel (spielt eine Rolle)"),
    (r"\b(Kurz gesagt|Unterm Strich|Am Ende des Tages|Fakt ist|Klar ist|Wichtig ist)\b", "Floskel"),
    (r"\b(ganz unkompliziert|gerne direkt|Ziel ist einfach|das Wichtigste zum Schluss)\b", "Verbotene Floskel aus den Präferenzen"),
    (r"\b(Coaching|Coach)\b", "Wort Coaching/Coach"),
    (r"\b(entscheidend|essenziell|maßgeblich|nahtlos|ganzheitlich)\b", "KI-Vokabular"),
    (r"\b(Lass uns|Schauen wir uns)\b", "Belehrender Einstieg"),
    (r"\bFlipperversum\b", "Flipperversum"),
    (r"\blohnt (sich )?(die|der|das|ein)\b", "Werbe- oder Ratgebersatz (lohnt ...)"),
    (r"\b(jeder|jede) Flipper\w* kennen muss\b", "Slogan"),
    (r"\bist die Alternative\b", "Slogan"),
    (r"\bsehr unterschiedlich\b", "Leerformel"),
    (r"\bbleibt knapp\b", "unbelegte Prognose"),
    (r"\+\s?\d[\d.,]*\s?%\s+mehr\b", "Doppelt gemoppelt (+X % mehr)"),
    (r"\bin der Hand\b", "Redewendung"),
    (r"\b(häufig|oft|meist|typischerweise) (unsaniert|nicht vor Ort)\b", "Unbelegte Verallgemeinerung"),
    (r"\bFlip-Spanne\b", "Begriff Flip-Spanne (misst nicht Vorher/Nachher, siehe STYLE.md)"),
    (r"\bCO2\b", "CO2 statt CO₂"),
    (r"(?<![\w−+])-\d", "Bindestrich statt Minuszeichen vor Zahl"),
    (r"\d,\d{1,2}\s?€", "Euro mit Nachkommastellen"),
]
# Kleinschreibung direkt nach Doppelpunkt (Hausregel: immer groß weiter), Uhrzeiten und Zahlen ausgenommen
DOPPELPUNKT = re.compile(r":\s+([a-zäöü][a-zäöüß]+)")

def text_aus(pfad):
    p = pathlib.Path(pfad)
    if p.suffix == ".pdf":
        import pymupdf
        return "\n".join(seite.get_text() for seite in pymupdf.open(p))
    return re.sub(r"<[^>]+>", " ", p.read_text())

def pruefen(text):
    funde = []
    for zeile in text.splitlines():
        if "http" in zeile:
            continue
        for muster, name in REGELN:
            if re.search(muster, zeile, flags=re.I if name != "Wort Coaching/Coach" else 0):
                funde.append((name, zeile.strip()[:140]))
        for m in DOPPELPUNKT.finditer(zeile):
            funde.append(("Kleinschreibung nach Doppelpunkt", zeile.strip()[:140]))
    return funde

if __name__ == "__main__":
    funde = pruefen(text_aus(sys.argv[1]))
    for name, zeile in funde:
        print(f"{name}: {zeile}")
    print(f"{len(funde)} Fund(e)")
    sys.exit(1 if funde else 0)
