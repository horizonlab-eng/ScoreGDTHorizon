# ScoreGDT: persoenliche GDT-Austauschordner anlegen (laeuft bei jeder Anmeldung)
# Liest die Import- und Exportpfade aus der zentralen Einstellungsdatei
# C:\ProgramData\scoregdt\config.ini, ersetzt Platzhalter wie %USERNAME%
# und legt fehlende Ordner an. So existiert der persoenliche Ordner schon,
# bevor medatixx die erste Anfrage hineinschreibt.

$ini = Join-Path $env:ProgramData 'scoregdt\config.ini'
if (-not (Test-Path $ini)) { exit 0 }

$zeilen = Get-Content -Path $ini -Encoding UTF8
foreach ($schluessel in 'gdtimportverzeichnis', 'gdtexportverzeichnis') {
    $zeile = $zeilen | Where-Object { $_ -match "^\s*$schluessel\s*=" } | Select-Object -First 1
    if (-not $zeile) { continue }
    $pfad = [Environment]::ExpandEnvironmentVariables(($zeile -split '=', 2)[1].Trim())
    if ($pfad -and -not (Test-Path -LiteralPath $pfad)) {
        try { New-Item -ItemType Directory -Path $pfad -Force | Out-Null } catch { }
    }
}
