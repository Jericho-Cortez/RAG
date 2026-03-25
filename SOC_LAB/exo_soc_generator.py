# ╔════════════════════════════════════════════════════════════════╗
# ║   GÉNÉRATEUR D'EXERCICES SOC - Apprentissage Métier            ║
# ║   Génère des exercices différents basés sur SOC_LAB             ║
# ╚════════════════════════════════════════════════════════════════╝

import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# NIVEAU DE DIFFICULTÉ
DIFFICULTY_LEVELS = {
    "Débutant": 1,
    "Intermédiaire": 2,
    "Avancé": 3
}

# ════════════════════════════════════════════════════════════════
# EXERCICES - RANSOMWARE SCENARIOS
# ════════════════════════════════════════════════════════════════

RANSOMWARE_EXERCISES = [
    {
        "id": "RANSOMWARE_001",
        "title": "🔴 Detection Ransomware - Chaîne de Processus",
        "difficulty": "Débutant",
        "scenario": """
╔════════════════════════════════════════════════════════════════╗
║                      🚨 CONTEXT INCIDENT 🚨                  ║
╚════════════════════════════════════════════════════════════════╝

Date: 2026-03-16 | Heure: 14:32:15
Machine: DESKTOP-JOHN-01 (Windows 10 - Utilisateur: john.doe)

📢 ALERTE DU CISO:
"Nous venons de recevoir un email d'une user: 'Tous mes fichiers sont .locked!'
Les fichiers dans Documents, Desktop, et Downloads ont tous l'extension .locked
Exemple: presentation.pptx → presentation.pptx.locked"

📊 DONNÉES DISPONIBLES:
- Event Viewer: Logs Windows d'authentification et processus
- Splunk: Tous les logs système indexés
- Process Explorer: Processus actuels (mais le malware a déjà supprimé les traces)
- File Integrity Monitor (FIM): Historique des fichiers modifiés

LA CHAÎNE DE PROCESSUS SUSPECTE:
  explorer.exe (PID: 4156)
    ↓ (a lancé)
  powershell.exe (PID: 5832) À 14:32:30
    ↓ (a lancé)
  cmd.exe (PID: 6204) À 14:32:35
    ↓ (a lancé)
  ransomware.exe (PID: 7391) À 14:32:40 ← MALWARE!
    ↓ (a chiffré)
  *.locked (Tous les fichiers!) À 14:32:45 et après

ℹ️ REMARQUES IMPORTANTES:
- Normalement explorer.exe NE lance JAMAIS powershell
- Normalement powershell NE lance JAMAIS cmd directement
- Cette chaîne = TRÈS ANORMALE = RED FLAG
- ransomware.exe apparaît dans les fichiers chiffrés
        """,
        "tools": ["Splunk", "Event Viewer", "Windows Process Hacker"],
        "learning_terms": [
            "Process Chain (Chaîne de processus): Séquence parent → child → grandchild",
            "Parent Process (Processus parent): Qui a lancé ce processus?",
            "Child Process (Processus enfant): Qui ce processus a-t-il lancé?",
            "EventCode 4688 (Process Creation): Windows enregistre quand un process est créé",
            "ProcessName vs ParentProcessName: Deux colonnes DIFFÉRENTES dans Splunk",
            "Command Injection: Technique: lancer des commandes cache via cmd/powershell"
        ],
        "expected_output": """
Résultat Splunk attendu:
┌─────────────┬──────────────────────┬──────────────┬──────────┐
│ TimeCreated │ ProcessName          │ ParentName   │ PID      │
├─────────────┼──────────────────────┼──────────────┼──────────┤
│ 14:32:30    │ powershell.exe       │ explorer.exe │ 5832     │
│ 14:32:35    │ cmd.exe              │ powershell   │ 6204     │
│ 14:32:40    │ ransomware.exe       │ cmd.exe      │ 7391     ⚠️ |
│ 14:32:45+   │ (fichiers chiffrés)  │ ransomware   │ 7391     │
└─────────────┴──────────────────────┴──────────────┴──────────┘

✅ RÉPONSE ET ANALYSE:
- Root Cause: explorer.exe a été compromis
- Timeline: 15 secondes du click à la première fichier chiffré
- Détection: La chaîne explorer→powershell→cmd→ransomware est TRÈS spécifique
- Impact: Tous les fichiers accessibles par l'utilisateur john.doe sont chiffrés
        """,
        "hints": [
            "💡 EventCode 4688 = Windows dit 'un nouveau processus est créé'",
            "💡 Dans Splunk, utilise 'ParentProcessName' pour voir qui a lancé quoi",
            "💡 La requête doit utiliser 'transaction' pour suivre les relations parent-child",
            "💡 explorer→powershell = TRÈS ANORMAL (l'utilisateur n'a rien cliqué dans pwsh)",
            "💡 Une chaîne 4+ processus = Signature forte pour détecter le malware"
        ]
    },
    {
        "id": "RANSOMWARE_002",
        "title": "🟠 Detection Ransomware - Fichiers Chiffrés",
        "difficulty": "Débutant",
        "scenario": """
╔════════════════════════════════════════════════════════════════╗
║                      🚨 CONTEXT INCIDENT 🚨                  ║
╚════════════════════════════════════════════════════════════════╝

Date: 2026-03-16 | Heure: 15:00:00
Machine: PROD-FILESERVER-02 (Windows Server 2019)

📢 ALERTE UTILISATEUR:
"Je ne peux plus ouvrir mes fichiers! Tout est devenu .locked!"

📊 CE QUE NOUS SAVONS:
- File Integrity Monitoring (FIM) suit les fichiers
- Les fichiers .locked VENAIENT D'APPARAÎTRE entre 14:32:40 et 14:33:15
- Extension .locked = Ransomware signature TRÈS spécifique

📋 DONNÉES DISPONIBLES DANS SPLUNK:
- EventCode 4658 = Un fichier a été SUPPRIMÉ (ou renommé par malware)
- EventCode 4663 = Un fichier a été CRÉÉ (ou renommé en .locked)
- Object_Name = Chemin du fichier (ex: C:\\Users\\john\\Documents\\presentation.pptx.locked)
- TimeCreated = Quand ça s'est passé exactement

ℹ️ CONTEXTE IMPORTANT:
Normalement, on voit ~5-10 fichiers modifiés par minute.
Aujourd'hui à 14:32:45, on a VU:
  → 200 fichiers .locked EN SEULEMENT 30 SECONDES! 🚨
  → Tous dans C:\\Users\\john\\Documents et C:\\Users\\john\\Desktop
  → ZÉRO fichiers pareils après 14:33:15 (malware s'est ARRÊTÉ)

TA MISSION:
1. Écrire une requête Splunk pour COMPTER les fichiers .locked
2. Trouver EXACTEMENT QUAND ça a commencé (Zero-Hour)
3. Calculer le TEMPS TOTAL (TTC = Time To Compromise)
4. Identifier le RÉPERTOIRE CIBLE (où les fichiers ont été chiffrés)
5. Estimer la VITESSE du ransomware (fichiers/seconde)
        """,
        "tools": ["Splunk", "File Integrity Monitoring (FIM)", "Windows Event Logs", "NTFS Explorer"],
        "learning_terms": [
            "File Integrity Monitoring (FIM): Outil qui trace les changements de fichiers",
            "EventCode 4658 (Delete File): Windows enregistre chaque suppression",
            "EventCode 4663 (Rename File): Windows enregistre chaque renommage",
            "Ransomware Marker (.locked): Extension = Signature du malware",
            "Zero-Hour: Le moment exact où l'infection a COMMENCÉ",
            "Time To Compromise (TTC): Combien de temps avant la première IOC",
            "Encryption Timestamp: Quand le chiffrage a commencé ET terminé"
        ],
        "expected_output": """
Résultat Splunk attendu:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 STATISTIQUES:
  Total fichiers .locked: 247 fichiers ✅
  Zero-Hour: 2026-03-16 14:32:45 (EXACT!)
  End Time: 2026-03-16 14:33:12
  Duration: 27 secondes
  Vitesse: 9.1 fichiers/seconde ⚠️ TRES RAPIDE!

📍 RÉPERTOIRES CIBLES:
  • C:\\Users\\john\\Documents      → 115 fichiers (.docx, .xlsx, .pptx)
  • C:\\Users\\john\\Desktop        → 89 fichiers
  • C:\\Users\\john\\Downloads      → 43 fichiers

📈 TIMELINE DÉTAILLÉE:
  14:32:45 → +15 fichiers
  14:32:50 → +45 fichiers (accélération!)
  14:32:55 → +87 fichiers (pic)
  14:33:00 → +67 fichiers
  14:33:05 → +33 fichiers
  14:33:10 → +0 fichiers (malware s'arrête)
  14:33:12 → STOP total

✅ ANALYSE:
- Pattern = Ransomware confirmé (pas un accident utilisateur)
- 27 secondes = TTC TRÈS court
- Les fichiers personnels SEULEMENT ciblés (stratégie)
- Pas les fichiers système (le malware était intelligent)
        """,
        "hints": [
            "💡 stats count as = Pour compter le nombre de fichiers",
            "💡 earliest(_time) et latest(_time) = Pour trouver le premier et dernier",
            "💡 timechart count by Object_Name = Pour voir la TIMELINE minute par minute",
            "💡 eval Duration = latest(_time) - earliest(_time) = Calcule en secondes",
            "💡 Cherche SEULEMENT les fichiers *.locked (pas tous les changements)"
        ]
    },
    {
        "id": "RANSOMWARE_003",
        "title": "🔵 Detection Ransomware - C2 Callback",
        "difficulty": "Débutant",
        "scenario": """
╔════════════════════════════════════════════════════════════════╗
║                      🚨 CONTEXT INCIDENT 🚨                  ║
╚════════════════════════════════════════════════════════════════╝

Date: 2026-03-16 | Heure: 14:33:30
Machine: DESKTOP-JOHN-01

📢 ALERTE FIRE WALL:
"Connexion suspecte détectée vers 203.0.113.45:443"

📊 CE QUE C'EST?
- 203.0.113.45 = IP suspecte (dans blockilst threat intel)
- Port 443 = HTTPS/SSL (CHIFFRÉ = malware communique en secret!)
- Le trafic est chiffré, on ne peut pas voir le contenu

⚠️ LE PROBLÈME:
"Est-ce vraiment une C2 (Command & Control)?"
Pourquoi? Parce que:
  • Plein de services légitimes = port 443 (Google, Microsoft, etc.)
  • Un utilisateur peut accidentellement visiter un site
  • Comment on SAIT que c'est le malware qui communique?

LA RÉPONSE: LES PATTERNS!
- Les C2 = Callbacks RÉGULIERS (toutes les 30 secondes, chaque minute, etc.)
- Les navigateurs normaux = Trafic ALÉATOIRE (bursty, irrégulier)
- Les C2 = Processus SUSPECT qui communique
  Exemple: ransomware.exe, whoami.exe, powershell.exe

📋 DONNÉES DISPONIBLES DANS SPLUNK:
- EventCode 5156 (Network Connection) = Windows enregistre TOUTES les connexions
- Champs: src_ip, dest_ip, dest_port, ProcessName, TimeCreated
- Pour cet incident:
  • 203.0.113.45 está dans notre blockist threat intel
  • ProcessName = ransomware.exe (=très suspicieux!)
  • Connexions répétées aux mêmes heures: 14:33:45, 14:34:45, 14:35:45...

TA MISSION:
1. Trouver TOUTES les connexions vers 203.0.113.45
2. Compter le nombre de connexions (1? 100?)
3. Vérifier si c'est un PATTERN RÉGULIER (beaconing?)
4. Identifier le PROCESSUS responsable (qui communique?)
5. Calculer la FRÉQUENCE (chaque N secondes?)
6. DÉCIDER: C2 confirmé? Oui/Non? POURQUOI?
        """,
        "tools": ["Splunk", "Firewall Logs", "Network Traffic Analysis", "Threat Intel"],
        "learning_terms": [
            "C2 Server (Command & Control): Serveur qui contrôle le malware à distance",
            "EventCode 5156 (Network Connection): Windows enregistre les connexions",
            "Port 443 (HTTPS/SSL): Port de communication chiffrée",
            "Beaconing Pattern: Connexions RÉGULIÈRES (toutes les N secondes)",
            "IOC (Indicator of Compromise): IP/domaine/hash qui = attaque confirmée",
            "Threat Intel: Base de données de IP/domaines malveillants connus"
        ],
        "expected_output": """
Résultat Splunk attendu:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 CONNEXIONS TROUVÉES:
  Dest IP: 203.0.113.45
  Dest Port: 443
  Total Connections: 8 connexions ⚠️
  Timeframe: 14:33:45 à 14:39:15

📈 PATTERN D'APPELS (BEACONING):
  14:33:45 (0 sec)    ← DEBUT C2
  14:34:45 (+60 sec)  ← Callback 1
  14:35:45 (+60 sec)  ← Callback 2
  14:36:45 (+60 sec)  ← Callback 3
  ... [pattern répète exactement toutes les 60 secondes]
  14:39:15 (END)

🔍 PROCESSUS COMMUNIQUANT:
  ProcessName: ransomware.exe (!) ← TRES MAUVAIS!
  Parent: cmd.exe
  Command Line: ransomware.exe -C2 203.0.113.45

📊 ANALYSE DE FRÉQUENCE:
  Période: 60 secondes (EXACTEMENT!)
  Count: 8 connexions en 5 minutes 30 secondes
  Pattern: TRÈS RÉGULIER = C2 CLASSIC BEACONING

✅ CONCLUSION:
▓▓▓▓▓ C2 COMMUNICATION CONFIRMÉE! ▓▓▓▓▓

Preuves:
  ✓ Processus suspect (ransomware.exe)
  ✓ Callbacks réguliers toutes les 60 secondes
  ✓ IP dans threat intel (malveillant)
  ✓ Port 443 (communication chiffrée)
  ✓ Coincide EXACTEMENT avec le timing d'infection (14:32-14:33)

⚡ ACTION RECOMMANDÉE:
  1. Isoler DESKTOP-JOHN-01 du réseau IMMÉDIATEMENT
  2. Bloquer 203.0.113.45 au firewall
  3. Checker d'autres machiges qui communiquent avec 203.0.113.45
  4. Collecter la mémoire de DESKTOP-JOHN-01 pour analyse
        """,
        "hints": [
            "💡 EventCode 5156 = Core logging pour les connexions réseau",
            "💡 stats count, values(TimeCreated) = Compte ET vois les temps exacts",
            "💡 timechart count by TimeCreated = Visualize le pattern",
            "💡 Beaconing = Connexions à intervalle RÉGULIER (60s, 30s, 5m...)",
            "💡 ProcessName = ransomware.exe EST le malware (pas explorer, pas svchost)"
        ]
    }
]

