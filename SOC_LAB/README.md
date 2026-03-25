# 🎓 LAB SOC ANALYST - INVESTIGATION RANSOMWARE

```
██████╗  █████╗ ███╗   ██╗███████╗ ██████╗ ███╗   ███╗███████╗
██╔════╝ ██╔══██╗████╗  ██║██╔════╝██╔═══██╗████╗ ████║██╔════╝
██║  ███╗███████║██╔██╗ ██║███████╗██║   ██║██╔████╔██║███████╗
██║   ██║██╔══██║██║╚██╗██║╚════██║██║   ██║██║╚██╔╝██║╚════██║
╚██████╔╝██║  ██║██║ ╚████║███████║╚██████╔╝██║ ╚═╝ ██║███████║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝
```

## 📜 Vue d'Ensemble

Ce lab te permet de **simuler une infection ransomware** et de pratiquer l'investigation SOC:
- 🎯 Analyser les logs avec **Splunk**
- 🔍 Identifier les IOCs (Indicators of Compromise)
- 📊 Reconstuire la timeline d'attaque
- 📋 Rédiger un rapport d'incident professionnel

**Objectif Pédagogique:** Appliquer les concepts de centralisation de logs + analyse SOC sur un cas réaliste.

---

## 📁 STRUCTURE DES FICHIERS

```
SOC_LAB/
├── 01_SCRIPTS_RANSOMWARE.ps1          ← Script simulation attaque (PowerShell)
├── 02_SPLUNK_QUERIES.txt              ← Requêtes SPL prêtes-à-copier
├── 03_GENERATE_SAMPLE_LOGS.sh         ← Générateur données de test
├── 04_RAPPORT_INCIDENT_TEMPLATE.md    ← Template rapport SOC
├── 05_GUIDE_INSTALLATION_COMPLET.md   ← This guide
└── README.md                          ← You are here
```

---

## 🚀 DÉMARRAGE RAPIDE (30 min)

### Pour IMPATIENTS (TL;DR)

#### Étape 1: Installer les VMs (10 min)
```bash
# Créer 2 VMs dans VirtualBox:
1. Rocky Linux 9 (4 vCPU, 8 GB RAM, 100 GB disk) → SIEM Server
2. Windows 10 (2 vCPU, 4 GB RAM, 50 GB disk) → Workstation

# Réseau: Bridged (même broadcast domain)
```

#### Étape 2: Installer Splunk (5 min)
```bash
# Sur Rocky:
cd /tmp
wget https://www.splunk.com/...  # Splunk installer
tar -xzf splunk-*.tgz -C /opt
sudo -u splunk /opt/splunk/bin/splunk start --accept-license [entrer mdp]

# Ouvrir: http://192.168.1.50:8000
# Login: admin / [ton mdp]
```

#### Étape 3: Exécuter la Simulation (5 min)
```powershell
# RUN AS ADMIN sur Windows:
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser -Force
& C:\Users\employee\01_SCRIPTS_RANSOMWARE.ps1

# Les logs sont générés automatiquement ✓
```

#### Étape 4: Analyser dans Splunk (10 min)
```spl
# Copier-coller dans Splunk Search:
index=main sourcetype="WinEventLog:Security" EventCode=5156 dest_ip="203.0.113.45"

# Voir les résultats C2 callback ✓
```

---

## 📋 FICHIERS DÉTAILLÉS

### 📌 01_SCRIPTS_RANSOMWARE.ps1
**Qu'est-ce que c'est?** Script PowerShell qui simule une infection ransomware  
**Qu'est-ce qu'il fait?**
1. Génère une chaîne de processus: powershell → cmd.exe
2. Crée des fichiers ".locked" (simulation chiffrage)
3. Modifie les permissions NTFS
4. Simule une connexion C2 vers 203.0.113.45:443
5. Crée une clé de persistence dans le registre

**Résultat:** Tous les événements sont enregistrés dans Event Viewer et envoyés à Splunk

**Comment l'utiliser?**
```powershell
# Windows VM - RUN AS ADMIN:
Set-ExecutionPolicy Bypass [-Scope CurrentUser] -Force
& C:\path\to\01_SCRIPTS_RANSOMWARE.ps1

# Optionnel - Spécifier la cible:
& C:\path\to\01_SCRIPTS_RANSOMWARE.ps1 -C2_IP "203.0.113.45" -C2_PORT 443 -TARGET_DIR "$env:USERPROFILE\Documents"
```

