"""
Praxis-Erweiterungen fuer ScoreGDT (Zweig "praxis").

Eigene Hilfsfunktionen sind hier gesammelt, damit die Dateien des Autors
moeglichst wenig veraendert werden muessen. Das erleichtert spaetere
Updates (Uebernahme der Aenderungen aus retconx/scoregdt).
"""
import os, glob, time, datetime
import logger

# PDFs im Exportordner, die aelter sind, werden beim Start geloescht.
# medatixx kopiert das PDF beim Einlesen, die Datei wird danach nicht mehr gebraucht.
PDF_AUFBEWAHRUNG_TAGE = 7

# Vorsilbe fuer Dateien, die gerade geschrieben werden. Sie darf NICHT mit dem
# Rueckschrieb-Namen (z. B. "MEDASCOR.*") uebereinstimmen, damit medatixx keine
# halb geschriebene Datei einliest.
HILFS_VORSILBE = "_schreibt_"


def zeitstempel() -> str:
    """Datum und Uhrzeit bis auf Tausendstelsekunden, z. B. 20261104121530123."""
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:17]


def ordnerAnlegen(*ordner: str):
    """Legt fehlende Ordner an (z. B. die persoenlichen Austauschordner)."""
    for pfad in ordner:
        if pfad and not os.path.isdir(pfad):
            try:
                os.makedirs(pfad, exist_ok=True)
                logger.logger.info("Ordner angelegt: " + pfad)
            except Exception as e:
                logger.logger.warning("Ordner konnte nicht angelegt werden: " + pfad + " (" + str(e) + ")")


def rueckschriebPfad(exportVerzeichnis: str, basisname: str, mitZeitstempel: bool) -> str:
    """
    Pfad fuer den Rueckschrieb an das PVS.
    mitZeitstempel=True:  MEDASCOR.20261104121530123  (in medatixx: "MEDASCOR.*")
    mitZeitstempel=False: MEDASCOR.gdt                 (Verhalten des Originals)
    """
    endung = zeitstempel() if mitZeitstempel else "gdt"
    return os.path.join(exportVerzeichnis, basisname + "." + endung)


def pdfPfad(exportVerzeichnis: str, art: str, patId: str) -> str:
    """Eindeutiger PDF-Name, z. B. ScoreGDT_score_1050_20261104121530123.pdf"""
    return os.path.join(exportVerzeichnis, "ScoreGDT_" + art + "_" + patId + "_" + zeitstempel() + ".pdf")


def hilfsPfad(zielPfad: str) -> str:
    """Hilfsname im selben Ordner, unter dem zuerst geschrieben wird."""
    ordner, name = os.path.split(zielPfad)
    return os.path.join(ordner, HILFS_VORSILBE + name.replace(".", "_") + ".tmp")


def fertigstellen(hilfsDatei: str, zielPfad: str) -> bool:
    """Benennt die fertig geschriebene Datei auf ihren endgueltigen Namen um."""
    try:
        os.replace(hilfsDatei, zielPfad)
        return True
    except Exception as e:
        logger.logger.error("Umbenennen fehlgeschlagen: " + hilfsDatei + " -> " + zielPfad + " (" + str(e) + ")")
        return False


def gdtSpeichern(gdtDatei, zielPfad: str, zeichensatz) -> bool:
    """Schreibt die GDT-Datei zuerst unter einem Hilfsnamen und benennt sie dann um."""
    hilfsDatei = hilfsPfad(zielPfad)
    if not gdtDatei.speichern(hilfsDatei, zeichensatz):
        return False
    return fertigstellen(hilfsDatei, zielPfad)


def pdfSpeichern(fpdfObjekt, zielPfad: str) -> bool:
    """Schreibt das PDF zuerst unter einem Hilfsnamen und benennt es dann um."""
    hilfsDatei = hilfsPfad(zielPfad)
    try:
        fpdfObjekt.output(hilfsDatei)
    except Exception as e:
        logger.logger.error("Fehler bei PDF-Output nach " + hilfsDatei + " (" + str(e) + ")")
        return False
    return fertigstellen(hilfsDatei, zielPfad)


def aufraeumen(exportVerzeichnis: str):
    """Loescht alte PDFs von ScoreGDT und liegengebliebene Hilfsdateien."""
    if not exportVerzeichnis or not os.path.isdir(exportVerzeichnis):
        return
    jetzt = time.time()
    regeln = [
        ("ScoreGDT_*.pdf", PDF_AUFBEWAHRUNG_TAGE * 86400),
        (HILFS_VORSILBE + "*.tmp", 86400),
    ]
    for muster, maxAlter in regeln:
        for datei in glob.glob(os.path.join(exportVerzeichnis, muster)):
            try:
                if jetzt - os.path.getmtime(datei) > maxAlter:
                    os.remove(datei)
                    logger.logger.info("Alte Datei geloescht: " + datei)
            except Exception as e:
                logger.logger.warning("Konnte alte Datei nicht loeschen: " + datei + " (" + str(e) + ")")


def anfrageLoeschen(pfad: str):
    """Loescht die Anfrage des PVS (z. B. SCORMEDA.gdt), wenn ScoreGDT beendet wird.
    Wird per atexit aufgerufen. Bei einem Neustart ueber os.execl (z. B.
    "Score auswaehlen") laeuft atexit nicht – die Anfrage bleibt dann erhalten."""
    try:
        if os.path.exists(pfad):
            os.remove(pfad)
            logger.logger.info("Anfrage geloescht: " + pfad)
    except Exception as e:
        logger.logger.warning("Anfrage konnte nicht geloescht werden: " + pfad + " (" + str(e) + ")")