# ════════════════════════════════════════════════════════════════
# EXERCICES - LATERAL MOVEMENT
# ════════════════════════════════════════════════════════════════

LATERAL_MOVEMENT_EXERCISES = [
    {
        "id": "LATERAL_001",
        "title": "🟣 Détection Pass-the-Hash",
        "difficulty": "Intermédiaire",
        "scenario": """
Un attaquant compromet une workstation.
Il essaie ensuite de se connecter à d'autres serveurs avec 
le HASH du compte d'administrateur (sans le mot de passe).

Données:
- EventCode 4624 = Logon attempt
- EventCode 4625 = Logon failed
- Logon_Type=3 = Network logon (e.g., via NTLM)

Ta mission:
1. Détecter les tentatives d'authentification Network depuis une workstation
2. Compter les échechs / succès
3. Identifier si c'est un pattern d'attaque (brute force? spray?)
4. Trouver les serveurs CIBLES (lateral movement réseau)
        """,
        "tools": ["Splunk", "Windows Security Log", "NTLM Auth", "Mimikatz"],
        "splunk_query": """
index=main (EventCode=4624 OR EventCode=4625) Logon_Type=3
| stats count(EventCode=4624) as "Success", 
  count(EventCode=4625) as "Failed",
  values(ComputerName) as "Targets"
| eval Overall_Success_Rate = Success / (Success + Failed)
        """,
        "learning_terms": [
            "Pass-the-Hash (PtH)",
            "NTLM Authentication",
            "EventCode 4624 (Logon Success)",
            "EventCode 4625 (Logon Failed)",
            "Logon_Type=3 (Network Logon)",
            "Lateral Movement (Se déplacer dans le réseau)"
        ],
        "expected_output": "30 tentatives Network depuis 192.168.1.100 vers 5 serveurs (DC, FileServer, etc.)",
        "hints": [
            "💡 PtH = Même hash = Même failure rate BASSE",
            "💡 Logon_Type=3 = Network = Pass-the-Hash suspect",
            "💡 Si 29/30 échouent = Attaquant teste les serveurs"
        ]
    }
]

