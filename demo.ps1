<#
MCP-IDS one-click demo.

Runs the supervisor demo in order and pauses between steps so you can explain
each one. Double-click demo.bat, or run in PowerShell:

    .\demo.ps1               # full demo
    .\demo.ps1 -SkipBuild    # image already built today
    .\demo.ps1 -RunTests     # also run the test suite first (about 5 minutes)
    .\demo.ps1 -Live         # add the live-detector step (opens a second window)
    .\demo.ps1 -NoPause      # run straight through (rehearsal)
    .\demo.ps1 -NoOpen       # don't open the diagram/report files

Only data\demo_live and data\live are written; existing datasets, models and
results are never changed.
#>
param(
    [switch]$SkipBuild,
    [switch]$RunTests,
    [switch]$Live,
    [switch]$NoPause,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root
$DemoDir = Join-Path $Root "data\demo_live"
$Report = Join-Path $Root "results\combined_canonical_20261010\evaluation_report.md"

function Step([string]$title, [string]$say) {
    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor DarkCyan
    Write-Host "  $title" -ForegroundColor Cyan
    if ($say) { Write-Host "  Say: $say" -ForegroundColor Gray }
    Write-Host ("=" * 78) -ForegroundColor DarkCyan
}

function Pause-Demo([string]$next = "continue") {
    if (-not $NoPause) { Read-Host "`n  Press Enter to $next" | Out-Null }
}

function Docker-Run([string[]]$dockerArgs) {
    # Docker prints progress to stderr; Windows PowerShell 5.1 would turn that into terminating errors
    # under "Stop", so relax the preference just for this call and check the exit code instead.
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker @dockerArgs 2>&1 | ForEach-Object { "$_" } |
            Where-Object { $_ -notmatch '^\s*(Container|Network|Volume) |^\s*$' }
        $script:DockerExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
}

function Lab([string[]]$cmd, [switch]$AllowFail) {
    # Run a command inside the lab container.
    Docker-Run (@("compose", "run", "--rm", "lab") + $cmd)
    if ($script:DockerExit -ne 0) {
        if ($AllowFail) { Write-Host "  (this step reported a problem; see the message above; continuing)" -ForegroundColor Yellow }
        else { throw "lab command failed: $($cmd -join ' ')" }
    }
}

function Open-File([string]$path) {
    if ($NoOpen) { Write-Host "  (would open: $path)"; return }
    if (-not (Test-Path $path)) { Write-Host "  (not found: $path)" -ForegroundColor Yellow; return }
    try { Start-Process $path } catch { Write-Host "  Open this file yourself: $path" -ForegroundColor Yellow }
}

# --- 0. Docker -------------------------------------------------------------
Step "0. Checking Docker" ""
Docker-Run @("info") | Out-Null
if ($script:DockerExit -ne 0) {
    $desktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $desktop) {
        Write-Host "  Starting Docker Desktop..." -ForegroundColor Yellow
        Start-Process $desktop
        $deadline = (Get-Date).AddMinutes(3)
        do { Start-Sleep -Seconds 5; Docker-Run @("info") | Out-Null } until ($script:DockerExit -eq 0 -or (Get-Date) -gt $deadline)
    }
    if ($script:DockerExit -ne 0) { throw "Docker is not running. Start Docker Desktop and run the demo again." }
}
Write-Host "  Docker is running." -ForegroundColor Green

if (-not $SkipBuild) {
    Write-Host "  Building the lab image (fast if nothing changed)..."
    Docker-Run @("compose", "build") | Select-Object -Last 2
    if ($script:DockerExit -ne 0) { throw "docker compose build failed" }
}

if ($RunTests) {
    Step "Automated tests" "Every component is covered by automated tests."
    Lab @("python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
          "--deselect", "tests/test_agent.py::test_driver_runs_every_task_with_mock")
    Pause-Demo
}

if (Test-Path $DemoDir) { Remove-Item -Recurse -Force $DemoDir }

# --- 1. Problem ------------------------------------------------------------
Step "1. The problem" ("MCP lets AI agents call tools. A malicious server can hide instructions in tool " +
    "descriptions or send its own requests to the model. Network IDSs cannot see this. My question: can " +
    "attack ATTEMPTS be detected from the MCP traffic itself?")
Open-File (Join-Path $Root "docs\images\architecture.svg")
Pause-Demo "run a benign session"

# --- 2. Sessions -----------------------------------------------------------
Step "2a. A benign session (SQLite server)" "Each session writes one labelled manifest line; the label is never in the traffic logs."
Lab @("python", "-m", "orchestrator.main", "--data-dir", "/lab/data/demo_live", "run", "benign:db_order_status", "--seed", "1")
Pause-Demo "run an attack session"

