# ScoreGDT-Updater (Praxis-Build, Etappe 5)
# Holt eine Version aus dem eigenen GitHub-Fork und installiert sie still.
#
#   Ohne Parameter          : fuer den Start ueber das Startmenue ("ScoreGDT aktualisieren").
#                             Holt sich selbst Administratorrechte, zeigt offene ScoreGDT-Sitzungen,
#                             fragt nach und bietet auch aeltere Versionen an (Rueckkehr).
#   -Still                  : ohne Rueckfragen (fuer die naechtliche Aufgabe um 03:00 Uhr)
#   -Version <Tag>          : genau diese Version installieren, z. B. -Version v1.45.3-praxis-12
#   -AufgabeEinrichten      : naechtliche Update-Aufgabe anlegen (macht der Installer)
#   -AufgabeEntfernen       : naechtliche Update-Aufgabe loeschen
#   -HintergrundStarten     : ScoreGDT in allen angemeldeten Sitzungen im Hintergrund starten
#                             (macht der Installer am Ende jeder Installation)
#
# Ablauf eines Updates:
#   1. Version bei GitHub nachsehen, mit build.txt vergleichen
#   2. Setup herunterladen und Pruefsumme (SHA-256) kontrollieren
#   3. Einstellungen aus C:\ProgramData\scoregdt sichern (Ordner "sicherung", die letzten 10)
#   4. Setup still ausfuehren (beendet ScoreGDT in allen Sitzungen, installiert,
#      startet den Hintergrundbetrieb in allen Sitzungen neu)
#   5. Pruefen, ob danach wirklich die neue Version installiert ist
# Alles steht in C:\ProgramData\scoregdt\update.log
param(
    [switch]$Still,
    [switch]$AufgabeEinrichten,
    [switch]$AufgabeEntfernen,
    [switch]$HintergrundStarten,
    [string]$Version = ''
)

$Repo        = 'horizonlab-eng/ScoreGDTHorizon'
$Aufgabe     = 'ScoreGDT Update'
$AufgabeHg   = 'ScoreGDT Hintergrund starten'
$AppOrdner   = Split-Path -Parent $PSCommandPath
$DatenOrdner = Join-Path $env:ProgramData 'scoregdt'
$LogDatei    = Join-Path $DatenOrdner 'update.log'
$SicherOrdner = Join-Path $DatenOrdner 'sicherung'
$BuildDatei  = Join-Path $AppOrdner 'build.txt'
$Kopf        = @{ 'User-Agent' = 'ScoreGDT-Updater' }

# Ohne Fortschrittsbalken ist der Download unter Windows PowerShell 5.1 um ein Vielfaches schneller
$ProgressPreference = 'SilentlyContinue'

function Log([string]$Text) {
    try {
        if (-not (Test-Path $DatenOrdner)) { New-Item -ItemType Directory -Path $DatenOrdner | Out-Null }
        "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Text" | Add-Content -Path $LogDatei
    } catch { }
    if (-not $Still) { Write-Host $Text }
}

function LogKuerzen {
    # Protokoll auf die letzten 1000 Zeilen begrenzen
    try {
        if (Test-Path $LogDatei) {
            $zeilen = Get-Content -Path $LogDatei
            if ($zeilen.Count -gt 1000) { $zeilen | Select-Object -Last 1000 | Set-Content -Path $LogDatei }
        }
    } catch { }
}

function IstAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Ende([int]$Code) {
    if (-not $Still) { Read-Host 'Enter zum Beenden' | Out-Null }
    exit $Code
}

# ---------- Hintergrundbetrieb in allen Sitzungen starten ----------
# Eine geplante Aufgabe fuer die Gruppe "Benutzer" (S-1-5-32-545) startet beim Ausloesen
# in jeder angemeldeten Sitzung ein eigenes ScoreGDT. Laeuft dort schon eines,
# beendet sich das neue sofort wieder (siehe hintergrund.py).
function HintergrundAufgabeSicherstellen {
    $exe = Join-Path $AppOrdner 'scoregdt.exe'
    $aktion = New-ScheduledTaskAction -Execute $exe -Argument '--hintergrund' -WorkingDirectory $AppOrdner
    # Gruppenname in der Sprache des Servers (deutsch: "VORDEFINIERT\Benutzer")
    $gruppe = (New-Object Security.Principal.SecurityIdentifier 'S-1-5-32-545').Translate([Security.Principal.NTAccount]).Value
    $wer = New-ScheduledTaskPrincipal -GroupId $gruppe -RunLevel Limited
    # Ohne Zeitlimit (Standard waere: nach 72 Stunden beenden) und mit normaler Prioritaet
    $einst = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances Parallel -Priority 4 -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $AufgabeHg -Action $aktion -Principal $wer -Settings $einst -Force | Out-Null
}

