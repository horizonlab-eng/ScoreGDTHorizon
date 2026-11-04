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
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QFrame, QPushButton, QDialog, QDialogButtonBox, QLineEdit, QListWidget, QListWidgetItem

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


class KuerzelAbfrage(QDialog):
    """Kleines Fenster "Wer dokumentiert?": Kuerzel eintippen + Enter oder Person doppelt anklicken.
    Bewusst ohne Vorauswahl, damit niemand versehentlich unter fremdem Kuerzel dokumentiert.
    Ergebnis: exec() == 1 und gewaehlterIndex = Index in der Personenliste."""

    def __init__(self, benutzernamen: list, benutzerkuerzel: list, patientText: str = ""):
        super().__init__()
        self.namen = list(benutzernamen)
        self.kuerzel = list(benutzerkuerzel)
        self.gewaehlterIndex = None
        self.setWindowTitle("ScoreGDT – Wer dokumentiert?")
        self.setMinimumWidth(420)

        fett = QFont()
        fett.setBold(True)
        layout = QVBoxLayout()
        if patientText:
            labelPatient = QLabel("Patient/in: " + patientText)
            labelPatient.setFont(fett)
            layout.addWidget(labelPatient)
        layout.addWidget(QLabel("Bitte Ihr Kürzel eingeben und Enter drücken\n(oder Ihren Namen doppelt anklicken):"))
        self.eingabe = QLineEdit()
        self.eingabe.setPlaceholderText("Kürzel")
        groesser = QFont()
        groesser.setPointSize(14)
        self.eingabe.setFont(groesser)
        self.eingabe.textChanged.connect(self.filtern)
        self.eingabe.returnPressed.connect(self.eingabeBestaetigt)
        layout.addWidget(self.eingabe)
        self.liste = QListWidget()
        for i in range(len(self.namen)):
            item = QListWidgetItem((self.kuerzel[i] if i < len(self.kuerzel) else "") + "  –  " + self.namen[i])
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.liste.addItem(item)
        self.liste.itemDoubleClicked.connect(self.listeBestaetigt)
        self.liste.itemActivated.connect(self.listeBestaetigt)
        layout.addWidget(self.liste)
        self.hinweis = QLabel("")
        layout.addWidget(self.hinweis)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.buttonBox.accepted.connect(self.okGeklickt)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)
        self.eingabe.setFocus()

    def filtern(self, text: str):
        t = text.strip().casefold()
        for r in range(self.liste.count()):
            item = self.liste.item(r)
            i = item.data(Qt.ItemDataRole.UserRole)
            k = self.kuerzel[i].casefold() if i < len(self.kuerzel) else ""
            item.setHidden(t != "" and not (k.startswith(t) or t in self.namen[i].casefold()))
        self.hinweis.setText("")

    def waehlen(self, index):
        self.gewaehlterIndex = index
        self.done(1)

    def eingabeBestaetigt(self):
        index = praxis_personen.kuerzelSuchen(self.eingabe.text(), self.kuerzel)
        if index is not None:
            self.waehlen(index)
            return
        sichtbar = [self.liste.item(r) for r in range(self.liste.count()) if not self.liste.item(r).isHidden()]
        if len(sichtbar) == 1 and self.eingabe.text().strip() != "":
            self.waehlen(sichtbar[0].data(Qt.ItemDataRole.UserRole))
        else:
            self.hinweis.setText("Kürzel nicht eindeutig – bitte vollständig eingeben oder Namen anklicken.")

    def listeBestaetigt(self, item):
        self.waehlen(item.data(Qt.ItemDataRole.UserRole))

    def okGeklickt(self):
        item = self.liste.currentItem()
        if item is not None and not item.isHidden():
            self.waehlen(item.data(Qt.ItemDataRole.UserRole))
        else:
            self.eingabeBestaetigt()
