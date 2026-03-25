# 🎓 SYSTÈME D'EXERCICES SOC - Guide Complet

## 📌 Vue d'Ensemble

Le système `/exo_soc` génère **dynamiquement des exercices SOC différents** à chaque exécution, te permettant d'apprendre et de pratiquer les outils et concepts du métier de way opérationnelle.

---

## 🚀 DÉMARRAGE RAPIDE

### Commande Basique
```bash
❯ Tu : /exo_soc

# Output: Un exercice aléatoire avec:
# - Contexte Réaliste
# - Mission à accomplir
# - Tools à utiliser
# - Termes à apprendre
# - Hints pour t'aider
```

### Voir la Solution
```bash
❯ Tu : /exo_soc show-solution

# Output: Solution + Requête SPL example + Expected Output
```

---

## 📚 TOUS LES NIVEAUX

### Niveau Débutant - Les Bases
```bash
❯ Tu : /exo_soc debutant

# Exemples d'exercices:
# 1. Détecter ransomware - Chaîne de processus
# 2. Détecter ransomware - Fichiers chiffrés
# 3. Détecter ransomware - C2 Callback
```

**Pour qui?** Ceux qui commencent en SOC (novice en Splunk)  
**Outils couverts:** Splunk básico, Event Viewer, File Integrity  
**Durée typique:** 15-30 min/exercice

---

### Niveau Intermédiaire
```bash
❯ Tu : /exo_soc intermediaire

# Exemples d'exercices:
# 1. Pass-the-Hash (Lateral Movement)
# 2. Incident Response - Timeline Reconstruction
# 3. Threat Hunting - Anomaly Detection
```

**Pour qui?** Analysts avec 6-12 mois d'expérience  
**Outils couverts:** SPL avancé, Lateral Movement, NTLM Auth  
**Durée typique:** 30-60 min/exercice  
**Prérequis:** Niveau Débutant maîtrisé

---

### Niveau Avancé
```bash
❯ Tu : /exo_soc avance

# Exemples d'exercices:
# 1. Threat Hunting - Outlier Detection
# 2. Advanced EDR Analysis
# 3. Complex Incident Correlation
```

**Pour qui?** SOC Analysts expérimentés + Hunters  
**Outils couverts:** Anomaly detection, Statistical analysis, Threat Hunting  
**Durée typique:** 60-120 min/exercice  
**Prérequis:** Tous les niveaux antérieurs

---

## 🎯 STRUCTURE DE CHAQUE EXERCICE

### 1️⃣ Scenario (Contexte Réaliste)
```
"Une workstation affiche des fichiers .locked dans le dossier Documents.
Les événements Windows montrent: powershell.exe → cmd.exe → ransomware.exe"
```
→ C'est votre scenario du monde réel

### 2️⃣ Mission (Ce que tu dois faire)
```
1. Écrire une requête Splunk
2. Identifier le processus parent
3. Expliquer pourquoi c'est une signature fiable
```
→ C'est la tâche concrète

### 3️⃣ Tools (Les outils à utiliser)
```
[Splunk] [Event Viewer] [Process Explorer]
```
→ Avec quel outil résoudre?

### 4️⃣ Learning Terms (Vocabulaire du métier)
```
• Process Chain (Chaîne de processus)
• Parent Process (Processus parent)
• Command Injection (Injection de commande)
• EventCode 4688 (Process Creation Event)
```
→ Apprendre la langue du SOC

### 5️⃣ Hints (Indices)
```
💡 Cherche EventCode 4688 (process creation)
💡 Regarde le ProcessName ET ParentProcessName
💡 Une chaîne powerShell→cmd est UN RED FLAG
```
→ Guidance pour ne pas être perdu

### 6️⃣ Solution (Optionnel - tape `/exo_soc show-solution`)
```
Splunk Query:
  index=main EventCode=4688 
  | search ProcessName=powershell.exe 
  | transaction ProcessName 
  | search ProcessName=cmd.exe

Expected Output:
  Timeline: powershell → cmd.exe → ransomware.exe
```
→ Comment on l'aurait résolu

---

## 💡 STRATÉGIE D'APPRENTISSAGE

### Semaine 1: Foundations (Débutant)
```
Day 1: /exo_soc debutant  (Detection ransomware - Processus)
Day 2: /exo_soc debutant  (Detection ransomware - Fichiers)
Day 3: /exo_soc debutant  (Detection ransomware - C2)
Day 4: /exo_soc show-solution (Revoir les solutions)
Review: Tu peux expliquer les 3 exercices? Passe à Intermediaire!
```

### Semaine 2-3: Advanced (Intermédiaire)
```
Day 5: /exo_soc intermediaire (Lateral Movement - PtH)
Day 6: /exo_soc intermediaire (Incident Response - Timeline)
Day 7: /exo_soc intermediaire (Threat Hunting)
Practice: Essaie les requêtes SPL sur ton lab réel
```

### Semaine 4+: Mastery (Avancé)
```
Day 8+: /exo_soc avance (Anomaly detection)
Challenge: Créer tes propres requêtes (pas juste copy-paste!)
Real-world: Appliquer sur des données réelles
```

---

## 🎯 VARIABILITÉ GARANTIE

