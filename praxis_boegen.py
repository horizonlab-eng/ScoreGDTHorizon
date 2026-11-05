"""
Ausgefuellte Boegen speichern und wieder oeffnen (Zweig "praxis").

Beim Senden speichert ScoreGDT alle Antworten des Bogens im Trendverzeichnis
des Patienten:
    <Trendverzeichnis>\\<PatId>\\boegen\\<JJJJMMTTHHMMSS>.json
Der Dateiname ist Datum (GDT 6200) und Uhrzeit (GDT 6201) des Rueckschriebs.
Klickt man den Eintrag in medatixx doppelt an, schickt medatixx genau diese
beiden Werte mit ("Daten einer Untersuchung zeigen", Satzart 6311). ScoreGDT
findet damit den Bogen und oeffnet ihn so ausgefuellt wie damals.

Wird der Bogen geaendert und erneut gesendet, entsteht in medatixx ein
Korrektur-Eintrag mit demselben Datum und derselben Uhrzeit (der urspruengliche
Eintrag bleibt - wie es fuer die Dokumentation vorgeschrieben ist - erhalten).
Die fruehere Fassung bleibt in der Datei unter "fruehereFassungen" erhalten.
"""
import os, json, datetime, glob
import logger

UNTERORDNER = "boegen"
FORMAT = 1


def ordner(trendverzeichnis: str, patId: str) -> str:
    return os.path.join(trendverzeichnis, patId, UNTERORDNER)


def schluessel(datum6200: str, uhrzeit6201: str) -> str:
    """'02112026', '134426' -> '20261102134426'"""
    d = (datum6200 or "").strip()
    u = (uhrzeit6201 or "").strip().ljust(6, "0")[:6]
    if len(d) != 8 or not d.isdigit() or not u.isdigit():
        return ""
    return d[4:8] + d[2:4] + d[0:2] + u


def alsDatum(schl: str):
    try:
        return datetime.datetime.strptime(schl, "%Y%m%d%H%M%S")
    except Exception:
        return None


# ---------- Zustand der Bedienelemente ----------
def zustandLesen(widgets: list, einheitToggles: dict) -> dict:
    import class_widgets
    werte = {}
    for w in widgets:
        typ = w.getTyp()
        qt = w.getQt()
        if typ == class_widgets.WidgetTyp.LINEEDIT:
            werte[w.getId()] = {"typ": "text", "wert": qt.text()}
        elif typ == class_widgets.WidgetTyp.COMBOBOX:
            werte[w.getId()] = {"typ": "auswahl", "wert": qt.currentIndex(), "text": qt.currentText()}
        elif typ in (class_widgets.WidgetTyp.RADIOBUTTON, class_widgets.WidgetTyp.CHECKBOX):
            werte[w.getId()] = {"typ": "haken", "wert": bool(qt.isChecked())}
    einheiten = {wid: t.getAktuelleEinheit() for wid, t in einheitToggles.items()}
    return {"widgets": werte, "einheiten": einheiten}


def gleich(a: dict, b: dict) -> bool:
    def kern(z):
        return ({k: v.get("wert") for k, v in z.get("widgets", {}).items()}, z.get("einheiten", {}), z.get("kommentar", "").strip())
    return kern(a) == kern(b)


def zustandSetzen(fenster, zustand: dict) -> list:
    """Setzt gespeicherte Antworten in das geoeffnete Fenster. Gibt die IDs zurueck,
    die es im Bogen nicht (mehr) gibt."""
    import class_widgets
    fehlend = []
    # 1. Einheiten (z. B. mg/dl <-> mmol/l) zuerst, solange die Felder noch leer sind
    for wid, einheit in zustand.get("einheiten", {}).items():
        t = fenster.einheitToggles.get(wid)
        if t is not None and t.getAktuelleEinheit() != einheit and einheit in t.getEinheitenListe():
            fenster.konvertButtonClicked(False, wid)
    # 2. Antworten
    nachId = {w.getId(): w for w in fenster.widgets}
    for wid, eintrag in zustand.get("widgets", {}).items():
        w = nachId.get(wid)
        if w is None:
            fehlend.append(wid)
            continue
        qt = w.getQt()
        typ = w.getTyp()
        try:
            if typ == class_widgets.WidgetTyp.LINEEDIT:
                qt.setText(str(eintrag.get("wert", "")))
            elif typ == class_widgets.WidgetTyp.COMBOBOX:
                i = int(eintrag.get("wert", 0))
                if 0 <= i < qt.count():
                    qt.setCurrentIndex(i)
            elif typ in (class_widgets.WidgetTyp.RADIOBUTTON, class_widgets.WidgetTyp.CHECKBOX):
                soll = bool(eintrag.get("wert"))
                if qt.isChecked() != soll:
                    gruppe = qt.group()
                    exklusiv = gruppe.exclusive() if gruppe is not None else False
                    if gruppe is not None and not soll:
                        gruppe.setExclusive(False)
                    qt.setChecked(soll)
                    if gruppe is not None:
                        gruppe.setExclusive(exklusiv)
        except Exception as e:
            logger.logger.warning("Bogen: Wert fuer " + wid + " nicht setzbar: " + str(e))
    return fehlend


# ---------- Speichern und Laden ----------
def speichern(trendverzeichnis: str, patId: str, daten: dict) -> str:
    """Speichert einen Bogen. Gibt es schon einen mit demselben Schluessel (Korrektur),
    wandert die bisherige Fassung nach "fruehereFassungen"."""
    if not trendverzeichnis or not os.path.isdir(trendverzeichnis):
        logger.logger.warning("Bogen nicht gespeichert: Trendverzeichnis fehlt")
        return ""
    ziel = ordner(trendverzeichnis, patId)
    os.makedirs(ziel, exist_ok=True)
    pfad = os.path.join(ziel, daten["schluessel"] + ".json")
    daten = dict(daten)
    daten["format"] = FORMAT
    alt = laden(pfad)
    if alt:
        frueher = alt.pop("fruehereFassungen", [])
        frueher.append(alt)
        daten["fruehereFassungen"] = frueher
    hilf = pfad + ".tmp"
    with open(hilf, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    os.replace(hilf, pfad)
    logger.logger.info("Bogen gespeichert: " + pfad)
    return pfad


def laden(pfad: str) -> dict:
    try:
        if os.path.exists(pfad):
            with open(pfad, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.logger.warning("Bogen nicht lesbar: " + pfad + " (" + str(e) + ")")
    return {}


def finden(trendverzeichnis: str, patId: str, datum6200: str, uhrzeit6201: str, toleranzSekunden: int = 120) -> dict:
    """Bogen zu Datum/Uhrzeit des angeklickten Eintrags. Erst exakt, dann der
    zeitlich naechste am selben Tag innerhalb der Toleranz."""
    schl = schluessel(datum6200, uhrzeit6201)
    if not schl or not trendverzeichnis:
        return {}
    o = ordner(trendverzeichnis, patId)
    genau = laden(os.path.join(o, schl + ".json"))
    if genau:
        return genau
    gesucht = alsDatum(schl)
    bester, abstand = None, None
    for datei in glob.glob(os.path.join(o, schl[:8] + "*.json")):
        d = alsDatum(os.path.basename(datei)[:14])
        if d is None or gesucht is None:
            continue
        diff = abs((d - gesucht).total_seconds())
        if diff <= toleranzSekunden and (abstand is None or diff < abstand):
            bester, abstand = datei, diff
    return laden(bester) if bester else {}
