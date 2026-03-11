# config.py - CORHack RAG Configuration
import os

VAULT_PATH       = os.getenv("VAULT_PATH", r"C:\Users\jbcde\Documents\Dossier Obsidian\Perso\EHE")
COLLECTION_NAME  = os.getenv("COLLECTION_NAME", "ehe_notes")

# Qdrant Vector DB
QDRANT_URL       = "http://localhost:6333"
EMBED_MODEL      = "all-minilm:l6-v2"
EMBED_DIM        = 384

# LLM (Groq Cloud) - DUAL MODEL SETUP
# Une seule clé API pour les 2 modèles !
LLM_BASE_URL        = "https://api.groq.com/openai/v1"
LLM_API_KEY         = "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"

# ⚡ MODÈLE RAPIDE (par défaut)
MODEL_FAST = {
    "name": "llama-3.3-70b-versatile",
    "label": "⚡ Llama 3.3 70B (Rapide)",
    "temperature": 0.5,
    "max_tokens": 2048,
    "tps": 280,
    "description": "Réponses rapides et directes"
}

# 🎯 MODÈLE PRÉCIS
MODEL_PRECISE = {
    "name": "openai/gpt-oss-120b",
    "label": "🎯 GPT-OSS 120B (Précis)",
    "temperature": 0.3,
    "max_tokens": 4096,
    "tps": 500,
    "description": "Réponses détaillées et rigoureuses"
}

# Défaut
LLM_MODEL_DEFAULT = "precise"  # "fast" ou "precise"

# Chunking (pour Markdown ET PDF)
# Réduit à 200 pour respecter la limite du modèle d'embedding (all-minilm:l6-v2 = ~256 tokens)
CHUNK_SIZE          = 200
CHUNK_OVERLAP       = 40

# Support des formats
# - Markdown (.md) : traités par défaut
# - PDF (.pdf) : extraction via PyMuPDF ou PyPDF2

# Prompt System (utilisé par les deux modèles)
SYSTEM_PROMPT = """Tu es un expert en IT et cybersécurité, assistant pour révision et formation.

RÈGLES STRICTES :
1. Réponds UNIQUEMENT avec l'information des notes fournies
2. Sois précis et factuel - pas d'improvisation
3. Cite la source quand pertinent (ex: "selon les notes du module X")
4. Pour questions techniques : donne définitions + cas d'usage + exemples concrets
5. Si information manquante/insuffisante : dis-le clairement avec ce qui manque
6. Structure avec titres (##) et puces pour clarté
7. Explique les acronymes (SSH = Secure Shell, TCP = Transmission Control Protocol)
8. Corrige les idées fausses poliment si tu les détectes

TON STYLE :
- Clair et pédagogique (pour formation/révision)
- Formule en français correct
- Va du simple au complexe
- Ajoute "Points clés" en fin si utile"""
