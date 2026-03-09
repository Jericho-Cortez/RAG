# query.py - CORHack RAG CLI (multi-vault) ✅ FIX UNICODE FINAL
import os
import time
import sys
import ollama
from qdrant_client import QdrantClient
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich import box
from openai import OpenAI
from config import *

# FIX UTF-8 STDOUT
sys.stdout.reconfigure(encoding='utf-8')

# Env vars écrasent config.py si définies
VAULT_PATH      = os.getenv("VAULT_PATH", VAULT_PATH)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", COLLECTION_NAME)

console = Console()
client  = QdrantClient(url=QDRANT_URL)

STYLE = Style.from_dict({"prompt": "#00d7ff bold"})

# GLOBAL CLEAN TEXT
def clean_text(text):
    if not isinstance(text, str):
        text = str(text)
    # Force round-trip UTF-8 to strip any invalid byte
    return text.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')

HELP_TEXT = """
[bold cyan]Commandes disponibles :[/bold cyan]
  [green]/help[/green]      → Affiche cette aide
  [green]/index[/green]     → Ré-indexe tout le vault
  [green]/status[/green]    → Affiche les stats de la base
  [green]/clear[/green]     → Efface l'historique de session
  [green]/vault[/green]     → Affiche le vault actif
  [green]/quit[/green]      → Quitter

[bold cyan]Filtrage par tag (préfixe @) :[/bold cyan]
  [yellow]@Certification[/yellow] ta question
  [yellow]@"Jour 1"[/yellow] ta question
  [yellow]@QCM[/yellow] ta question

[bold cyan]Exemples :[/bold cyan]
  @Certification Explique les attaques réseau module 6
  Quelle est la différence entre vulnérabilité et menace ?
"""

def get_embedding(text: str) -> list[float]:
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]

def retrieve(query: str, top_k: int = 35, tag_filter: str | None = None) -> list:
    query_vec = get_embedding(query)

    filter_param = None
    if tag_filter:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        filter_param = Filter(
            must=[FieldCondition(key="tag", match=MatchValue(value=tag_filter))]
        )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=top_k,
        with_payload=True,
        query_filter=filter_param,
    )
    return results.points

def generate_answer(query: str, results: list, history: list) -> str:
    results = results[:20]
    context = "\n\n---\n\n".join(
        f"[Note {i+1}] {clean_text(r.payload['file'])} | {clean_text(r.payload['tag'])}\n{clean_text(r.payload['text'])}"
        for i, r in enumerate(results)
    )

    query = clean_text(query)
    context = clean_text(context)
    messages = [{"role": "system", "content": clean_text(SYSTEM_PROMPT)}]
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": clean_text(msg["content"])})
    messages.append({"role": "user", "content": f"Question: {query}\n\n{context}"})

    llm_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    console.print("[bold]🤖 Assistant : génération en cours...[/bold]")

    for attempt in range(5):
        try:
            stream = llm_client.chat.completions.create(model=LLM_MODEL, messages=messages, stream=True)
            full_response = ""
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                full_response += token
            console.print()
            console.print(Markdown(clean_text(full_response)))
            console.print()
            return full_response
        except Exception as e:
            if "429" in str(e) and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            console.print(f"[red]Erreur LLM: {e}[/red]")
            return "Erreur lors de la génération. Vérifie ta clé API Groq."
def show_status():
    """Affiche les stats de la base Qdrant."""
    try:
        collection_info = client.get_collection(COLLECTION_NAME)
        console.print(f"[cyan]✓ Collection : {COLLECTION_NAME}[/cyan]")
        console.print(f"[cyan]  Points (chunks) : {collection_info.points_count}[/cyan]")
    except Exception as e:
        console.print(f"[red]Erreur stats : {e}[/red]")
def parse_filter(user_input: str):
    import re
    match = re.match(r'^@(\S+|".+?")\s+(.*)', user_input.strip())
    if match:
        tag = match.group(1).strip('"')
        question = match.group(2).strip()
        return tag, question
    return None, user_input.strip()

def run_cli():
    history = []
    vault_name = os.path.basename(VAULT_PATH.rstrip("\\/"))

    console.print(Panel(
        f"[bold white]CORHack RAG[/bold white]\n"
        f"[cyan]Vault actif :[/cyan] [bold]{clean_text(vault_name)}[/bold]\n"
        f"[dim]Chemin complet :[/dim] [gray]{clean_text(VAULT_PATH.replace('\\', '/'))}[/gray]\n"
        f"[dim]Collection  : {COLLECTION_NAME}[/dim]\n"
        f"[dim]Tape [bold]/help[/bold] pour les commandes[/dim]",
        box=box.DOUBLE_EDGE,
        style="bold cyan"
    ))

    session = PromptSession(style=STYLE)

    while True:
        try:
            user_input = session.prompt(HTML("<prompt>❯ Tu : </prompt>")).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]👋 À bientôt ![/yellow]")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            console.print("[yellow]👋 À bientôt ![/yellow]")
            break
        elif user_input == "/help":
            console.print(HELP_TEXT)
        elif user_input == "/status":
            show_status()
        elif user_input == "/vault":
            console.print(f"[cyan]📁 Vault actif : {clean_text(VAULT_PATH)}[/cyan]")
            console.print(f"[cyan]🗄  Collection  : {COLLECTION_NAME}[/cyan]")
        elif user_input == "/clear":
            history.clear()
            console.clear()
            console.print("[green]✓ Historique effacé[/green]")
        elif user_input == "/index":
            console.print("[yellow]🔄 Lancement de l'indexation...[/yellow]")
            import subprocess
            subprocess.run(["python", "ingest.py"])
            console.print("[green]✓ Indexation terminée ![/green]")
        else:
            tag_filter, question = parse_filter(user_input)
            if tag_filter:
                console.print(f"[dim]🔍 Filtre : [bold]{tag_filter}[/bold][/dim]")
            try:
                results = retrieve(question, top_k=35, tag_filter=tag_filter)
                if not results:
                    console.print("[yellow]⚠ Aucun chunk trouvé. Lance /index d'abord.[/yellow]")
                    continue
                sources = list({clean_text(r.payload['file']) for r in results})
                console.print(f"[dim]📎 Sources : {', '.join(sources)}[/dim]")
                answer = generate_answer(question, results, history)
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": answer})
            except Exception as e:
                console.print(f"[red]❌ Erreur : {e}[/red]")

if __name__ == "__main__":
    run_cli()
