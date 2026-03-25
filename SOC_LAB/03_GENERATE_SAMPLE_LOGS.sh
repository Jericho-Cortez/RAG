#!/bin/bash
# ╔════════════════════════════════════════════════════════════════╗
# ║   GÉNÉRATEUR DE LOGS RÉALISTES - Linux/Windows              ║
# ║   À exécuter sur server Linux pour peupler Splunk             ║
# ╚════════════════════════════════════════════════════════════════╝

# Usage: bash generate_sample_logs.sh

set -e

LOGS_DIR="./sample_logs"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
C2_IP="203.0.113.45"
TARGET_USER="employee"

mkdir -p "$LOGS_DIR"

echo "[*] Génération des logs d'exemple..."

# ════════════════════════════════════════════════════════════════
# 1️⃣  WINDOWS SECURITY EVENT LOG (simul.)
# ════════════════════════════════════════════════════════════════

cat > "$LOGS_DIR/windows_security_events.csv" << 'EOF'
TimeCreated,EventID,EventType,ProcessName,CommandLine,ParentProcessName,User
2026-03-13T14:32:15Z,4688,ProcessCreate,powershell.exe,powershell.exe -NoProfile -WindowStyle Hidden,explorer.exe,CORP\employee
2026-03-13T14:32:16Z,4688,ProcessCreate,cmd.exe,cmd.exe /c timeout 1,powershell.exe,CORP\employee
2026-03-13T14:32:17Z,4658,FileDelete,SYSTEM,N/A,N/A,SYSTEM
2026-03-13T14:32:18Z,4658,FileCreate,SYSTEM,report_financier_2026.docx.locked,N/A,SYSTEM
2026-03-13T14:32:19Z,4658,FileCreate,SYSTEM,donnees_clients.xlsx.locked,N/A,SYSTEM
2026-03-13T14:32:20Z,4657,RegistrySet,HKCU\Software\Microsoft\Windows\CurrentVersion\Run,.ransomware_persistence,C:\Windows\Temp\recovery.exe,CORP\employee
2026-03-13T14:32:21Z,5156,NetworkConnection,svchost.exe,(null),powershell.exe,SYSTEM
2026-03-13T14:32:22Z,5156,NetworkConnection,OUT,203.0.113.45,443,192.168.1.100,SYSTEM
EOF

echo "✅ Fichier créé: windows_security_events.csv"

# ════════════════════════════════════════════════════════════════
# 2️⃣  LINUX AUTH LOG
# ════════════════════════════════════════════════════════════════

cat > "$LOGS_DIR/auth.log" << EOF
Mar 13 14:32:15 siem-server sshd[1234]: Invalid user employee from 192.168.1.100
Mar 13 14:32:16 siem-server sshd[1235]: Accepted publickey for employee from 192.168.1.100 port 12345 ssh2
Mar 13 14:32:17 siem-server sudo: employee : TTY=pts/0 ; PWD=/home/employee ; USER=root ; COMMAND=/bin/bash
Mar 13 14:32:18 siem-server kernel: audit type=EXECVE msg=audit(1615641138.234:567):  argc=3 a0="/usr/bin/nc" a1="-l" a2="8888"
EOF

echo "✅ Fichier créé: auth.log"

# ════════════════════════════════════════════════════════════════
# 3️⃣  FIREWALL LOG (iptables/ufw)
# ════════════════════════════════════════════════════════════════

cat > "$LOGS_DIR/firewall.log" << EOF
Mar 13 14:32:21 firewall kernel: UFW BLOCK IN=eth0 OUT= MAC=00:0a:0b:0c:0d:0e SRC=203.0.113.45 DST=192.168.1.100 PROTO=TCP SPT=12345 DPT=443 WINDOW=1024 RES=0x00 SYN
Mar 13 14:32:22 firewall kernel: UFW ALLOW OUT=eth0 IN= SRC=192.168.1.100 DST=203.0.113.45 PROTO=TCP SPT=54321 DPT=443 WINDOW=2048 RES=0x00 ACK
Mar 13 14:32:23 firewall kernel: UFW ALLOW OUT=eth0 IN= SRC=192.168.1.100 DST=203.0.113.45 PROTO=TCP SPT=54321 DPT=443 LEN=1234 WINDOW=2048 RES=0x00 PSH,ACK
EOF

echo "✅ Fichier créé: firewall.log"

# ════════════════════════════════════════════════════════════════
# 4️⃣  DNS QUERY LOG
# ════════════════════════════════════════════════════════════════

