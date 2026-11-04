"""
Automatischer Oberflaechentest (laeuft beim Bau auf GitHub unter Windows, ohne Bildschirm).
Baut die Praxis-Fenster unsichtbar auf und prueft ihr Verhalten. Schlaegt ein Test
fehl, bricht der Bau ab und es wird keine neue Version veroeffentlicht.

Aufruf aus dem Projektordner:  python tests/oberflaechentest.py
"""
import os, sys, json, shutil, tempfile, configparser, datetime
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
os.environ["SCOREGDT_CONFIG"] = cfg
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
pruefe(d["vorauswahlUeber"] == "fragen", "Standard: beim Öffnen nach dem Kürzel fragen")
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

# --- "Wer dokumentiert?" ---
a = praxisStartfenster.KuerzelAbfrage(namen, kuerzel, "Max Mustermann")
pruefe(a.gewaehlterIndex is None and a.liste.currentItem() is None, "Kürzel-Abfrage: niemand vorausgewählt")
a.eingabe.setText("sh"); a.eingabeBestaetigt()
pruefe(a.result() == 1 and a.gewaehlterIndex == 1, "Kürzel-Abfrage: 'sh' + Enter wählt Sabine Muster")
b = praxisStartfenster.KuerzelAbfrage(namen, kuerzel)
b.eingabe.setText("ZZ"); b.eingabeBestaetigt()
pruefe(b.gewaehlterIndex is None and b.hinweis.text() != "", "Kürzel-Abfrage: unbekanntes Kürzel wird nicht angenommen")
c = praxisStartfenster.KuerzelAbfrage(namen, kuerzel)
c.eingabe.setText("Beispiel"); c.eingabeBestaetigt()
pruefe(c.gewaehlterIndex == 0, "Kürzel-Abfrage: eindeutiger Namensteil wählt Dr. Beispiel")
pruefe(praxis_personen.kuerzelSuchen(" bo ", kuerzel) == 0, "Kürzel-Suche ignoriert Leerzeichen und Groß/klein")

# --- Rollen-Dialog ---
r = dialogPraxisRollen.RollenDialog(cfg, scoresPfad, namen, kuerzel)
pruefe(r.rbFragen.isChecked(), "Rollen-Dialog: 'nach dem Kürzel fragen' ist voreingestellt")
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

# --- Etappe 4: Verlauf ---
import class_trends, dialogTrendanzeige, praxis_pdf, scorepdf, dialogPraxisPdf
from PySide6.QtWidgets import QPushButton
test = class_trends.Test("qSofa-Score", "Infektiologie", class_trends.GdtTool.SCOREGDT)
for i in range(5):
    test.addTrend(class_trends.Trend(datetime.datetime(2026, 11, 4, 10, i), str(i) + " Punkte", "Beurteilung"))
pruefe(len(test.getLetzteTrends()) == 5, "Verlauf: mehrere Scores am selben Tag bleiben erhalten")
for i in range(40):
    test.addTrend(class_trends.Trend(datetime.datetime(2026, 1, 1) + datetime.timedelta(days=i), "x", "y"))
pruefe(len(test.getLetzteTrends()) == 30, "Verlauf: höchstens 30 Einträge je Score")
dt = dialogTrendanzeige.Trendanzeige([test])
knopf = [k for k in dt.findChildren(QPushButton) if k.text() == "PDF ansehen / drucken"]
pruefe(len(knopf) == 1, "Trendanzeige: Knopf 'PDF ansehen / drucken' vorhanden")
if knopf:
    knopf[0].click()
    pruefe(dt.result() == dialogTrendanzeige.ANSEHEN, "Trendanzeige: Knopf liefert 'ansehen'")

# --- Etappe 4: PDF/A und Briefpapier ---
def beispielPdf(pfad, zeilen=10):
    pdf = scorepdf.scorepdf("P", "mm", "A4", "Testbericht")
    pdf.add_page()
    pdf.set_font("dejavu", "", 11)
    for i in range(zeilen):
        pdf.cell(0, 7, "Zeile " + str(i + 1) + ": Ergebnis – Beurteilung äöüß", new_x="LMARGIN", new_y="NEXT")
    pdf.output(pfad)

