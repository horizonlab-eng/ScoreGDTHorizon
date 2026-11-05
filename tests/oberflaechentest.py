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

# --- Acrobat-Vorlagen (Einzel-Score und Verlauf) ---
import praxis_vorlage
pruefe(not praxis_vorlage.vorhanden("score"), "Vorlage: anfangs keine Vorlage (Standard-Layout)")
praxis_vorlage.startvorlageErzeugen("score")
praxis_vorlage.startvorlageErzeugen("verlauf")
pruefe(praxis_vorlage.vorhanden("score") and praxis_vorlage.vorhanden("verlauf"), "Vorlage: Startvorlagen angelegt")
ps = praxis_vorlage.pruefen("score")
print("        Felder Score-Vorlage:", ps)
pruefe(ps["ok"] and ps["seiten"] == 2 and len(ps["felder"]) == 12 and not ps["unbekannt"], "Vorlage Score: 2 Seiten, 12 bekannte Felder")
pv = praxis_vorlage.pruefen("verlauf")
pruefe(pv["ok"] and "Details" in pv["felder"] and "Ergebnis" not in pv["felder"], "Vorlage Verlauf: Details ja, Ergebnis nein")
felder = praxis_vorlage.felderLesen(praxis_vorlage.vorlagePfad("score"))
titel = [f for f in felder if f.name == "titel" and f.seite == 0]
pruefe(len(titel) == 1 and titel[0].groesse == 16 and titel[0].fett and titel[0].ausrichtung == "C", "Vorlage: Schriftgröße, fett und Ausrichtung gelesen")
pruefe(any(f.name == "details" and f.mehrzeilig for f in felder), "Vorlage: Details ist mehrzeilig")
pruefe(len([f for f in felder if f.name == "titel"]) == 2, "Vorlage: Titel auf beiden Seiten (ein Feld, zwei Widgets)")

for art, erwartet in (("score", ["Mustermann", "7 Punkte", "Auffälliges"]), ("verlauf", ["Barthel-Index", "Geriatrie", "CHA2DS2-VASc"])):
    probe = os.path.join(cfg, "probe_" + art + ".pdf")
    ok = praxis_vorlage.probeErzeugen(art, probe)
    pruefe(ok and os.path.exists(probe), "Vorlage " + art + ": Probe-PDF erzeugt")
    if not ok:
        continue
    pruefe(praxis_pdf.istPdfA(probe), "Vorlage " + art + ": Ergebnis ist PDF/A-2b")
    lp = PdfReader(probe)
    gesamt = " ".join((s.extract_text() or "") for s in lp.pages)
    erste = lp.pages[0].extract_text() or ""
    print("        Seite 1 (" + art + "):", erste[:300].replace("\n", " | "))
    pruefe(len(lp.pages) >= 2, "Vorlage " + art + ": lange Tabelle läuft auf " + str(len(lp.pages)) + " Seiten")
    pruefe(all(e in gesamt for e in erwartet), "Vorlage " + art + ": Inhalte stehen im PDF")
    pruefe("BRIEFKOPF" in erste and "Seite 1 von " + str(len(lp.pages)) in erste, "Vorlage " + art + ": Briefpapier und Seitenzahl auf Seite 1")
    if len(lp.pages) >= 2:
        zweite = lp.pages[1].extract_text() or ""
        pruefe("FOLGESEITE" in zweite and "Mustermann" in zweite, "Vorlage " + art + ": Folgeseite mit Kopf")
        if art == "score":
            pruefe("7 Punkte" not in zweite, "Vorlage score: Ergebnis nur auf Seite 1")
    pruefe("/AcroForm" not in lp.trailer["/Root"] and all(not s.get("/Annots") for s in lp.pages), "Vorlage " + art + ": keine Formularfelder mehr im fertigen PDF")
    pruefe("Beispielbeurteilung 1 " in gesamt or art == "score", "Vorlage " + art + ": Beurteilungsspalte vorhanden")

d2 = dialogPraxisPdf.PdfDialog()
pruefe(d2.vorlageLabels["score"].text().startswith("Aktiv") and d2.vorlageKnoepfe["score"]["acrobat"].isEnabled(), "PDF-Dialog: Vorlage wird als aktiv angezeigt")
os.remove(praxis_vorlage.vorlagePfad("verlauf"))
d2.anzeigeAktualisieren()
pruefe(not d2.vorlageKnoepfe["verlauf"]["probe"].isEnabled(), "PDF-Dialog: ohne Vorlage sind Probe/Bearbeiten aus")

# --- Gespeicherte Bögen (Doppelklick in medatixx = "Untersuchung zeigen") ---
import praxis_boegen, class_widgets
pruefe(praxis_boegen.schluessel("02112026", "134426") == "20261102134426", "Bogen: Schlüssel aus 6200/6201")
pruefe(praxis_boegen.schluessel("", "134426") == "", "Bogen: ohne Datum kein Schlüssel")

