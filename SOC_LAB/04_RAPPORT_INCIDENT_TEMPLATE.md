# ╔════════════════════════════════════════════════════════════════╗
# ║           TEMPLATE - RAPPORT D'INCIDENT SOC                   ║
# ║           À compléter après l'analyse Splunk                  ║
# ╚════════════════════════════════════════════════════════════════╝

---

# RAPPORT D'INCIDENT D'INCIDENT SOC
**Référence Incident:** INC-2026-0313-001  
**Date du Rapport:** 13 Mars 2026  
**Analyste SOC:** [Ton Nom]  
**Statut:** ⚠️ CRITICAL (En Investigation)

---

## 1️⃣  RÉSUMÉ EXÉCUTIF

### Vue d'ensemble
Une infection ransomware a été détectée sur la workstation de l'employé `employee@corp.local` 
(192.168.1.100). Le malware a chiffré plusieurs fichiers sensibles (documents, feuilles de calcul) 
et a établi une connexion de commande et contrôle (C2) vers un serveur externe non autorisé.

### Sévérité
- **Niveau:** 🔴 CRITIQUE
- **Impact Potentiel:** Perte de données, extorsion, compromission de la confidentialité
- **Temps d'Incident:** ~30 secondes (T+0 à T+30)
- **Détection:** Automatique via alerte Splunk

---

## 2️⃣  CHRONOLOGIE DE L'ATTAQUE (Timeline)

| Phase | T+ | Événement | IoC | Log Source |
|-------|-----|----------|-----|-----------|
| **Exécution** | 0s | powershell.exe lancé sans argument | ProcessCreate | Windows Security |
| **Exécution** | 0.5s | cmd.exe enfant de powershell | ProcessCreate | Sysmon |
| **Chiffrement** | 1s | Création `.locked` (rapport_financier_2026.docx.locked) | FileCreate | Sysmon |
| **Chiffrement** | 1.5s | Création `.locked` (donnees_clients.xlsx.locked) | FileCreate | Sysmon |
| **Persistance** | 2s | Clé registre HKCU\...\Run modifiée | RegistrySet | Windows Security |
| **C2 Callback** | 2.5s | Connexion TCP vers 203.0.113.45:443 | NetworkConnection | Windows Security / Firewall |
| **Exfiltration** | 3-30s | Trafic chiffré vers C2 | Network Traffic | Firewall / PCAP |

---

## 3️⃣  INDICATEURS DE COMPROMISSION (IOCs)

### IP Addresses
| Type | Valeur | Confiance | Catégorie | Action |
|------|--------|-----------|-----------|--------|
| **C2 Server** | 203.0.113.45 | 🟢 Très Haute | Command & Control | BLOQUER (EMERGENT) |
| **Port C2** | 443 (HTTPS) | 🟢 Très Haute | Exfiltration | BLOQUER |

### File Indicators
| File Name | Extension | MD5 Hash | SHA256 | Statut |
|-----------|-----------|---------|--------|--------|
| report_financier_2026 | .docx.locked | `[À calculer]` | `[À calculer]` | Chiffré |
| donnees_clients | .xlsx.locked | `[À calculer]` | `[À calculer]` | Chiffré |
| recovery.txt | .txt (ransom note) | `[À calculer]` | `[À calculer]` | Ransom note |

**Marqueur Universelle:** Extension `.locked` = Très probable ransomware

### Process Indicators
| Process | Parent | Command Line | Confiance | Contexte |
|---------|--------|--------------|-----------|----------|
| powershell.exe | explorer.exe | `-NoProfile -WindowStyle Hidden` | 🟠 Haute | Script injection |
| cmd.exe | powershell.exe | `/c timeout 1` | 🟠 Haute | Reverse shell attempt |

### Registry Indicators
| Registry Path | Value Name | Data | Anomalie |
|---------------|-----------|------|----------|
| HKCU\Software\Microsoft\Windows\CurrentVersion\Run | .ransomware_persistence | C:\Windows\Temp\recovery.exe | Persistence |

### HTTP/Network Indicators
| Indicator | Type | Protocol | Port | Destination |
|-----------|------|----------|------|-------------|
| TLS ClientHello | Handshake | TLS 1.2 | 443 | 203.0.113.45 |
| Cert CN | Certificate | X.509 | 443 | c2server.ru |

