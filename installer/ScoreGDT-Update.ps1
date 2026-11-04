# ScoreGDT-Updater (Praxis-Build)
# Holt die neueste Version aus dem eigenen GitHub-Fork und installiert sie still.
#   Ohne Parameter : fragt vor der Installation nach (fuer den manuellen Start)
#   -Still         : ohne Rueckfragen (fuer die naechtliche Aufgabe)
param([switch]$Still, [switch]$AufgabeEinrichten, [switch]$AufgabeEntfernen)

$Repo     = 'horizonlab-eng/ScoreGDTHorizon'
$Aufgabe  = 'ScoreGDT Update'
$AppOrdner = Split-Path -Parent $PSCommandPath
$LogOrdner = Join-Path $env:ProgramData 'scoregdt'
$LogDatei  = Join-Path $LogOrdner 'update.log'

function Log([string]$Text) {
    if (-not (Test-Path $LogOrdner)) { New-Item -ItemType Directory -Path $LogOrdner | Out-Null }
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Text" | Add-Content -Path $LogDatei
    if (-not $Still) { Write-Host $Text }
}

if ($AufgabeEinrichten) {
    if (Get-ScheduledTask -TaskName $Aufgabe -ErrorAction SilentlyContinue) { exit 0 }
    $aktion  = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Still"
    $ausloeser = New-ScheduledTaskTrigger -Daily -At '03:00'
    Register-ScheduledTask -TaskName $Aufgabe -Action $aktion -Trigger $ausloeser -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
    Log "Naechtliche Update-Aufgabe eingerichtet (03:00 Uhr)"
    exit 0
}
if ($AufgabeEntfernen) {
    Unregister-ScheduledTask -TaskName $Aufgabe -Confirm:$false -ErrorAction SilentlyContinue
    exit 0
}

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'ScoreGDT-Updater' } -UseBasicParsing
    $neu = $release.tag_name
    $buildDatei = Join-Path $AppOrdner 'build.txt'
    $alt = ''
    if (Test-Path $buildDatei) { $alt = (Get-Content $buildDatei -Raw).Trim() }

    if ($neu -eq $alt) {
        Log "Keine neue Version (installiert: $alt)"
    } else {
        $setup = $release.assets | Where-Object { $_.name -like '*-Setup.exe' } | Select-Object -First 1
        if (-not $setup) { throw "Im Release $neu wurde keine Setup-Datei gefunden" }
        $installieren = $true
        if (-not $Still) {
            $antwort = Read-Host "Neue Version $neu verfuegbar (installiert: $alt). Jetzt installieren? (j/n)"
            $installieren = ($antwort -eq 'j')
        }
        if ($installieren) {
            $ziel = Join-Path $env:TEMP $setup.name
            Log "Lade $($setup.name) herunter ..."
            Invoke-WebRequest -Uri $setup.browser_download_url -OutFile $ziel -UseBasicParsing
            Log "Installiere $neu (bisher: $alt) ..."
            $p = Start-Process -FilePath $ziel -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS' -Wait -PassThru
            Remove-Item $ziel -ErrorAction SilentlyContinue
            if ($p.ExitCode -ne 0) { throw "Setup endete mit Fehlercode $($p.ExitCode)" }
            Log "Update auf $neu erfolgreich"
        }
    }
} catch {
    Log "FEHLER: $_"
    if (-not $Still) { Read-Host 'Enter zum Beenden' | Out-Null }
    exit 1
}
if (-not $Still) { Read-Host 'Fertig. Enter zum Beenden' | Out-Null }