def testFenster():
    class F: pass
    f = F()
    f.widgets = [
        class_widgets.LineEdit("w1", "p1", "Alter", "", "Jahre", r"^\d+$", False, "", False, False),
        class_widgets.ComboBox("w2", "p1", "Mobilität", "", "", [("selbstständig", "0"), ("mit Hilfe", "1"), ("bettlägerig", "2")], 0, False, False, False),
        class_widgets.CheckBox("w3", "p1", "", "Sturz im letzten Jahr", "", "", "1", False, False, "", False, False, False),
        class_widgets.RadioButton("w4", "p2", "Ja", "", "", "1", False, False, "", False, False),
    ]
    f.einheitToggles = {}
    f.konvertButtonClicked = lambda checked, wid: None
    return f

trendDir = os.path.join(cfg, "trends")
os.makedirs(trendDir)
f1 = testFenster()
f1.widgets[0].getQt().setText("84")
f1.widgets[1].getQt().setCurrentIndex(2)
f1.widgets[2].getQt().setChecked(True)
f1.widgets[3].getQt().setChecked(True)
z1 = praxis_boegen.zustandLesen(f1.widgets, f1.einheitToggles)
daten = dict(z1)
daten.update({"schluessel": "20261102134426", "score": "Testscore", "datum": "02112026", "uhrzeit": "134426", "kuerzel": "SH", "name": "Sabine Muster", "kommentar": "Hallo äöü"})
pfad = praxis_boegen.speichern(trendDir, "21879", daten)
pruefe(os.path.exists(pfad) and pfad.endswith(os.path.join("21879", "boegen", "20261102134426.json")), "Bogen: im Trendverzeichnis des Patienten gespeichert")
g = praxis_boegen.finden(trendDir, "21879", "02112026", "134426")
pruefe(g.get("score") == "Testscore" and g.get("kuerzel") == "SH" and g.get("kommentar") == "Hallo äöü", "Bogen: exakt wiedergefunden (mit Ersteller und Kommentar)")
pruefe(praxis_boegen.finden(trendDir, "21879", "02112026", "134431").get("score") == "Testscore", "Bogen: wenige Sekunden Abweichung werden toleriert")
pruefe(praxis_boegen.finden(trendDir, "21879", "02112026", "150000") == {}, "Bogen: anderer Eintrag am selben Tag wird nicht verwechselt")
pruefe(praxis_boegen.finden(trendDir, "99999", "02112026", "134426") == {}, "Bogen: anderer Patient findet nichts")
f2 = testFenster()
fehlend = praxis_boegen.zustandSetzen(f2, g)
z2 = praxis_boegen.zustandLesen(f2.widgets, f2.einheitToggles)
pruefe(fehlend == [] and praxis_boegen.gleich(z1, z2), "Bogen: alle Antworten wiederhergestellt")
pruefe(f2.widgets[0].getQt().text() == "84" and f2.widgets[1].getQt().currentIndex() == 2 and f2.widgets[2].getQt().isChecked() and f2.widgets[3].getQt().isChecked(), "Bogen: Text, Auswahl, Haken und Optionsfeld stimmen")
f2.widgets[1].getQt().setCurrentIndex(1)
pruefe(not praxis_boegen.gleich(z1, praxis_boegen.zustandLesen(f2.widgets, f2.einheitToggles)), "Bogen: Änderung wird erkannt")
pruefe(not praxis_boegen.gleich(dict(z1, kommentar="a"), dict(z1, kommentar="b")), "Bogen: geänderter Kommentar wird erkannt")
korr = praxis_boegen.zustandLesen(f2.widgets, f2.einheitToggles)
korr.update({"schluessel": "20261102134426", "score": "Testscore", "datum": "02112026", "uhrzeit": "134426", "kuerzel": "SH", "name": "Sabine Muster", "korrekturVon": "BO"})
praxis_boegen.speichern(trendDir, "21879", korr)
g2 = praxis_boegen.finden(trendDir, "21879", "02112026", "134426")
pruefe(g2.get("korrekturVon") == "BO" and g2["widgets"]["w2"]["wert"] == 1 and len(g2.get("fruehereFassungen", [])) == 1 and g2["fruehereFassungen"][0]["widgets"]["w2"]["wert"] == 2, "Bogen: Korrektur gespeichert, frühere Fassung bleibt erhalten")
f3 = testFenster()
weg = dict(g); weg["widgets"] = dict(g["widgets"]); weg["widgets"]["altesFeld"] = {"typ": "text", "wert": "x"}
pruefe(praxis_boegen.zustandSetzen(f3, weg) == ["altesFeld"], "Bogen: Felder, die es im Score nicht mehr gibt, werden gemeldet")

# --- Hintergrundbetrieb: Bausteine vorhanden ---
pruefe(hintergrund.pipeName().startswith("ScoreGDT-"), "Hintergrund: Pipe-Name pro Sitzung")
pruefe(callable(getattr(praxis, "gdtSpeichern", None)), "Praxis-Hilfsfunktionen vorhanden")

shutil.rmtree(cfg, ignore_errors=True)
if fehler:
    print("\n" + str(len(fehler)) + " Test(s) fehlgeschlagen")
    sys.exit(1)
print("\nAlle Oberflächentests bestanden")
