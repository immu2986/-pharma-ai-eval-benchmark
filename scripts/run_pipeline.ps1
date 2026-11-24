$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = "src"
if (-not (Test-Path data/cases.jsonl)) { python scripts/build_synthetic_dataset.py; python -m pharmaeval autograde; python scripts/generate_synthetic_annotations.py }
python -m pharmaeval run-all
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -q
Write-Host "Done. Open reports/dashboard.html"
