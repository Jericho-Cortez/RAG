# ╔═══════════════════════════════════════════════════════════════╗
# ║     SIMULATEUR RANSOMWARE - Lab SOC Analyst                   ║
# ║     ⚠️  À exécuter UNIQUEMENT en environnement isolé (VM)     ║
# ╚═══════════════════════════════════════════════════════════════╝

# Script PowerShell qui simule une infection ransomware
# Génère les logs d'événements pour Splunk

# RUN WITH: powershell -ExecutionPolicy Bypass -File .\01_SCRIPTS_RANSOMWARE.ps1

param(
    [string]$C2_IP = "203.0.113.45",
    [int]$C2_PORT = 443,
    [string]$TARGET_DIR = "$env:USERPROFILE\Documents"
)

# ════════════════════════════════════════════════════════════════
# 1️⃣  ÉTAPE 1: Enable Sysmon logging (prerequisite)
# ════════════════════════════════════════════════════════════════

Write-Host "[*] Configuration de Sysmon..." -ForegroundColor Cyan
$SysmonService = Get-Service -Name Sysmon -ErrorAction SilentlyContinue

if (-not $SysmonService) {
    Write-Host "⚠️  Sysmon n'est pas installé. Install depuis: https://docs.microsoft.com/en-us/sysinternals/downloads/sysmon" -ForegroundColor Yellow
    Write-Host "    Pour l'instant, on continue avec Event Viewer standard." -ForegroundColor Yellow
}

# ════════════════════════════════════════════════════════════════
# 2️⃣  ÉTAPE 2: Trigger Windows Event (ProcessCreate) 
# ════════════════════════════════════════════════════════════════

Write-Host "[+] Génération de l'événement ProcessCreate..." -ForegroundColor Green

# Lancer powershell enfant (trouvé dans historique du malware)
powershell.exe -NoProfile -WindowStyle Hidden -Command {
    Start-Sleep -Milliseconds 500
    
    # Lancer cmd.exe enfant
    cmd.exe /c timeout 1
    
    Write-Host "    ✓ ProcessCreate: powershell.exe -> cmd.exe [Enregistré]" -ForegroundColor Green
}

Start-Sleep -Seconds 1

# ════════════════════════════════════════════════════════════════
# 3️⃣  ÉTAPE 3: File Modification (chiffrage simulé)
# ════════════════════════════════════════════════════════════════

Write-Host "[+] Simulation des modifications de fichiers..." -ForegroundColor Green

if (-not (Test-Path $TARGET_DIR)) {
    New-Item -ItemType Directory -Path $TARGET_DIR -Force | Out-Null
}

# Créer les fichiers "chiffrés" (simulation)
$files_to_encrypt = @(
    "$TARGET_DIR\report_financier_2026.docx",
    "$TARGET_DIR\donnees_clients.xlsx",
    "$TARGET_DIR\contrats_importants.pdf",
    "$TARGET_DIR\archive_email.pst"
)

foreach ($file in $files_to_encrypt) {
    # Créer le fichier
    if (-not (Test-Path $file)) {
        @"
SAMPLE DATA FOR ENCRYPTION TEST
This is a mock document that would be encrypted by ransomware.
"@ | Out-File -FilePath $file -Encoding UTF8 -Force
        Write-Host "    ✓ Créé: $file" -ForegroundColor Green
    }
    
    # Renommer en .locked (simulation chiffrage)
    $locked_file = "$file.locked"
    if (-not (Test-Path $locked_file)) {
        Copy-Item $file -Destination $locked_file -Force
        Write-Host "    ✓ Chiffré (simulé): $locked_file" -ForegroundColor Green
    }
}

# ════════════════════════════════════════════════════════════════
# 4️⃣  ÉTAPE 4: File Permissions Change (NTFS ACL)
# ════════════════════════════════════════════════════════════════

Write-Host "[+] Modification des permissions NTFS..." -ForegroundColor Green

foreach ($file in $files_to_encrypt) {
    $locked_file = "$file.locked"
    if (Test-Path $locked_file) {
        try {
            $acl = Get-Acl $locked_file
            # Désactiver l'héritage des permissions
            $acl.SetAccessRuleProtection($true, $false)
            Set-Acl -Path $locked_file -AclObject $acl
            Write-Host "    ✓ ACL modifiée: $locked_file" -ForegroundColor Green
        } catch {
            Write-Host "    ⚠️  Erreur ACL: $_" -ForegroundColor Yellow
        }
    }
}

# ════════════════════════════════════════════════════════════════
# 5️⃣  ÉTAPE 5: Network Connection (C2 callback)
# ════════════════════════════════════════════════════════════════

Write-Host "[+] Simulation de connexion au serveur C2..." -ForegroundColor Green