cat > "$LOGS_DIR/dns.log" << EOF
[192.168.1.100] query: c2server.ru A 
[192.168.1.100] query: malware.tk A 
[192.168.1.100] query: recovery-files.xyz A 
[192.168.1.100] query: exfil-data.cc A 
EOF

echo "✅ Fichier créé: dns.log"

# ════════════════════════════════════════════════════════════════
# 5️⃣  SYSMON LOG (Windows only - simulation)
# ════════════════════════════════════════════════════════════════

cat > "$LOGS_DIR/sysmon_events.csv" << 'EOF'
EventID,ParentImage,ParentCommandLine,Image,CommandLine,TargetFilename,Destination,DestinationPort,User
1,C:\Windows\explorer.exe,explorer.exe,C:\Windows\System32\powershell.exe,powershell.exe -NoProfile -WindowStyle Hidden,N/A,N/A,N/A,CORP\employee
1,C:\Windows\System32\powershell.exe,PowerShell,C:\Windows\System32\cmd.exe,cmd.exe /c,N/A,N/A,N/A,CORP\employee
11,C:\Windows\System32\cmd.exe,cmd,N/A,N/A,C:\Users\employee\Documents\report_financier_2026.docx.locked,N/A,N/A,CORP\employee
11,C:\Windows\System32\cmd.exe,cmd,N/A,N/A,C:\Users\employee\Documents\donnees_clients.xlsx.locked,N/A,N/A,CORP\employee
3,C:\Windows\System32\svchost.exe,svchost.exe,N/A,N/A,N/A,203.0.113.45,443,SYSTEM
EOF

echo "✅ Fichier créé: sysmon_events.csv"

# ════════════════════════════════════════════════════════════════
# 6️⃣  PCAP SIM (hex dump for network traffic)
# ════════════════════════════════════════════════════════════════

cat > "$LOGS_DIR/network_c2_traffic.txt" << 'EOF'
# Simulation du trafic C2 (Protocol Analysis)
# Source: 192.168.1.100:54321
# Destination: 203.0.113.45:443
# Protocol: TLS/SSL (encrypted)
# Payload (hex): 160303007a010076030366b4d...

Packet 1: TLS Client Hello
  - Client IP: 192.168.1.100
  - Server IP: 203.0.113.45
  - Port: 443
  - TLS Version: 1.2
  - Cipher Suites: [TLS_RSA_WITH_AES_128_CBC_SHA, ...]

Packet 2: TLS Server Hello
  - Server IP: 203.0.113.45
  - Client IP: 192.168.1.100
  - TLS Version: 1.2
  - Certificate: CN=c2server.ru

Packet 3-10: Encrypted Data Exchange
  - Application Data (encrypted ransomware C2 commands)
  
EOF

echo "✅ Fichier créé: network_c2_traffic.txt"

# ════════════════════════════════════════════════════════════════
# 7️⃣  FILE INTEGRITY MONITORING (FIM) LOG
# ════════════════════════════════════════════════════════════════

cat > "$LOGS_DIR/fim_changes.csv" << 'EOF'
Timestamp,File_Path,Event_Type,Old_Hash_MD5,New_Hash_MD5,Old_Size,New_Size,User
2026-03-13T14:32:17Z,/home/employee/Documents/report.docx,MODIFIED,a1b2c3d4e5f6,f6e5d4c3b2a1,1024000,1024,root
2026-03-13T14:32:18Z,/home/employee/Documents/report.docx,RENAMED_ENCRYPTED,f6e5d4c3b2a1,f6e5d4c3b2a1,1024,1024,root
2026-03-13T14:32:19Z,/home/employee/Documents/clients.xlsx,MODIFIED,b2c3d4e5f6a1,a1f6e5d4c3b2,512000,512,root
2026-03-13T14:32:20Z,/home/employee/Documents/clients.xlsx.locked,CREATED,NEW,a1f6e5d4c3b2,0,512,root
EOF

echo "✅ Fichier créé: fim_changes.csv"

# ════════════════════════════════════════════════════════════════
# 8️⃣  SUMMARY - Afficher le contenu
# ════════════════════════════════════════════════════════════════

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║               📊 LOGS GÉNÉRÉS AVEC SUCCÈS                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
ls -lh "$LOGS_DIR"
echo ""
echo "✅ À importer dans Splunk:"
echo "   1. Data Inputs > Upload Files > $LOGS_DIR/*.csv"
echo "   2. Source type: auto | Index: main"
echo "   3. Exécuter les requêtes: 02_SPLUNK_QUERIES.txt"
echo ""
