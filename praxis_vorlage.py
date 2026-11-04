"""
PDF-Vorlagen aus Adobe Acrobat Pro (Zweig "praxis").

Statt Raender in Millimetern einzustellen, gestaltet der Administrator das PDF
in Acrobat Pro ("Formular vorbereiten"): Briefpapier, Logo, Linien, feste Texte
und Textfelder mit festen Namen. ScoreGDT liest die Felder (Lage, Groesse,
Schriftgroesse, Ausrichtung, fett, Farbe) und schreibt den passenden Text genau
in diese Rahmen. Die Formularfelder selbst verschwinden im fertigen PDF.

Vorlagen (zentral, fuer alle):
    C:\\ProgramData\\scoregdt\\vorlage_score.pdf     Einzel-Score
    C:\\ProgramData\\scoregdt\\vorlage_verlauf.pdf   Verlauf / Trend
Fehlt eine Vorlage, gilt das bisherige Layout (Briefpapier + Raender).

Seite 1 der Vorlage = erste Seite. Seite 2 (optional) = alle Folgeseiten,
falls die Tabelle "Details" nicht auf eine Seite passt.

Feldnamen (Gross-/Kleinschreibung egal):
    Titel, Patient, Geburtsdatum, Datum, Ergebnis, Beurteilung, Kommentar,
    DokumentiertVon, Einrichtung, Seite, Details, DetailsFolgeseite
"""
import os, re, tempfile
import logger

basedir = os.path.dirname(__file__)

ARTEN = {"score": "vorlage_score.pdf", "verlauf": "vorlage_verlauf.pdf"}
ART_NAMEN = {"score": "Einzel-Score", "verlauf": "Verlauf"}

FELDER = {
    "titel": "Titel",
    "patient": "Patient",
    "geburtsdatum": "Geburtsdatum",
    "datum": "Datum",
    "ergebnis": "Ergebnis",
    "beurteilung": "Beurteilung",
    "kommentar": "Kommentar",
    "dokumentiertvon": "DokumentiertVon",
    "einrichtung": "Einrichtung",
    "seite": "Seite",
    "details": "Details",
    "detailsfolgeseite": "DetailsFolgeseite",
}
FELD_ERKLAERUNG = {
    "Titel": "Name des Scores bzw. „Medizinischer Score-Trend“",
    "Patient": "Name der Patientin / des Patienten",
    "Geburtsdatum": "Geburtsdatum",
    "Datum": "Untersuchungsdatum (Score) bzw. Erstellungsdatum (Verlauf)",
    "Ergebnis": "Ergebnis mit Einheit (nur Einzel-Score)",
    "Beurteilung": "Auswertung / Interpretation (nur Einzel-Score)",
    "Kommentar": "Kommentar (nur Einzel-Score)",
    "DokumentiertVon": "Name und Kürzel der Person",
    "Einrichtung": "Name der Einrichtung (falls in ScoreGDT eingestellt)",
    "Seite": "„Seite 1 von 2“",
    "Details": "Tabelle mit den Einzelwerten bzw. dem Verlauf",
    "DetailsFolgeseite": "Tabelle auf den Folgeseiten (Seite 2 der Vorlage)",
}
# Auf Folgeseiten werden nur diese Felder ausgefuellt
KOPF_FELDER = {"titel", "patient", "geburtsdatum", "datum", "einrichtung", "seite", "dokumentiertvon"}

# Spalten der Tabelle "Details": (Anteil an der Breite, Ausrichtung)
SPALTEN = {
    "score": [(0.65, "L"), (0.35, "R")],
    "verlauf": [(0.17, "L"), (0.23, "L"), (0.60, "L")],
}

MM = 72 / 25.4  # 1 mm in Punkt


def configOrdner() -> str:
    import praxis_pdf
    return praxis_pdf.configOrdner()


def vorlagePfad(art: str) -> str:
    return os.path.join(configOrdner(), ARTEN[art])


def vorhanden(art: str) -> bool:
    return os.path.exists(vorlagePfad(art))