# ════════════════════════════════════════════════════════════════
# EXERCICES - THREAT HUNTING
# ════════════════════════════════════════════════════════════════

THREAT_HUNTING_EXERCISES = [
    {
        "id": "HUNTING_001",
        "title": "🕵️ Threat Hunting - Chercher les Outliers",
        "difficulty": "Avancé",
        "scenario": """
Tu es un Threat Hunter. Le CISO te dit:
"On ne sait pas si on a d'autres infections. Cherche les anomalies."

Données:
- 10 000 workstations (normale = 100-500 logs/jour)
- 1 machine: 5000 logs/jour (7x la normale!)
- Processus inhabituels chez cette machine?

Ta mission (Threat Hunting):
1. Identifier les machines OUTLIERS (anomalies statistiques)
2. Pour chaque outlier, chercher les processus inhabituels
3. Comparer avec la baseline normale
4. Décider: Infection? Misconfiguration? Légitime?
        """,
        "tools": ["Splunk", "Stats & Analytics", "Baseline Analysis", "Anomaly Detection"],
        "splunk_query": """
index=main sourcetype="WinEventLog:Security"
| stats count as "Event_Count" by ComputerName
| eventstats avg(Event_Count) as "Avg", 
  stdev(Event_Count) as "Stdev"
| eval Outlier = if(Event_Count > (Avg + 3*Stdev), "YES", "NO")
| where Outlier="YES"
        """,
        "learning_terms": [
            "Outlier Detection (Détection d'anomalies)",
            "Baseline (Référence normale)",
            "Statistical Analysis (Moyenne, écart-type)",
            "Threat Hunting (Chasse aux menaces)",
            "Anomaly (Ce qui sort de la normale)"
        ],
        "expected_output": "Machine 'DESKTOP-INFECTED' = 5023 events (Outlier: YES)",
        "hints": [
            "💡 Normal range = Avg ± 3*StDev (statistique de base)",
            "💡 Outlier = potentiellement compromis",
            "💡 Cherche ensuite les processus inhabituels SUR ce pc"
        ]
    }
]

