# query.py - CORHack RAG CLI (multi-vault) ✅ Avec support PDF
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
from quiz import run_quiz, show_quiz_history
from knowledge_graph import run_graph_command, run_path_command, KnowledgeGraph


# FIX UTF-8 STDOUT
sys.stdout.reconfigure(encoding='utf-8')

# Env vars écrasent config.py si définies
VAULT_PATH      = os.getenv("VAULT_PATH", VAULT_PATH)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", COLLECTION_NAME)

console = Console()
client  = QdrantClient(url=QDRANT_URL)

STYLE = Style.from_dict({"prompt": "#00d7ff bold"})

current_graph = None

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
  [green]/tags[/green]      → Liste tous les tags disponibles
  [green]/quiz[/green]      → Lance un quiz de révision
  [green]/history[/green]   → Affiche l'historique des quiz
  [green]/graph[/green]     → Génère le graphe de connaissances
  [green]/path[/green]      → Trouve le chemin entre 2 concepts
  [green]/clear[/green]     → Efface l'historique de session
  [green]/vault[/green]     → Affiche le vault actif
  [green]/quit[/green]      → Quitter

[bold cyan]Questions & Réponses :[/bold cyan]
  Tape ta question et choisis le modèle :
  [yellow]1[/yellow] ⚡ Llama 3.3 (Rapide & léger)
  [yellow]2[/yellow] 🎯 GPT-OSS 120B (Précis & détaillé)

[bold cyan]Graphe de Connaissances :[/bold cyan]
  [yellow]/graph[/yellow]              → Graphe de tous les concepts
  [yellow]/graph @Certification[/yellow] → Graphe filtré par tag
  [yellow]/path SSH Firewall[/yellow]   → Chemin entre deux concepts

[bold cyan]Mode Quiz :[/bold cyan]
  [yellow]/quiz[/yellow]              → 10 questions aléatoires
  [yellow]/quiz 20[/yellow]           → 20 questions aléatoires
  [yellow]/quiz @Certification[/yellow] → Quiz sur un tag spécifique

[bold cyan]Exemples :[/bold cyan]
  /graph @Certification
  /path TCP Firewall
  /quiz @Certification 10
