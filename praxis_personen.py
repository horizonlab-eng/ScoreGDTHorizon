"""
Personen, Rollen und Favoriten pro Person (Zweig "praxis", Etappe 3).

Ablage (zentral, fuer alle Benutzer beschreibbar) im Einstellungsordner
C:\\ProgramData\\scoregdt:
    personen.json                  Rollen, Rolle je Person, Standard-Score je Person,
                                   zuletzt gewaehlte Person je Arbeitsplatz
    rollen\\<Rolle>\\favoriten.xml   Favoriten-Vorlage einer Rolle
    personen\\<Kuerzel>\\favoriten.xml Favoriten einer Person

Die Personen selbst (Name und Kuerzel) bleiben in der config.ini des Originals
([Benutzer] namen/kuerzel) und werden weiter unter "BenutzerInnen verwalten"
gepflegt. favoriten.xml hat das Format des Originals, daher funktionieren die
Favoriten-Dialoge und -Funktionen des Autors unveraendert mit diesen Ordnern.
"""
import os, json, shutil, re
import logger, class_score

DATEI = "personen.json"
VORAUSWAHL_ARBEITSPLATZ = "arbeitsplatz"
VORAUSWAHL_WINDOWS = "windows"
VORAUSWAHL_FRAGEN = "fragen"   # bei jedem Aufruf nach dem Kuerzel fragen (Standard)

STANDARD = {
    "rollen": ["Arzt", "MFA"],
    "personRolle": {},          # Kuerzel -> Rolle
    "personStandardscore": {},  # Kuerzel -> Score-Name
    "zuletzt": {},              # "pc:<Arbeitsplatz>" bzw. "user:<Windows-Benutzer>" -> Kuerzel
    "vorauswahlUeber": VORAUSWAHL_FRAGEN,
}


# ---------- Laden und Speichern ----------
def laden(configPath: str) -> dict:
    daten = json.loads(json.dumps(STANDARD))
    pfad = os.path.join(configPath, DATEI)
    try:
        if os.path.exists(pfad):
            with open(pfad, "r", encoding="utf-8") as f:
                gelesen = json.load(f)
            for schluessel in STANDARD:
                if schluessel in gelesen and isinstance(gelesen[schluessel], type(STANDARD[schluessel])):
                    daten[schluessel] = gelesen[schluessel]
    except Exception as e:
        logger.logger.warning("personen.json konnte nicht gelesen werden: " + str(e))
    return daten


def speichern(configPath: str, daten: dict) -> bool:
    pfad = os.path.join(configPath, DATEI)
    hilf = pfad + ".tmp"
    try:
        with open(hilf, "w", encoding="utf-8") as f:
            json.dump(daten, f, ensure_ascii=False, indent=2)
        os.replace(hilf, pfad)
        return True
    except Exception as e:
        logger.logger.error("personen.json konnte nicht gespeichert werden: " + str(e))
        return False


# ---------- Ordner ----------
def _sicher(name: str) -> str:
    """Macht aus einem Kuerzel/Rollennamen einen gueltigen Ordnernamen."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip().strip(".")
    return name or "_"


def personOrdner(configPath: str, kuerzel: str) -> str:
    return os.path.join(configPath, "personen", _sicher(kuerzel))


def rollenOrdner(configPath: str, rolle: str) -> str:
    return os.path.join(configPath, "rollen", _sicher(rolle))


def _favoritenKopieren(quelleOrdner: str, zielOrdner: str) -> bool:
    quelle = os.path.join(quelleOrdner, "favoriten.xml")
    if not os.path.exists(quelle):
        return False
    os.makedirs(zielOrdner, exist_ok=True)
    shutil.copyfile(quelle, os.path.join(zielOrdner, "favoriten.xml"))
    return True


def rollenvorlageSicherstellen(configPath: str, rolle: str) -> str:
    """Die Vorlage einer Rolle startet als Kopie der Praxis-Favoriten (favoriten.xml im Einstellungsordner)."""
    ordner = rollenOrdner(configPath, rolle)
    if not os.path.exists(os.path.join(ordner, "favoriten.xml")):
        _favoritenKopieren(configPath, ordner)
    return ordner


def personFavoritenOrdner(configPath: str, kuerzel: str, rolle: str) -> str:
    """Ordner mit den Favoriten einer Person. Fehlen sie, werden sie aus der
    Vorlage der Rolle (oder den Praxis-Favoriten) angelegt."""
    ordner = personOrdner(configPath, kuerzel)
    if not os.path.exists(os.path.join(ordner, "favoriten.xml")):
        quelle = rollenvorlageSicherstellen(configPath, rolle) if rolle else configPath
        if not _favoritenKopieren(quelle, ordner):
            _favoritenKopieren(configPath, ordner)
    return ordner


def personZuruecksetzen(configPath: str, kuerzel: str, rolle: str) -> bool:
    """Ueberschreibt die Favoriten einer Person mit der Vorlage ihrer Rolle."""
    quelle = rollenvorlageSicherstellen(configPath, rolle) if rolle else configPath
    return _favoritenKopieren(quelle, personOrdner(configPath, kuerzel))


def favoritenRoot(configPath: str, scoresPfad: str, kuerzel: str, rolle: str):
    """Favoriten einer Person als Score-Root (wie getScoreFavoritenRoot des Originals).
    Sind sie leer oder nicht lesbar, werden die Praxis-Favoriten verwendet."""
    try:
        ordner = personFavoritenOrdner(configPath, kuerzel, rolle)
        root = class_score.Score.getScoreFavoritenRoot(ordner, scoresPfad)
        if len(root.findall("score")) > 0:
            return root
    except Exception as e:
        logger.logger.warning("Favoriten von " + kuerzel + " nicht lesbar: " + str(e))
    return class_score.Score.getScoreFavoritenRoot(configPath, scoresPfad)


# ---------- Vorauswahl der Person ----------
def arbeitsplatzSchluessel(daten: dict) -> str:
    if daten.get("vorauswahlUeber") == VORAUSWAHL_WINDOWS:
        return "user:" + os.environ.get("USERNAME", "")
    return "pc:" + (os.environ.get("CLIENTNAME") or os.environ.get("COMPUTERNAME") or "")


def vorauswahl(configPath: str, kuerzelListe: list, ersatzIndex: int) -> int:
    """Index der Person, die an diesem Arbeitsplatz (bzw. mit diesem Windows-Konto) zuletzt gearbeitet hat."""
    daten = laden(configPath)
    kuerzel = daten["zuletzt"].get(arbeitsplatzSchluessel(daten))
    if kuerzel in kuerzelListe:
        return kuerzelListe.index(kuerzel)
    if 0 <= ersatzIndex < len(kuerzelListe):
        return ersatzIndex
    return 0


def sollFragen(configPath: str) -> bool:
    return laden(configPath).get("vorauswahlUeber") == VORAUSWAHL_FRAGEN


def kuerzelSuchen(eingabe: str, kuerzelListe: list):
    """Index der Person mit genau diesem Kuerzel (Gross-/Kleinschreibung egal), sonst None."""
    e = eingabe.strip().casefold()
    for i, k in enumerate(kuerzelListe):
        if k.strip().casefold() == e and e != "":
            return i
    return None


def merken(configPath: str, kuerzel: str):
    daten = laden(configPath)
    daten["zuletzt"][arbeitsplatzSchluessel(daten)] = kuerzel
    speichern(configPath, daten)


# ---------- Administrator ----------
def istAdmin() -> bool:
    """True, wenn ScoreGDT "als Administrator ausgefuehrt" wird."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return os.name != "nt"  # ausserhalb von Windows (Tests) nicht einschraenken