# ════════════════════════════════════════════════════════════════
# EXERCICES - INCIDENT RESPONSE
# ════════════════════════════════════════════════════════════════

INCIDENT_RESPONSE_EXERCISES = [
    {
        "id": "IR_001",
        "title": "🚨 Incident Response - Timeline Reconstruction",
        "difficulty": "Intermédiaire",
        "scenario": """
L'équipe fire.com a appelé: "Notre VP a reçu un email de phishing.
Il a clické. C'est quoi l'impact?"

Timeline Logs:
- 14:32:15 - Email arrive (Gateway log)
- 14:32:30 - Email ouvert par Jean (Outlook log)
- 14:32:45 - Téléchargement fichier "invoice.docx" (Proxy log)
- 14:33:00 - Malware détecté (Antivirus: ransomware.exe)
- 14:33:15 - C2 Callback (Firewall: 203.0.113.45)
- 14:33:30 - Fichiers chiffrés (File Integrity log)

Ta mission (Incident Response):
1. Reconstruire la timeline EXACTE
2. Identifier le ZERO-HOUR (quand a commencé l'infection?)
3. Estimer le TTC (Time To Compromise)
4. Proposer les ACTIONS (containment immédiat)
        """,
        "tools": ["Splunk", "Timeline Analysis", "Email Gateway", "Proxy Logs"],
        "splunk_query": """
index=main ("Email Received" OR "Download" OR "Malware" OR "C2" OR "Encryption")
| sort + _time
| eval Time_Diff = _time - prev(_time)
| table _time, Event_Type, Time_Diff, ComputerName
        """,
        "learning_terms": [
            "Phishing (Email malveillant)",
            "Zero-Hour (Moment d'infection)",
            "Time To Compromise (TTC = délai infection)",
            "Incident Timeline (Chronologie)",
            "Containment (Isolement/Confinement)"
        ],
        "expected_output": "Zero-Hour @ 14:32:45 (Download) | TTC: 45 secondes | Action: Isoler ASAP",
        "hints": [
            "💡 Timeline = Ordre chronologique EXACT",
            "💡 Zero-Hour = quand compromise commencé (pas email)",
            "💡 TTC = du click à la première IOC compromise"
        ]
    }
]

# ════════════════════════════════════════════════════════════════
# EXERCICES - TOOLS & TERMINOLOGY
# ════════════════════════════════════════════════════════════════