**Évite:** Ne pas exécuter sur une vrai machine production! 🔴

---

### 📌 02_SPLUNK_QUERIES.txt
**Qu'est-ce que c'est?** 10 requêtes SPL (Splunk Processing Language) prêtes-à-copier  
**Qu'est-ce qu'elles cherchent?**
1. Chaîne de processus (powershell → cmd) 
2. Fichiers .locked (ransomware markers)
3. Connexion C2 (203.0.113.45:443)
4. Timeline complète d'attaque
5. Extraction des IOCs
6. Alerte C2

**Comment les utiliser?**
```
1. Ouvrir Splunk: http://192.168.1.50:8000
2. Aller à: Search & Reporting > Search
3. Copy-paste une requête
4. Click: Search
5. Voir les résultats!
```

**Exemple Query:**
```spl
# Détecter la connexion C2
index=main sourcetype="WinEventLog:Security" EventCode=5156 
| search dest_ip="203.0.113.45" dest_port=443 
| table TimeCreated, src_ip, dest_ip, dest_port
```

---

### 📌 03_GENERATE_SAMPLE_LOGS.sh
**Qu'est-ce que c'est?** Script Bash qui génère des données de logs d'exemple  
**Qu'est-ce qu'il génère?**
- Windows Security Events (CSV)
- Linux auth.log
- Firewall rules
- DNS queries
- Sysmon events
- Network PCAP data
- File Integrity Monitoring (FIM)

**Comment l'utiliser?**
```bash
# Rocky VM:
bash generate_sample_logs.sh

# Crée le dossier:
sample_logs/
├── windows_security_events.csv
├── auth.log
├── firewall.log
├── dns.log
├── sysmon_events.csv
├── network_c2_traffic.txt
└── fim_changes.csv

# Importer dans Splunk:
# Data Inputs > Upload Files > sample_logs/*.csv
```

---

### 📌 04_RAPPORT_INCIDENT_TEMPLATE.md
**Qu'est-ce que c'est?** Template professionnel de rapport d'incident SOC  
**Structure:**
1. Résumé exécutif
2. Chronologie d'attaque (Timeline)
3. Indicateurs de compromission (IOCs)
4. Analyse technique (MITRE ATT&CK)
5. Impact & périmètre
6. Requêtes Splunk utilisées
7. Actions de réponse (Inmédiate, CT, LT)
8. Règles de détection proposées
9. Recommandations de mitigation
10. Conclusion

**Comment l'utiliser?**
1. Faire l'investigation dans Splunk
2. Remplir le template avec tes résultats
3. Ajouter tes conclusions SOC
4. Envoyer au CISO/Management

**Résultat:** Rapport prêt pour la vraie production! 📊

---

### 📌 05_GUIDE_INSTALLATION_COMPLET.md
**Qu'est-ce que c'est?** Guide détaillé étape-par-étape de 2-3 heures  
**Couvre:**
1. Setup Hardware/VMs
2. Installation Rocky Linux + Splunk
3. Configuration rsyslog
4. Windows Event Forwarder setup
5. Lancer la simulation
6. Analyser dans Splunk
7. Troubleshooting courant
8. Validation complète

**Pour qui?** Ceux qui font le lab pour la première fois

---

## 🎯 WORKFLOW COMPLET (3-4 heures)

### Phase 1: SETUP (1-2 heures)
- [ ] Créer les 2 VMs (Rocky + Windows)
- [ ] Installer Splunk sur Rocky
- [ ] Configurer rsyslog
- [ ] Tester la connectivité
- **Validation:** Splunk web accessible, rsyslog écoute port 514

### Phase 2: SIMULATION (30 min)
- [ ] Copier 01_SCRIPTS_RANSOMWARE.ps1 sur Windows
- [ ] Exécuter le script PowerShell
- [ ] Vérifier les fichiers .locked
- **Validation:** Fichiers visibles dans Documents/, logs dans Event Viewer

### Phase 3: INVESTIGATION (1-1.5 heures)
- [ ] Ouvrir Splunk Search
- [ ] Exécuter les 10 requêtes (02_SPLUNK_QUERIES.txt)
- [ ] Extraire les IOCs
- [ ] Reconstruire la timeline
- **Validation:** Tous les événements retrouvés, IOCs identifiés

