# CORHack RAG - Obsidian Vault Assistant

Assistant RAG intelligent pour réviser et explorer tes vaults Obsidian avec IA.

## Features

- Markdown + PDF (PyMuPDF)
- LLM Dual-Model : Llama 3.3 70B (rapide) + GPT-OSS 120B (précis) via Groq Cloud
- Quiz adaptatif : normal, chrono, révision + difficulté progressive
- Graphe de connaissances interactif
- Multi-vault dynamique (`/switch`)
- Tags avec statistiques de pertinence

## Prérequis

- **Python 3.12+**
- **Docker Desktop** (pour Qdrant)
- **Ollama** installé et lancé (`ollama serve`) avec le modèle `all-minilm:l6-v2`
- **Clé Groq API** gratuite : https://console.groq.com/keys

## Installation rapide

```bash
# 1. Clone le projet
git clone https://github.com/Jericho-Cortez/RAG.git
cd RAG

# 2. Crée le virtualenv et installe les dépendances
python -m venv .venv
# Windows :
.venv\Scripts\activate
# Linux/Mac :
source .venv/bin/activate

pip install -r requirements.txt

# 3. Configure ta clé API Groq
cp .env.example .env
# Édite .env et remplace gsk_YOUR_API_KEY_HERE par ta clé

# 4. Télécharge le modèle d'embedding
ollama pull all-minilm:l6-v2

# 5. Lance Qdrant via Docker
docker compose up -d qdrant

# 6. Lance CORHack
python query.py
```

### Windows (raccourci PowerShell)

```powershell
.\launch.ps1
```

Le launcher gère automatiquement Docker, Qdrant, Ollama et les dépendances.

## Commandes

| Commande | Description |
|----------|-------------|
| `/help` | Affiche l'aide |
| `/tags` | Tags triés par pertinence |
| `/quiz @Tag 10` | Quiz de 10 questions sur un tag |
| `/quiz chrono` | Mode chronométré (30s/question) |
| `/quiz revision` | Revoir les questions échouées |
| `/history` | Historique et stats des quiz |
| `/graph @Tag` | Graphe de connaissances |
| `/path SSH Firewall` | Chemin entre 2 concepts |
| `/switch` | Changer de vault |
| `/index` | Réindexer le vault |
| `/status` | Stats de la base |
| `/quit` | Quitter |

## Architecture

```
Obsidian Vault (.md/.pdf)
        |
   [ingest.py] ──► Ollama (all-minilm:l6-v2) ──► Qdrant (vectors)
        |
   [query.py] ──► Groq Cloud (LLM) ──► Réponse
        |
   [quiz.py] ──► Questions générées par LLM
   [knowledge_graph.py] ──► Graphe interactif HTML
```

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `GROQ_API_KEY` | *requis* | Clé API Groq |
| `VAULT_PATH` | `./vault` | Chemin du vault Obsidian |
| `COLLECTION_NAME` | `obsidian` | Nom de la collection Qdrant |
| `QDRANT_URL` | `http://localhost:6333` | URL Qdrant |

## Licence

MIT
