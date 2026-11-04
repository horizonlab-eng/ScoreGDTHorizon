"""
Dialog "Rollen und Favoriten-Vorlagen" (Zweig "praxis", Etappe 3) - nur Administrator.

- Rollen anlegen und entfernen, Favoriten-Vorlage je Rolle bearbeiten
- Personen (aus "BenutzerInnen verwalten") einer Rolle zuordnen, Standard-Score je Person
- Favoriten einer Person auf die Vorlage ihrer Rolle zuruecksetzen
- Vorauswahl der Person nach Arbeitsplatz oder nach Windows-Anmeldung
"""
import praxis_personen, dialogEinstellungenFavoriten, class_score
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QGroupBox, QListWidget,
    QPushButton, QInputDialog, QMessageBox, QTableWidget, QTableWidgetItem, QComboBox,
    QRadioButton, QLabel, QHeaderView, QAbstractItemView
)

KEINE_ROLLE = "(keine – Praxis-Favoriten)"
KEIN_STANDARD = "(Praxis-Standard)"


class RollenDialog(QDialog):
    def __init__(self, configPath: str, scoresPfad: str, benutzernamen: list, benutzerkuerzel: list):
        super().__init__()
        self.configPath = configPath
        self.scoresPfad = scoresPfad
        self.namen = list(benutzernamen)
        self.kuerzel = list(benutzerkuerzel)
        self.daten = praxis_personen.laden(configPath)
        self.alleScores = sorted(
            [str(s.get("name")) for s in class_score.Score.getGesamtRoot(scoresPfad).findall("score")],
            key=lambda n: n.casefold())

        self.setWindowTitle("Rollen und Favoriten-Vorlagen")
        self.setMinimumSize(820, 600)
        layout = QVBoxLayout()

        # --- Rollen ---
        gbRollen = QGroupBox("Rollen")
        lyRollen = QHBoxLayout()
        self.listeRollen = QListWidget()
        self.listeRollen.addItems(self.daten["rollen"])
        knoepfe = QVBoxLayout()
        self.knopfRolleNeu = QPushButton("Rolle hinzufügen …")
        self.knopfRolleWeg = QPushButton("Rolle entfernen")
        self.knopfVorlage = QPushButton("Favoriten-Vorlage bearbeiten …")
        self.knopfRolleNeu.clicked.connect(self.rolleHinzufuegen)
        self.knopfRolleWeg.clicked.connect(self.rolleEntfernen)
        self.knopfVorlage.clicked.connect(self.vorlageBearbeiten)
        for k in (self.knopfRolleNeu, self.knopfRolleWeg, self.knopfVorlage):
            knoepfe.addWidget(k)
        knoepfe.addStretch()
        lyRollen.addWidget(self.listeRollen)
        lyRollen.addLayout(knoepfe)
        gbRollen.setLayout(lyRollen)

        # --- Personen ---
        gbPersonen = QGroupBox("Personen (Name und Kürzel unter Einstellungen → BenutzerInnen verwalten)")
        lyPersonen = QVBoxLayout()
        self.tabelle = QTableWidget(len(self.namen), 4)
        self.tabelle.setHorizontalHeaderLabels(["Name", "Kürzel", "Rolle", "Standard-Score"])
        self.tabelle.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabelle.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for i in range(len(self.namen)):
            k = self.kuerzel[i] if i < len(self.kuerzel) else ""
            for spalte, text in ((0, self.namen[i]), (1, k)):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tabelle.setItem(i, spalte, item)
            self.tabelle.setCellWidget(i, 2, self.rollenAuswahl(self.daten["personRolle"].get(k, "")))
            cbScore = QComboBox()
            cbScore.addItem(KEIN_STANDARD)
            cbScore.addItems(self.alleScores)
            aktuell = self.daten["personStandardscore"].get(k, "")
            if aktuell in self.alleScores:
                cbScore.setCurrentText(aktuell)
            self.tabelle.setCellWidget(i, 3, cbScore)
        self.knopfZuruecksetzen = QPushButton("Favoriten der markierten Person auf die Vorlage ihrer Rolle zurücksetzen")
        self.knopfZuruecksetzen.clicked.connect(self.personZuruecksetzen)
        lyPersonen.addWidget(self.tabelle)
        lyPersonen.addWidget(self.knopfZuruecksetzen)
        gbPersonen.setLayout(lyPersonen)

        # --- Vorauswahl ---
        gbVor = QGroupBox("Person beim Öffnen von ScoreGDT")
        lyVor = QVBoxLayout()
        self.rbFragen = QRadioButton("Bei jedem Aufruf nach dem Kürzel fragen (empfohlen)")
        self.rbArbeitsplatz = QRadioButton("Nach Arbeitsplatz vorauswählen (zuletzt an diesem PC gewählte Person)")
        self.rbWindows = QRadioButton("Nach Windows-Anmeldung (sinnvoll, wenn Windows-Konten personenbezogen sind)")
        modus = self.daten.get("vorauswahlUeber")
        if modus == praxis_personen.VORAUSWAHL_WINDOWS:
            self.rbWindows.setChecked(True)
        elif modus == praxis_personen.VORAUSWAHL_ARBEITSPLATZ:
            self.rbArbeitsplatz.setChecked(True)
        else:
            self.rbFragen.setChecked(True)
        lyVor.addWidget(self.rbFragen)
        lyVor.addWidget(self.rbArbeitsplatz)
        lyVor.addWidget(self.rbWindows)
        gbVor.setLayout(lyVor)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout.addWidget(gbRollen)
        layout.addWidget(gbPersonen)
        layout.addWidget(gbVor)
        layout.addWidget(QLabel("Neue Personen bekommen beim ersten Start die Favoriten-Vorlage ihrer Rolle und können sie danach im Startfenster selbst anpassen."))
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)

    # ---------- Hilfen ----------
    def rollen(self) -> list:
        return [self.listeRollen.item(i).text() for i in range(self.listeRollen.count())]

    def rollenAuswahl(self, aktuell: str) -> QComboBox:
        cb = QComboBox()
        cb.addItem(KEINE_ROLLE)
        cb.addItems(self.rollen() if hasattr(self, "listeRollen") else self.daten["rollen"])
        if aktuell:
            cb.setCurrentText(aktuell)
        return cb

    def rollenAuswahlenAktualisieren(self):
        for i in range(self.tabelle.rowCount()):
            cb = self.tabelle.cellWidget(i, 2)
            aktuell = cb.currentText()
            cb.clear()
            cb.addItem(KEINE_ROLLE)
            cb.addItems(self.rollen())
            cb.setCurrentText(aktuell if aktuell in self.rollen() else KEINE_ROLLE)

    def gewaehlteRolle(self) -> str:
        item = self.listeRollen.currentItem()
        return item.text() if item is not None else ""

    # ---------- Aktionen ----------
    def rolleHinzufuegen(self):
        name, ok = QInputDialog.getText(self, "Rolle hinzufügen", "Name der neuen Rolle:")
        name = name.strip()
        if ok and name and name not in self.rollen():
            self.listeRollen.addItem(name)
            self.rollenAuswahlenAktualisieren()

    def rolleEntfernen(self):
        rolle = self.gewaehlteRolle()
        if not rolle:
            return
        mb = QMessageBox(QMessageBox.Icon.Question, "Rolle entfernen",
                         "Rolle \"" + rolle + "\" entfernen? Personen mit dieser Rolle verwenden danach die Praxis-Favoriten als Vorlage. Ihre eigenen Favoriten bleiben erhalten.",
                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        mb.button(QMessageBox.StandardButton.Yes).setText("Ja")
        mb.button(QMessageBox.StandardButton.No).setText("Nein")
        if mb.exec() == QMessageBox.StandardButton.Yes:
            self.listeRollen.takeItem(self.listeRollen.currentRow())
            self.rollenAuswahlenAktualisieren()

    def vorlageBearbeiten(self):
        rolle = self.gewaehlteRolle()
        if not rolle:
            QMessageBox(QMessageBox.Icon.Information, "Hinweis", "Bitte zuerst eine Rolle markieren.", QMessageBox.StandardButton.Ok).exec()
            return
        ordner = praxis_personen.rollenvorlageSicherstellen(self.configPath, rolle)
        df = dialogEinstellungenFavoriten.EinstellungenFavoriten(ordner, self.scoresPfad)
        df.setWindowTitle("Favoriten-Vorlage der Rolle " + rolle)
        df.exec()

    def personZuruecksetzen(self):
        zeile = self.tabelle.currentRow()
        if zeile < 0:
            QMessageBox(QMessageBox.Icon.Information, "Hinweis", "Bitte zuerst eine Person markieren.", QMessageBox.StandardButton.Ok).exec()
            return
        kuerzel = self.tabelle.item(zeile, 1).text()
        rolle = self.tabelle.cellWidget(zeile, 2).currentText()
        rolle = "" if rolle == KEINE_ROLLE else rolle
        if praxis_personen.personZuruecksetzen(self.configPath, kuerzel, rolle):
            QMessageBox(QMessageBox.Icon.Information, "Hinweis", "Favoriten von " + self.tabelle.item(zeile, 0).text() + " wurden zurückgesetzt.", QMessageBox.StandardButton.Ok).exec()

    def datenUebernehmen(self) -> dict:
        daten = praxis_personen.laden(self.configPath)
        daten["rollen"] = self.rollen()
        daten["personRolle"] = {}
        daten["personStandardscore"] = {}
        for i in range(self.tabelle.rowCount()):
            kuerzel = self.tabelle.item(i, 1).text()
            rolle = self.tabelle.cellWidget(i, 2).currentText()
            if rolle != KEINE_ROLLE:
                daten["personRolle"][kuerzel] = rolle
            score = self.tabelle.cellWidget(i, 3).currentText()
            if score != KEIN_STANDARD:
                daten["personStandardscore"][kuerzel] = score
        if self.rbWindows.isChecked():
            daten["vorauswahlUeber"] = praxis_personen.VORAUSWAHL_WINDOWS
        elif self.rbArbeitsplatz.isChecked():
            daten["vorauswahlUeber"] = praxis_personen.VORAUSWAHL_ARBEITSPLATZ
        else:
            daten["vorauswahlUeber"] = praxis_personen.VORAUSWAHL_FRAGEN
        return daten

    def accept(self):
        if praxis_personen.speichern(self.configPath, self.datenUebernehmen()):
            self.done(1)
        else:
            QMessageBox(QMessageBox.Icon.Warning, "Hinweis von ScoreGDT", "Die Einstellungen konnten nicht gespeichert werden.", QMessageBox.StandardButton.Ok).exec()