TERMINOLOGY_EXERCISES = [
    {
        "id": "TERMS_001",
        "title": "📚 Apprendre les Termes SOC",
        "difficulty": "Débutant",
        "scenario": """
Pour bien faire du SOC, tu DOIS connaître la vocabulaire.

Voici 5 termes clés du jour:
        """,
        "tools": ["Knowledge"],
        "learning_terms": [
            "IOC (Indicator of Compromise): IP, Hash, Domaine qui indique une attaque",
            "C2 (Command & Control): Serveur malveillant qui contrôle le ransomware",
            "Beaconing: Pattern régulier de connexions vers C2",
            "MITRE ATT&CK: Framework taxonomie des techniques d'attaque",
            "EDR (Endpoint Detection & Response): Outil qui détecte anomalies endpoints"
        ],
        "splunk_query": "# Cet exercice ne requiert pas de Splunk query - c'est théorique!",
        "expected_output": "Tu peux expliquer ces 5 termes? Si oui, continue. Si non, relire.",
        "hints": [
            "💡 IOC = Arme/Preuve d'attaque",
            "💡 C2 = Cerveau du malware (elle prend orders d'ici)",
            "💡 MITRE = Bible du SOC (toutes les techniques connues)"
        ]
    }
]

# ════════════════════════════════════════════════════════════════
# EXERCICES - WIRESHARK & NETWORK ANALYSIS
# ════════════════════════════════════════════════════════════════

NETWORK_EXERCISES = [
    {
        "id": "NETWORK_001",
        "title": "🌐 Wireshark - Identifier une Connexion Suspecte",
        "difficulty": "Débutant",
        "scenario": """
╔════════════════════════════════════════════════════════════════╗
║                  📡 ANALYSE TRAFIC RÉSEAU 📡                 ║
╚════════════════════════════════════════════════════════════════╝

Date: 2026-03-16 | Machine: PROD-WEBSERVER-01

📢 SITUATION:
"L'équipe réseau vient de capturer un PCAP (packet capture) d'une machine.
Tu dois analyser le trafic pour trouver les connexions anormales."

📊 CE QUE TU VAS VOIR DANS WIRESHARK:

▌ PORT 443 (HTTPS Normal):
├─ IP: 10.0.1.100 → 93.184.216.34:443  (Google - OK)
├─ IP: 10.0.1.100 → 151.101.193.219:443 (CDN - OK)

▌ PORT 4444 (SUSPECT!):
├─ IP: 10.0.1.100 → 203.0.113.99:4444 (??? QUI? POURQUOI?)
│  └─ Données CHIFFRÉES (TLS)
│  └─ NON-standard port
│  └─ Connexion persistante (30+ minutes!)

▌ PORT 22 (SSH - SUSPECT!):
├─ IP: 10.0.1.100 → 192.168.99.1:22
│  └─ Tentative de connexion SSH
│  └─ JAMAIS AUTORISÉ sur ce réseau!

TA MISSION DANS WIRESHARK:
1. Filtrer pour trouver les ports NON-standard (pas 80, 443, 53, 22, etc.)
2. Identifier les CONNEXIONS LONGUES (durée > 5 minutes)
3. Checker le TRAFIC CHIFFRÉ (pourquoi?)
4. Noter l'IP DESTINATAIRE (est-elle trustée?)
5. Écrire le Wireshark FILTER pour isoler l'anomalie
        """,
        "tools": ["Wireshark", "PCAP Analyzer", "Network Flow Analysis"],
        "learning_terms": [
            "PCAP (Packet CAPture): Fichier contenant tous les paquets réseau",
            "Wireshark Display Filter: Syntaxe pour filtrer le trafic",
            "Non-standard Port: Port autre que les ports bien connus (1-1024)",
            "Connection Persistence: Connexion qui reste ouverte longtemps",
            "TLS/SSL Handshake: Début d'une connexion chiffrée"
        ],
        "expected_output": """
✅ RÉSULTAT ATTENDU:

Wireshark Filter utilisé:
└─ tcp.dstport == 4444

Connexions trouvées:
├─ Source: 10.0.1.100
├─ Destination: 203.0.113.99:4444
├─ Protocol: TCP (données chiffrées en TLS)
├─ Duration: 32 minutes 15 secondes
├─ Data Transferred: ~145 MB
└─ Status: ⚠️ TRÈS SUSPECT

Analyse:
✓ Port non-standard (4444 = C2 beacon classique)
✓ Connexion très longue (persistence)
✓ Trafic chiffré = caché
✓ IP non trustée (threat intel)
""",
        "hints": [
            "💡 Dans Wireshark: tcp.dstport != 80 && tcp.dstport != 443 (ports normaux)",
            "💡 Cherche les connexions avec des DRAPEAUX TCP (SYN, ACK)",
            "💡 Regarde la colonne 'Info' pour voir le type de trafic",
            "💡 Les ports 4444, 5555, 6666 = TRÈS souvent du malware",
            "💡 Follow TCP Stream pour voir le contenu (si c'est pas chiffré!)"
        ]
    }
]

# ════════════════════════════════════════════════════════════════
# EXERCICES - FORENSICS & SYSTEM ANALYSIS
# ════════════════════════════════════════════════════════════════

