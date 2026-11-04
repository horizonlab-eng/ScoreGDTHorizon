"""
Dialog "PDF und Briefpapier" (Zweig "praxis", Etappe 4) - nur Administrator.

- Briefpapier-PDF hinterlegen oder entfernen (wird nach C:\\ProgramData\\scoregdt\\briefpapier.pdf kopiert;
  Seite 1 = erste Seite, Seite 2 (optional) = Folgeseiten)
- Raender oben/unten, damit der Text nicht in Logo oder Fusszeile rutscht
- PDF/A-2b ein/aus
- Testseite erzeugen und im PDF-Programm anzeigen
- Vorlagen fuer Adobe Acrobat Pro (Einzel-Score und Verlauf): Startvorlage anlegen,
  in Acrobat bearbeiten, andere PDF uebernehmen, Probe-PDF anzeigen, entfernen
"""
import os, shutil, tempfile
import praxis_pdf, praxis_vorlage, scorepdf
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QFileDialog, QSpinBox, QCheckBox, QFormLayout, QMessageBox, QGridLayout
)


class PdfDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF und Briefpapier")
        self.setMinimumWidth(760)
        werte = praxis_pdf.einstellungen()
        layout = QVBoxLayout()

        gbBrief = QGroupBox("Briefpapier")
        lyBrief = QVBoxLayout()
        self.labelBrief = QLabel()
        knoepfe = QHBoxLayout()
        self.knopfWaehlen = QPushButton("Briefpapier-PDF auswählen …")
        self.knopfEntfernen = QPushButton("Briefpapier entfernen")
        self.knopfWaehlen.clicked.connect(self.briefpapierWaehlen)
        self.knopfEntfernen.clicked.connect(self.briefpapierEntfernen)
        knoepfe.addWidget(self.knopfWaehlen)
        knoepfe.addWidget(self.knopfEntfernen)
        lyBrief.addWidget(self.labelBrief)
        lyBrief.addLayout(knoepfe)
        lyBrief.addWidget(QLabel("Seite 1 des Briefpapiers wird für die erste Seite verwendet,\neine eventuelle Seite 2 für alle Folgeseiten. Format: A4."))
        gbBrief.setLayout(lyBrief)

        gbRand = QGroupBox("Ränder für den Text (damit er nicht in Logo oder Fußzeile rutscht)")
        lyRand = QFormLayout()
        self.spinOben = QSpinBox()
        self.spinOben.setRange(5, 150)
        self.spinOben.setSuffix(" mm")
        self.spinOben.setValue(int(werte["oben"]))
        self.spinUnten = QSpinBox()
        self.spinUnten.setRange(10, 150)
        self.spinUnten.setSuffix(" mm")
        self.spinUnten.setValue(int(werte["unten"]))
        lyRand.addRow("Abstand oben:", self.spinOben)
        lyRand.addRow("Abstand unten:", self.spinUnten)
        gbRand.setLayout(lyRand)

        self.checkPdfa = QCheckBox("PDF/A-2b erzeugen (für Archiv und ePA, empfohlen)")
        self.checkPdfa.setChecked(bool(werte["pdfa"]))
        self.labelGs = QLabel("")

        self.knopfTest = QPushButton("Testseite erzeugen und anzeigen")
        self.knopfTest.clicked.connect(self.testseite)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Vorlagen aus Adobe Acrobat Pro
        gbVorlagen = QGroupBox("Gestaltung mit Adobe Acrobat Pro (Vorlagen)")
        lyVorlagen = QVBoxLayout()
        erklaerung = QLabel("Ist eine Vorlage hinterlegt, gestaltet sie das PDF – Briefpapier und Ränder oben gelten dann nur noch "
                            "für die Startvorlage. In Acrobat: Werkzeuge › „Formular vorbereiten“. Felder verschieben und in der "
                            "Größe ändern; Schrift, Größe und Ausrichtung unter Eigenschaften. Feldnamen nicht ändern.")
        erklaerung.setWordWrap(True)
        lyVorlagen.addWidget(erklaerung)
        raster = QGridLayout()
        self.vorlageLabels = {}
        self.vorlageKnoepfe = {}
        for zeile, art in enumerate(("score", "verlauf")):
            titel = QLabel("<b>" + praxis_vorlage.ART_NAMEN[art] + "</b>")
            status = QLabel()
            status.setWordWrap(True)
            k = {
                "start": QPushButton("Startvorlage anlegen"),
                "acrobat": QPushButton("In Acrobat bearbeiten"),
                "uebernehmen": QPushButton("Andere PDF übernehmen …"),
                "probe": QPushButton("Probe-PDF anzeigen"),
                "entfernen": QPushButton("Vorlage entfernen"),
            }
            k["start"].clicked.connect(lambda _=False, a=art: self.vorlageAnlegen(a))
            k["acrobat"].clicked.connect(lambda _=False, a=art: self.vorlageBearbeiten(a))
            k["uebernehmen"].clicked.connect(lambda _=False, a=art: self.vorlageUebernehmen(a))
            k["probe"].clicked.connect(lambda _=False, a=art: self.vorlageProbe(a))
            k["entfernen"].clicked.connect(lambda _=False, a=art: self.vorlageEntfernen(a))
            raster.addWidget(titel, zeile * 2, 0)
            raster.addWidget(status, zeile * 2, 1, 1, 4)
            for spalte, schluessel in enumerate(("start", "acrobat", "uebernehmen", "probe", "entfernen")):
                raster.addWidget(k[schluessel], zeile * 2 + 1, spalte)
            self.vorlageLabels[art] = status
            self.vorlageKnoepfe[art] = k
        lyVorlagen.addLayout(raster)
        felderHinweis = QLabel("Feldnamen: " + ", ".join(praxis_vorlage.FELD_ERKLAERUNG.keys()))
        felderHinweis.setWordWrap(True)
        felderHinweis.setToolTip("\n".join(k + ": " + v for k, v in praxis_vorlage.FELD_ERKLAERUNG.items()))
        lyVorlagen.addWidget(felderHinweis)
        gbVorlagen.setLayout(lyVorlagen)

        layout.addWidget(gbBrief)
        layout.addWidget(gbRand)
        layout.addWidget(gbVorlagen)
        layout.addWidget(self.checkPdfa)
        layout.addWidget(self.labelGs)
        layout.addWidget(self.knopfTest)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)
        self.anzeigeAktualisieren()

    def anzeigeAktualisieren(self):
        pfad = praxis_pdf.briefpapierPfad()
        self.labelBrief.setText("Hinterlegt: " + pfad if pfad else "Kein Briefpapier hinterlegt (PDF ohne Hintergrund).")
        self.knopfEntfernen.setEnabled(bool(pfad))
        self.labelGs.setText("" if praxis_pdf.ghostscriptProgramm() else "Hinweis: Ghostscript wurde nicht gefunden – PDFs werden ohne PDF/A erzeugt.")
        for art in ("score", "verlauf"):
            self.vorlageStatus(art)

    # ---------- Vorlagen (Acrobat Pro) ----------
    def vorlageStatus(self, art: str):
        k = self.vorlageKnoepfe[art]
        da = praxis_vorlage.vorhanden(art)
        for schluessel in ("acrobat", "probe", "entfernen"):
            k[schluessel].setEnabled(da)
        if not da:
            self.vorlageLabels[art].setText("Keine Vorlage – es gilt das Standard-Layout mit Briefpapier.")
            return
        p = praxis_vorlage.pruefen(art)
        if not p["ok"]:
            self.vorlageLabels[art].setText("<span style='color:#b00'>Vorlage nicht lesbar: " + p["fehler"] + "</span>")
            return
        text = "Aktiv: " + praxis_vorlage.vorlagePfad(art) + " – " + str(p["seiten"]) + " Seite(n), Felder: " + (", ".join(p["felder"]) or "keine")
        if "Details" not in p["felder"]:
            text += "<br><span style='color:#b00'>Feld „Details“ fehlt – die Tabelle wird nicht gedruckt.</span>"
        if p["unbekannt"]:
            text += "<br><span style='color:#b60'>Unbekannte Feldnamen (werden ignoriert): " + ", ".join(p["unbekannt"]) + "</span>"
        self.vorlageLabels[art].setText(text)

    def vorlageAnlegen(self, art: str):
        if praxis_vorlage.vorhanden(art):
            mb = QMessageBox(QMessageBox.Icon.Question, "Hinweis von ScoreGDT",
                             "Es gibt schon eine Vorlage für „" + praxis_vorlage.ART_NAMEN[art] + "“. Überschreiben?\n"
                             "Die bisherige Gestaltung geht dabei verloren.",
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            mb.button(QMessageBox.StandardButton.Yes).setText("Überschreiben")
            mb.button(QMessageBox.StandardButton.No).setText("Abbrechen")
            if mb.exec() != QMessageBox.StandardButton.Yes:
                return
        try:
            praxis_pdf.einstellungenSpeichern(self.werte())
            praxis_vorlage.startvorlageErzeugen(art)
        except Exception as e:
            QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Startvorlage konnte nicht angelegt werden:\n" + str(e), QMessageBox.StandardButton.Ok).exec()
        self.anzeigeAktualisieren()

    def vorlageBearbeiten(self, art: str):
        try:
            os.startfile(praxis_vorlage.vorlagePfad(art))  # type: ignore
            QMessageBox(QMessageBox.Icon.Information, "Hinweis von ScoreGDT",
                        "Die Vorlage ist im PDF-Programm geöffnet.\n\n"
                        "1. Werkzeuge › „Formular vorbereiten“ wählen.\n"
                        "2. Felder verschieben/vergrößern, Schrift unter „Eigenschaften“ einstellen.\n"
                        "3. Logo, Linien und feste Texte frei ergänzen.\n"
                        "4. Speichern (Strg+S) und Acrobat schließen.\n"
                        "5. Hier „Probe-PDF anzeigen“ klicken.",
                        QMessageBox.StandardButton.Ok).exec()
        except Exception as e:
            QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Konnte nicht geöffnet werden: " + str(e), QMessageBox.StandardButton.Ok).exec()
        self.anzeigeAktualisieren()

    def vorlageUebernehmen(self, art: str):
        quelle, _ = QFileDialog.getOpenFileName(self, "PDF als Vorlage „" + praxis_vorlage.ART_NAMEN[art] + "“ übernehmen", "", "PDF-Dateien (*.pdf)")
        if not quelle:
            return
        try:
            from pypdf import PdfReader
            if len(PdfReader(quelle).pages) < 1:
                raise ValueError("Die Datei enthält keine Seite.")
            os.makedirs(praxis_pdf.configOrdner(), exist_ok=True)
            shutil.copyfile(quelle, praxis_vorlage.vorlagePfad(art))
        except Exception as e:
            QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Die Vorlage konnte nicht übernommen werden:\n" + str(e), QMessageBox.StandardButton.Ok).exec()
        self.anzeigeAktualisieren()

    def vorlageProbe(self, art: str):
        ziel = os.path.join(tempfile.gettempdir(), "ScoreGDT_Probe_" + art + ".pdf")
        self.anzeigeAktualisieren()
        if praxis_vorlage.probeErzeugen(art, ziel):
            try:
                os.startfile(ziel)  # type: ignore
            except Exception as e:
                QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Probe-PDF erzeugt, aber nicht geöffnet: " + ziel + "\n" + str(e), QMessageBox.StandardButton.Ok).exec()
        else:
            QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Das Probe-PDF konnte nicht erzeugt werden. Details stehen im Protokoll.\n"
                        "Ist die Vorlage evtl. noch in Acrobat geöffnet?", QMessageBox.StandardButton.Ok).exec()

    def vorlageEntfernen(self, art: str):
        mb = QMessageBox(QMessageBox.Icon.Question, "Hinweis von ScoreGDT",
                         "Vorlage „" + praxis_vorlage.ART_NAMEN[art] + "“ entfernen? Danach gilt wieder das Standard-Layout.",
                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        mb.button(QMessageBox.StandardButton.Yes).setText("Entfernen")
        mb.button(QMessageBox.StandardButton.No).setText("Abbrechen")
        if mb.exec() == QMessageBox.StandardButton.Yes:
            try:
                os.remove(praxis_vorlage.vorlagePfad(art))
            except Exception as e:
                QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Konnte nicht entfernt werden: " + str(e), QMessageBox.StandardButton.Ok).exec()
        self.anzeigeAktualisieren()

    def briefpapierWaehlen(self):
        quelle, _ = QFileDialog.getOpenFileName(self, "Briefpapier auswählen", "", "PDF-Dateien (*.pdf)")
        if not quelle:
            return
        try:
            from pypdf import PdfReader
            if len(PdfReader(quelle).pages) < 1:
                raise ValueError("Die Datei enthält keine Seite.")
            os.makedirs(praxis_pdf.configOrdner(), exist_ok=True)
            shutil.copyfile(quelle, os.path.join(praxis_pdf.configOrdner(), praxis_pdf.BRIEFPAPIER))
        except Exception as e:
            QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Das Briefpapier konnte nicht übernommen werden:\n" + str(e), QMessageBox.StandardButton.Ok).exec()
        self.anzeigeAktualisieren()

    def briefpapierEntfernen(self):
        pfad = praxis_pdf.briefpapierPfad()
        if pfad:
            try:
                os.remove(pfad)
            except Exception as e:
                QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Konnte nicht entfernt werden: " + str(e), QMessageBox.StandardButton.Ok).exec()
        self.anzeigeAktualisieren()

    def werte(self) -> dict:
        return {"pdfa": self.checkPdfa.isChecked(), "oben": self.spinOben.value(), "unten": self.spinUnten.value()}

    def testseiteErzeugen(self, ziel: str) -> str:
        """Erzeugt eine Testseite mit den aktuellen Einstellungen. Gibt zurueck, was angewendet wurde."""
        praxis_pdf.einstellungenSpeichern(self.werte())
        pdf = scorepdf.scorepdf("P", "mm", "A4", "Testseite ScoreGDT")
        pdf.add_page()
        pdf.set_font("dejavu", "", 11)
        pdf.cell(0, 8, "Oberer Textrand: " + str(self.spinOben.value()) + " mm – unterer Textrand: " + str(self.spinUnten.value()) + " mm", new_x="LMARGIN", new_y="NEXT")
        for i in range(1, 61):
            pdf.cell(0, 7, "Beispielzeile " + str(i) + ": Ergebnis, Beurteilung und Kommentar – äöüß", new_x="LMARGIN", new_y="NEXT")
        roh = ziel + ".roh.tmp"
        pdf.output(roh)
        return praxis_pdf.fertigstellen(roh, ziel)

    def testseite(self):
        ziel = os.path.join(tempfile.gettempdir(), "ScoreGDT_Testseite.pdf")
        try:
            angewendet = self.testseiteErzeugen(ziel)
            os.startfile(ziel)  # type: ignore
            if self.checkPdfa.isChecked() and "PDF/A" not in angewendet:
                QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Die Testseite wurde erzeugt, aber ohne PDF/A. Details stehen im Protokoll.", QMessageBox.StandardButton.Ok).exec()
        except Exception as e:
            QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Testseite konnte nicht erzeugt werden: " + str(e), QMessageBox.StandardButton.Ok).exec()

    def accept(self):
        if praxis_pdf.einstellungenSpeichern(self.werte()):
            self.done(1)
        else:
            QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Die Einstellungen konnten nicht gespeichert werden.", QMessageBox.StandardButton.Ok).exec()
