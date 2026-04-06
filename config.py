# config.py - CORHack RAG Configuration
import os
from pathlib import Path
from dotenv import load_dotenv

# Charge .env si présent (pour la clé API, etc.)
load_dotenv()

VAULT_PATH       = os.getenv("VAULT_PATH", str(Path.home() / "Documents" / "Obsidian"))
COLLECTION_NAME  = os.getenv("COLLECTION_NAME", "obsidian_notes")

# Qdrant Vector DB
QDRANT_URL       = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL      = "all-minilm:l6-v2"
EMBED_DIM        = 384

# LLM (Groq Cloud) - DUAL MODEL SETUP
LLM_BASE_URL        = "https://api.groq.com/openai/v1"
LLM_API_KEY         = os.getenv("GROQ_API_KEY", "")

# ⚡ MODÈLE RAPIDE (par défaut)
MODEL_FAST = {
    "name": "llama-3.3-70b-versatile",
    "label": "⚡ Llama 3.3 70B (Rapide)",
    "temperature": 0.5,
    "max_tokens": 1024,  # 🚀 Réduit de 2048 → plus de place pour contexte
    "tps": 280,
    "description": "Réponses rapides et directes"
}

# 🎯 MODÈLE PRÉCIS
MODEL_PRECISE = {
    "name": "openai/gpt-oss-120b",
    "label": "🎯 GPT-OSS 120B (Précis)",
    "temperature": 0.3,
    "max_tokens": 2048,  # 🚀 Réduit de 4096 → respecte limites Groq
    "tps": 500,
    "description": "Réponses détaillées et rigoureuses"
}

# Défaut
LLM_MODEL_DEFAULT = "precise"  # "fast" ou "precise"

# Chunking (pour Markdown ET PDF)
# Réduit à 200 pour respecter la limite du modèle d'embedding (all-minilm:l6-v2 = ~256 tokens)
CHUNK_SIZE          = 512       # 🚀 Augmenté de 200 → chunks plus grands = moins d'embeddings
CHUNK_OVERLAP       = 50        # Garder contexte sur les frontières

# Support des formats
# - Markdown (.md) : traités par défaut
# - PDF (.pdf) : extraction via PyMuPDF ou PyPDF2

# 🚀 OPTIMISATIONS CONTEXTE (pour respecter limites Groq)
MAX_CHUNKS_RETRIEVE  = 25      # Réduit de 40 → chunks pertinents uniquement
MAX_CHUNKS_CONTEXT   = 15      # Réduit de 35 → contexte plus compact
MAX_CHUNK_LENGTH     = 800     # Tronque chaque chunk à 800 chars (prévient débordement)
TOKEN_ESTIMATE_RATIO = 4       # 1 token ≈ 4 caractères (approximation)

# Prompt System (utilisé par les deux modèles)
SYSTEM_PROMPT = """Tu es un expert en IT et cybersécurité, assistant pour révision et formation.

RÈGLES STRICTES :
1. Réponds UNIQUEMENT avec l'information des notes fournies
2. Sois précis et factuel - pas d'improvisation
3. Cite la source quand pertinent (ex: "selon les notes du module X")
4. Pour questions techniques : donne définitions + cas d'usage + exemples concrets
5. Si information manquante/insuffisante : dis-le clairement avec ce qui manque
6. Structure avec titres (##), sous-sections courtes et puces pour clarté
7. Explique les acronymes (SSH = Secure Shell, TCP = Transmission Control Protocol)
8. Corrige les idées fausses poliment si tu les détectes
9. Évite les tableaux ASCII, les grands séparateurs et les pavés compacts
10. Préfère les listes à puces, les définitions courtes et les exemples concrets
11. Laisse une ligne vide entre les sections, et évite d’enchaîner trop d’idées dans le même bloc
12. Commence par un TL;DR de 3 points maximum si la réponse est longue
13. Respecte cet ordre quand c’est pertinent : TL;DR, objectif, définitions, architecture, actions, livrables, points clés
14. Si un tableau serait utile, transforme-le en cartes courtes clé → détail au lieu d’un tableau ASCII
15. Fais des cartes courtes quand tu listes des concepts, services, livrables ou missions
16. Garde chaque grande section bien séparée visuellement, avec un paragraphe ou une ligne vide entre elles
17. N’ajoute pas une deuxième section de résumé si tu as déjà un TL;DR
18. Évite les lignes trop longues dans les puces : une idée principale par puce
19. N’utilise jamais de tableaux ASCII alignés avec des espaces

TON STYLE :
- Clair et pédagogique (pour formation/révision)
- Formule en français correct
- Va du simple au complexe
- Mets un peu d’air visuel dans la réponse pour faciliter la lecture
- Ajoute "Points clés" en fin si utile"""
