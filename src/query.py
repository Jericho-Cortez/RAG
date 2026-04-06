# query.py - CORHack RAG CLI (multi-vault) ✅ Avec support PDF
import os
import re
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
from rich.console import Console, Group
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

ANSWER_THEME = {
    "tldr_border": "bright_green",
    "section_border_primary": "bright_cyan",
    "section_border_secondary": "bright_blue",
    "source_border": "bright_cyan",
    "panel_box": box.ROUNDED,
    "section_padding": (0, 2),
    "summary_padding": (0, 2),
    "source_padding": (0, 2),
}

current_graph = None

# GLOBAL CLEAN TEXT
def clean_text(text):
    if not isinstance(text, str):
        text = str(text)
    # Force round-trip UTF-8 to strip any invalid byte
    return text.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')


def normalize_display_text(text: str) -> str:
    """Nettoie le texte avant affichage Rich."""
    text = clean_text(text)
    text = re.sub(r"(?m)^\s*[─━―\-=]{10,}\s*$", "", text)
    text = re.sub(r"(?m)^(#{1,6}\s+)", r"\n\1", text)
    text = re.sub(r"(?m)^(\d+(?:\.\d+)*\.?\s+)", r"\n\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def highlight_acronyms(text: str) -> str:
    """Met en évidence les acronymes les plus utiles dans le rendu."""
    acronyms = [
        "PCA", "PRA", "HA", "NFS", "VM", "VMs", "API", "CPU", "RAM",
        "PDF", "CLI", "IDE", "TLS", "SSH", "TCP", "UDP", "LLM", "JSON",
        "DNS", "RAG", "LLMs"
    ]

    highlighted = text
    for acronym in acronyms:
        highlighted = re.sub(rf"\b{re.escape(acronym)}\b", f"**{acronym}**", highlighted)
    return highlighted


def clean_section_title(title: str) -> str:
    """Nettoie un titre avant affichage."""
    title = clean_text(title)
    title = re.sub(r"\*+", "", title)
    title = re.sub(r"`+", "", title)
    title = re.sub(r"^(#{1,6}\s+)", "", title)
    title = re.sub(r"^(\d+(?:\.\d+)*\.?\s+)", "", title)
    title = title.strip(" -–—:|")
    summary_aliases = {
        "tldr": "Résumé express",
        "tl;dr": "Résumé express",
        "points clés": "Points clés",
        "points cles": "Points clés",
        "résumé": "Résumé express",
        "resume": "Résumé express",
        "à retenir": "À retenir",
        "a retenir": "À retenir",
    }
    return summary_aliases.get(title.lower(), title or "Section")


def is_summary_title(title: str) -> bool:
    """Indique si le bloc correspond à un résumé."""
    normalized = title.lower()
    return normalized in {"résumé express", "points clés", "à retenir"}


def remove_leading_summary(text: str) -> str:
    """Supprime un éventuel résumé initial pour éviter le doublon avec le panneau TL;DR."""
    lines = normalize_display_text(text).splitlines()
    if not lines:
        return ""

    summary_heading = re.compile(r"^(?:#{1,6}\s+)?(?:tldr|tl;dr|résumé|resume|points clés|points cles|à retenir|a retenir)\b", re.IGNORECASE)
    bullet_pattern = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
    heading_pattern = re.compile(r"^(?:#{1,6}\s+|\d+(?:\.\d+)*\.?\s+)")

    start_index = None
    for index, line in enumerate(lines[:20]):
        if summary_heading.match(line.strip()):
            start_index = index
            break

    if start_index is None:
        return "\n".join(lines).strip()

    index = start_index + 1
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            break
        if heading_pattern.match(stripped) and not bullet_pattern.match(stripped):
            break
        index += 1

    while index < len(lines) and not lines[index].strip():
        index += 1

    return "\n".join(lines[index:]).strip()


def extract_tldr(text: str) -> list[str]:
    """Extrait jusqu'à trois idées clés pour un bloc TL;DR."""
    lines = normalize_display_text(text).splitlines()
    summary_lines: list[str] = []
    capture = False
    bullet_pattern = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
    heading_pattern = re.compile(r"^(?:#{1,6}\s+|\d+(?:\.\d+)*\.?\s+)")
    summary_heading = re.compile(r"^(?:#{1,6}\s+)?(?:tldr|tl;dr|points clés|points cles|résumé|resume|à retenir|a retenir)\b", re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if capture and summary_lines:
                break
            continue

        if summary_heading.match(stripped):
            capture = True
            continue

        if capture:
            if heading_pattern.match(stripped) and not bullet_pattern.match(stripped):
                break
            if bullet_pattern.match(stripped):
                summary_lines.append(bullet_pattern.sub("", stripped).strip())
            elif summary_lines:
                summary_lines[-1] = f"{summary_lines[-1]} {stripped}"
            if len(summary_lines) >= 3:
                break

    if summary_lines:
        return summary_lines[:3]

    for line in lines:
        stripped = line.strip()
        if bullet_pattern.match(stripped):
            summary_lines.append(bullet_pattern.sub("", stripped).strip())
        if len(summary_lines) >= 3:
            break

    return summary_lines[:3]


def guess_block_title(block: str, fallback_index: int) -> str:
    """Déduit un titre lisible pour un bloc de réponse."""
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        line = re.sub(r"^(#{1,6}\s+)", "", line)
        line = re.sub(r"^(\d+(?:\.\d+)*\.?\s+)", "", line)
        line = clean_section_title(line)
        if line:
            return line[:60]

    return f"Section {fallback_index}"


def is_table_like_block(block: str) -> bool:
    """Détecte les blocs qui ressemblent à des tableaux ou listes compactes."""
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if len(lines) < 3:
        return False

    pattern = re.compile(r"\s{2,}")
    table_like_lines = 0
    for line in lines:
        if line.startswith(("-", "•", "*", "1.", "1)", "2.", "2)")):
            continue
        if pattern.search(line) and len(line) >= 40:
            table_like_lines += 1

    return table_like_lines >= max(2, len(lines) // 2)


def split_table_cells(line: str) -> list[str]:
    """Découpe une ligne de tableau selon les séparateurs les plus probables."""
    if "|" in line:
        cells = [cell.strip() for cell in line.split("|")]
    else:
        cells = [cell.strip() for cell in re.split(r"\s{2,}", line)]
    return [cell for cell in cells if cell]


def parse_table_block(block: str) -> tuple[list[str] | None, list[list[str]]]:
    """Essaie d'extraire un en-tête et des lignes de données à partir d'un bloc compact."""
    rows: list[list[str]] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r"[─━―\-=]{5,}", line):
            continue

        cells = split_table_cells(line)
        if len(cells) >= 2:
            rows.append(cells)

    if len(rows) < 2:
        return None, rows

    header = None
    first_row = rows[0]
    if len(first_row) >= 3 and all(len(cell) <= 30 for cell in first_row):
        header = first_row
        rows = rows[1:]

    return header, rows


def classify_section_order(title: str, block: str, fallback_index: int) -> tuple[int, int]:
    """Classe les sections pour respecter un ordre plus logique à l'affichage."""
    text = f"{title}\n{block}".lower()

    sections = [
        ["résumé", "resume", "tldr", "tl;dr", "points clés", "points cles", "à retenir", "a retenir"],
        ["objectif", "présentation", "presentation", "objectif général", "objectif global"],
        ["définitions", "definitions", "concepts clés", "concepts cles", "acronymes"],
        ["architecture", "topologie", "composition", "architecture proposée"],
        ["actions", "tâches", "taches", "missions", "travaux", "déployer", "deployer"],
        ["livrables", "compétences", "competences", "résultats", "resultats"],
    ]

    for order, keywords in enumerate(sections, start=1):
        if any(keyword in text for keyword in keywords):
            return order, fallback_index

    return len(sections) + 1, fallback_index


def render_table_like_block(block: str, block_index: int):
    """Convertit un bloc de type tableau en vrai tableau Rich."""
    header, rows = parse_table_block(block)

    if not rows:
        return Panel(
            Markdown(highlight_acronyms(block)),
            title=f"📌 {guess_block_title(block, block_index)}",
            border_style=ANSWER_THEME["section_border_primary"],
            box=ANSWER_THEME["panel_box"],
            padding=ANSWER_THEME["section_padding"],
        )

    if header:
        table = Table(
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold cyan",
            expand=True,
            pad_edge=False,
            show_lines=False,
        )

        for column in header:
            table.add_column(highlight_acronyms(clean_section_title(column))[:28], overflow="fold")

        for row in rows:
            row_values = [highlight_acronyms(cell) for cell in row]
            if len(row_values) < len(header):
                row_values.extend([""] * (len(header) - len(row_values)))
            elif len(row_values) > len(header):
                row_values = row_values[: len(header) - 1] + [" ".join(row_values[len(header) - 1:])]
            table.add_row(*row_values)

        return Panel(
            table,
            title=f"📊 {clean_section_title(guess_block_title(block, block_index))}",
            border_style=ANSWER_THEME["section_border_primary"],
            box=ANSWER_THEME["panel_box"],
            padding=(0, 1),
        )

    bullets = []
    for row in rows:
        label = highlight_acronyms(row[0])
        value = " ".join(highlight_acronyms(cell) for cell in row[1:]).strip()
        if value:
            bullets.append(f"• **{label}** : {value}")
        else:
            bullets.append(f"• {label}")

    return Panel(
        Markdown("\n".join(bullets)),
        title=f"📌 {clean_section_title(guess_block_title(block, block_index))}",
        border_style=ANSWER_THEME["section_border_primary"],
        box=ANSWER_THEME["panel_box"],
        padding=ANSWER_THEME["section_padding"],
    )


def split_display_blocks(text: str) -> list[str]:
    """Découpe une réponse en blocs pour l'affichage."""
    lines = normalize_display_text(text).splitlines()
    blocks: list[list[str]] = []
    current_block: list[str] = []

    heading_pattern = re.compile(r"^(?:#{1,6}\s+|\d+(?:\.\d+)*\.?\s+)")

    for line in lines:
        stripped = line.strip()
        if heading_pattern.match(stripped) and current_block:
            blocks.append(current_block)
            current_block = [line]
        else:
            current_block.append(line)

    if current_block:
        blocks.append(current_block)

    return ["\n".join(block).strip() for block in blocks if any(line.strip() for line in block)]


def display_sources(sources: list[str]):
    """Affiche les sources dans un panneau compact."""
    unique_sources = []
    for source in sources:
        source = clean_text(source)
        if source not in unique_sources:
            unique_sources.append(source)

    if not unique_sources:
        return

    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    table.add_column("Sources", style="cyan")

    for source in unique_sources:
        table.add_row(f"• {source}")

    console.print(Panel(
        table,
        title=f"📎 Sources ({len(unique_sources)})",
        border_style=ANSWER_THEME["source_border"],
        box=ANSWER_THEME["panel_box"],
        padding=ANSWER_THEME["source_padding"],
    ))


def display_answer(full_response: str):
    """Affiche la réponse finale avec une mise en page plus propre."""
    body_text = remove_leading_summary(full_response)
    rendered_blocks = []

    tldr_items = extract_tldr(full_response)
    if tldr_items:
        tldr_text = "\n".join(f"• {highlight_acronyms(item)}" for item in tldr_items)
        rendered_blocks.append(Panel(
            Markdown(tldr_text),
            title="🧭 Résumé express",
            border_style=ANSWER_THEME["tldr_border"],
            box=ANSWER_THEME["panel_box"],
            padding=ANSWER_THEME["summary_padding"],
        ))

    rendered_blocks.append(Panel(
        Markdown(highlight_acronyms(body_text)),
        title="📌 Réponse",
        border_style=ANSWER_THEME["section_border_primary"],
        box=ANSWER_THEME["panel_box"],
        padding=ANSWER_THEME["section_padding"],
    ))

    console.print()
    console.print(*rendered_blocks, sep="\n\n")
    console.print()

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
            display_answer(full_response)
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
    
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan", pad_edge=False)
    table.add_column("Choix", style="green", width=7)
    table.add_column("Modèle", style="bold")
    table.add_column("Profil", style="dim")
    table.add_column("Débit", justify="right", style="magenta", width=8)
    table.add_row("1", MODEL_FAST['label'], MODEL_FAST['description'], f"{MODEL_FAST['tps']} tps")
    table.add_row("2", MODEL_PRECISE['label'], MODEL_PRECISE['description'], f"{MODEL_PRECISE['tps']} tps")

    console.print()
    console.print(Panel(
        table,
        title="Quel modèle veux-tu utiliser ?",
        border_style="cyan",
        padding=(0, 1),
    ))

    choice = Prompt.ask("  Modèle", choices=["1", "2"], default="2").strip()
    
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
                    display_sources(sources)
                    
                    answer = generate_answer(question, results, history, model_config)
                    history.append({"role": "user", "content": question})
                    history.append({"role": "assistant", "content": answer})
            except Exception as e:
                console.print(f"[red]❌ Erreur : {e}[/red]")

if __name__ == "__main__":
    run_cli()
