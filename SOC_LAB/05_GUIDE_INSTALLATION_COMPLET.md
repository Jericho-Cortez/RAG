# ╔════════════════════════════════════════════════════════════════╗
# ║    GUIDE INSTALLATION - LAB SOC RANSOMWARE                   ║
# ║    Étape par étape (Splunk + Rocky Linux + VM)               ║
# ╚════════════════════════════════════════════════════════════════╝

## 📋 TABLE DES MATIÈRES

1. [Prérequis](#prérequis)
2. [Étape 1: Préparer les VMs](#étape-1-préparer-les-vms)
3. [Étape 2: Installer Rocky Linux + Splunk](#étape-2-installer-rocky-linux--splunk)
4. [Étape 3: Configurer rsyslog](#étape-3-configurer-rsyslog)
5. [Étape 4: Windows Agent Setup](#étape-4-windows-agent-setup)
6. [Étape 5: Lancer la Simulation](#étape-5-lancer-la-simulation)
7. [Étape 6: Analyser dans Splunk](#étape-6-analyser-dans-splunk)
8. [Troubleshooting](#troubleshooting)

---

## 🔧 PRÉREQUIS

### Hardware Requirements
| Composant | Minimum | Recommandé |
|-----------|---------|-----------|
| CPU | 4 vCores | 8 vCores |
| RAM | 8 GB | 16 GB |
| Disk | 100 GB | 250 GB |
| Virtualization | VirtualBox / Hyper-V / VMware |  |

### Software
- VirtualBox (gratuit) ou Hyper-V
- Rocky Linux 9 ISO (https://rockylinux.org/download)
- Windows 10 ISO (si pas déjà installé)
- Splunk Free Edition (https://www.splunk.com/en_us/download.html)

---

## ⚙️ ÉTAPE 1: PRÉPARER LES VMs

### 1.1 Créer la VM Rocky Linux (SIEM)

**Dans VirtualBox:**
```bash
# 1. Créer nouvelle VM
Name: "SOC-Lab-Rocky-SIEM"
Type: Linux
Version: Red Hat (64-bit)
RAM: 8 GB
vCPU: 4
Disk: 100 GB (dynamique)
Network: Bridged Adapter (ou NAT)

# 2. Boot depuis Rocky Linux ISO
# 3. Installer: Workstation Installation (avec GUI optionnel)
# 4. Après installation:
hostnamectl set-hostname siem-server
ip addr show  # Note l'IP (ex: 192.168.1.50)
```

### 1.2 Créer la VM Windows 10 (Workstation)

```bash
# VirtualBox:
Name: "SOC-Lab-Windows-Workstation"
Type: Windows
Version: Windows 10 (64-bit)
RAM: 4 GB
vCPU: 2
Disk: 50 GB
Network: Same as Rocky VM (Bridged)

# Après installation:
Settings > System > About
  - Note l'IP (ex: 192.168.1.100)
  - Note le hostname
```

### 1.3 Tester la Connectivité

Sur Rocky Linux:
```bash
ping 192.168.1.100  # Windows VM
# PING 192.168.1.100 (192.168.1.100) 56(84) bytes of data.
# 64 bytes from 192.168.1.100: icmp_seq=1 ttl=128 time=1.234 ms
# ✓ Connectivité OK
```

---

## 📥 ÉTAPE 2: INSTALLER ROCKY LINUX + SPLUNK

### 2.1 Préparation Rocky Linux

```bash
# SSH sur Rocky VM
ssh ubuntu@192.168.1.50

# Mise à jour du système
sudo dnf update -y
sudo dnf install -y wget curl openssh-server openssh-clients

# Démarrer SSH
sudo systemctl start sshd
sudo systemctl enable sshd
```

### 2.2 Installer Splunk Free Edition

```bash
# Télécharger Splunk
cd /tmp
wget "https://www.splunk.com/bin/splunk/DownloadActivityServlet?architecture=x86_64&platform=linux&release=9.0.4&license=free" \
  -O splunk-9.0.4-linux-2.6.23-generic-x86_64.tgz

# Extraire
tar -xzf splunk-*.tgz -C /opt
cd /opt/splunk

# Créer utilisateur splunk
sudo useradd -m splunk
sudo chown -R splunk:splunk /opt/splunk

# Démarrer Splunk
sudo -u splunk ./bin/splunk start --accept-license --answer-yes --no-audit --seed-passwd mypass123

# Output:
# Splunk> All in. Turning to face you...
# Checking prerequisites...
# All checks passed.
# ...
# Splunk has started and various commands should now be available for your use!
# 
# This appears to be your first time running this shell so commands  
# are being initialized. Please wait while we initialize the system...
# PLEASE REVIEW THIS LICENSE AGREEMENT CAREFULLY BEFORE INSTALLING OR USING
# SPLUNK SOFTWARE... [Accept]
# 🎉 Splunk installed successfully
```

### 2.3 Vérifier Splunk

```bash
# Ouvrir le navigateur depuis ton PC hôte
# http://192.168.1.50:8000

# Login:
# Username: admin
# Password: mypass123  (first time setup)

# ✓ Voir le dashboard Splunk
```

---

## 📡 ÉTAPE 3: CONFIGURER RSYSLOG

### 3.1 Configuration rsyslog pour recevoir les logs

```bash
# SSH sur Rocky VM
ssh ubuntu@192.168.1.50

# Éditer rsyslog
sudo nano /etc/rsyslog.conf

# Ajouter ces lignes (décommenter):
# ════════════════════════════════
# Provide UDP syslog reception
$ModLoad imudp
$UDPServerRun 514

# Provide TCP syslog reception
$ModLoad imtcp
$InputTCPServerRun 514
# ════════════════════════════════

# Redémarrer rsyslog
sudo systemctl restart rsyslog
sudo systemctl status rsyslog

# Vérifier que rsyslog écoute sur 514
sudo netstat -tlnp | grep 514
# tcp        0      0 0.0.0.0:514             0.0.0.0:*               LISTEN      1234/rsyslogd
# udp        0      0 0.0.0.0:514             0.0.0.0:*               LISTEN      1234/rsyslogd
# ✓ OK
```

### 3.2 Configurer Splunk pour recevoir les logs

```bash
# Dans Splunk Web Interface:
# 1. Aller à: Settings > Data Inputs > TCP/UDP
# 2. Cliquer: New Event Source
# 3. Configure:
#    - Source: Port 514
#    - Sourcetype: syslog
#    - Index: main
#    - Click: Submit

# Vérifier:
# Settings > Indexes > main
# ✓ Receiving data from 192.168.1.100 (Windows)
```

---

## 🔗 ÉTAPE 4: WINDOWS AGENT SETUP

### 4.1 Configurer Event Viewer Forwarding

```powershell
# RUN AS ADMIN sur Windows 10 VM

# Ouvrir Gestion des tâches planifiées:
wevtutil qe Security /c:10 /rd:true /f:text

# Exporter les logs vers fichier CSV:
wevtutil query-events Security /c:100 /format:text > C:\events.txt

# ✓ Fichier créé
```

### 4.2 Configurer Event Log Forwarding (optionnel - avancé)

```powershell
# Pour les VMs Splunk + Windows, installer Universal Forwarder:

# 1. Télécharger Splunk Universal Forwarder
# https://www.splunk.com/en_us/download/universal-forwarder.html

# 2. Installer
# Accepter les termes
# Destination: Le serveur Rocky (192.168.1.50:9997)

# 3. Configurer inputs.conf:
# C:\Program Files\SplunkUniversalForwarder\etc\system\default\inputs.conf
# ─────────────────────────────────────────
# [WinEventLog:Security]
# sourcetype = WinEventLog:Security
# index = main
# ─────────────────────────────────────────

# 4. Redémarrer le service
# Services.msc > Splunk Universal Forwarder > Restart
```

---

## 🚀 ÉTAPE 5: LANCER LA SIMULATION

### 5.1 Préparation sur Windows VM

```powershell
# RUN AS ADMIN

# 1. Copier le script: 01_SCRIPTS_RANSOMWARE.ps1
# C:\Users\employee\01_SCRIPTS_RANSOMWARE.ps1

# 2. Autoriser l'exécution de scripts
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser -Force

# 3. Vérifier les logs actuels (baseline)
Get-WinEvent -LogName Security | Select-Object -First 5 TimeCreated, Id, Message

# 4. Noter l'heure actuelle (T0)
Get-Date
# Output: 13-03-2026 14:30:00
```

### 5.2 Exécuter la Simulation

```powershell
# Sur Windows VM - RUN AS ADMIN:

& C:\Users\employee\01_SCRIPTS_RANSOMWARE.ps1

# Output:
# [*] Configuration de Sysmon...
# [+] Génération de l'événement ProcessCreate...
#     ✓ ProcessCreate: powershell.exe -> cmd.exe [Enregistré]
# [+] Simulation des modifications de fichiers...
#     ✓ Créé: C:\Users\employee\Documents\report_financier_2026.docx
#     ✓ Chiffré (simulé): C:\Users\employee\Documents\report_financier_2026.docx.locked
# [+] Modification des permissions NTFS...
#     ✓ ACL modifiée: ...
# [+] Simulation de connexion au serveur C2...
#     [C2 Connection Attempt] Vers: 203.0.113.45:443 (simul.)
#     ✓ Tentative de connexion enregistrée dans Event Viewer
# ...
# ✅ Simulation ransomware terminée!

# ✓ Simulation lancée - Les logs sont générés!
```

### 5.3 Vérifier les Fichiers Créés

```powershell
# Windows PowerShell:

ls C:\Users\employee\Documents\ -Recurse | Where-Object Name -Match "\.locked"

# Output:
# Mode                 LastWriteTime         Length Name
# ----                 -------------         ------ ----
# -a----        13/03/2026     14:32:17       1024 report_financier_2026.docx.locked
# -a----        13/03/2026     14:32:18        1024 donnees_clients.xlsx.locked

# ✓ Fichiers chiffrés visibles!
```

---

## 📊 ÉTAPE 6: ANALYSER DANS SPLUNK

### 6.1 Vérifier l'Ingestion des Données

```
Dans Splunk:
1. Home > Search & Reporting
2. Search: index=main
3. Time Range: Last 5 minutes
4. Enter

# Output: Should show events from Windows VM
```

### 6.2 Exécuter les Requêtes d'Investigation

```spl
# Query 1: Détecterla chaîne de processus

index=main sourcetype="WinEventLog:Security" EventCode=4688 
| search (CommandLine="*powershell*" OR CommandLine="*cmd*") 
| table TimeCreated, ProcessName, ParentProcessName, CommandLine
```

```spl
# Query 2: Fichiers chiffrés

index=main sourcetype="WinEventLog:Security" EventCode=4658
| search Object_Name="*.locked"
| table TimeCreated, Object_Name
```

```spl
# Query 3: Connexion C2

index=main EventCode=5156 dest_ip="203.0.113.45"
| table TimeCreated, src_ip, dest_ip, dest_port
```

### 6.3 Créer une Alerte

```
1. Settings > Saved Searches > New
   Name: Ransomware_C2_Alert
   Search: index=main EventCode=5156 dest_ip="203.0.113.45"
   
2. Alert Trigger: When count >= 1
3. Actions: Email to soc@company.com
4. Save

✓ Alerte activée!
```

---

## 🐛 TROUBLESHOOTING

### Problème: Pas de logs dans Splunk

**Solution:**
```bash
# 1. Vérifier rsyslog sur Rocky
sudo systemctl status rsyslog
# Si pas running:
sudo systemctl start rsyslog

# 2. Vérifier que port 514 écoute
sudo netstat -tlnp | grep 514
# Si vide, redémarrer rsyslog

# 3. Tester manuellement depuis Windows:
# En PowerShell:
$logname = "Security"
$log = Get-WinEvent -LogName $logname -MaxEvents 1
$remotehost = "192.168.1.50:514"
# (envoi manuel si needed)

# 4. Vérifier Splunk Input
# Settings > Data Inputs > TCP
# Voir si 514 écoute
```

### Problème: Les événements Windows n'apparaissent pas

**Solution:**
```powershell
# Windows PowerShell - RUN AS ADMIN:

# 1. Vérifier que Event Viewer a des événements:
Get-WinEvent -LogName Security -MaxEvents 10

# 2. Si vide, lancer manuellement:
# (Re-exécuter 01_SCRIPTS_RANSOMWARE.ps1)

# 3. Vérifier l'approvisionnement Universal Forwarder (si utilisé):
# Services.msc > Splunk Universal Forwarder > Status = "Running"
# Si arrêté: Start > OK

# 4. Vérifier les fichiers journal du forwarder:
# C:\Program Files\SplunkUniversalForwarder\var\log\splunk\splunkd.log
Get-Content "C:\Program Files\SplunkUniversalForwarder\var\log\splunk\splunkd.log" -Tail 20
```

### Problème: Splunk ralentit / crash

**Solution:**
```bash
# Rocky VM - SSH:

# 1. Vérifier usage CPU/RAM:
top
# Si > 90%, attendreque l'indexation finisse
# Ctrl+C

# 2. Augmenter ressources (VirtualBox):
# Settings > System > RAM: 12 GB
# Settings > Processor > vCPU: 6

# 3. Redémarrer Splunk:
sudo -u splunk /opt/splunk/bin/splunk restart
```

### Problème: Impossible de se connecter à Splunk

**Solution:**
```bash
# Rocky VM - SSH:

# 1. Vérifier que Splunk tourne:
ps aux | grep splunk

# 2. Redémarrer:
sudo -u splunk /opt/splunk/bin/splunk start

# 3. Vérifier le port:
sudo netstat -tlnp | grep 8000

# 4. Vérifier les logs:
tail -f /opt/splunk/var/log/splunk/splunkd.log
```

---

## ✅ VALIDATION COMPLÈTE

Quand tout est OK, tu dois voir:

- [ ] Rocky VM accessible via SSH (192.168.1.50)
- [ ] Splunk Web accessible (http://192.168.1.50:8000)
- [ ] Windows VM peut être pinguée (192.168.1.100)
- [ ] Script ransomware exécuté sans erreurs
- [ ] Fichiers .locked visibles sur Windows
- [ ] Logs visibles dans Splunk (index=main)
- [ ] Requêtes SPL retournent des résultats
- [ ] Alerte C2 crée avec succès

---

## 🎓 PROCHAINES ÉTAPES

Une fois le lab fonctionnel:

1. **Analyser plus profondément** les logs
2. **Créer un rapport d'incident** (utiliser 04_RAPPORT_INCIDENT_TEMPLATE.md)
3. **Proposer des règles de mitigation**
4. **Étendre le lab** à d'autres scénarios (lateral movement, data exfiltration)
5. **Documentent ton travail** pour portfolio

---

**Durée Estimée:** 2-3 heures (première fois)  
**Difficulté:** 🟠 Intermédiaire  
**Support:** Slack #soc-lab ou documentation Splunk

Good luck! 🚀