"""

def get_embedding(text: str) -> list[float]:
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]

def retrieve(query: str, top_k: int = None, tag_filter: str | None = None) -> list:
    # Par défaut : 40 chunks pour une meilleure couverture
    if top_k is None:
        top_k = 40
    
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

def generate_answer(query: str, results: list, history: list, model_config: dict = None) -> str:
    # Utiliser le modèle précis par défaut si non spécifié
    if model_config is None:
        model_config = MODEL_PRECISE
    
    # Utiliser jusqu'à 35 contextes
    results = results[:35]
    context = "\n\n---\n\n".join(
        f"[Source: {clean_text(r.payload['file'])} | {clean_text(r.payload['tag'])}]\n{clean_text(r.payload['text'])}"
        for i, r in enumerate(results)
    )

    query = clean_text(query)
    context = clean_text(context)
    messages = [{"role": "system", "content": clean_text(SYSTEM_PROMPT)}]
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": clean_text(msg["content"])})
    messages.append({"role": "user", "content": f"Question: {query}\n\n{context}"})

    llm_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    model_label = model_config['label']
    console.print(f"[bold]🤖 {model_label} : génération en cours...[/bold]")

    temp = model_config['temperature']
    max_tokens = model_config['max_tokens']
    model_name = model_config['name']

    for attempt in range(5):
        try:
            stream = llm_client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True,
                temperature=temp,
                max_tokens=max_tokens
            )
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
        from qdrant_client.models import ScrollRequest
        
        collection_info = client.get_collection(COLLECTION_NAME)
        console.print(f"[cyan]✓ Collection : {COLLECTION_NAME}[/cyan]")
        console.print(f"[cyan]  Points (chunks) : {collection_info.points_count}[/cyan]")
        
        # Compte les sources (MD vs PDF)
        scroll_result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            with_payload=True
        )
        
        md_count = 0
        pdf_count = 0
        for point in scroll_result[0]:
            if 'file' in point.payload:
                if point.payload['file'].endswith('.pdf'):
                    pdf_count += 1
                else:
                    md_count += 1
        
        if md_count > 0:
            console.print(f"[cyan]  📋 Fichiers Markdown : {md_count} chunks[/cyan]")
        if pdf_count > 0:
            console.print(f"[cyan]  📄 Fichiers PDF : {pdf_count} chunks[/cyan]")
    except Exception as e:
        console.print(f"[red]Erreur stats : {e}[/red]")

def parse_filter(user_input: str):
    import re
    # Gère @tag ou @"tag avec espaces"
    match = re.match(r'^@(?:"([^"]+)"|(\S+))\s+(.*)', user_input.strip())
    if match:
        # group(1) = tag entre guillemets, group(2) = tag sans guillemets
        tag = match.group(1) or match.group(2)
        question = match.group(3).strip()
        return tag, question
    return None, user_input.strip()


def select_model():
    """Dialogue interactif pour sélectionner le modèle."""
    from rich.prompt import Prompt
    
    console.print("\n[bold cyan]Quel modèle veux-tu utiliser ?[/bold cyan]")
    console.print(f"  [green]1[/green] {MODEL_FAST['label']}")
    console.print(f"     └─ {MODEL_FAST['description']} ({MODEL_FAST['tps']} tps)")
    console.print(f"  [green]2[/green] {MODEL_PRECISE['label']}")
    console.print(f"     └─ {MODEL_PRECISE['description']} ({MODEL_PRECISE['tps']} tps)")
    
    choice = Prompt.ask("  Choix", choices=["1", "2"], default="2").strip()
    
    if choice == "1":
        return "fast", MODEL_FAST
    else:
        return "precise", MODEL_PRECISE

def show_tags():
    """Affiche tous les tags disponibles dans la collection."""
    try:
        # Récupère un échantillon de points pour extraire les tags uniques
        from qdrant_client.models import ScrollRequest
        
        scroll_result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            with_payload=True
        )
        
        tags = set()
        for point in scroll_result[0]:
            if 'tag' in point.payload:
                tags.add(clean_text(point.payload['tag']))
        
        if tags:
            console.print("[bold cyan]📑 Tags disponibles :[/bold cyan]")
            for tag in sorted(tags):
                console.print(f"  [green]@{tag}[/green]")
        else:
            console.print("[yellow]⚠ Aucun tag trouvé[/yellow]")
    except Exception as e:
        console.print(f"[red]Erreur : {e}[/red]")

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
        elif user_input == "/tags":
            show_tags()
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
            try:
                from ingest import ingest_vault
                ingest_vault()
                console.print("[green]✓ Indexation terminée ![/green]")
            except Exception as e:
                console.print(f"[red]❌ Erreur lors de l'indexation : {e}[/red]")
        elif user_input.startswith("/quiz"):
            # Parse la commande : /quiz [@tag] [nombre]
            parts = user_input.split()
            tag_filter = None
            num_questions = 10

            for part in parts[1:]:
                if part.startswith("@"):
                    tag_filter = part[1:].strip('"')
                elif part.isdigit():
                    num_questions = int(part)

            console.print(f"[cyan]🎯 Lancement du quiz : {num_questions} questions[/cyan]")
            if tag_filter:
                console.print(f"[cyan]🏷️  Tag : {tag_filter}[/cyan]\n")

            try:
                run_quiz(tag_filter, num_questions)
            except Exception as e:
                console.print(f"[red]❌ Erreur quiz : {e}[/red]")

        elif user_input == "/history":
            show_quiz_history()

        elif user_input.startswith("/graph"):
            parts = user_input.split()
            tag_filter = None

            for part in parts[1:]:
                if part.startswith("@"):
                    tag_filter = part[1:].strip('"')

            try:
                global current_graph
                current_graph = run_graph_command([f"@{tag_filter}"] if tag_filter else [])
            except Exception as e:
                console.print(f"[red]❌ Erreur graphe : {e}[/red]")

        elif user_input.startswith("/path"):
            parts = user_input.split(maxsplit=2)

            if len(parts) < 3:
                console.print("[yellow]Usage : /path Concept1 Concept2[/yellow]")
                continue
            
            entity1 = parts[1]
            entity2 = parts[2]

            try:
                run_path_command(entity1, entity2, current_graph)
            except Exception as e:
                console.print(f"[red]❌ Erreur : {e}[/red]")

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
                
                # Sélectionner le modèle
                model_type, model_config = select_model()
                
                answer = generate_answer(question, results, history, model_config)
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": answer})
            except Exception as e:
                console.print(f"[red]❌ Erreur : {e}[/red]")

if __name__ == "__main__":
    run_cli()