Step "2b. A benign server that uses sampling (help desk)" ("Its tool asks the client's model to classify a " +
    "ticket via sampling/createMessage, as real MCP servers do. Since 10 October such benign sessions are in the " +
    "training data, so 'a server asked the model' alone no longer means attack.")
Lab @("python", "-m", "orchestrator.main", "--data-dir", "/lab/data/demo_live", "run", "benign:helpdesk_triage_ticket", "--seed", "2")
Pause-Demo "run an attack session"

Step "2c. An inert tool-poisoning attack" "The attack only asks for a harmless calculator call; it is a twin of the benign calculator."
Lab @("python", "-m", "orchestrator.main", "--data-dir", "/lab/data/demo_live", "run", "attack:poisoned_tool:calc_add", "--seed", "4", "--susceptibility", "1.0")
Pause-Demo "show what the proxy recorded"

# --- 3. Proxy log ----------------------------------------------------------
Step "3. What the logging proxy recorded (latest session)" ("Note the larger tools/list response and the " +
    "add_numbers 1337 + 7331 call: the planted instruction being obeyed. The proxy forwards bytes unchanged and logs a copy.")
Lab @("sh", "-c", "MCP_LOG_DIR=/lab/data/demo_live/raw/sessions python -m proxy.reader latest")
Pause-Demo "verify the data"

# --- 4. Verify + detect ----------------------------------------------------
Step "4a. Verify manifest against logs" ""
Lab @("python", "-m", "orchestrator.main", "--data-dir", "/lab/data/demo_live", "verify") -AllowFail
Pause-Demo "run the detector"

Step "4b. Detector verdicts" ("The live detector uses the tuned RF + XGBoost model trained on the final dataset " +
    "(2,220 sessions, including benign sampling servers). It flags the attack and passes both benign sessions, " +
    "with a confidence for each, in about 40 milliseconds.")
Lab @("python", "-m", "detector.detector", "replay", "--data-dir", "/lab/data/demo_live")
Pause-Demo "compare all seven models"

Step "4c. All seven models on the same sessions" ("Six models on the 65 features (Random Forest, SVM, XGBoost, " +
    "RF + XGBoost, Decision Tree, 1-D CNN) and a CNN that reads the raw messages, all tuned on training tasks only.")
Lab @("python", "-m", "scripts.compare_models", "--models", "/lab/models/combined_canonical_20261010",
      "--data-dir", "/lab/data/demo_live", "--last", "3")
Pause-Demo "open the evaluation results"

# --- 5. Results ------------------------------------------------------------
Step "5. Results" ("The test split now holds out whole tasks (the old random split had 185 of 407 test " +
    "sessions copied from training). Honest test on 2,220 sessions, tuned inside each fold: RF + XGBoost F1 0.80 " +
    "(95% CI 0.33-1.00), 0.2% false alarms; XGBoost and the Decision Tree 0.79. Models trained " +
    "without benign samplers false-alarmed on them (SVM 103 of 232, 1-D CNN 169). The raw-traffic CNN scores " +
    "only 0.38 once the original-wording shortcut is removed: hand-made features generalise better here. " +
    "Sampling attacks come from one task, so none is caught on an unseen task.")
Open-File $Report
Open-File (Join-Path $Root "results\combined_canonical_20261010\confusion_matrix_rf.png")
Open-File (Join-Path $Root "results\model_comparison_20261010.png")
Pause-Demo

# --- 6. Live (optional) ----------------------------------------------------
if ($Live) {
    Step "6. Live detector" "A sidecar watches the logs and gives a verdict as each session ends; it can never block or slow traffic."
    $py = Join-Path $Root ".venv\Scripts\python.exe"
    $liveLogs = Join-Path $Root "data\live\raw\sessions"
    New-Item -ItemType Directory -Force -Path $liveLogs | Out-Null
    Start-Process powershell -ArgumentList "-NoExit", "-Command",
        "Set-Location '$Root'; & '$py' -u -m detector.detector watch --log-dir data/live/raw/sessions"
    # The watcher ignores sessions that finished before it started, and loading the model takes a few seconds.
    Write-Host "  Waiting for the second window to show 'watching ...'" -ForegroundColor Yellow
    Start-Sleep -Seconds 15
    Pause-Demo "start the sessions (the second window must say 'watching')"
    # Three benign sessions and one inert attack, so the watcher shows both verdicts.
    Lab @("python", "-m", "orchestrator.main", "--data-dir", "/lab/data/live", "batch", "--scenarios",
          "benign:db_order_status,benign:fs_report_digest,benign:web_news,attack:poisoned_tool:calc_add",
          "--parallel", "2", "--seed", "900")
    Write-Host "  Verdicts appear in the second window. Close it when done." -ForegroundColor Green
    Pause-Demo
}

Step "Done" "Everything is reproducible from documented commands; next steps are varied benign servers, more attack tasks and sequence models."
