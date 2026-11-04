"""
Startfenster (Zweig "praxis", Etappe 3).

Erweitert das Auswahlfenster des Autors (dialogScoreAuswahl.ScoreAuswahl) um eine
Kopfzeile mit Patient, Personenauswahl und Rolle. Angezeigt werden die Favoriten
der gewaehlten Person. Wird die Person gewechselt oder werden ihre Favoriten
bearbeitet, schliesst sich das Fenster mit Ergebnis 2 und wird vom Hauptprogramm
mit der neuen Person sofort wieder geoeffnet (das Auswahlfenster des Autors baut
seine Liste nur beim Erzeugen auf).

Ergebnis von exec():  1 = Score/Verlauf gewaehlt,  0 = abgebrochen,
                      2 = neu oeffnen mit Person neuerPersonIndex
"""
import praxis_personen, dialogScoreAuswahl, dialogEinstellungenFavoriten
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QComboBox, QFrame, QPushButton

NEU_OEFFNEN = 2


class Startfenster(dialogScoreAuswahl.ScoreAuswahl):
    def __init__(self, configPath: str, scoresPfad: str, patId: str, patientText: str,
                 benutzernamen: list, benutzerkuerzel: list, personIndex: int, praxisStandardscore: str):
        daten = praxis_personen.laden(configPath)
        if not (0 <= personIndex < len(benutzerkuerzel)):
            personIndex = 0
        kuerzel = benutzerkuerzel[personIndex] if benutzerkuerzel else ""
        rolle = daten["personRolle"].get(kuerzel, "")
        standardscore = daten["personStandardscore"].get(kuerzel) or praxisStandardscore
        root = praxis_personen.favoritenRoot(configPath, scoresPfad, kuerzel, rolle)

        super().__init__(root, standardscore, configPath, patId)

        self.scoresPfad = scoresPfad
        self.personIndex = personIndex
        self.neuerPersonIndex = None
        self.personKuerzel = kuerzel
        self.personRolle = rolle

        fett = QFont()
        fett.setBold(True)

        kopf = QHBoxLayout()
        labelPatient = QLabel("Patient/in: " + patientText)
        labelPatient.setFont(fett)
        labelPerson = QLabel("Mitarbeiter/in:")
        self.comboBoxPerson = QComboBox()
        for i in range(len(benutzernamen)):
            k = benutzerkuerzel[i] if i < len(benutzerkuerzel) else ""
            self.comboBoxPerson.addItem(benutzernamen[i] + " (" + k + ")")
        self.comboBoxPerson.setCurrentIndex(personIndex)
        self.comboBoxPerson.setMinimumWidth(260)
        self.comboBoxPerson.currentIndexChanged.connect(self.personGewechselt)
        labelRolle = QLabel("Rolle: " + (rolle if rolle else "keine (Praxis-Favoriten)"))
        kopf.addWidget(labelPatient)
        kopf.addStretch()
        kopf.addWidget(labelPerson)
        kopf.addWidget(self.comboBoxPerson)
        kopf.addWidget(labelRolle)
        linie = QFrame()
        linie.setFrameShape(QFrame.Shape.HLine)

        layout = self.layout()
        layout.insertLayout(0, kopf)
        layout.insertWidget(1, linie)

        # Bedienelemente des Originals verstaendlicher beschriften
        self.buttonTrendAusdruck.setText("Verlauf / PDF (Trendanzeige)")
        self.buttonTrendAusdruck.setToolTip("Statt einen Score zu erfassen: bisherige Ergebnisse dieses Patienten anzeigen")
        for knopf in self.findChildren(QPushButton):
            if knopf.text() == "Score-Favoriten verwalten":
                knopf.setText("Meine Favoriten bearbeiten")
        self.setWindowTitle(self.windowTitle() + "  –  " + (benutzernamen[personIndex] if benutzernamen else ""))

    def personGewechselt(self, index: int):
        if index != self.personIndex:
            self.neuerPersonIndex = index
            self.done(NEU_OEFFNEN)

    def favoritenVerwaltenButtonClicked(self):
        """Ueberschreibt den Knopf des Originals: bearbeitet die Favoriten DIESER Person."""
        ordner = praxis_personen.personFavoritenOrdner(self.configPath, self.personKuerzel, self.personRolle)
        df = dialogEinstellungenFavoriten.EinstellungenFavoriten(ordner, self.scoresPfad)
        df.setWindowTitle("Meine Favoriten – " + self.comboBoxPerson.currentText())
        if df.exec() == 1:
            self.neuerPersonIndex = self.personIndex
            self.done(NEU_OEFFNEN)