FORENSICS_EXERCISES = [
    {
        "id": "FORENSICS_001",
        "title": "🔬 Forensics - Registry Hacking Detection",
        "difficulty": "Intermédiaire",
        "scenario": """
╔════════════════════════════════════════════════════════════════╗
║              🖥️ ANALYSE LA REGISTRY WINDOWS 🖥️              ║
╚════════════════════════════════════════════════════════════════╝

Date: 2026-03-17 | Machine: DESKTOP-INFECTED (Windows 10)

📢 SITUATION:
"Une machine semble compromise. L'antivirus a trouvé des traces.
Tu dois analyser la Windows Registry pour trouver les modifications du malware."

📊 REGISTRY WINDOWS - CLÉS IMPORTANTES:

HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\Run
├─ "Windows Updater" → C:\\Users\\Admin\\AppData\\Local\\wupdater.exe ⚠️
│  └─ NOM = "Windows Updater" (ressemble à Windows Update - TRICKY!)
│  └─ CHEMIN = Caché dans AppData (BAD!)
│
├─ "OneDrive" → C:\\Program Files\\Microsoft OneDrive\\onedrive.exe ✓ OK
└─ "Adobe Update" → C:\\Program Files\\Adobe\\AdobeUpdate.exe ✓ OK

HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
├─ "GoogleChrome" → C:\\Users\\John\\AppData\\Roaming\\chrome.exe ⚠️
│  └─ Chrome N'EST PAS dans Roaming!

Hôtes fichier (C:\\Windows\\System32\\drivers\\etc\\hosts)
├─ 127.0.0.1 localhost
├─ 127.0.0.1 google.com ⚠️ MALVEILLANT!
└─ 127.0.0.1 microsoft.com ⚠️ MALVEILLANT!

TA MISSION:
1. Identifier TOUTES les entrées registry suspectes
2. Vérifier que le CHEMIN du fichier existe VRAIMENT
3. Checker si c'est du FILE MASQUERADING (faux nom)
4. Lister les INDICATEURS D'INFECTION
5. Expliquer comment le malware PERSISTE au redémarrage
        """,
        "tools": ["Registry Editor", "Autoruns", "Process Monitor", "Strings"],
        "learning_terms": [
            "Registry Run Keys: Dossier automatique de démarrage",
            "File Masquerading: Donner un faux nom à un fichier malveillant",
            "Persistence Mechanism: Comment malware reste après reboot",
            "Autoruns: Outil pour voir TOUT ce qui démarre",
            "Hosts File Hijacking: Rediriger google.com vers 127.0.0.1"
        ],
        "expected_output": """
✅ RÉSULTAT ATTENDU:

ENTRÉES REGISTRY SUSPECTES:
┌─ wupdater.exe
│  ├─ Name: "Windows Updater" (ressemble TROP à Windows Update!)
│  ├─ Path: C:\\Users\\Admin\\AppData\\Local\\wupdater.exe (NON-STANDARD!)
│  └─ Status: ⚠️ MALWARE PROBABLE
│
└─ chrome.exe
   ├─ Name: "GoogleChrome"
   ├─ Path: C:\\Users\\John\\AppData\\Roaming\\chrome.exe (FAUX!)
   └─ Status: ⚠️ FILE MASQUERADING

HOSTS FILE HIJACKING:
└─ google.com → 127.0.0.1 (PHISHING LOCAL!)

PERSISTENCE OBSERVÉE:
✓ 2 entrées Run keys = Malware survit au reboot
✓ Hosts file modifié = Redirection de trafic
✓ Fichiers cachés dans AppData = Difficile à voir manuellement
""",
        "hints": [
            "💡 Autoruns.exe = Meilleur ami du forensics (tout en un endroit)",
            "💡 Regarde les CHEMINS: C:\\Program Files = Normal, C:\\Users\\..\\AppData = SUSPECT",
            "💡 Les vrais Windows Updates = JAMAIS dans Roaming!",
            "💡 Si le chemin N'EXISTE PAS = C'est du malware (ou leftover)",
            "💡 MD5 hash du fichier pour vérifier si c'est malveillant"
        ]
    }
]

# ════════════════════════════════════════════════════════════════
# EXERCICES - PRIVILEGE ESCALATION
# ════════════════════════════════════════════════════════════════