### Même commande = Exercices différents
```bash
# Session 1
❯ Tu : /exo_soc debutant
→ Ransomware - Process Chain

# Session 2 (demain)
❯ Tu : /exo_soc debutant
→ Ransomware - Encrypted Files (DIFFERENT!)

# Session 3 (semaine d'après)
❯ Tu : /exo_soc debutant
→ Ransomware - C2 Callback (ENCORE DIFFERENT!)
```

**= Apprentissage par répétition du concept, pas par répétition du même exercice**

---

## 📊 CATÉGORIES D'EXERCICES

### 🔴 Ransomware Detection (Débutant)
- Process chain analysis
- Encrypted file detection
- C2 callback detection
- Registry persistence

### 🟣 Lateral Movement (Intermédiaire)
- Pass-the-Hash detection
- Credential dumping patterns
- Lateral movement timelines

### 🕵️ Threat Hunting (Avancé)
- Outlier detection
- Baseline deviation analysis
- Anomaly correlation
- Profile matching

### 🚨 Incident Response (Intermédiaire)
- Timeline reconstruction
- Impact assessment
- Containment strategies
- Evidence collection

### 📚 Terminology (Tous niveaux)
- Vocabulaire SOC
- Tool familiarity
- Framework knowledge

---

## 🛠️ TOOLS COUVERTS

| Tool | Niveau | Exercices |
|------|--------|-----------|
| **Splunk** | Débutant+ | Tous |
| **Event Viewer** | Débutant | Ransomware |
| **Process Explorer** | Débutant | Lateral Movement |
| **NTLM Analysis** | Intermédiaire | PtH Detection |
| **Timeline Analysis** | Intermédiaire | Incident Response |
| **Anomaly Detection** | Avancé | Threat Hunting |

---

## 📈 PROGRESSION RECOMMANDÉE

```
Week 1-2: Débutant (3-5 exercices)
        ↓
Maîtriser les processus ransom básicos

Week 3-4: Intermédiaire (3-5 exercices)
        ↓
Comprendre Lateral Movement + IR

Week 5+: Avancé (2-3 exercices)
        ↓
Threat Hunting professionnel
```

---

## 🎓 APRÈS LES EXERCICES

### 1. Pratiquer sur Lab Réel
Utilise les fichiers du dossier `SOC_LAB/`:
- `01_SCRIPTS_RANSOMWARE.ps1` ← Simule une vraie attaque
- `02_SPLUNK_QUERIES.txt` ← Requêtes réelles Splunk
- `04_RAPPORT_INCIDENT_TEMPLATE.md` ← Applique sur des données réelles

### 2. Créer tes Propres Exercices
Ne pas juste copy-paste les solutions!
- Modifier le SPL query
- Ajouter plus logique
- Chercher d'autres IOCs

### 3. Documenter ton Apprentissage
- Quels termes as-tu appris?
- Quels tools as-tu maîtrisé?
- Quelles intuitions as-tu développées?

---

## 🎯 OBJECTIFS PÉDAGOGIQUES

Après avoir complété tous les exercices, tu devrais pouvoir:

### Compétences Techniques
✅ Écrire des requêtes Splunk avancées  
✅ Analyser les logs Windows en profondeur  
✅ Détecter les patterns d'attaque  
✅ Corréler les événements multi-source  

### Compétences Conceptuelles
✅ Comprendre la "kill chain" attaque  
✅ Connaître MITRE ATT&CK framework  
✅ Appliquer threat hunting methodology  
✅ Structurer un rapport d'incident  

### Compétences Métier
✅ Parler la langue SOC  
✅ Utiliser les outils standards  
✅ Prendre les bonnes décisions sous pression  
✅ Communiquer les risques aux non-téchniques  

---

## 💬 INTEGRATIONS AVEC RAG

Les exercices SOC s'intègrent avec ton RAG:

### Avant Exercise: Research
```bash
❯ Tu : Qu'est-ce qu'une Pass-the-Hash attack?
→ RAG répond avec contexte de tes notes

❯ Tu : /exo_soc intermediaire  
→ Exercice sur PtH (concept que tu viens de lire!)
```

### Après Exercise: Learning
```bash
❯ Tu : /exo_soc show-solution
→ Voir la solution SPL

❯ Tu : Pourquoi EventCode 4625 indique une PtH?
→ RAG explique le concept + contexte
```

**= Boucle d'apprentissage TRÈS efficace!**

---

## 📝 COMMANDES COMPLÈTES

```bash
/exo_soc                    # Exercice aléatoire (anyù niveau)
/exo_soc debutant           # Exercice niveau Débutant
/exo_soc intermediaire      # Exercice niveau Intermédiaire
/exo_soc avance             # Exercice niveau Avancé
/exo_soc show-solution      # Affiche la solution du dernier exo
/exo_soc list               # Liste tous les exercices
```

---

## 🎊 BON COURAGE!

C'est un système complet pour:
- ✅ Apprendre les tools SOC
- ✅ Maîtriser les concepts
- ✅ Développer ton portfolio
- ✅ Préparer des entretiens

**À chaque `/exo_soc`, tu apprends quelque chose de nouveau!** 🚀

---

**Questions?** Regarde [README.md du SOC_LAB](./README.md) ou les autres guides.

Happy learning! 🎓
