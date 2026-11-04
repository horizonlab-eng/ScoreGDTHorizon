"""
PDF-Fertigstellung (Zweig "praxis", Etappe 4).

Jedes PDF, das ScoreGDT erzeugt (Einzel-Score und Verlauf), laeuft hier durch:
  1. Briefpapier unterlegen (falls C:\\ProgramData\\scoregdt\\briefpapier.pdf vorhanden;
     Seite 1 der Vorlage fuer Seite 1, Seite 2 der Vorlage - falls vorhanden -
     fuer alle Folgeseiten)
  2. In PDF/A-2b umwandeln (Ghostscript, liegt im Programmordner unter ghostscript\\)
Schlaegt ein Schritt fehl, wird mit dem bis dahin erzeugten PDF weitergearbeitet
(ein normales PDF ist besser als gar keins); der Fehler steht im Protokoll.

Einstellungen (Administrator, Dialog "PDF und Briefpapier") stehen in personen.json
unter "pdf": {"pdfa": true, "oben": 15, "unten": 25}  (Raender in mm).
"""
import os, sys, shutil, subprocess
import logger

basedir = os.path.dirname(__file__)

STANDARD = {"pdfa": True, "oben": 10, "unten": 20}
BRIEFPAPIER = "briefpapier.pdf"


def configOrdner() -> str:
    return os.environ.get("SCOREGDT_CONFIG") or os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "scoregdt")


def einstellungen() -> dict:
    import praxis_personen
    werte = dict(STANDARD)
    try:
        gespeichert = praxis_personen.laden(configOrdner()).get("pdf", {})
        for k in STANDARD:
            if k in gespeichert:
                werte[k] = type(STANDARD[k])(gespeichert[k])
    except Exception as e:
        logger.logger.warning("PDF-Einstellungen nicht lesbar: " + str(e))
    return werte


def einstellungenSpeichern(werte: dict) -> bool:
    import praxis_personen
    daten = praxis_personen.laden(configOrdner())
    daten["pdf"] = {k: werte.get(k, STANDARD[k]) for k in STANDARD}
    return praxis_personen.speichern(configOrdner(), daten)


def briefpapierPfad() -> str:
    pfad = os.path.join(configOrdner(), BRIEFPAPIER)
    return pfad if os.path.exists(pfad) else ""


def oberRand() -> float:
    return float(einstellungen()["oben"])


def unterRand() -> float:
    return float(einstellungen()["unten"])


# ---------- Ghostscript ----------
def ghostscriptOrdner() -> str:
    return os.environ.get("SCOREGDT_GHOSTSCRIPT") or os.path.join(basedir, "ghostscript")


def ghostscriptProgramm() -> str:
    ordner = ghostscriptOrdner()
    for name in ("gswin64c.exe", "gswin32c.exe", "gs"):
        pfad = os.path.join(ordner, "bin", name)
        if os.path.exists(pfad):
            return pfad
    return shutil.which("gswin64c") or shutil.which("gs") or ""


def _psPfad(pfad: str) -> str:
    """Pfad fuer PostScript-Strings: Schraegstriche statt Backslashes, Klammern maskiert."""
    return pfad.replace("\\", "/").replace("(", "\\(").replace(")", "\\)")


def alsPdfA(eingabe: str, ausgabe: str) -> bool:
    gs = ghostscriptProgramm()
    if not gs:
        logger.logger.warning("PDF/A: Ghostscript nicht gefunden, PDF bleibt ohne PDF/A")
        return False
    ordner = ghostscriptOrdner()
    icc = os.path.join(ordner, "srgb.icc")
    definition = os.path.join(ordner, "PDFA_def.ps")
    if not (os.path.exists(icc) and os.path.exists(definition)):
        logger.logger.warning("PDF/A: srgb.icc oder PDFA_def.ps fehlt in " + ordner)
        return False
    befehl = [
        gs, "-dPDFA=2", "-dBATCH", "-dNOPAUSE", "-dNOOUTERSAVE", "-dQUIET",
        "-sColorConversionStrategy=RGB", "-sProcessColorModel=DeviceRGB",
        "-dPDFACompatibilityPolicy=1", "-sDEVICE=pdfwrite",
        "-sICCProfile=" + _psPfad(icc),
        "--permit-file-read=" + _psPfad(ordner) + "/",
        "-sOutputFile=" + ausgabe,
        definition, eingabe,
    ]
    try:
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        erg = subprocess.run(befehl, capture_output=True, timeout=90, creationflags=flags)
        if erg.returncode != 0 or not os.path.exists(ausgabe) or os.path.getsize(ausgabe) == 0:
            logger.logger.error("PDF/A: Ghostscript-Fehler " + str(erg.returncode) + ": " + erg.stderr.decode("utf-8", "replace")[-500:])
            return False
        return True
    except Exception as e:
        logger.logger.error("PDF/A: Ghostscript konnte nicht ausgefuehrt werden: " + str(e))
        return False


