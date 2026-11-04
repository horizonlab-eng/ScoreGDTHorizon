"""
Automatischer Oberflaechentest (laeuft beim Bau auf GitHub unter Windows, ohne Bildschirm).
Baut die Praxis-Fenster unsichtbar auf und prueft ihr Verhalten. Schlaegt ein Test
fehl, bricht der Bau ab und es wird keine neue Version veroeffentlicht.

Aufruf aus dem Projektordner:  python tests/oberflaechentest.py
"""
import os, sys, json, shutil, tempfile, configparser
from xml.etree import ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJEKT)
os.chdir(PROJEKT)

from PySide6.QtWidgets import QApplication
import class_score, praxis_personen, praxisStartfenster, dialogPraxisRollen, hintergrund, praxis

fehler = []
def pruefe(bedingung, text):
    print(("OK    " if bedingung else "FEHLER") + "  " + text)
    if not bedingung:
        fehler.append(text)

app = QApplication(sys.argv)
scoresPfad = os.path.join(PROJEKT, "scores")
alle = [str(s.get("name")) for s in class_score.Score.getGesamtRoot(scoresPfad).findall("score")]

# Einstellungsordner wie C:\ProgramData\scoregdt nachbilden
cfg = tempfile.mkdtemp()
ini = configparser.ConfigParser(interpolation=None)
ini.read(os.path.join(PROJEKT, "config.ini"), encoding="utf-8")
ini["Benutzer"]["namen"] = "Dr. Beispiel::Sabine Muster"
ini["Benutzer"]["kuerzel"] = "BO::SH"
ini["GDT"]["gdtimportverzeichnis"] = "F:\\ScoreGDT\\Import\\%USERNAME%"
with open(os.path.join(cfg, "config.ini"), "w", encoding="utf-8") as f:
    ini.write(f)
ini2 = configparser.ConfigParser(interpolation=None)
ini2.read(os.path.join(cfg, "config.ini"), encoding="utf-8")
pruefe(ini2["GDT"]["gdtimportverzeichnis"].endswith("%USERNAME%"), "Einstellungen mit %USERNAME% lesbar")

def favoriten(ordner, namen):
    os.makedirs(ordner, exist_ok=True)
    r = ET.Element("favoriten")
    for n in namen:
        ET.SubElement(r, "favorit").text = n
    ET.ElementTree(r).write(os.path.join(ordner, "favoriten.xml"), "utf-8", True)

favoriten(cfg, alle[:12])                                    # Praxis-Favoriten
favoriten(praxis_personen.rollenOrdner(cfg, "MFA"), alle[:3])  # Vorlage MFA
d = praxis_personen.laden(cfg)
d["personRolle"] = {"SH": "MFA"}
praxis_personen.speichern(cfg, d)

namen, kuerzel = ["Dr. Beispiel", "Sabine Muster"], ["BO", "SH"]

# --- Startfenster ---
s0 = praxisStartfenster.Startfenster(cfg, scoresPfad, "1050", "Max Mustermann (* 01.01.1995)", namen, kuerzel, 0, "")
pruefe(s0.comboBoxPerson.count() == 2, "Startfenster: zwei Personen in der Auswahl")
pruefe(len(s0.radioButtonsScore) == 12, "Startfenster: Person ohne Rolle sieht die 12 Praxis-Favoriten")
pruefe(s0.buttonTrendAusdruck.text().startswith("Verlauf"), "Startfenster: Knopf heißt 'Verlauf / PDF'")
s0.comboBoxPerson.setCurrentIndex(1)
pruefe(s0.result() == praxisStartfenster.NEU_OEFFNEN and s0.neuerPersonIndex == 1, "Startfenster: Personenwechsel öffnet neu mit Person 2")
s1 = praxisStartfenster.Startfenster(cfg, scoresPfad, "1050", "Max Mustermann", namen, kuerzel, 1, "")
pruefe(len(s1.radioButtonsScore) == 3, "Startfenster: MFA sieht die 3 Scores ihrer Rollenvorlage")
pruefe(os.path.exists(os.path.join(praxis_personen.personOrdner(cfg, "SH"), "favoriten.xml")), "Startfenster: eigene Favoriten der Person angelegt")
s9 = praxisStartfenster.Startfenster(cfg, scoresPfad, "1050", "X", namen, kuerzel, 9, "")
pruefe(s9.personIndex == 0, "Startfenster: ungültige Person fällt auf die erste zurück")

# --- Rollen-Dialog ---
r = dialogPraxisRollen.RollenDialog(cfg, scoresPfad, namen, kuerzel)
pruefe(r.tabelle.rowCount() == 2, "Rollen-Dialog: zwei Personen in der Tabelle")
r.listeRollen.addItem("VERAH")
r.rollenAuswahlenAktualisieren()
r.tabelle.cellWidget(0, 2).setCurrentText("Arzt")
r.tabelle.cellWidget(1, 2).setCurrentText("VERAH")
r.tabelle.cellWidget(0, 3).setCurrentText(alle[5])
r.rbWindows.setChecked(True)
r.accept()
gespeichert = praxis_personen.laden(cfg)
pruefe("VERAH" in gespeichert["rollen"], "Rollen-Dialog: neue Rolle gespeichert")
pruefe(gespeichert["personRolle"] == {"BO": "Arzt", "SH": "VERAH"}, "Rollen-Dialog: Rollen der Personen gespeichert")
pruefe(gespeichert["personStandardscore"].get("BO") == alle[5], "Rollen-Dialog: Standard-Score gespeichert")
pruefe(gespeichert["vorauswahlUeber"] == "windows", "Rollen-Dialog: Vorauswahl nach Windows-Anmeldung gespeichert")
r.tabelle.selectRow(1)

# --- Hintergrundbetrieb: Bausteine vorhanden ---
pruefe(hintergrund.pipeName().startswith("ScoreGDT-"), "Hintergrund: Pipe-Name pro Sitzung")
pruefe(callable(getattr(praxis, "gdtSpeichern", None)), "Praxis-Hilfsfunktionen vorhanden")

shutil.rmtree(cfg, ignore_errors=True)
if fehler:
    print("\n" + str(len(fehler)) + " Test(s) fehlgeschlagen")
    sys.exit(1)
print("\nAlle Oberflächentests bestanden")