PRIVESC_EXERCISES = [
    {
        "id": "PRIVESC_001",
        "title": "⬆️  Privilege Escalation - Détection UAC Bypass",
        "difficulty": "Intermédiaire",
        "scenario": """
╔════════════════════════════════════════════════════════════════╗
║           🔐 ESCALADE DE PRIVILÈGE DÉTECTÉE 🔐               ║
╚════════════════════════════════════════════════════════════════╝

Date: 2026-03-16 | Machine: DESKTOP-EMPLOYEE-05

📢 SITUATION:
"Un utilisateur (employee) a lancé un exécutable.
Soudain, il a des droits ADMIN sans avoir taper de mot de passe!
Comment c'est possible?"

📊 LA TIMELINE DE L'EXPLOIT:

14:32:00 - L'utilisateur (employee) lance setup.exe depuis Desktop

14:32:05 - setup.exe enregistre le fichier:
          C:\\Windows\\System32\\upnphost.dll.bak
          (la BONNE DLL est renommée!)

14:32:10 - setup.exe crée un DOSSIER vide dans C:\\Windows\\Tasks
          (Tasks = dossier SPÉCIAL = accès admin automatique?!)

14:32:15 - Création d'une NOUVELLE DLL:
          C:\\Windows\\System32\\upnphost.dll
          (PAS DES PRIVILEGES ADMIN = mais la DLL remplace l'originale?!)

14:32:20 - EventCode 4688: Processus "upnphost" LANCÉ PAR WINDOWS!
          ¡Automatique! (UAC BYPASSED!)

14:32:25 - NEW PROCESS with ADMIN RIGHTS:
          svchost.exe LANCÉ PAR upnphost.dll (administrateur)

TA MISSION:
1. Identifier la TECHNIQUE d'escalade (quel CVE?)
2. Trouver les INDICATEURS dans les logs (Event Viewer)
3. Comparer le HASH de la DLL originale vs malveillante
4. Écrire la requête pour DÉTECTER cet exploit
5. Proposer une MITIGATION
        """,
        "tools": ["Event Viewer", "Process Monitor", "File Hash Checker", "Splunk"],
        "learning_terms": [
            "UAC (User Account Control): Mécanisme de sécurité Windows",
            "DLL Hijacking: Remplacer une DLL système par une malveillante",
            "Privilege Escalation: Passer de user → admin",
            "Process Monitor: Voir TOUS les accès fichiers/registry",
            "EventCode 4688: Process Creation (qui a lancé quoi)"
        ],
        "expected_output": """
✅ RÉSULTAT ATTENDU:

TECHNIQUE: DLL Hijacking via upnphost.dll (CVE-2019-1388 related)

LOGS TROUVÉS:
├─ EventCode 4698: Scheduled Task Created (malveillant)
├─ EventCode 4688: upnphost.exe lancé (NO USER = SYSTEM!)
├─ EventCode 5157: Network Connection Blocked (malware C2?)
├─ File: upnphost.dll HASH ≠ Expected HASH
└─ Registry: HKLM\\Software\\DLLs (nouvelle clé!)

SPLUNK QUERY:
index=main (EventCode=4688 AND ProcessName=upnphost.exe)
| search User=SYSTEM
| table TimeCreated, ProcessName, User, CommandLine

DÉTECTION: ⚠️ ESCALADE CONFIRMÉE
└─ process=upnphost.exe lancé par SYSTEM (impossibilité normale)
""",
        "hints": [
            "💡 Cherche EventCode 4688 où User=SYSTEM et ProcessName=upnphost",
            "💡 File Monitor: Va voir C:\\Windows\\System32\\*.dll avec timestamp",
            "💡 Hash = Outil clé! Compare avec le hash original de Windows",
            "💡 Les escalades = toujours des processus SYSTÈME lancés",
            "💡 Mitigation: Signer les DLL, renforcer UAC"
        ]
    }
]

# ════════════════════════════════════════════════════════════════
# EXERCICES - MALWARE CLASSIFICATION
# ════════════════════════════════════════════════════════════════

MALWARE_EXERCISES = [
    {
        "id": "MALWARE_001",
        "title": "🦠 Classification Malware - Identifier le Type",
        "difficulty": "Débutant",
        "scenario": """
╔════════════════════════════════════════════════════════════════╗
║              🔍 ANALYSE DU COMPORTEMENT MALWARE 🔍            ║
╚════════════════════════════════════════════════════════════════╝

📢 SITUATION:
"L'antivirus a bloqué 3 fichiers. Mais QUEL TYPE DE MALWARE?
Ransomware? Spyware? Trojan? Adware?
Tu dois analyser le COMPORTEMENT pour classifier."

📊 3 MALWARES À CLASSIFIER:

▌ MALWARE #1: zeus_2048.exe
  Comportement observé:
  ├─ Redirige firefox.exe → page "onlinebanking.com.fake"
  ├─ Enregistre TOUS les clics clavier (keylog)
  ├─ Dump de la mémoire du navigateur
  ├─ Vole les cookies (les mots de passe!)
  └─ Envoie les données à 185.220.101.45:8080
  
  → TYPE: ???

▌ MALWARE #2: cleanup_tool.exe
  Comportement observé:
  ├─ Parcourt C:\\ cherchant fichiers .docx, .xlsx, .jpg, etc.
  ├─ Chiffre CHAQUE fichier avec AES-256
  ├─ Crée un RANSOM NOTE "PAY_OR_DIE.txt"
  ├─ Supprime Volume Shadow Copies (backup impossible!)
  └─ Envoie la clé à cryptoserver.onion
  
  → TYPE: ???

▌ MALWARE #3: update_manager.exe
  Comportement observé:
  ├─ Affiche 50+ POPUPS publicitaires par jour
  ├─ Modifie la page d'accueil → search-safe.com
  ├─ Ralentit considérablement le PC
  ├─ Demande 50 fois par jour "Cliquez pour installer"
  └─ Gère C:\\Program Files\\SearchSafePro\\
  
  → TYPE: ???

TA MISSION:
1. Classifier CHAQUE malware (type?)
2. Décrire le COMPORTEMENT CLÉS
3. Identifier le VECTEUR D'ATTAQUE (comment il arrive?)
4. Évaluer l'IMPACT (données volées? système détruit?)
5. Proposer la REMÉDIATION
        """,
        "tools": ["Behavioral Analysis", "Sandboxing", "MITRE ATT&CK", "Any.run"],
        "learning_terms": [
            "Ransomware: Chiffre fichiers → demande rançon",
            "Spyware: Vole données personnelles (passwords, clics)",
            "Trojan: Porte arrière sur la machine",
            "Adware: Affiche publicités envahissantes",
            "Behavioral Analysis: Analyser ce que le malware FAIT"
        ],
        "expected_output": """
✅ CLASSIFICATION ATTENDUE:

MALWARE #1: zeus_2048.exe
├─ TYPE: SPYWARE (banking trojan)
├─ COMPORTEMENT: Vol de credentials/cookies bancaires
├─ IMPACT: Accès aux comptes bancaires
└─ MITRE: T1056 (Input Capture - keylogging)

MALWARE #2: cleanup_tool.exe
├─ TYPE: RANSOMWARE
├─ COMPORTEMENT: Chiffrage de fichiers + demande rançon
├─ IMPACT: Données inaccessibles
└─ MITRE: T1486 (Data Encrypted for Impact)

MALWARE #3: update_manager.exe
├─ TYPE: ADWARE
├─ COMPORTEMENT: Publicités envahissantes
├─ IMPACT: Harcèlement utilisateur, données de navigation
└─ MITRE: T1547 (Boot or Logon Autostart Execution)

VECTEURS D'ATTAQUE:
├─ Trojan: Email
├─ Ransomware: RDP brute force / Phishing
└─ Adware: Faux installer / Bundleware
""",
        "hints": [
            "💡 Ransomware = chiffrage de fichiers + rançon (obvious!)",
            "💡 Spyware = vol de données (passwords, clics, visites)",
            "💡 Adware = JUSTE des pubs (pas destructif)",
            "💡 MITRE ATT&CK: Cherche les techniques correspondantes",
            "💡 Sandboxing: Lance le malware dans une VM isolée!"
        ]
    }
]

