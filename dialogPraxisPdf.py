"""
Dialog "PDF und Briefpapier" (Zweig "praxis", Etappe 4) - nur Administrator.

- Briefpapier-PDF hinterlegen oder entfernen (wird nach C:\\ProgramData\\scoregdt\\briefpapier.pdf kopiert;
  Seite 1 = erste Seite, Seite 2 (optional) = Folgeseiten)
- Raender oben/unten, damit der Text nicht in Logo oder Fusszeile rutscht
- PDF/A-2b ein/aus
- Testseite erzeugen und im PDF-Programm anzeigen
"""
import os, shutil, tempfile
import praxis_pdf, scorepdf
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QFileDialog, QSpinBox, QCheckBox, QFormLayout, QMessageBox
)


class PdfDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF und Briefpapier")
        self.setMinimumWidth(560)
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

        layout.addWidget(gbBrief)
        layout.addWidget(gbRand)
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
