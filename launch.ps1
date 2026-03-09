# launch.ps1 - CORHack RAG Launcher (multi-vault)
$PROJECT_DIR = "C:\Users\jbcde\Documents\Projet\RAG-Obsidian"
$VENV_PYTHON  = "$PROJECT_DIR\.venv\Scripts\python.exe"
$QDRANT_URL   = "http://localhost:6333/healthz"
$lastVault = if (Test-Path "$PROJECTDIR\.corhack-cache.json") {
    $cache = Get-Content "$PROJECTDIR\.corhack-cache.json" | ConvertFrom-Json
    $cache.PSObject.Properties.Name | Select-Object -First 1 | Split-Path -Parent
} else { "C:\Users\jbcde\Documents\Dossier Obsidian\Perso\" }


function Write-Step { param($msg) Write-Host "  ► $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "  ✗ $msg" -ForegroundColor Red }

Clear-Host
Write-Host ""
Write-Host "  ██████╗ ██████╗ ██████╗ ██╗  ██╗ █████╗  ██████╗██╗  ██╗" -ForegroundColor Cyan
Write-Host "  ██╔════╝██╔═══██╗██╔══██╗██║  ██║██╔══██╗██╔════╝██║ ██╔╝" -ForegroundColor Cyan
Write-Host "  ██║     ██║   ██║██████╔╝███████║███████║██║     █████╔╝ " -ForegroundColor Cyan
Write-Host "  ██║     ██║   ██║██╔══██╗██╔══██║██╔══██║██║     ██╔═██╗ " -ForegroundColor Cyan
Write-Host "  ╚██████╗╚██████╔╝██║  ██║██║  ██║██║  ██║╚██████╗██║  ██╗" -ForegroundColor Cyan
Write-Host "   ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "           RAG • Obsidian Vault Assistant" -ForegroundColor DarkCyan
Write-Host ""

# ── 0. Choix du vault ─────────────────────────────────────────
Write-Host "  ─────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Step "Quel dossier veux-tu indexer ?"
Write-Host "  Dernier dossier : $lastVault" -ForegroundColor DarkGray
Write-Host ""
$VAULT_PATH = Read-Host "  ❯ Chemin du vault"

if (-not (Test-Path $VAULT_PATH)) {
    Write-Fail "Dossier introuvable : $VAULT_PATH"
    exit 1
}

$VAULT_NAME      = (Get-Item $VAULT_PATH).Name.Replace(' ', '_').Replace('(','').Replace(')','')
$COLLECTION_NAME = "obsidian_$VAULT_NAME"
$env:VAULT_PATH      = $VAULT_PATH
$env:COLLECTION_NAME = $COLLECTION_NAME
$env:PYTHONUTF8      = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-OK "Vault     : $VAULT_PATH"
Write-OK "Collection: $COLLECTION_NAME"
Write-Host ""

# ── 1. Docker Desktop ─────────────────────────────────────────
Write-Step "Vérification de Docker Desktop..."
$dockerRunning = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerRunning) {
    Write-Warn "Docker Desktop n'est pas lancé → démarrage..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    $timeout = 30
    while ($timeout -gt 0) {
        Start-Sleep -Seconds 2
        $timeout -= 2
        $check = docker info 2>&1
        if ($LASTEXITCODE -eq 0) { break }
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Docker Desktop n'a pas démarré. Lance-le manuellement."
        exit 1
    }
}
Write-OK "Docker Desktop actif"

# ── 2. Qdrant via docker compose ──────────────────────────────
Write-Step "Lancement de Qdrant..."
Set-Location $PROJECT_DIR
docker compose up -d 2>&1 | Out-Null

# ── 3. Attente Qdrant healthy ─────────────────────────────────
Write-Step "Attente que Qdrant soit prêt..."
$maxTries = 15; $tries = 0; $ready = $false
while ($tries -lt $maxTries) {
    try {
        $r = Invoke-WebRequest -Uri $QDRANT_URL -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 2; $tries++
    Write-Host "  ." -NoNewline -ForegroundColor DarkGray
}
Write-Host ""
if (-not $ready) { Write-Fail "Qdrant inaccessible après 30s."; exit 1 }
Write-OK "Qdrant opérationnel sur localhost:6333"

# ── 4. Ollama ─────────────────────────────────────────────────
Write-Step "Vérification d'Ollama..."
$ollamaRunning = Get-Process "ollama" -ErrorAction SilentlyContinue
if (-not $ollamaRunning) {
    Write-Warn "Ollama non détecté → démarrage..."
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}
Write-OK "Ollama actif sur localhost:11434 (embeddings)"

# ── 5. Vérif clé Groq ─────────────────────────────────────────
Write-Step "Vérification config Groq..."
$configContent = Get-Content "$PROJECT_DIR\config.py" -Raw
if ($configContent -match 'LLM_API_KEY\s*=\s*"gsk_') {
    Write-OK "Clé Groq détectée (LLM via cloud)"
} else {
    Write-Warn "Clé Groq non configurée → vérifie config.py"
}

# ── Vérif dépendances Python ──────────────────────────────────
Write-Step "Vérification des dépendances Python..."
$checkDeps = & $VENV_PYTHON -c "import networkx, pyvis, qdrant_client, ollama, openai, rich" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Dépendances manquantes → installation automatique..."
    & "$PROJECT_DIR\.venv\Scripts\pip.exe" install -r "$PROJECT_DIR\requirements.txt" | Out-Null
    Write-OK "Dépendances installées"
} else {
    Write-OK "Dépendances Python OK"
}

# ── 6. Scan + index intelligent ───────────────────────────────
Write-Step "Scan des fichiers .md dans '$VAULT_PATH'..."
$mdFiles = Get-ChildItem -Path $VAULT_PATH -Recurse -Filter "*.md" -ErrorAction SilentlyContinue
Write-Host "  📄 Fichiers .md trouvés : $($mdFiles.Count)" -ForegroundColor DarkCyan

if ($mdFiles.Count -eq 0) {
    Write-Warn "Aucun fichier .md trouvé dans ce dossier !"
    Write-Host "  Vérifie que le chemin contient bien des fichiers Markdown." -ForegroundColor DarkGray
    $forceIndex = Read-Host "  Forcer quand même l'indexation ? (o/N)"
    if ($forceIndex -ne "o" -and $forceIndex -ne "O") { exit 1 }
}

# Cache timestamps (1 cache par vault)
$cacheFile    = "$PROJECT_DIR\.corhack-cache-$VAULT_NAME.json"
$changedFiles = @()

if (Test-Path $cacheFile) {
    $cache = Get-Content $cacheFile | ConvertFrom-Json
} else {
    $cache = @{}
}

$currentFiles = @{}
foreach ($file in $mdFiles) {
    $mtime = $file.LastWriteTime.ToFileTime()
    $currentFiles[$file.FullName] = $mtime
    if (-not $cache.PSObject.Properties.Name.Contains($file.FullName) -or
        $cache.$($file.FullName) -ne $mtime) {
        $changedFiles += $file.FullName
    }
}

$deleted = $cache.PSObject.Properties.Name | Where-Object { $_ -notin $currentFiles.Keys }
if ($deleted) { Write-Warn "Fichiers supprimés : $($deleted.Count)" }

$currentFiles | ConvertTo-Json | Set-Content $cacheFile

# Vérifie collection ET chunks dans Qdrant
$collectionExists = $false
$chunkCount       = 0
try {
    $collectionInfo   = Invoke-RestMethod -Uri "http://localhost:6333/collections/$COLLECTION_NAME" -UseBasicParsing
    $collectionExists = $true
    $chunkCount       = $collectionInfo.result.points_count
    Write-Host "  📊 Collection existante : $chunkCount chunks" -ForegroundColor DarkCyan
} catch {
    Write-Host "  📊 Nouvelle collection détectée" -ForegroundColor DarkCyan
}

# Indexe si : nouvelle collection OU vide OU fichiers modifiés/supprimés
if (-not $collectionExists -or $chunkCount -eq 0 -or $changedFiles.Count -gt 0 -or $deleted) {
    if (-not $collectionExists -or $chunkCount -eq 0) {
        Write-Warn "Collection vide ou inexistante → première indexation complète..."
        $env:CHANGED_FILES = ""
        $env:DELETED_FILES = ""
        & $VENV_PYTHON "$PROJECT_DIR\ingest.py"
    } else {
        Write-Warn "$($changedFiles.Count) fichier(s) modifié(s) → indexation incrémentale..."
        # Passer via fichier temp pour éviter les problèmes d'encoding
        $tempFile = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "corhack_index_$([guid]::NewGuid()).json")
        @{
            changed = $changedFiles
            deleted = @($deleted)
        } | ConvertTo-Json | Set-Content $tempFile -Encoding UTF8
        
        $env:CORHACK_INDEX_FILE = $tempFile
        & $VENV_PYTHON "$PROJECT_DIR\ingest.py"
        $env:CORHACK_INDEX_FILE = ""
        Remove-Item $tempFile -ErrorAction SilentlyContinue
    }
    Write-OK "Indexation terminée"
} else {
    Write-OK "Index à jour ($chunkCount chunks, $($mdFiles.Count) fichiers)"
}

# ── 7. Lance le CLI ───────────────────────────────────────────
Write-Host ""
Write-OK "Tout est prêt ! Lancement du CLI..."
Write-Host ""
Start-Sleep -Seconds 1
& $VENV_PYTHON "$PROJECT_DIR\query.py"