# ---------- Felder lesen ----------
class Feld:
    def __init__(self):
        self.name = ""        # Schluessel in FELDER (klein) oder Originalname, falls unbekannt
        self.bekannt = False
        self.seite = 0
        self.x = self.y = self.w = self.h = 0.0  # Punkt, Ursprung oben links
        self.groesse = 10.0
        self.autoGroesse = False
        self.ausrichtung = "L"
        self.mehrzeilig = False
        self.fett = False
        self.farbe = (0, 0, 0)


def _erbe(knoten, schluessel):
    """Wert aus dem Feld oder einem uebergeordneten Feld (PDF-Vererbung)."""
    tiefe = 0
    while knoten is not None and tiefe < 20:
        if schluessel in knoten:
            return knoten[schluessel]
        eltern = knoten.get("/Parent")
        knoten = eltern.get_object() if eltern is not None else None
        tiefe += 1
    return None


def _feldname(widget) -> str:
    teile = []
    knoten = widget
    tiefe = 0
    while knoten is not None and tiefe < 20:
        if "/T" in knoten:
            teile.insert(0, str(knoten["/T"]))
        eltern = knoten.get("/Parent")
        knoten = eltern.get_object() if eltern is not None else None
        tiefe += 1
    if not teile:
        return ""
    # Acrobat haengt bei kopierten Feldern ".0", ".1" oder "#0" an
    return re.sub(r"#\d+$", "", teile[0]).strip()