### Phase 4: REPORTING (30 min)
- [ ] Utiliser 04_RAPPORT_INCIDENT_TEMPLATE.md
- [ ] Remplir avec les résultats Splunk
- [ ] Ajouter les recommandations
- **Résultat:** Rapport d'incident complet

---

## 🛠️ TECHNOS UTILISÉES

| Tech | Version | Rôle |
|------|---------|------|
| **Rocky Linux** | 9 | OS Serveur SIEM |
| **Splunk** | Free Edition | SIEM central |
| **rsyslog** | Standard | Log forwarder |
| **Windows 10** | Latest | Workstation attaquée |
| **PowerShell** | 5.1+ | Script de simulation |
| **Sysmon** | Latest (opcional) | Event logging avancé |

---

## 📊 LIVRABLES ATTENDUS

Après cette session, tu auras:

1. ✅ **Lab SOC Fonctionnel** - Splunk + Rocky + Windows
2. ✅ **Rapport d'Incident** - Professionnel et détaillé
3. ✅ **IOCs Identifiés** - IPs, fichiers, processus
4. ✅ **Requêtes Splunk** - Réutilisables pour d'autres cas
5. ✅ **Cas d'Usage Réaliste** - Pour ton portfolio
6. ✅ **Compétences SOC** - Prêt pour entreti...
   - Analyse de logs centralisés
   - Corrélation d'événements
   - Identification d'IoCs
   - Réponse aux incidents

---

## 🎓 PROCHAINES ÉTAPES (BONUS)

Une fois le lab maîtrisé:

### Extension 1: DETECTION RULES
Écrire des règles Yara/SIGMA pour détecter automatiquement cette attaque

### Extension 2: ALERTING
Configurer alertes email/Slack quand C2 détecté

### Extension 3: THREAT HUNTING
Chercher les AUTRES machines du réseau infectées

### Extension 4: INCIDENT RESPONSE
Pratiquer l'isolation, la containment, la remediation

### Extension 5: ADVANCED LAB
- Ajouter lateral movement (Pass-the-Hash)
- Ajouter data exfiltration
- Ajouter persistence mechanisms
- Implémenter defence evasion

---

## 🆘 HELP & TROUBLESHOOTING

### Erreur: "No data in Splunk"
→ Voir section Troubleshooting dans 05_GUIDE_INSTALLATION_COMPLET.md

### Erreur: "Cannot connect to Splunk"
→ `ssh ubuntu@192.168.1.50`  
→ `sudo systemctl status splunk`  
→ Redémarrer si needed

### Erreur Script: "Access Denied"
→ RUN AS ADMIN sur Windows  
→ `Set-ExecutionPolicy Bypass`

### VMs trop Lentes?
→ Augmenter RAM/vCPU dans VirtualBox settings

---

## 📝 NOTES IMPORTANTES

### Security
- 🔴 **NE PAS exécuter sur production**
- 🔴 **NE PAS utiliser cette IP/Port en vrai** (203.0.113.45 est réservée test)
- ✅ Utiliser des VMs isolées + reseau privé

### Performance
- Splunk Free = 500 MB/jour de data. Assez pour ce lab.
- La première indexation est lente (~5 min). Patience!

### Résultats
- Les logs mettent 10-30 sec pour apparaître dans Splunk (délai indexation)
- Si pas visible immédiatement, attendre + rafraîchir

---

## 📚 RESSOURCES ADDITIONNELLES

- **Splunk Docs:** https://docs.splunk.com
- **Rocky Linux:** https://rockylinux.org
- **SPL Tutorial:** https://www.splunk.com/en_us/training.html
- **MITRE ATT&CK:** https://attack.mitre.org
- **Windows Event IDs:** https://www.myeventlogs.com/

---

## ✨ BON COURAGE!

C'est un super projet pour ton portfolio SOC Analyst. Les recruteurs ADORENT voir:
- ✅ Labs pratiques
- ✅ Rapports d'incident
- ✅ Analyse Splunk

**Prêt à commencer?** → Voir **05_GUIDE_INSTALLATION_COMPLET.md**

---

**PS:** Garde ce README à portée de main pendant la session. Reviens ici si besoin de clarity sur les fichiers!

Good luck! 🚀🎯
