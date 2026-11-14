import sys, os, logging, datetime
basedir = os.path.dirname(__file__)

logOrdner = os.path.join(basedir, "log")
try:
    os.makedirs(logOrdner, exist_ok=True)
except Exception:
    pass
# Alte Logdateien aufraeumen (nur die neuesten 5 behalten).
# Auf dem Terminalserver laufen mehrere ScoreGDT-Hintergrundprozesse gleichzeitig;
# eine Datei, die ein anderer Prozess noch offen hat, laesst sich nicht loeschen.
# Das darf den Programmstart nie verhindern.
try:
    logListe = sorted(f for f in os.listdir(logOrdner) if f.endswith("_scoregdt.log"))
    for alteDatei in logListe[:-5]:
        try:
            os.remove(os.path.join(logOrdner, alteDatei))
        except Exception:
            pass
except Exception:
    pass
datum = datetime.datetime.strftime(datetime.datetime.today(), "%Y%m%d")
try:
    logHandler = logging.FileHandler(os.path.join(logOrdner, datum + "_scoregdt.log"), mode="a", encoding="utf_8")
except Exception:
    logHandler = logging.NullHandler()
logLevel = logging.WARNING
logForm = logging.Formatter("{asctime} {levelname:8}: {message}", "%d.%m.%Y %H:%M:%S", "{")
for arg in sys.argv:
    if arg.lower() == "debug":
        logLevel = logging.DEBUG
        break
logHandler.setFormatter(logForm)
logger = logging.getLogger(__name__)
logger.addHandler(logHandler)
logger.setLevel(logLevel)