---

## 4️⃣  ANALYSE TECHNIQUE

### Vecteur d'Attaque
```
Utilisateur télécharge ZIP → Double-click → Extraction
      ↓
PowerShell lancé (hidden)  ← Code injection / Macro
      ↓
CMD.exe enfant            ← Obfuscation
      ↓
Ransomware.exe (simulé)   ← Exécution
      ↓
Chiffrage fichiers        ← Impact utilisateur
Connexion C2              ← Communication malware
```

### Technique d'Étape (MITRE ATT&CK)

| Étape | Technique MITRE | Tactic | Détail |
|-------|-----------------|--------|--------|
| 1 | T1566.002 | Initial Access | Spear Phishing Attachment |
| 2 | T1204.002 | Execution | User Execution: Malicious File |
| 3 | T1059.001 | Execution | PowerShell |
| 4 | T1059.003 | Execution | Windows Command Shell (cmd.exe) |
| 5 | T1565.001 | Impact | Data Destruction: Encryption |
| 6 | T1190 | Lateral Movement | C2 Callback (Exploitation) |

### Analyse du Malware (Comportement)

**🎯 Objectif:** Chiffrer les données de l'employé → Demande de rançon

**Comportement Observé:**
1. Énumération des répertoires sensibles (Documents, Desktop)
2. Chiffrage des fichiers: `.docx` → `.docx.locked`
3. Écrasement du fichier original (destruction)
4. Création d'une note de rançon: `recovery.txt` ou `HOW_TO_RECOVER.txt`
5. Callback C2 pour exfiltration / reçu de comande

**Familles Probables:** Ryuk, LockBit, Cerber (à valider avec VirusTotal)

---

## 5️⃣  IMPACT & PÉRIMÈTRE

### Systèmes Affectés
| Système | OS | IP | Statut | Fichiers Impact | Action |
|---------|----|----|--------|-----------------|--------|
| Workstation Employee | Windows 10 | 192.168.1.100 | 🔴 Infecté | ~4 fichiers | ISOLER |
| SIEM / Rocky Linux | Rocky 9 | 192.168.1.50 | 🟢 Sûr | N/A | MONITORER |

### Données Compromises
- Rapports financiers 2026 (confidentialité: 🔴 CRITIQUE)
- Données clients (RGPD: 🔴 CRITIQUE → Signaler CNIL)
- Archives emails (confidentialité: 🔴 CRITIQUE)
- Contrats importants (impact légal: 🔴 CRITIQUE)

**→ ESCALADE RECOMMANDÉE:** Notifier CISO + Legal

---

## 6️⃣  REQUÊTES SPLUNK D'INVESTIGATION

### Query 1: Vue complète de l'attaque
```spl
index=main 
| search (
    (EventCode=4688 AND (CommandLine="*powershell*" OR CommandLine="*cmd*")) 
    OR 
    (EventCode=4658 AND Object_Name="*.locked") 
    OR 
    (EventCode=5156 AND dest_ip="203.0.113.45")
  )
| sort + TimeCreated
| fields TimeCreated, EventCode, EventDescription, CommandLine, Object_Name, dest_ip
```

### Query 2: Détail du C2 Connection
```spl
index=main EventCode=5156 dest_ip="203.0.113.45"
| stats count by src_ip, dest_ip, dest_port, TimeCreated
| convert ctime(TimeCreated) as "Timestamp"
```

### Query 3: Fichiers Chiffrés
```spl
index=main EventCode=4658 Object_Name="*.locked"
| stats count by Object_Name
| rename Object_Name as "Encrypted_File"
```

---

## 7️⃣  ACTIONS DE RÉPONSE

### Actions IMMÉDIATE (0-30 min)
- [ ] **Isolation:** Déconnecter 192.168.1.100 du réseau (unplugged)
- [ ] **Containement:** Bloquer 203.0.113.45 au firewall (`iptables DROP`)
- [ ] **Notification:** Alerter CTO + CISO + Incident Manager
- [ ] **Préservation:** Imager le disque de la workstation (BitLocker enabled)

