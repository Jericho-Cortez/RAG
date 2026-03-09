# config.py
import os

VAULT_PATH       = os.getenv("VAULT_PATH", r"C:\Users\jbcde\Documents\Dossier Obsidian\Perso\EHE")
COLLECTION_NAME  = os.getenv("COLLECTION_NAME", "ehe_notes")

QDRANT_URL       = "http://localhost:6333"
EMBED_MODEL      = "all-minilm:l6-v2"
EMBED_DIM        = 384
LLM_MODEL        = "llama-3.3-70b-versatile"
LLM_BASE_URL     = "https://api.groq.com/openai/v1"
LLM_API_KEY      = "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"

CHUNK_SIZE       = 300
CHUNK_OVERLAP    = 60

SYSTEM_PROMPT = """Tu es mon assistant de révision pour formation IT/cybersécurité.
Réponds UNIQUEMENT à partir des notes de cours fournies.
Explique clairement en français, avec des exemples concrets si possible.
Structure ta réponse avec des titres et des puces quand c'est utile.
Si l'information n'est pas dans les notes, dis-le clairement."""