pruefe(bool(praxis_pdf.ghostscriptProgramm()), "Ghostscript gefunden: " + str(praxis_pdf.ghostscriptProgramm()))
roh = os.path.join(cfg, "_roh1.tmp"); ziel = os.path.join(cfg, "a.pdf")
beispielPdf(roh)
erledigt = praxis_pdf.fertigstellen(roh, ziel, briefpapier="", pdfa=True)
print("        PDF/A-Kennung:", praxis_pdf.pdfaKennung(ziel))
pruefe("PDF/A" in erledigt and praxis_pdf.istPdfA(ziel), "PDF/A-2b erzeugt (" + erledigt + ")")
pruefe(praxis_pdf.pdfaKennung(ziel)["conformance"] == "B", "PDF/A-Stufe B (PDF/A-2b)")
pruefe(not os.path.exists(roh), "Roh-PDF wird aufgeräumt")

from fpdf import FPDF
bp = FPDF()
bp.add_page(); bp.set_font("helvetica", "B", 20); bp.text(20, 20, "BRIEFKOPF"); bp.rect(10, 270, 190, 15)
bp.add_page(); bp.set_font("helvetica", "B", 20); bp.text(20, 20, "FOLGESEITE")
bp.output(os.path.join(cfg, "briefpapier.pdf"))
pruefe(praxis_pdf.briefpapierPfad() != "", "Briefpapier wird gefunden")
roh2 = os.path.join(cfg, "_roh2.tmp"); ziel2 = os.path.join(cfg, "b.pdf")
beispielPdf(roh2, zeilen=60)
erledigt2 = praxis_pdf.fertigstellen(roh2, ziel2)
pruefe("Briefpapier" in erledigt2 and "PDF/A" in erledigt2 and praxis_pdf.istPdfA(ziel2), "Briefpapier + PDF/A (" + erledigt2 + ")")
from pypdf import PdfReader
seiten = PdfReader(ziel2).pages
pruefe(len(seiten) >= 2, "Mehrseitiges PDF: " + str(len(seiten)) + " Seiten")
if len(seiten) >= 2:
    t0, t1 = seiten[0].extract_text() or "", seiten[1].extract_text() or ""
    pruefe("BRIEFKOPF" in t0 and "Zeile 1" in t0, "Seite 1: Briefkopf und Inhalt")
    pruefe("FOLGESEITE" in t1 and "BRIEFKOPF" not in t1, "Seite 2: Folgeseiten-Vorlage")

d = dialogPraxisPdf.PdfDialog()
d.spinOben.setValue(45); d.spinUnten.setValue(30)
d.accept()
w = praxis_pdf.einstellungen()
pruefe(w["oben"] == 45 and w["unten"] == 30 and w["pdfa"] is True, "PDF-Dialog: Einstellungen gespeichert")
ziel3 = os.path.join(cfg, "testseite.pdf")
erledigt3 = d.testseiteErzeugen(ziel3)
pruefe(os.path.exists(ziel3) and "PDF/A" in erledigt3, "PDF-Dialog: Testseite erzeugt (" + erledigt3 + ")")
pruefe(praxis_personen.laden(cfg)["pdf"].get("oben") == 45 and "VERAH" in praxis_personen.laden(cfg)["rollen"], "PDF-Einstellungen und Rollen bestehen nebeneinander")

# --- Hintergrundbetrieb: Bausteine vorhanden ---
pruefe(hintergrund.pipeName().startswith("ScoreGDT-"), "Hintergrund: Pipe-Name pro Sitzung")
pruefe(callable(getattr(praxis, "gdtSpeichern", None)), "Praxis-Hilfsfunktionen vorhanden")

shutil.rmtree(cfg, ignore_errors=True)
if fehler:
    print("\n" + str(len(fehler)) + " Test(s) fehlgeschlagen")
    sys.exit(1)
print("\nAlle Oberflächentests bestanden")
