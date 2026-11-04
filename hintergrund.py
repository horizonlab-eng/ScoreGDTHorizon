"""
Hintergrundbetrieb fuer ScoreGDT (Zweig "praxis").

ScoreGDT wird bei der Windows-Anmeldung einmal pro Sitzung mit
    scoregdt.exe --hintergrund
gestartet und wartet unsichtbar (Symbol neben der Uhr). medatixx ruft statt
scoregdt.exe das kleine Hilfsprogramm ScoreGDT-Start.exe auf. Dieses meldet
sich ueber eine lokale Pipe ("ScoreGDT-<Sitzungsnummer>") und das laufende
ScoreGDT oeffnet sofort ein neues Fenster - ohne das langsame Laden von
Python und Qt.

Laeuft kein Hintergrund-ScoreGDT, startet das Hilfsprogramm
    scoregdt.exe --hintergrund --sofort <Argumente>
Dann dauert es einmal laenger, danach laeuft der Hintergrundbetrieb.

ScoreGDT beendet sich an vielen Stellen selbst (sys.exit) oder startet sich
neu (os.execl). Im Hintergrundbetrieb wuerde das das ganze Programm beenden.
Beides wird hier abgefangen: sys.exit schliesst nur das betroffene Fenster,
os.execl oeffnet ein neues Fenster im laufenden Programm (z. B. "Score
auswaehlen" ohne Neustart).
"""
import sys, os, ctypes, time
import logger, praxis
from PySide6.QtCore import QTimer, QObject, Qt, QEvent
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QWidget
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SCHALTER_HINTERGRUND = "--hintergrund"
SCHALTER_SOFORT = "--sofort"
TRENNER = "\x1f"


class FensterBeenden(Exception):
    """Ersetzt im Hintergrundbetrieb sys.exit: bricht nur den laufenden Ablauf ab."""


def istHintergrundStart(argv) -> bool:
    return SCHALTER_HINTERGRUND in argv


def sitzungsnummer() -> int:
    """Windows-Sitzungsnummer (auf dem Terminalserver je angemeldeter Sitzung eindeutig)."""
    try:
        nr = ctypes.c_ulong()
        if ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(nr)):
            return nr.value
    except Exception:
        pass
    return 0