if ($HintergrundStarten) {
    try {
        HintergrundAufgabeSicherstellen
        Start-ScheduledTask -TaskName $AufgabeHg
        Log "Hintergrundbetrieb in den angemeldeten Sitzungen gestartet"
    } catch {
        Log "Hinweis: Hintergrundbetrieb konnte nicht gestartet werden ($_). Er startet beim naechsten Aufruf aus medatixx bzw. bei der naechsten Anmeldung."
    }
    exit 0
}

# ---------- Naechtliche Aufgabe ----------
if ($AufgabeEinrichten) {
    $aktion    = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Still"
    $ausloeser = New-ScheduledTaskTrigger -Daily -At '03:00'
    # Verpasste Termine (Server war aus) nachholen, hoechstens 2 Stunden laufen lassen
    $einst     = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $Aufgabe -Action $aktion -Trigger $ausloeser -Settings $einst -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
    Log "Naechtliche Update-Aufgabe eingerichtet (03:00 Uhr)"
    exit 0
}
if ($AufgabeEntfernen) {
    Unregister-ScheduledTask -TaskName $Aufgabe -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $AufgabeHg -Confirm:$false -ErrorAction SilentlyContinue
    exit 0
}

# ---------- Manueller Start: Administratorrechte holen ----------
if (-not (IstAdmin)) {
    if ($Still) { Log "FEHLER: Updater braucht Administratorrechte"; exit 1 }
    Write-Host 'Der Updater braucht Administratorrechte. Bitte die folgende Windows-Abfrage mit "Ja" bestaetigen.'
    $argumente = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    if ($Version) { $argumente += " -Version `"$Version`"" }
    try { Start-Process -FilePath 'powershell.exe' -ArgumentList $argumente -Verb RunAs } catch { Write-Host 'Abgebrochen.'; Start-Sleep 3 }
    exit 0
}

# ---------- Nur ein Updater gleichzeitig ----------
$sperre = New-Object System.Threading.Mutex($false, 'Global\ScoreGDT-Update')
$sperreErhalten = $false
try { $sperreErhalten = $sperre.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $sperreErhalten = $true }
if (-not $sperreErhalten) {
    Log "Ein anderer ScoreGDT-Updater laeuft gerade - abgebrochen"
    Ende 0
}

$neuDatei = $null
try {
    LogKuerzen
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $alt = ''
    if (Test-Path $BuildDatei) { $alt = (Get-Content $BuildDatei -Raw).Trim() }

    # ----- Welche Version? -----
    if ($Version) {
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/tags/$Version" -Headers $Kopf -UseBasicParsing
    } else {
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers $Kopf -UseBasicParsing
    }
    $neu = $release.tag_name

    if (-not $Still) {
        Write-Host ''
        Write-Host "Installiert:            $alt"
        Write-Host "Neueste Version:        $neu"
        Write-Host ''
        if ($neu -eq $alt -and -not $Version) {
            $antwort = Read-Host 'ScoreGDT ist aktuell. [a] = andere (aeltere) Version waehlen, Enter = beenden'
        } else {
            $antwort = Read-Host "[j] = $neu installieren, [a] = andere (aeltere) Version waehlen, [n] = abbrechen"
        }
        if ($antwort -eq 'a') {
            $liste = @(Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases?per_page=15" -Headers $Kopf -UseBasicParsing |
                       Where-Object { -not $_.draft -and -not $_.prerelease } |
                       Sort-Object { [datetime]$_.published_at } -Descending)
            Write-Host ''
            for ($i = 0; $i -lt $liste.Count; $i++) {
                $markierung = ''
                if ($liste[$i].tag_name -eq $alt) { $markierung = '   <- installiert' }
                Write-Host ("  {0,2}  {1}   vom {2:dd.MM.yyyy HH:mm}{3}" -f ($i + 1), $liste[$i].tag_name, ([datetime]$liste[$i].published_at).ToLocalTime(), $markierung)
            }
            $nr = Read-Host 'Nummer der gewuenschten Version (Enter = abbrechen)'
            if (-not ($nr -match '^\d+$') -or [int]$nr -lt 1 -or [int]$nr -gt $liste.Count) { Log 'Abgebrochen'; Ende 0 }
            $release = $liste[[int]$nr - 1]
            $neu = $release.tag_name
        } elseif ($antwort -ne 'j') {
            Ende 0
        }
    } elseif ($neu -eq $alt) {
        Log "Keine neue Version (installiert: $alt)"
        exit 0
    }

    # ----- Offene Sitzungen (nur bei manuellem Start) -----
    if (-not $Still) {
        $laufend = @(Get-Process -Name scoregdt -IncludeUserName -ErrorAction SilentlyContinue)
        if ($laufend.Count -gt 0) {
            $namen = ($laufend | ForEach-Object { ($_.UserName -split '\\')[-1] } | Sort-Object -Unique) -join ', '
            Write-Host ''
            Write-Host "ScoreGDT laeuft gerade bei: $namen"
            Write-Host 'Die Installation beendet ScoreGDT dort. Ein offenes, noch nicht gesendetes Formular geht dabei verloren.'
            Write-Host 'Der Hintergrundbetrieb startet danach in allen Sitzungen von selbst neu.'
            $weiter = Read-Host 'Trotzdem jetzt installieren? (j/n)'
            if ($weiter -ne 'j') { Log 'Abgebrochen (offene Sitzungen)'; Ende 0 }
        }
    }

    # ----- Herunterladen und pruefen -----
    $setup = $release.assets | Where-Object { $_.name -like '*-Setup.exe' } | Select-Object -First 1
    if (-not $setup) { throw "Im Release $neu wurde keine Setup-Datei gefunden" }
    $neuDatei = Join-Path $env:TEMP ("ScoreGDT-Update-" + [guid]::NewGuid().ToString('N') + ".exe")
    Log "Lade $($setup.name) ($neu) herunter ..."
    Invoke-WebRequest -Uri $setup.browser_download_url -OutFile $neuDatei -Headers $Kopf -UseBasicParsing
    $groesse = (Get-Item $neuDatei).Length
    if ($setup.size -and $groesse -ne [long]$setup.size) { throw "Download unvollstaendig ($groesse von $($setup.size) Bytes)" }
    if ($setup.digest -and $setup.digest -like 'sha256:*') {
        $soll = $setup.digest.Substring(7).ToLower()
        $ist  = (Get-FileHash -Path $neuDatei -Algorithm SHA256).Hash.ToLower()
        if ($soll -ne $ist) { throw "Pruefsumme stimmt nicht - Datei beschaedigt oder veraendert, Update abgebrochen" }
        Log "Pruefsumme (SHA-256) in Ordnung"
    } else {
        Log "Hinweis: GitHub liefert keine Pruefsumme, nur die Groesse wurde geprueft"
    }

    # ----- Einstellungen sichern -----
    try {
        if (-not (Test-Path $SicherOrdner)) { New-Item -ItemType Directory -Path $SicherOrdner | Out-Null }
        $inhalt = Get-ChildItem -Path $DatenOrdner -Force | Where-Object { $_.Name -ne 'sicherung' -and $_.Extension -ne '.log' -and $_.Extension -ne '.tmp' }
        if ($inhalt) {
            $altName = $alt
            if (-not $altName) { $altName = 'unbekannt' }
            $zip = Join-Path $SicherOrdner ("vor-update_{0}_{1}.zip" -f (Get-Date -Format 'yyyy-MM-dd_HHmm'), ($altName -replace '[^\w\.\-]', '_'))
            $inhalt | Compress-Archive -DestinationPath $zip -Force
            Log "Einstellungen gesichert: $zip"
            Get-ChildItem -Path $SicherOrdner -Filter 'vor-update_*.zip' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 10 | Remove-Item -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Log "Hinweis: Einstellungen konnten nicht gesichert werden ($_) - Update laeuft trotzdem weiter"
    }

    # ----- Installieren -----
    Log "Installiere $neu (bisher: $alt) ..."
    $p = Start-Process -FilePath $neuDatei -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS', "/LOG=`"$(Join-Path $DatenOrdner 'setup-letztes.log')`"" -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Setup endete mit Fehlercode $($p.ExitCode) (Details: setup-letztes.log)" }

    $jetzt = ''
    if (Test-Path $BuildDatei) { $jetzt = (Get-Content $BuildDatei -Raw).Trim() }
    if ($jetzt -ne $neu) { throw "Nach der Installation ist '$jetzt' installiert statt '$neu'" }
    Log "Update auf $neu erfolgreich"
    if (-not $Still) { Write-Host ''; Write-Host "Fertig. ScoreGDT $neu ist installiert." }
} catch {
    Log "FEHLER: $_"
    if ($neuDatei) { Remove-Item $neuDatei -ErrorAction SilentlyContinue }
    try { $sperre.ReleaseMutex() } catch { }
    Ende 1
}
if ($neuDatei) { Remove-Item $neuDatei -ErrorAction SilentlyContinue }
try { $sperre.ReleaseMutex() } catch { }
Ende 0
