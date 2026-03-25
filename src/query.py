# query.py - CORHack RAG CLI (multi-vault) ✅ Avec support PDF
import os
import time
import sys
from collections import defaultdict
from pathlib import Path

# Add parent directory to path for root config.py imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import ollama
from qdrant_client import QdrantClient
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich import box
from openai import OpenAI
from config import *
from src.quiz import run_quiz, show_quiz_history
from src.knowledge_graph import run_graph_command, run_path_command, KnowledgeGraph

# Import des constantes d'optimisation
from config import MAX_CHUNKS_RETRIEVE, MAX_CHUNKS_CONTEXT, MAX_CHUNK_LENGTH, TOKEN_ESTIMATE_RATIO

# Import du générateur d'exercices SOC
try:
    from SOC_LAB.exo_soc_generator import (
        get_random_exercise, 
        format_exercise_display, 
        get_exercise_by_difficulty, 
        list_all_exercises,
        get_exercise_by_id
    )
    SOC_LAB_AVAILABLE = True
except ImportError:
    SOC_LAB_AVAILABLE = False


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
  [green]/switch[/green]    → Change vers un autre vault
  [green]/index[/green]     → Ré-indexe tout le vault
  [green]/status[/green]    → Affiche les stats de la base
  [green]/tags[/green]      → Liste tous les tags (triés par pertinence)
  [green]/quiz[/green]      → Lance un quiz de révision
  [green]/history[/green]   → Affiche l'historique des quiz
  [green]/graph[/green]     → Génère le graphe de connaissances
  [green]/path[/green]      → Trouve le chemin entre 2 concepts
  [green]/exo_soc[/green]   → 🆕 Génère un exercice SOC aléatoire
  [green]/clear[/green]     → Efface l'historique de session
  [green]/vault[/green]     → Affiche le vault actif
  [green]/quit[/green]      → Quitter

[bold cyan]Exercices SOC :[/bold cyan]
  [yellow]/exo_soc[/yellow]                    → Exercice aléatoire (Tous niveaux)
  [yellow]/exo_soc debutant[/yellow]          → Exercice niveau Débutant
  [yellow]/exo_soc intermediaire[/yellow]     → Exercice niveau Intermédiaire
  [yellow]/exo_soc avance[/yellow]            → Exercice niveau Avancé
  [yellow]/exo_soc show-solution[/yellow]     → Affiche la solution du dernier exo
  [yellow]/exo_soc list[/yellow]              → Liste tous les exercices disponibles

[bold cyan]Questions & Réponses :[/bold cyan]
  Tape ta question et choisis le modèle :
  [yellow]1[/yellow] ⚡ Llama 3.3 (Rapide & léger)
  [yellow]2[/yellow] 🎯 GPT-OSS 120B (Précis & détaillé)

[bold cyan]Graphe de Connaissances :[/bold cyan]
  [yellow]/graph[/yellow]              → Graphe de tous les concepts
  [yellow]/graph @Certification[/yellow] → Graphe filtré par tag
  [yellow]/path SSH Firewall[/yellow]   → Chemin entre deux concepts

[bold cyan]Tags :[/bold cyan]
  [yellow]/tags[/yellow]               → Tous les tags (triés par chunks)
  [yellow]/tags Dictionnaire[/yellow]  → Filtrer par mot-clé

[bold cyan]Mode Quiz :[/bold cyan]
  [yellow]/quiz[/yellow]                    → 10 questions (mode normal)
  [yellow]/quiz 20[/yellow]                → 20 questions
  [yellow]/quiz @Certification[/yellow]    → Quiz sur un tag spécifique
  [yellow]/quiz @Certification 10[/yellow] → 10 questions + tag
  [yellow]/quiz @tag chrono[/yellow]       → Mode chronométré (30s/question)
  [yellow]/quiz @tag revision[/yellow]     → Révise les erreurs précédentes
  [yellow]/quiz @tag moyen[/yellow]        → Difficulté moyenne
  [yellow]/quiz progressif[/yellow]        → Facile → Moyen → Difficile
  [yellow]/history[/yellow]                → Historique avec statistiques