def installierteVersion(basedir: str) -> str:
    """Build-Kennung aus build.txt (z. B. v1.45.3-praxis-13), leer wenn nicht vorhanden."""
    try:
        with open(os.path.join(basedir, "build.txt"), "r", encoding="ascii", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""


def pipeName() -> str:
    return "ScoreGDT-" + str(sitzungsnummer())


class Hintergrund(QObject):
    def __init__(self, app: QApplication, fensterKlasse, basedir: str):
        super().__init__()
        self.app = app
        self.fensterKlasse = fensterKlasse
        self.programm = sys.argv[0]
        self.fenster = []  # offene Hauptfenster (Referenzen halten)
        self.anfragen = {}  # id(Fenster) -> (Pfad der gelesenen Anfrage, Zeitstempel der Datei)
        self.neustarts = set()  # id(Fenster), die per "Neustart" ersetzt werden
        self.server = None
        self.tray = None
        self.basedir = basedir
        self.vordergrundBis = 0.0  # bis zu diesem Zeitpunkt werden neue Fenster nach vorne geholt
        self.warteschlange = []    # Aufrufe, die nacheinander abgearbeitet werden
        self.beimOeffnen = False   # True, solange ein Fenster aufgebaut wird (inkl. Startfenster)

    # ---------- Start ----------
    def starten(self) -> int:
        argv = list(sys.argv[1:])
        sofort = SCHALTER_SOFORT in argv
        fensterArgs = [a for a in argv if a not in (SCHALTER_HINTERGRUND, SCHALTER_SOFORT)]

        # Laeuft in dieser Sitzung schon ein Hintergrund-ScoreGDT? Dann nur weiterreichen.
        if self.anLaufendesWeiterreichen(fensterArgs if sofort else None):
            logger.logger.info("Hintergrund: laeuft bereits in dieser Sitzung")
            return 0

        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        QLocalServer.removeServer(pipeName())
        if not self.server.listen(pipeName()):
            logger.logger.error("Hintergrund: Pipe konnte nicht geoeffnet werden: " + self.server.errorString())
            # Ohne Pipe trotzdem normal weiterarbeiten, falls ein Fenster gewuenscht ist
        else:
            self.server.newConnection.connect(self.neueVerbindung)
            logger.logger.warning("Hintergrund: gestartet, wartet auf " + pipeName())

        self.app.setQuitOnLastWindowClosed(False)
        self.app.installEventFilter(self)
        self.abfangenEinrichten()
        self.trayEinrichten()

        if sofort:
            self.vordergrundBis = time.time() + 20
            self.aufrufEinplanen(fensterArgs)
        return self.app.exec()

    def anLaufendesWeiterreichen(self, fensterArgs) -> bool:
        sock = QLocalSocket()
        sock.connectToServer(pipeName())
        if not sock.waitForConnected(300):
            return False
        if fensterArgs is not None:
            sock.write((TRENNER.join(fensterArgs) + "\n").encode("utf-8"))
            sock.flush()
            sock.waitForBytesWritten(1000)
            sock.waitForReadyRead(2000)
        sock.disconnectFromServer()
        return True

    # ---------- Aufrufe vom Hilfsprogramm ----------
    def neueVerbindung(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self.nachrichtLesen(s))
            sock.disconnected.connect(sock.deleteLater)

    def nachrichtLesen(self, sock):
        if not sock.canReadLine():
            return
        zeile = bytes(sock.readLine()).decode("utf-8").rstrip("\r\n")
        sock.write(b"OK\n")
        sock.flush()
        args = [a for a in zeile.split(TRENNER) if a != ""]
        logger.logger.warning("Hintergrund: Aufruf erhalten")
        self.vordergrundBis = time.time() + 20
        self.aufrufEinplanen(args, offenesStartfensterSchliessen=True)

    # ---------- Aufrufe nacheinander abarbeiten ----------
    def aufrufEinplanen(self, args, offenesStartfensterSchliessen=False):
        """Fenster werden nie ineinander verschachtelt geoeffnet (das blockierte sich
        gegenseitig). Ist beim neuen Aufruf noch ein Startfenster ohne Auswahl offen,
        wird es geschlossen - dort wurde noch nichts eingegeben."""
        self.warteschlange.append(list(args))
        if self.beimOeffnen:
            import praxisStartfenster
            offen = QApplication.activeModalWidget()
            if offenesStartfensterSchliessen and isinstance(offen, (praxisStartfenster.Startfenster, praxisStartfenster.KuerzelAbfrage)):
                logger.logger.warning("Hintergrund: offenes Startfenster durch neuen Aufruf ersetzt")
                offen.reject()
            elif offen is not None:
                self.nachVorne(offen)
            return
        QTimer.singleShot(0, self.naechsterAufruf)

    def naechsterAufruf(self):
        if self.beimOeffnen or not self.warteschlange:
            return
        args = self.warteschlange.pop(0)
        self.beimOeffnen = True
        try:
            self.oeffnen(args)
        finally:
            self.beimOeffnen = False
        if self.warteschlange:
            QTimer.singleShot(0, self.naechsterAufruf)

    # ---------- Fenster ----------
    def oeffnen(self, args):
        sys.argv = [self.programm] + list(args)
        try:
            fenster = self.fensterKlasse()
        except FensterBeenden:
            return
        except Exception as e:
            logger.logger.error("Hintergrund: Fenster konnte nicht geoeffnet werden: " + str(e))
            return
        if getattr(fenster, "_praxisBeendet", False):
            return
        self.fenster.append(fenster)
        self.anfrageMerken(fenster)
        fenster.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        fid = id(fenster)
        fenster.destroyed.connect(lambda *_ , f=fenster, i=fid: self.fensterZu(f, i))
        fenster.show()
        self.nachVorne(fenster)

    def anfrageMerken(self, fenster):
        """Merkt sich, welche Anfrage-Datei (SCORMEDA.gdt) dieses Fenster gelesen hat."""
        try:
            pfad = os.path.join(fenster.gdtImportVerzeichnis, fenster.kuerzelscoregdt + fenster.kuerzelpraxisedv + ".gdt")
            if os.path.exists(pfad):
                self.anfragen[id(fenster)] = (pfad, os.path.getmtime(pfad))
        except Exception:
            pass

    def fensterZu(self, fenster, fid):
        """Fenster wurde geschlossen: Anfrage loeschen - ausser bei Neustart (Score wechseln)
        oder wenn medatixx inzwischen eine neue Anfrage geschrieben hat."""
        self.fensterEntfernen(fenster)
        eintrag = self.anfragen.pop(fid, None)
        if fid in self.neustarts:
            self.neustarts.discard(fid)
            return
        if eintrag is None:
            return
        pfad, zeit = eintrag
        try:
            if os.path.exists(pfad) and os.path.getmtime(pfad) == zeit:
                praxis.anfrageLoeschen(pfad)
        except Exception:
            pass

    def fensterEntfernen(self, fenster):
        if fenster in self.fenster:
            self.fenster.remove(fenster)

    def schliessen(self, fenster):
        try:
            fenster.close()
            fenster.deleteLater()
        except RuntimeError:
            pass  # bereits geloescht
        self.fensterEntfernen(fenster)

    def aktuellesFenster(self):
        """Sucht im Aufrufstapel das Hauptfenster, aus dem sys.exit/os.execl kam."""
        f = sys._getframe(2)
        while f is not None:
            s = f.f_locals.get("self")
            if isinstance(s, self.fensterKlasse):
                return s
            f = f.f_back
        return None

    # ---------- Fenster nach vorne holen ----------
    def eventFilter(self, obj, event):
        """Jedes Fenster (auch Dialoge, die ScoreGDT waehrend des Aufbaus zeigt),
        das kurz nach einem Aufruf erscheint, wird nach vorne geholt."""
        if event.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow() and time.time() < self.vordergrundBis:
            QTimer.singleShot(0, lambda w=obj: self.nachVorne(w))
        return False

    def nachVorne(self, fenster):
        try:
            fenster.raise_()
            fenster.activateWindow()
            if os.name != "nt":
                return
            hwnd = int(fenster.winId())
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            vorne = user32.GetForegroundWindow()
            fremderThread = user32.GetWindowThreadProcessId(vorne, None)
            eigenerThread = kernel32.GetCurrentThreadId()
            verbunden = False
            if fremderThread and fremderThread != eigenerThread:
                verbunden = bool(user32.AttachThreadInput(fremderThread, eigenerThread, True))
            HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
            SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0040
            user32.ShowWindow(hwnd, 5)  # SW_SHOW
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            if verbunden:
                user32.AttachThreadInput(fremderThread, eigenerThread, False)
        except Exception as e:
            logger.logger.warning("Hintergrund: Fenster konnte nicht nach vorne geholt werden: " + str(e))

    # ---------- sys.exit und os.execl abfangen ----------
    def abfangenEinrichten(self):
        def beenden(*_):
            fenster = self.aktuellesFenster()
            if fenster is not None:
                fenster._praxisBeendet = True
                QTimer.singleShot(0, lambda: self.schliessen(fenster))
            raise FensterBeenden()

        def neustarten(_pfad, *args):
            # Aufruf im Original: os.execl(sys.executable, __file__, *sys.argv)
            neueArgs = list(args[2:])
            fenster = self.aktuellesFenster()
            if fenster is not None:
                fenster._praxisBeendet = True
                self.neustarts.add(id(fenster))
                QTimer.singleShot(0, lambda: self.schliessen(fenster))
            self.vordergrundBis = time.time() + 20
            QTimer.singleShot(50, lambda: self.aufrufEinplanen(neueArgs))
            raise FensterBeenden()

        vorherigerHook = sys.excepthook

        def fehlerHook(typ, wert, tb):
            if issubclass(typ, FensterBeenden):
                return  # gewollter Abbruch eines Fensters, kein Fehler
            logger.logger.error("Hintergrund: unbehandelter Fehler: " + typ.__name__ + ": " + str(wert))
            try:
                vorherigerHook(typ, wert, tb)
            except Exception:
                pass

        sys.exit = beenden
        os.execl = neustarten
        sys.excepthook = fehlerHook

    # ---------- Symbol neben der Uhr ----------
    def trayEinrichten(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(QIcon(os.path.join(self.basedir, "icons", "program.png")), self)
        build = installierteVersion(self.basedir)
        self.tray.setToolTip("ScoreGDT ist bereit" + (" (" + build + ")" if build else ""))
        menue = QMenu()
        if build:
            versionAktion = QAction("Version: " + build, menue)
            versionAktion.setEnabled(False)
            menue.addAction(versionAktion)
            menue.addSeparator()
        beendenAktion = QAction("ScoreGDT im Hintergrund beenden", menue)
        beendenAktion.triggered.connect(self.wirklichBeenden)
        menue.addAction(beendenAktion)
        self.tray.setContextMenu(menue)
        self._menue = menue
        self.tray.show()

    def wirklichBeenden(self):
        if self.fenster:
            mb = QMessageBox(QMessageBox.Icon.Question, "Hinweis von ScoreGDT",
                             "Es ist noch ein ScoreGDT-Fenster offen. Trotzdem beenden?",
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            mb.button(QMessageBox.StandardButton.Yes).setText("Ja")
            mb.button(QMessageBox.StandardButton.No).setText("Nein")
            if mb.exec() != QMessageBox.StandardButton.Yes:
                return
        if self.server is not None:
            self.server.close()
        if self.tray is not None:
            self.tray.hide()
        self.app.quit()


def starten(app: QApplication, fensterKlasse, basedir: str) -> int:
    h = Hintergrund(app, fensterKlasse, basedir)
    app._praxisHintergrund = h  # Referenz halten
    return h.starten()