def _da(da: str, feld: Feld):
    m = re.search(r"/([^\s/]+)\s+(\d+(?:\.\d+)?)\s+Tf", da)
    if m:
        schrift = m.group(1).lower()
        feld.fett = "bold" in schrift or schrift in ("hebo", "tibo", "cobo", "hebi", "tibi") or schrift.endswith(",bold")
        groesse = float(m.group(2))
        if groesse > 0:
            feld.groesse = groesse
        else:
            feld.autoGroesse = True
    m = re.search(r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg", da)
    if m:
        feld.farbe = tuple(int(max(0, min(1, float(v))) * 255) for v in m.groups())
    else:
        m = re.search(r"([\d.]+)\s+g(?:\s|$)", da)
        if m:
            g = int(max(0, min(1, float(m.group(1)))) * 255)
            feld.farbe = (g, g, g)


def felderLesen(pfad_oder_leser) -> list:
    """Liest alle Textfelder der Vorlage."""
    from pypdf import PdfReader
    leser = pfad_oder_leser if not isinstance(pfad_oder_leser, str) else PdfReader(pfad_oder_leser)
    acro = leser.trailer["/Root"].get("/AcroForm")
    acroDa = ""
    if acro is not None:
        acroDa = str(acro.get_object().get("/DA", ""))
    felder = []
    for nr, seite in enumerate(leser.pages):
        mb = seite.mediabox
        links, unten, oben = float(mb.left), float(mb.bottom), float(mb.top)
        for annot in seite.get("/Annots") or []:
            w = annot.get_object()
            if w.get("/Subtype") != "/Widget":
                continue
            ft = _erbe(w, "/FT")
            if ft is not None and ft != "/Tx":
                continue
            name = _feldname(w)
            if not name:
                continue
            f = Feld()
            schluessel = re.sub(r"[\s_\-]", "", name).lower()
            f.bekannt = schluessel in FELDER
            f.name = schluessel if f.bekannt else name
            f.seite = nr
            r = [float(v) for v in w["/Rect"]]
            x1, x2 = min(r[0], r[2]), max(r[0], r[2])
            y1, y2 = min(r[1], r[3]), max(r[1], r[3])
            f.x, f.w = x1 - links, x2 - x1
            f.y, f.h = oben - y2, y2 - y1
            da = _erbe(w, "/DA")
            _da(str(da) if da is not None else acroDa, f)
            q = _erbe(w, "/Q")
            f.ausrichtung = {1: "C", 2: "R"}.get(int(q) if q is not None else 0, "L")
            ff = _erbe(w, "/Ff")
            f.mehrzeilig = bool(int(ff) & 4096) if ff is not None else False
            felder.append(f)
    return felder


def pruefen(art: str) -> dict:
    """Fuer den Admin-Dialog: welche Felder hat die Vorlage, was fehlt, was ist unbekannt."""
    ergebnis = {"ok": False, "seiten": 0, "felder": [], "unbekannt": [], "fehler": ""}
    try:
        from pypdf import PdfReader
        leser = PdfReader(vorlagePfad(art))
        ergebnis["seiten"] = len(leser.pages)
        felder = felderLesen(leser)
        ergebnis["felder"] = sorted({FELDER[f.name] for f in felder if f.bekannt})
        ergebnis["unbekannt"] = sorted({f.name for f in felder if not f.bekannt})
        ergebnis["ok"] = True
    except Exception as e:
        ergebnis["fehler"] = str(e)
    return ergebnis


# ---------- Text in Felder schreiben ----------
def _neuesOverlay():
    from fpdf import FPDF
    pdf = FPDF(unit="pt")
    pdf.add_font("dejavu", "", os.path.join(basedir, "fonts", "DejaVuSans.ttf"))
    pdf.add_font("dejavu", "B", os.path.join(basedir, "fonts", "DejaVuSans-Bold.ttf"))
    pdf.add_font("dejavu", "I", os.path.join(basedir, "fonts", "DejaVuSans-Oblique.ttf"))
    pdf.set_auto_page_break(False)
    pdf.set_margins(0, 0, 0)
    pdf.c_margin = 0
    return pdf


def _zeilenUmbrechen(pdf, breite: float, text: str) -> list:
    if breite <= 1:
        return [text]
    try:
        zeilen = pdf.multi_cell(breite, 10, text, dry_run=True, output="LINES")
        return list(zeilen) or [""]
    except Exception:
        return text.split("\n")


def _feldSchreiben(pdf, f: Feld, text: str):
    text = (text or "").strip()
    if not text:
        return
    stil = "B" if f.fett else ""
    pdf.set_text_color(*f.farbe)
    rand = 2.0
    breite = max(1.0, f.w - 2 * rand)
    groesse = f.groesse if not f.autoGroesse else max(6.0, min(12.0, f.h * 0.65))
    mehrzeilig = f.mehrzeilig or f.h >= groesse * 2.6
    if mehrzeilig:
        while True:
            pdf.set_font("dejavu", stil, groesse)
            zh = groesse * 1.2
            zeilen = _zeilenUmbrechen(pdf, breite, text)
            if len(zeilen) * zh <= f.h - 2 or groesse <= 6:
                break
            groesse -= 0.5
        maxZeilen = max(1, int((f.h - 2) // zh))
        if len(zeilen) > maxZeilen:
            zeilen = zeilen[:maxZeilen]
            zeilen[-1] = zeilen[-1].rstrip()[:-1] + "…"
        y = f.y + 1
        for z in zeilen:
            pdf.set_xy(f.x + rand, y)
            pdf.cell(breite, zh, z, align=f.ausrichtung)
            y += zh
    else:
        text = " ".join(text.split())
        pdf.set_font("dejavu", stil, groesse)
        while pdf.get_string_width(text) > breite and groesse > 6:
            groesse -= 0.5
            pdf.set_font("dejavu", stil, groesse)
        while pdf.get_string_width(text) > breite and len(text) > 2:
            text = text[:-2] + "…"
        zh = groesse * 1.2
        pdf.set_xy(f.x + rand, f.y + max(0.0, (f.h - zh) / 2))
        pdf.cell(breite, zh, text, align=f.ausrichtung)
    pdf.set_text_color(0, 0, 0)


def _detailsSchreiben(pdf, f: Feld, eintraege: list, start: int, spalten: list) -> int:
    """Schreibt Tabellenzeilen ab Index start in das Feld f. Gibt den Index der
    ersten Zeile zurueck, die nicht mehr gepasst hat (len(eintraege) = alles geschrieben)."""
    groesse = f.groesse if not f.autoGroesse else 10.0
    zh = groesse * 1.25
    rand = 3.0
    y = f.y
    unten = f.y + f.h
    i = start
    zebra = 0
    pdf.set_draw_color(150, 150, 150)
    while i < len(eintraege):
        art = eintraege[i][0]
        inhalt = eintraege[i][1] if len(eintraege[i]) > 1 else ""
        if art == "abstand":
            hoehe = zh * 0.5
            if y + hoehe > unten:
                return i + 1
            y += hoehe
            i += 1
            continue
        if art in ("ueberschrift", "unterueberschrift"):
            fett = groesse + (1 if art == "ueberschrift" else 0)
            hoehe = fett * 1.25 + 4
            # Ueberschrift nicht allein am Seitenende stehen lassen
            if y + hoehe + zh + 2 > unten and y > f.y:
                return i
            pdf.set_font("dejavu", "B", fett)
            pdf.set_xy(f.x, y)
            if art == "ueberschrift":
                pdf.set_fill_color(225, 225, 225)
                pdf.cell(f.w, hoehe, "  " + str(inhalt), fill=True)
            else:
                pdf.cell(f.w, hoehe, str(inhalt), border="B")
            y += hoehe
            zebra = 0
            i += 1
            continue
        # Tabellenzeile
        pdf.set_font("dejavu", "", groesse)
        werte = list(inhalt) if isinstance(inhalt, (list, tuple)) else [str(inhalt)]
        if not werte:
            i += 1
            continue
        breiten = [f.w * a for a, _ in spalten[:len(werte)]] if len(werte) <= len(spalten) else [f.w / len(werte)] * len(werte)
        if len(werte) < len(spalten):
            breiten[-1] = f.w - sum(breiten[:-1])
        ausrichtungen = [a for _, a in spalten[:len(werte)]] + ["L"] * max(0, len(werte) - len(spalten))
        umbrochen = [_zeilenUmbrechen(pdf, max(1.0, b - 2 * rand), str(w)) for b, w in zip(breiten, werte)]
        anzahl = max(1, max(len(u) for u in umbrochen))
        hoehe = anzahl * zh + 2
        if y + hoehe > unten:
            if y > f.y:
                return i
            # Zeile ist hoeher als der ganze Bereich: abschneiden
            anzahl = max(1, int((f.h - 2) // zh))
            umbrochen = [u[:anzahl] for u in umbrochen]
            hoehe = anzahl * zh + 2
        if zebra % 2 == 0:
            pdf.set_fill_color(242, 242, 242)
            pdf.rect(f.x, y, f.w, hoehe, style="F")
        x = f.x
        for b, u, a in zip(breiten, umbrochen, ausrichtungen):
            yz = y + 1
            for z in u:
                pdf.set_xy(x + rand, yz)
                pdf.cell(max(1.0, b - 2 * rand), zh, z, align=a)
                yz += zh
            x += b
        y += hoehe
        zebra += 1
        i += 1
    return i


def _seitenPlanen(felder: list, anzahlVorlagenseiten: int):
    """Welche Vorlagenseite und welcher Tabellenbereich gilt fuer Seite 1 und die Folgeseiten."""
    erste = [f for f in felder if f.seite == 0]
    detailsErste = next((f for f in erste if f.name == "details"), None)
    folgeSeite = 1 if anzahlVorlagenseiten > 1 else 0
    detailsFolge = next((f for f in felder if f.name == "detailsfolgeseite"), None)
    if detailsFolge is not None:
        folgeSeite = detailsFolge.seite
    else:
        detailsFolge = next((f for f in felder if f.seite == folgeSeite and f.name == "details"), None) or detailsErste
    return detailsErste, folgeSeite, detailsFolge


def _overlayBauen(felder, seitenGroessen, daten: dict, details: list, spalten: list, gesamt: int):
    """Baut das Overlay (nur Text). Gibt (pdf, Seitenzahl, Liste der Vorlagenseiten je Seite) zurueck."""
    detailsErste, folgeSeite, detailsFolge = _seitenPlanen(felder, len(seitenGroessen))
    werte = {k.lower(): v for k, v in daten.items()}
    pdf = _neuesOverlay()
    basis = []
    index = 0
    seite = 0
    while True:
        vorlagenseite = 0 if seite == 0 else folgeSeite
        breite, hoehe = seitenGroessen[vorlagenseite]
        pdf.add_page(format=(breite, hoehe))
        basis.append(vorlagenseite)
        werte["seite"] = "Seite " + str(seite + 1) + " von " + str(gesamt or "?")
        for f in felder:
            if f.seite != vorlagenseite or not f.bekannt or f.name in ("details", "detailsfolgeseite"):
                continue
            if seite > 0 and f.name not in KOPF_FELDER:
                continue
            _feldSchreiben(pdf, f, str(werte.get(f.name, "")))
        bereich = detailsErste if seite == 0 else detailsFolge
        if bereich is None or not details:
            break
        neu = _detailsSchreiben(pdf, bereich, details, index, spalten)
        if neu >= len(details):
            break
        if neu == index and seite > 0:
            logger.logger.warning("Vorlage: Tabellenzeile passt in keinen Bereich - Rest weggelassen")
            break
        index = neu
        seite += 1
        if seite >= 50:
            break
    return pdf, seite + 1, basis


def erzeugen(art: str, daten: dict, details: list, ziel: str, pdfa=None) -> bool:
    """Fuellt die Vorlage und legt das fertige PDF (ggf. PDF/A) unter ziel ab."""
    import praxis, praxis_pdf
    from pypdf import PdfReader, PdfWriter
    hilfs = praxis.hilfsPfad(ziel)
    overlayDatei = hilfs + ".text.tmp"
    try:
        leser = PdfReader(vorlagePfad(art))
        felder = felderLesen(leser)
        groessen = [(float(s.mediabox.width), float(s.mediabox.height)) for s in leser.pages]
        spalten = SPALTEN.get(art, SPALTEN["score"])
        # 1. Durchgang zaehlt die Seiten (fuer "Seite 1 von N"), 2. Durchgang schreibt
        _, gesamt, _ = _overlayBauen(felder, groessen, daten, details, spalten, 0)
        overlay, _, basis = _overlayBauen(felder, groessen, daten, details, spalten, gesamt)
        titel = str(daten.get("Titel", "ScoreGDT"))
        overlay.set_title(titel)
        overlay.output(overlayDatei)

        # Formularfelder der Vorlage entfernen (nur Gestaltung bleibt)
        for s in leser.pages:
            if "/Annots" in s:
                del s["/Annots"]
        text = PdfReader(overlayDatei)
        schreiber = PdfWriter()
        for nr, textSeite in enumerate(text.pages):
            hintergrund = leser.pages[basis[nr]]
            neu = schreiber.add_blank_page(width=hintergrund.mediabox.width, height=hintergrund.mediabox.height)
            neu.merge_page(hintergrund)
            neu.merge_page(textSeite)
        schreiber.add_metadata({"/Title": titel, "/Creator": "ScoreGDT (Praxis-Build)"})
        with open(hilfs, "wb") as datei:
            schreiber.write(datei)
        erledigt = praxis_pdf.fertigstellen(hilfs, ziel, briefpapier="", pdfa=pdfa)
        logger.logger.warning("PDF aus Vorlage " + ARTEN[art] + " erzeugt (" + (erledigt or "ohne PDF-A") + ")")
        return os.path.exists(ziel)
    except Exception as e:
        logger.logger.error("PDF aus Vorlage " + ARTEN.get(art, art) + " fehlgeschlagen: " + str(e))
        return False
    finally:
        for d in (overlayDatei, hilfs):
            try:
                if os.path.exists(d):
                    os.remove(d)
            except Exception:
                pass


# ---------- Startvorlage ----------
def _layout(art: str, oben: float, unten: float, seitenHoehe: float = 297.0):
    """Felder der Startvorlage in mm: (Seite, Name, x, y, Breite, Hoehe, Schriftgroesse, Ausrichtung 0/1/2, mehrzeilig, fett)
    und feste Beschriftungen: (Seite, x, y, Text, fett)."""
    felder, texte, linien = [], [], []
    ende = seitenHoehe - unten
    for seite in (0, 1):
        y = oben
        if seite == 0:
            felder.append((0, "Titel", 20, y, 170, 12, 16, 1, False, True))
            y += 15
        else:
            felder.append((1, "Titel", 20, y, 170, 9, 12, 1, False, True))
            y += 11
        texte.append((seite, 20, y, "Patient/in:", False))
        felder.append((seite, "Patient", 45, y, 85, 7, 11, 0, False, True))
        texte.append((seite, 133, y, "geb.:", False))
        felder.append((seite, "Geburtsdatum", 145, y, 45, 7, 11, 0, False, False))
        y += 8
        if seite == 0:
            texte.append((0, 20, y, "Datum:" if art == "score" else "Erstellt am:", False))
            felder.append((0, "Datum", 45, y, 40, 7, 10, 0, False, False))
            texte.append((0, 95, y, "Dokumentiert von:" if art == "score" else "Erstellt von:", False))
            felder.append((0, "DokumentiertVon", 128, y, 62, 7, 10, 0, False, False))
            y += 8
            texte.append((0, 20, y, "Einrichtung:", False))
            felder.append((0, "Einrichtung", 45, y, 145, 7, 10, 0, False, False))
            y += 10
        else:
            y += 2
        linien.append((seite, y))
        y += 3
        if seite == 0 and art == "score":
            yE = ende - 50
            felder.append((0, "Details", 20, y, 170, yE - 3 - y, 10, 0, True, False))
            linien.append((0, yE))
            texte.append((0, 20, yE + 2, "Ergebnis:", True))
            felder.append((0, "Ergebnis", 50, yE + 1, 140, 9, 12, 0, False, True))
            texte.append((0, 20, yE + 13, "Beurteilung:", True))
            felder.append((0, "Beurteilung", 50, yE + 12, 140, 15, 10, 0, True, False))
            texte.append((0, 20, yE + 29, "Kommentar:", True))
            felder.append((0, "Kommentar", 50, yE + 28, 140, 12, 10, 0, True, False))
        else:
            name = "Details" if seite == 0 else "DetailsFolgeseite"
            felder.append((seite, name, 20, y, 170, ende - 9 - y, 10, 0, True, False))
        felder.append((seite, "Seite", 140, ende - 7, 50, 6, 8, 2, False, False))
    return felder, texte, linien


def startvorlageErzeugen(art: str, ziel: str = "") -> str:
    """Legt eine Startvorlage mit allen Feldern an (auf dem Briefpapier, falls vorhanden).
    Gibt den Pfad zurueck. Diese Datei wird dann in Acrobat Pro weiter gestaltet."""
    import praxis_pdf
    from fpdf import FPDF
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (NameObject, TextStringObject, NumberObject, FloatObject,
                               ArrayObject, DictionaryObject, BooleanObject)
    ziel = ziel or vorlagePfad(art)
    werte = praxis_pdf.einstellungen()
    feldListe, texte, linien = _layout(art, float(werte["oben"]), float(werte["unten"]))

    # 1. Feste Beschriftungen zeichnen
    pdf = FPDF(unit="mm", format="A4")
    pdf.add_font("dejavu", "", os.path.join(basedir, "fonts", "DejaVuSans.ttf"))
    pdf.add_font("dejavu", "B", os.path.join(basedir, "fonts", "DejaVuSans-Bold.ttf"))
    pdf.set_auto_page_break(False)
    for seite in (0, 1):
        pdf.add_page()
        pdf.set_text_color(90, 90, 90)
        for s, x, y, text, fett in texte:
            if s == seite:
                pdf.set_font("dejavu", "B" if fett else "", 10)
                pdf.set_xy(x, y)
                pdf.cell(30, 7, text)
        pdf.set_draw_color(160, 160, 160)
        for s, y in linien:
            if s == seite:
                pdf.line(20, y, 190, y)
    roh = os.path.join(tempfile.gettempdir(), "_scoregdt_startvorlage_" + art + ".tmp")
    pdf.output(roh)
    quelle = roh
    bp = praxis_pdf.briefpapierPfad()
    if bp:
        mitBp = roh + ".bp"
        if praxis_pdf.aufBriefpapier(roh, bp, mitBp):
            quelle = mitBp

    # 2. Formularfelder anlegen (wie Acrobat: ein Feld, je Seite ein Widget)
    leser = PdfReader(quelle)
    schreiber = PdfWriter()
    for s in leser.pages:
        schreiber.add_page(s)
    eltern = {}
    for seite, name, x, y, b, h, groesse, q, mehrzeilig, fett in feldListe:
        page = schreiber.pages[seite]
        mb = page.mediabox
        links, oben = float(mb.left), float(mb.top)
        rect = ArrayObject([FloatObject(round(links + x * MM, 2)), FloatObject(round(oben - (y + h) * MM, 2)),
                            FloatObject(round(links + (x + b) * MM, 2)), FloatObject(round(oben - y * MM, 2))])
        da = TextStringObject(("/HeBo " if fett else "/Helv ") + str(groesse) + " Tf 0 g")
        if name not in eltern:
            feld = DictionaryObject({
                NameObject("/FT"): NameObject("/Tx"),
                NameObject("/T"): TextStringObject(name),
                NameObject("/TU"): TextStringObject(FELD_ERKLAERUNG.get(name, name)),
                NameObject("/Kids"): ArrayObject(),
                NameObject("/DA"): da,
                NameObject("/Q"): NumberObject(q),
            })
            if mehrzeilig:
                feld[NameObject("/Ff")] = NumberObject(4096)
            eltern[name] = schreiber._add_object(feld)
        widget = DictionaryObject({
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/Parent"): eltern[name],
            NameObject("/Rect"): rect,
            NameObject("/F"): NumberObject(4),
            NameObject("/DA"): da,
            NameObject("/Q"): NumberObject(q),
            NameObject("/P"): page.indirect_reference,
            NameObject("/MK"): DictionaryObject({NameObject("/BC"): ArrayObject([FloatObject(0.55), FloatObject(0.7), FloatObject(0.95)])}),
        })
        wref = schreiber._add_object(widget)
        eltern[name].get_object()["/Kids"].append(wref)
        if "/Annots" not in page:
            page[NameObject("/Annots")] = ArrayObject()
        page["/Annots"].append(wref)
    schriften = DictionaryObject()
    for kurz, basis in (("/Helv", "/Helvetica"), ("/HeBo", "/Helvetica-Bold")):
        schriften[NameObject(kurz)] = schreiber._add_object(DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject(basis),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }))
    acro = DictionaryObject({
        NameObject("/Fields"): ArrayObject(list(eltern.values())),
        NameObject("/DR"): DictionaryObject({NameObject("/Font"): schriften}),
        NameObject("/DA"): TextStringObject("/Helv 10 Tf 0 g"),
        NameObject("/NeedAppearances"): BooleanObject(True),
    })
    schreiber._root_object[NameObject("/AcroForm")] = schreiber._add_object(acro)
    schreiber.add_metadata({"/Title": "ScoreGDT-Vorlage " + ART_NAMEN[art]})
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    hilf = ziel + ".tmp"
    with open(hilf, "wb") as datei:
        schreiber.write(datei)
    os.replace(hilf, ziel)
    for d in (roh, roh + ".bp"):
        try:
            if os.path.exists(d):
                os.remove(d)
        except Exception:
            pass
    return ziel


# ---------- Beispieldaten (Probe-PDF im Admin-Dialog) ----------
def beispiel(art: str):
    daten = {
        "Patient": "Mustermann, Max", "Geburtsdatum": "01.02.1945", "Datum": "04.11.2026",
        "DokumentiertVon": "Sabine Muster (SH)", "Einrichtung": "Praxis am Horizont",
    }
    if art == "score":
        daten.update({"Titel": "Geriatrisches Screening (Beispiel)", "Ergebnis": "7 Punkte",
                      "Beurteilung": "Auffälliges Ergebnis – weiterführendes Assessment empfohlen. Dieser Text ist absichtlich etwas länger, um den Zeilenumbruch zu zeigen.",
                      "Kommentar": "Beispielkommentar: Angaben durch Angehörige ergänzt."})
        details = [("zeile", ["Frage " + str(i) + ": Beispielfrage mit etwas längerem Text äöüß", str(i % 3) + " Punkte"]) for i in range(1, 46)]
    else:
        daten.update({"Titel": "Medizinische Score-Trends (Beispiel)"})
        details = []
        for gruppe, tests in (("Geriatrie", ["Barthel-Index", "Timed Up and Go"]), ("Kardiologie", ["CHA2DS2-VASc"])):
            details.append(("ueberschrift", gruppe))
            for t in tests:
                details.append(("unterueberschrift", t))
                for j in range(12):
                    details.append(("zeile", ["%02d.%02d.2026" % (1 + j, 1 + j % 12), str(60 + j * 5) + " Punkte",
                                              "Beispielbeurteilung " + str(j + 1) + " – Verlauf stabil, keine Änderung der Therapie"]))
                details.append(("abstand",))
    return daten, details


def probeErzeugen(art: str, ziel: str) -> bool:
    daten, details = beispiel(art)
    return erzeugen(art, daten, details, ziel)