[bold cyan]Exemples :[/bold cyan]
  /tags
  /tags Jour
  /graph @Certification
  /path TCP Firewall
  /quiz @Certification 10
  /quiz chrono 15
"""

def get_embedding(text: str) -> list[float]:
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]

def detect_long_query(query: str) -> tuple[bool, list[str]]:
    """🔍 Détecte si requête dépasse ~1500 tokens et la fragmente.**
    Retourne: (est_longue, fragments)
    """
    est_tokens = len(query) // TOKEN_ESTIMATE_RATIO
    
    if est_tokens <= 300:
        return False, [query]
    
    # Fragmenter aux points d'arrêt naturels (phrases, points-virgules, points)
    import re
    fragments = re.split(r'(?<=[.!?])\s+|(?<=;)\s+', query)
    
    chunks = []
    current = ""
    for frag in fragments:
        if (len(current) + len(frag)) // TOKEN_ESTIMATE_RATIO > 300:
            if current:
                chunks.append(current.strip())
            current = frag
        else:
            current += (" " if current else "") + frag
    if current:
        chunks.append(current.strip())
    
    console.print(f"[yellow]📋 Requête longue → fragmentée en {len(chunks)} sous-questions[/yellow]")
    return True, chunks if len(chunks) > 1 else [query]

def retrieve(query: str, top_k: int = None, tag_filter: str | None = None) -> list:
    # Par défaut : 25 chunks (optimisé pour limites contexte Groq)
    if top_k is None:
        top_k = MAX_CHUNKS_RETRIEVE
    
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
    
    # 🚀 OPTIMISATION : limiter à MAX_CHUNKS_CONTEXT et tronquer chaque chunk
    results = results[:MAX_CHUNKS_CONTEXT]
    context_parts = []
    total_chars = 0
    
    for i, r in enumerate(results):
        source = clean_text(r.payload['file'])
        tag = clean_text(r.payload['tag'])
        text = clean_text(r.payload['text'])
        
        # Tronquer si dépasse MAX_CHUNK_LENGTH
        if len(text) > MAX_CHUNK_LENGTH:
            text = text[:MAX_CHUNK_LENGTH] + "..."
        
        chunk = f"[Source: {source} | {tag}]\n{text}"
        context_parts.append(chunk)
        total_chars += len(chunk)
    
    context = "\n\n---\n\n".join(context_parts)
    
    # ⚠️ Avertir si contexte trop gros (dépasserait ~32k tokens)
    est_tokens = (len(clean_text(SYSTEM_PROMPT)) + len(query) + total_chars) // TOKEN_ESTIMATE_RATIO
    if est_tokens > 6000:
        console.print(f"[yellow]⚠️  Contexte volumineux (~{est_tokens} tokens estimés). Réponse peut être tronquée.[/yellow]")

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


def switch_vault():
    """Change vers un nouveau vault."""
    from rich.prompt import Prompt
    from pathlib import Path
    
    console.print("\n[bold cyan]Changement de Vault[/bold cyan]")
    new_path = Prompt.ask("  Nouveau chemin du vault").strip()
    
    # Valider le chemin
    path_obj = Path(new_path)
    if not path_obj.exists():
        console.print(f"[red]❌ Dossier inexistant : {new_path}[/red]")
        return False
    
    if not path_obj.is_dir():
        console.print(f"[red]❌ Ce n'est pas un dossier : {new_path}[/red]")
        return False
    
    # Vérifier qu'il y a au moins des fichiers .md ou .pdf
    md_files = list(path_obj.rglob("*.md"))
    pdf_files = list(path_obj.rglob("*.pdf"))
    
    if not md_files and not pdf_files:
        console.print(f"[yellow]⚠ Aucun fichier .md ou .pdf trouvé dans ce dossier[/yellow]")
        force = Prompt.ask("  Forcer le changement quand même ? (o/N)", choices=["o", "n"], default="n")
        if force != "o":
            return False
    
    # Mettre à jour les variables globales
    global VAULT_PATH, COLLECTION_NAME, client
    
    old_path = VAULT_PATH
    old_collection = COLLECTION_NAME
    
    VAULT_PATH = str(path_obj)
    vault_name = path_obj.name.replace(' ', '_').replace('(', '').replace(')', '')
    COLLECTION_NAME = f"obsidian_{vault_name}"
    
    console.print(f"[green]✓ Nouveau vault :[/green] [bold]{vault_name}[/bold]")
    console.print(f"[green]✓ Chemin :[/green] {VAULT_PATH}")
    console.print(f"[green]✓ Collection :[/green] {COLLECTION_NAME}")
    
    # Vérifier si la collection existe
    try:
        collection_info = client.get_collection(COLLECTION_NAME)
        console.print(f"[cyan]📊 Collection existante : {collection_info.points_count} chunks[/cyan]")
    except Exception as e:
        console.print(f"[yellow]⚠ Collection inexistante - indexe d'abord avec /index[/yellow]")
    
    console.print("[green]✓ Vault changé avec succès ![/green]\n")
    return True

def show_tags(search_keyword: str = None):
    """Affiche les tags avec statistiques, triés par pertinence."""
    try:
        from qdrant_client.models import ScrollRequest
        
        # Récupère tous les points pour extraire les statistiques de tags
        scroll_result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=10000,
            with_payload=True
        )
        
        # Agrégation des statistiques par tag
        tag_stats = defaultdict(lambda: {"count": 0, "files": set()})
        
        for point in scroll_result[0]:
            if 'tag' in point.payload:
                tag = clean_text(point.payload['tag'])
                tag_stats[tag]["count"] += 1
                if 'file' in point.payload:
                    tag_stats[tag]["files"].add(point.payload['file'])
        
        if not tag_stats:
            console.print("[yellow]⚠️ Aucun tag trouvé[/yellow]")
            return
        
        # Filtre si recherche
        if search_keyword:
            tag_stats = {k: v for k, v in tag_stats.items() if search_keyword.lower() in k.lower()}
            if not tag_stats:
                console.print(f"[yellow]⚠️ Aucun tag trouvé pour '{search_keyword}'[/yellow]")
                return
        
        # Trie par pertinence (nombre de chunks décroissant)
        sorted_tags = sorted(tag_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        
        # Tableau de résultats
        table = Table(title="📑 Tags par pertinence", box=box.ROUNDED, style="cyan")
        table.add_column("Rang", style="dim", width=5)
        table.add_column("Tag", style="bold yellow")
        table.add_column("Chunks", style="green", width=10)
        table.add_column("Fichiers", style="blue", width=12)
        table.add_column("Pertinence", style="magenta", width=15)
        
        total_chunks = sum(v["count"] for v in tag_stats.values())
        
        for idx, (tag, stats) in enumerate(sorted_tags, 1):
            chunk_count = stats["count"]
            file_count = len(stats["files"])
            percentage = (chunk_count / total_chunks) * 100
            
            # Barre de pertinence
            bar_length = 10
            filled = int((percentage / 100) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            pertinence = f"{bar} {percentage:.1f}%"
            
            # Emojis de pertinence
            if percentage >= 20:
                rank_emoji = "🔥"
            elif percentage >= 10:
                rank_emoji = "⭐"
            else:
                rank_emoji = "📌"
            
            table.add_row(
                f"{rank_emoji} {idx}",
                f"@{tag}",
                str(chunk_count),
                str(file_count),
                pertinence
            )
        
        console.print(table)
        
        # Résumé
        console.print(f"\n[dim]Total : {len(sorted_tags)} tags | {total_chunks} chunks[/dim]")
        
        # Suggestions de commandes
        top_tags = [tag for tag, _ in sorted_tags[:3]]
        if top_tags:
            console.print(f"\n[bold cyan]💡 Suggestions :[/bold cyan]")
            for tag in top_tags:
                console.print(f"  [yellow]/quiz @{tag}[/yellow] → Quiz sur {tag}")
    
    except Exception as e:
        console.print(f"[red]❌ Erreur : {e}[/red]")

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
    
    # Variable pour stocker le dernier exercice générés
    last_exercise = None

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
        elif user_input.startswith("/tags"):
            # Parse : /tags ou /tags @keyword
            parts = user_input.split()
            search_keyword = None
            if len(parts) > 1:
                search_keyword = parts[1].lstrip("@")
            show_tags(search_keyword)
        elif user_input == "/help":
            console.print(HELP_TEXT)
        elif user_input == "/status":
            show_status()
        elif user_input == "/vault":
            console.print(f"[cyan]📁 Vault actif : {clean_text(VAULT_PATH)}[/cyan]")
            console.print(f"[cyan]🗄  Collection  : {COLLECTION_NAME}[/cyan]")
        elif user_input == "/switch":
            if switch_vault():
                # Recharger le panel d'info avec le nouveau vault
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
                history.clear()  # Effacer l'historique du vault précédent
                console.print("[dim]📝 Historique effacé[/dim]")
        elif user_input == "/clear":
            history.clear()
            console.clear()
            console.print("[green]✓ Historique effacé[/green]")
        elif user_input == "/index":
            console.print("[yellow]🔄 Lancement de l'indexation...[/yellow]")
            try:
                from ingest import ingest_vault
                ingest_vault(VAULT_PATH, COLLECTION_NAME)
                console.print("[green]✓ Indexation terminée ![/green]")
            except Exception as e:
                console.print(f"[red]❌ Erreur lors de l'indexation : {e}[/red]")
        elif user_input.startswith("/quiz"):
            # Parse la commande : /quiz [@tag] [nombre] [mode] [difficulté]
            parts = user_input.split()
            tag_filter = None
            num_questions = 10
            mode = "normal"  # normal, chrono, revision
            difficulty = "progressif"  # progressif, uniforme, facile, moyen, difficile

            for part in parts[1:]:
                if part.startswith("@"):
                    tag_filter = part[1:].strip('"')
                elif part.isdigit():
                    num_questions = int(part)
                elif part in ["chrono", "revision"]:
                    mode = part
                elif part in ["progressif", "uniforme", "facile", "moyen", "difficile"]:
                    difficulty = part

            console.print(f"[cyan]🎯 Lancement du quiz : {num_questions} questions[/cyan]")
            if tag_filter:
                console.print(f"[cyan]🏷️  Tag : {tag_filter}[/cyan]")
            console.print(f"[cyan]Mode : {mode} | Difficulté : {difficulty}[/cyan]\n")

            try:
                run_quiz(tag_filter, num_questions, mode=mode, difficulty=difficulty)
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

        elif user_input.startswith("/exo_soc"):
            # Commande: /exo_soc [debutant|intermediaire|avance|show-solution|list|ID]
            if not SOC_LAB_AVAILABLE:
                console.print("[red]❌ SOC Lab non disponible. Vérifie que exo_soc_generator.py existe.[/red]")
                continue
            
            parts = user_input.split()
            command = parts[1].lower() if len(parts) > 1 else None
            
            try:
                if command == "list":
                    # Afficher tous les exercices
                    console.print(Panel(
                        list_all_exercises(),
                        title="📚 Exercices Disponibles",
                        style="cyan"
                    ))
                elif command == "show-solution":
                    # Afficher la solution du dernier exercice (gardé en mémoire)
                    if last_exercise:
                        console.print(Panel(
                            format_exercise_display(last_exercise, show_solution=True),
                            title="✅ Solution de l'Exercice",
                            style="green"
                        ))
                    else:
                        console.print("[yellow]⚠️  Aucun exercice en mémoire. Fais /exo_soc d'abord.[/yellow]")
                elif command in ["debutant", "intermediaire", "avance"]:
                    # Exercice de niveau spécifique
                    exercise = get_exercise_by_difficulty(
                        "Débutant" if command == "debutant" else
                        "Intermédiaire" if command == "intermediaire" else
                        "Avancé"
                    )
                    last_exercise = exercise
                    console.print(Panel(
                        format_exercise_display(exercise),
                        title=f"🎯 Exercice {exercise['difficulty']}",
                        style="yellow"
                    ))
                    console.print("[dim]Tape /exo_soc show-solution pour voir la solution[/dim]")
                elif command and "_" in command:
                    # Chercher par ID (format: RANSOMWARE_001, LATERAL_001, etc.)
                    exercise = get_exercise_by_id(command)
                    if "error" not in exercise:
                        last_exercise = exercise
                        console.print(Panel(
                            format_exercise_display(exercise),
                            title=f"🎯 Exercice ID: {exercise['id']}",
                            style="blue"
                        ))
                        console.print("[dim]Tape /exo_soc show-solution pour voir la solution[/dim]")
                    else:
                        console.print(f"[red]{exercise['error']}[/red]")
                else:
                    # Exercice aléatoire
                    exercise = get_random_exercise()
                    last_exercise = exercise
                    console.print(Panel(
                        format_exercise_display(exercise),
                        title=f"🎯 Exercice Aléatoire - {exercise['difficulty']}",
                        style="magenta"
                    ))
                    console.print("[dim]Tape /exo_soc show-solution pour voir la solution[/dim]")
            except Exception as e:
                console.print(f"[red]❌ Erreur exercice : {e}[/red]")

        else:
            tag_filter, question = parse_filter(user_input)
            if tag_filter:
                console.print(f"[dim]🔍 Filtre : [bold]{tag_filter}[/bold][/dim]")
            try:
                # 🔍 Détecter si requête est trop longue
                is_long, fragments = detect_long_query(question)
                
                # Sélectionner le modèle UNE FOIS
                model_type, model_config = select_model()
                
                if is_long and len(fragments) > 1:
                    # Fragmenter la requête
                    combined_answer = ""
                    for idx, fragment in enumerate(fragments, 1):
                        console.print(f"\\n[cyan]Fragment {idx}/{len(fragments)}...[/cyan]")
                        results = retrieve(fragment, tag_filter=tag_filter)
                        if not results:
                            console.print("[yellow]⚠ Aucun chunk trouvé pour ce fragment.[/yellow]")
                            continue
                        
                        answer = generate_answer(fragment, results, history, model_config)
                        combined_answer += f"\\n**Partie {idx}:**\\n{answer}"
                    
                    console.print(f"\\n[green]✓ Tous les fragments traités[/green]")
                    history.append({"role": "user", "content": question})
                    history.append({"role": "assistant", "content": combined_answer})
                else:
                    # Question courte : traitement normal
                    results = retrieve(question, tag_filter=tag_filter)
                    if not results:
                        console.print("[yellow]⚠ Aucun chunk trouvé. Lance /index d'abord.[/yellow]")
                        continue
                    sources = list({clean_text(r.payload['file']) for r in results})
                    console.print(f"[dim]📎 Sources : {', '.join(sources)}[/dim]")
                    
                    answer = generate_answer(question, results, history, model_config)
                    history.append({"role": "user", "content": question})
                    history.append({"role": "assistant", "content": answer})
            except Exception as e:
                console.print(f"[red]❌ Erreur : {e}[/red]")

if __name__ == "__main__":
    run_cli()