def pdfaKennung(pfad: str) -> dict:
    """Liest aus dem PDF: PDF/A-Teil und -Stufe (XMP-Metadaten) und ob ein
    PDF/A-OutputIntent mit Farbprofil vorhanden ist."""
    import re
    ergebnis = {"part": "", "conformance": "", "outputIntent": False}
    try:
        from pypdf import PdfReader
        root = PdfReader(pfad).trailer["/Root"]
        meta = root.get("/Metadata")
        xmp = meta.get_object().get_data() if meta is not None else b""
        intents = root.get("/OutputIntents") or []
        for oi in intents:
            oi = oi.get_object()
            if str(oi.get("/S")) == "/GTS_PDFA1" and oi.get("/DestOutputProfile") is not None:
                ergebnis["outputIntent"] = True
    except Exception:
        with open(pfad, "rb") as f:
            xmp = f.read()
    m = re.search(rb"pdfaid:part\s*(?:=\s*['\"]|>)\s*(\d)", xmp)
    if m:
        ergebnis["part"] = m.group(1).decode()
    m = re.search(rb"pdfaid:conformance\s*(?:=\s*['\"]|>)\s*([A-Za-z])", xmp)
    if m:
        ergebnis["conformance"] = m.group(1).decode().upper()
    return ergebnis


def istPdfA(pfad: str) -> bool:
    """True, wenn das PDF als PDF/A-2 gekennzeichnet ist und ein PDF/A-Farbprofil traegt."""
    k = pdfaKennung(pfad)
    return k["part"] == "2" and k["outputIntent"]


# ---------- Briefpapier ----------
def aufBriefpapier(eingabe: str, briefpapier: str, ausgabe: str) -> bool:
    try:
        from pypdf import PdfReader, PdfWriter
        vorlage = PdfReader(briefpapier)
        inhalt = PdfReader(eingabe)
        schreiber = PdfWriter()
        for nr, seite in enumerate(inhalt.pages):
            hintergrund = vorlage.pages[0] if (nr == 0 or len(vorlage.pages) == 1) else vorlage.pages[1]
            neu = schreiber.add_blank_page(width=hintergrund.mediabox.width, height=hintergrund.mediabox.height)
            neu.merge_page(hintergrund)
            neu.merge_page(seite)
        with open(ausgabe, "wb") as f:
            schreiber.write(f)
        return True
    except Exception as e:
        logger.logger.error("Briefpapier konnte nicht unterlegt werden: " + str(e))
        return False


# ---------- Gesamtablauf ----------
def fertigstellen(roh: str, ziel: str, briefpapier=None, pdfa=None) -> str:
    """Macht aus dem Roh-PDF das fertige PDF und legt es unter ziel ab.
    Gibt zurueck, was geklappt hat: z. B. "Briefpapier, PDF/A" oder ""."""
    if briefpapier is None:
        briefpapier = briefpapierPfad()
    if pdfa is None:
        pdfa = einstellungen()["pdfa"]
    aktuell = roh
    zwischen = []
    erledigt = []
    if briefpapier:
        bp = roh + ".bp.tmp"
        if aufBriefpapier(aktuell, briefpapier, bp):
            aktuell = bp
            zwischen.append(bp)
            erledigt.append("Briefpapier")
    if pdfa:
        pa = roh + ".pdfa.tmp"
        if alsPdfA(aktuell, pa):
            aktuell = pa
            zwischen.append(pa)
            erledigt.append("PDF/A")
    if aktuell == roh:
        os.replace(roh, ziel)
    else:
        os.replace(aktuell, ziel)
        try:
            os.remove(roh)
        except Exception:
            pass
    for z in zwischen:
        if z != aktuell and os.path.exists(z):
            try:
                os.remove(z)
            except Exception:
                pass
    return ", ".join(erledigt)