### Actions COURT-TERME (1-4 heures)
- [ ] Scan réseau pour d'autres infections similaires
- [ ] Audit des autres workstations (connexions à 203.0.113.45)
- [ ] Interroger l'employé: "Where did you download the file?"
- [ ] Vérifier backups: Restauration possible?
- [ ] Analyser le fichier ZIP original (malware analysis lab)

### Actions LONG-TERME (1-7 jours)
- [ ] Documenter l'incident (ce rapport)
- [ ] Implémenter détection Splunk (alerte automatique)
- [ ] Deployer Sysmon / EDR sur tous les endpoints
- [ ] Renforcer filtrage DNS (bloquer c2server.ru, malware.tk, etc.)
- [ ] Formation utilisateurs (phishing awareness)

---

## 8️⃣  RÈGLES DE DÉTECTION PROPOSÉES

### Alerte Splunk: Processus Enfants Suspectes

**Name:** `Ransomware_Process_Chain_Detection`  
**Severity:** 🔴 CRITICAL

```spl
index=main EventCode=4688 
| transaction ProcessName=powershell.exe 
| search ProcessName=cmd.exe 
| alert "CRITICAL: Ransomware process chain detected (powershell -> cmd)"
```

### Alerte: Connexion C2
**Name:** `C2_Outbound_Connection_Block`  
**Severity:** 🔴 CRITICAL

```spl
index=main EventCode=5156 
| search dest_ip IN (203.0.113.45, 192.0.2.1) dest_port=443 
| alert "CRITICAL: C2 Server Connection Detected - Isolate Host Immediately"
```

### Alerte: Extension .locked
**Name:** `Ransomware_File_Extension_Detection`  
**Severity:** 🟠 HIGH

```spl
index=main EventCode=4658 Object_Name="*.locked"
| alert "HIGH: Ransomware file encryption detected (.locked files)"
```

---

## 9️⃣  RECOMMANDATIONS DE MITIGATION

### Court Terme (1-7 jours)
1. ✅ **Bloquer IP C2** → `iptables -A INPUT -s 203.0.113.45 -j DROP`
2. ✅ **Bloquer Domaine DNS** → DNS sinkhole untuk c2server.ru
3. ✅ **Mettre à jour EDR** → Deploy Microsoft Defender / CrowdStrike
4. ✅ **Audit Backups** → Vérifier que backups ne sont pas chiffrés

### Moyen Terme (1-4 semaines)
5. 🟡 **Implémenter MFA** → Tous les systèmes critiques
6. 🟡 **Segmentation Réseau** → VLAN pour données sensibles
7. 🟡 **Monitoring Centralisé** → Étendre Splunk à tous les endpoints
8. 🟡 **Politique Zero Trust** → Least privilege access

### Long Terme (1-3 mois)
9. 🔵 **Disaster Recovery Plan** → Tester récupération après ransomware
10. 🔵 **Inci...
Wait, continuing...

---

## 🔟  CONCLUSION

### Remarques Finales
Cet incident démontre l'efficacité d'une stratégie multicouches:
- ✅ Détection rapide grâce aux logs centralisés (Splunk)
- ✅ Identification précise via IOCs
- ✅ Mitigation rapide = réduction de l'impact

**Sans détection:** Ransom demandé, données perdues, perte financière  
**Avec détection:** Isolation en 30 sec, perte mineure, incident clos

### Leçons Apprises
1. Les log centralisés SAUVENT les organisations
2. La corrélation d'événements est criticale
3. La réaction rapide est plus efficace que la prévention parfaite

### Date Fermeture Estimée
- [ ] Investigation: 13-14 Mars 2026
- [ ] Remediation: 14-15 Mars 2026
- [ ] Follow-up: 15-16 Mars 2026
- **Status:** 🟡 Ouvert

---

**Approuvé par:**
- [ ] Analyste SOC: __________________ Date: _______
- [ ] CISO: __________________ Date: _______
- [ ] CTO: __________________ Date: _______

---

**Distribution:**
- Management (CISO)
- Legal / Compliance
- Incident Response Team
- Infrastructure Team

---

**Document Confidentiel** | Classification: INTERNAL USE ONLY