# ════════════════════════════════════════════════════════════════
# POOL D'EXERCICES
# ════════════════════════════════════════════════════════════════

EXERCISE_POOL = (
    RANSOMWARE_EXERCISES +
    LATERAL_MOVEMENT_EXERCISES +
    THREAT_HUNTING_EXERCISES +
    INCIDENT_RESPONSE_EXERCISES +
    TERMINOLOGY_EXERCISES +
    NETWORK_EXERCISES +
    FORENSICS_EXERCISES +
    PRIVESC_EXERCISES +
    MALWARE_EXERCISES
)

# ════════════════════════════════════════════════════════════════
# GÉNÉRATEUR D'EXERCICE
# ════════════════════════════════════════════════════════════════

def get_random_exercise(difficulty: Optional[str] = None, category: Optional[str] = None) -> Dict:
    """
    Génère un exercice aléatoire basé sur les critères.
    
    Args:
        difficulty: "Débutant", "Intermédiaire", "Avancé" (optionnel)
        category: "Ransomware", "Lateral_Movement", etc. (optionnel)
    
    Returns:
        Dict avec exercice complet
    """
    
    pool = EXERCISE_POOL
    
    # Filtrer par difficulté si spécifié
    if difficulty:
        pool = [ex for ex in pool if ex["difficulty"] == difficulty]
    
    # Filtrer par catégorie si spécifié
    if category:
        pool = [ex for ex in pool if category in ex["id"]]
    
    if not pool:
        return {"error": "Pas d'exercice trouvé pour ces critères"}
    
    return random.choice(pool)

def format_exercise_display(exercise: Dict, show_solution: bool = False) -> str:
    """
    Formate l'exercice pour affichage Rich/console.
    """
    
    output = f"""
╔════════════════════════════════════════════════════════════════╗
║  {exercise['title'].center(59)}║
╚════════════════════════════════════════════════════════════════╝

📊 Difficulté: {exercise['difficulty']}
🎯 ID: {exercise['id']}

{exercise['scenario']}

─────────────────────────────────────────────────────────────────
🛠️  TOOLS À UTILISER:
{', '.join(f'[{t}]' for t in exercise['tools'])}

─────────────────────────────────────────────────────────────────
📚 TERMES À APPRENDRE:
"""
    
    for term in exercise['learning_terms']:
        output += f"\n  • {term}"
    
    output += f"""

─────────────────────────────────────────────────────────────────
💡 HINTS:
"""
    
    for hint in exercise['hints']:
        output += f"\n  {hint}"
    
    if show_solution:
        output += f"""

─────────────────────────────────────────────────────────────────
✅ SOLUTION SUGGÉRÉE:
"""
        
        # Afficher la Splunk query SI elle existe
        if 'splunk_query' in exercise:
            output += f"""
Splunk Query:
```spl
{exercise['splunk_query']}
```
"""
        
        output += f"""
Expected Output:
{exercise['expected_output']}
"""
    
    output += "\n"
    return output

def get_exercise_by_difficulty(level: str) -> Dict:
    """Retourne un exercice de difficulté spécifiée."""
    return get_random_exercise(difficulty=level)

def get_exercise_by_id(exercise_id: str) -> Dict:
    """Retourne un exercice spécifique par son ID."""
    for ex in EXERCISE_POOL:
        if ex['id'].upper() == exercise_id.upper():
            return ex
    return {"error": f"Exercice '{exercise_id}' non trouvé. Utilise /exo_soc list pour voir tous les IDs."}

def list_all_exercises() -> str:
    """Liste tous les exercices disponibles."""
    output = "📚 EXERCICES DISPONIBLES:\n\n"
    for ex in EXERCISE_POOL:
        output += f"• [{ex['id']}] {ex['title']} ({ex['difficulty']})\n"
    return output

if __name__ == "__main__":
    # Test du générateur
    ex = get_random_exercise()
    print(format_exercise_display(ex, show_solution=False))
    print("\nPour voir la solution, regarde le code ou fais /exo_soc show-solution")