# Créer une connexion de test (curl)
# ⚠️  Cela génère un événement de connexion réseau capturé par netstat
$c2_connection = $C2_IP + ":" + $C2_PORT

Write-Host "    [C2 Connection Attempt] Vers: $c2_connection (simul.)" -ForegroundColor Yellow

# Essayer une connexion (elle échouera, mais génère les events)
try {
    $socket = New-Object System.Net.Sockets.TcpClient
    $async = $socket.BeginConnect($C2_IP, $C2_PORT, $null, $null)
    $wait = $async.AsyncWaitHandle.WaitOne(1000, $false)
    if (!$wait) {
        $socket.Close()
        Write-Host "    ✓ Tentative de connexion enregistrée dans Event Viewer" -ForegroundColor Green
    }
} catch {
    Write-Host "    ✓ Tentative de connexion enregistrée (erreur normale) " -ForegroundColor Green
}

# ════════════════════════════════════════════════════════════════
# 6️⃣  ÉTAPE 6: Registry Modification (persistence)
# ════════════════════════════════════════════════════════════════

Write-Host "[+] Modification du registre (persistence)..." -ForegroundColor Green

$reg_path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$reg_value = ".ransomware_persistence"

try {
    # Lire avant (baseline)
    $before = Get-ItemProperty -Path $reg_path -ErrorAction SilentlyContinue
    
    # Créer la "clé de persistence" (simulation)
    New-ItemProperty -Path $reg_path -Name $reg_value -Value "C:\Windows\Temp\recovery.exe" -PropertyType String -Force -ErrorAction SilentlyContinue | Out-Null
    
    Write-Host "    ✓ Enregistrement de persistence créé: $reg_value" -ForegroundColor Green
} catch {
    Write-Host "    ⚠️  Impossible de modifier le registre: $_" -ForegroundColor Yellow
}

# ════════════════════════════════════════════════════════════════
# 7️⃣  ÉTAPE 7: Affichage de la chronologie
# ════════════════════════════════════════════════════════════════

Write-Host "`n" -ForegroundColor Cyan
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║             CHRONOLOGIE DE L'ATTAQUE SIMULÉE               ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

$timeline = @(
    @{ Time = "T+0s"; Event = "ProcessCreate: powershell.exe"; IoC = "Command injection via shell" },
    @{ Time = "T+0.5s"; Event = "ProcessCreate: cmd.exe (child of powershell)"; IoC = "Chainload obfuscation" },
    @{ Time = "T+1s"; Event = "FileDelete + FileCreate: *.locked"; IoC = "Ransomware file markers" },
    @{ Time = "T+2s"; Event = "FileCreate: recovery.txt (ransom note)"; IoC = "Ransom note" },
    @{ Time = "T+3s"; Event = "RegistrySet: HKCU\...\Run (persistence)"; IoC = "Persistence mechanism" },
    @{ Time = "T+4s"; Event = "NetworkConnection: 203.0.113.45:443"; IoC = "C2 callback" }
)

$timeline | Format-Table -AutoSize @{Name="Time"; Expression={$_.Time}}, @{Name="Event"; Expression={$_.Event}}, @{Name="IoC"; Expression={$_.IoC}}

# ════════════════════════════════════════════════════════════════
# 8️⃣  ÉTAPE 8: IOCs (Indicators of Compromise) 
# ════════════════════════════════════════════════════════════════

Write-Host "`n"
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║                  IOCs À RECHERCHER                         ║" -ForegroundColor Yellow
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow

$iocs = @(
    @{ Type = "IP Address"; Value = $C2_IP; Category = "C2 Server" },
    @{ Type = "Port"; Value = $C2_PORT; Category = "C2 Server" },
    @{ Type = "File Extension"; Value = ".locked"; Category = "Encrypted Files" },
    @{ Type = "Registry Key"; Value = ".ransomware_persistence"; Category = "Persistence" },
    @{ Type = "Process Chain"; Value = "powershell.exe -> cmd.exe"; Category = "Execution" },
    @{ Type = "File Hash (MD5)"; Value = "[À calculer via Splunk]"; Category = "File Indicator" }
)

$iocs | Format-Table -AutoSize @{Name="Type"; Expression={$_.Type}}, @{Name="Value"; Expression={$_.Value}}, @{Name="Category"; Expression={$_.Category}}

Write-Host "`n✅ Simulation ransomware terminée!" -ForegroundColor Green
Write-Host "📊 Les logs doivent maintenant être visibles dans:" -ForegroundColor Green
Write-Host "   - Event Viewer (Événements Windows > Sécurité)" -ForegroundColor Gray
Write-Host "   - Splunk (index=main)" -ForegroundColor Gray
Write-Host "`n"
