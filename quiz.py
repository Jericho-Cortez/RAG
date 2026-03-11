# quiz.py - Module Quiz Avancé pour CORHack RAG
import random
import json
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from qdrant_client import QdrantClient
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table
from rich import box
from openai import OpenAI
from config import *

console = Console()

def clean_text(text):
    """Nettoyage UTF-8."""
    if not isinstance(text, str):
        text = str(text)
    return text.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')

def retrieve_chunks_by_tag(client: QdrantClient, tag: str, limit: int = 50):
    """Récupère des chunks aléatoires pour un tag donné."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue, ScrollRequest
    
    filter_param = Filter(
        must=[FieldCondition(key="tag", match=MatchValue(value=tag))]
    )
    
    scroll_result = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=filter_param,
        limit=limit,
        with_payload=True
    )
    
    return scroll_result[0]  # Retourne la liste de points

def generate_question(llm_client: OpenAI, context: str, difficulty: str = "moyen") -> dict:
    """Génère une question QCM avec niveau de difficulté."""
    
    difficulty_prompts = {
        "facile": "Génère une question FACILE testant les concepts de base.",
        "moyen": "Génère une question MOYENNE testant la compréhension.",
        "difficile": "Génère une question DIFFICILE testant l'analyse et la synthèse."
    }
    
    prompt = f"""À partir de ce contenu de cours, génère UNE question QCM de révision.
{difficulty_prompts.get(difficulty, difficulty_prompts['moyen'])}

CONTENU DU COURS :
{context}

FORMAT REQUIS (JSON strict) :
{{
  "question": "Question claire et précise",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct": 0,
  "explanation": "Explication détaillée de la bonne réponse",
  "difficulty": "{difficulty}"
}}

RÈGLES :
- Question claire et précise
- 4 options réalistes (A, B, C, D)
- "correct" est l'index (0-3) de la bonne réponse
- Explication pédagogique (2-3 phrases)
- JSON valide uniquement, sans commentaires

Réponds UNIQUEMENT avec le JSON, rien d'autre."""

    try:
        response = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "Tu es un générateur de QCM éducatif. Réponds uniquement en JSON valide."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=650
        )
        
        content = response.choices[0].message.content.strip()
        
        # Nettoie les balises markdown si présentes
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        
        question_data = json.loads(content)
        
        # Validation
        required_keys = ["question", "options", "correct", "explanation"]
        if not all(k in question_data for k in required_keys):
            raise ValueError("JSON incomplet")
        
        if len(question_data["options"]) != 4:
            raise ValueError("Pas exactement 4 options")
        
        if not (0 <= question_data["correct"] <= 3):
            raise ValueError("Index correct invalide")
        
        question_data["difficulty"] = difficulty
        return question_data
        
    except Exception as e:
        console.print(f"[red]❌ Erreur génération question: {str(e)[:60]}[/red]")
        return None

def run_quiz(tag_filter: str = None, num_questions: int = 10, mode: str = "normal", difficulty: str = "progressif"):
    """
    Lance un quiz interactif avec plusieurs modes.
    
    Modes :
    - normal : Quiz standard
    - chrono : Quiz chronométré (30s par question)
    - revision : Review des erreurs précédentes
    
    Difficultés :
    - progressif : Facile → Moyen → Difficile
    - uniforme : Toutes les questions du même niveau
    - facile/moyen/difficile : Un seul niveau
    """
    
    client = QdrantClient(url=QDRANT_URL)
    llm_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    
    # Mode révision
    if mode == "revision":
        review_missed_questions(tag_filter)
        return
    
    # Récupère des chunks
    console.print(f"[cyan]🔍 Récupération de contenu pour le quiz...[/cyan]")
    
    if tag_filter:
        chunks = retrieve_chunks_by_tag(client, tag_filter, limit=num_questions * 3)
    else:
        from qdrant_client.models import ScrollRequest
        scroll_result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=num_questions * 3,
            with_payload=True
        )
        chunks = scroll_result[0]
    
    if not chunks:
        console.print("[red]❌ Aucun contenu trouvé pour générer le quiz[/red]")
        return
    
    console.print(f"[green]✓ {len(chunks)} chunks récupérés[/green]")
    
    # Sélectionne des chunks variés
    random.shuffle(chunks)
    selected_chunks = chunks[:num_questions]
    
    # Définit les difficultés
    if difficulty == "progressif":
        difficulties = ["facile"] * (num_questions // 3) + ["moyen"] * (num_questions // 3) + ["difficile"] * (num_questions - 2 * (num_questions // 3))
    else:
        difficulties = [difficulty] * num_questions
    random.shuffle(difficulties)
    
    # Génère les questions
    console.print(f"[cyan]🧠 Génération de {num_questions} questions ({difficulty})...[/cyan]\n")
    
    questions = []
    with Progress() as progress:
        task = progress.add_task("[cyan]Génération...", total=num_questions)
        for i, (chunk, diff) in enumerate(zip(selected_chunks, difficulties)):
            context = clean_text(chunk.payload['text'][:2000])  # Limite le contexte
            question = generate_question(llm_client, context, difficulty=diff)
            
            if question:
                question['source'] = clean_text(chunk.payload.get('file', 'Unknown'))
                question['tag'] = clean_text(chunk.payload.get('tag', 'Unknown'))
                questions.append(question)
            
            progress.update(task, advance=1)
            if len(questions) >= num_questions:
                break
    
    if not questions:
        console.print("[red]❌ Échec de la génération des questions[/red]")
        return
    
    # Lance le quiz
    mode_emoji = "⏱️ " if mode == "chrono" else "🎯 "
    console.print(Panel(
        f"[bold white]{mode_emoji}Quiz de révision[/bold white]\n"
        f"[cyan]{len(questions)} questions | Difficulté : {difficulty}[/cyan]\n"
        f"[dim]Tag : {tag_filter or 'Tous'} | Mode : {mode}[/dim]",
        box=box.DOUBLE_EDGE,
        style="bold green"
    ))
    
    score = 0
    results = []
    wrong_questions = []
    timings = []
    
    for i, q in enumerate(questions):
        start_time = time.time()
        
        # Barre de progression
        progress_bar = "█" * (i) + "░" * (len(questions) - i)
        console.print(f"\n[bold cyan]Question {i+1}/{len(questions)}[/bold cyan] {progress_bar}")
        console.print(f"[dim]Difficulté : {q.get('difficulty', 'unkn').upper()} | Source : {q['source']}[/dim]")
        console.print(f"[white]{clean_text(q['question'])}[/white]\n")
        
        # Affiche les options
        for idx, option in enumerate(q['options']):
            letter = chr(65 + idx)
            console.print(f"  [yellow]{letter}.[/yellow] {clean_text(option)}")
        
        # Demande la réponse (avec timeout en mode chrono)
        answer = None
        if mode == "chrono":
            console.print(f"[bold yellow]⏱️ 30 secondes pour répondre ![/bold yellow]")
            try:
                answer = Prompt.ask("[bold]Ta réponse (A/B/C/D)", choices=["A", "B", "C", "D", "a", "b", "c", "d"], show_choices=True).upper()
                if not answer:
                    answer = "?"
            except:
                answer = "?"
        else:
            answer = Prompt.ask("[bold]Ta réponse (A/B/C/D)", choices=["A", "B", "C", "D", "a", "b", "c", "d"]).upper()
        
        elapsed = time.time() - start_time
        timings.append(elapsed)
        
        if answer == "?":
            answer_idx = -1
            correct = False
        else:
            answer_idx = ord(answer) - 65
            correct = answer_idx == q['correct']
        
        if correct:
            score += 1
            bonus = 10 if elapsed < 5 else 0  # Bonus pour réponse rapide
            console.print(f"[bold green]✅ Correct ! [dim](+1 point{' bonus' if bonus else ''})[/dim][/bold green]")
        else:
            correct_letter = chr(65 + q['correct'])
            console.print(f"[bold red]❌ Faux ! La bonne réponse : {correct_letter}[/bold red]")
            wrong_questions.append((i + 1, q, answer if answer != "?" else "Pas de réponse"))
        
        # Explication améliorée
        console.print(f"[bold cyan]💡 Explication :[/bold cyan]")
        console.print(f"[dim]{clean_text(q['explanation'])}[/dim]")
        
        results.append({
            "question": q['question'],
            "user_answer": answer,
            "correct_answer": chr(65 + q['correct']),
            "correct": correct,
            "source": q['source'],
            "tag": q['tag'],
            "difficulty": q.get('difficulty', 'unknown'),
            "time": elapsed
        })
        
        # Pause
        if i < len(questions) - 1:
            Prompt.ask("[dim]Appuie sur Entrée pour continuer[/dim]")
    
    # Résultats détaillés
    percentage = (score / len(questions)) * 100
    avg_time = sum(timings) / len(timings) if timings else 0
    
    # Tableau de résultats
    table = Table(title="Résultats par difficulté", box=box.ROUNDED)
    table.add_column("Difficulté", style="cyan")
    table.add_column("Score", style="green")
    table.add_column("Temps moyen", style="yellow")
    
    for diff in ["facile", "moyen", "difficile"]:
        diff_questions = [r for r in results if r['difficulty'] == diff]
        if diff_questions:
            diff_score = sum(1 for r in diff_questions if r['correct'])
            diff_time = sum(r['time'] for r in diff_questions) / len(diff_questions)
            table.add_row(diff, f"{diff_score}/{len(diff_questions)}", f"{diff_time:.1f}s")
    
    console.print("\n")
    console.print(table)
    
    # Résumé final
    console.print("\n" + "="*60)
    
    performance_msg = ""
    if percentage >= 90:
        performance_msg = "🏆 EXCEPTIONNEL ! Excellente maîtrise !"
    elif percentage >= 80:
        performance_msg = "🥇 EXCELLENT ! Très bien préparé !"
    elif percentage >= 70:
        performance_msg = "🥈 BON ! Continue tes efforts !"
    elif percentage >= 60:
        performance_msg = "🥉 ACCEPTABLE ! À réviser..."
    else:
        performance_msg = "📚 À APPROFONDIR ! Révise les bases !"
    
    console.print(Panel(
        f"[bold white]📊 Résultats du Quiz[/bold white]\n\n"
        f"[cyan]Score : {score}/{len(questions)} ({percentage:.1f}%)[/cyan]\n"
        f"[yellow]Temps moyen : {avg_time:.1f}s par question[/yellow]\n"
        f"[bold]{performance_msg}[/bold]",
        box=box.DOUBLE_EDGE,
        style="bold cyan"
    ))
    
    # Offre révision si des questions échouées
    if wrong_questions and mode != "chrono":
        console.print(f"\n[yellow]❌ {len(wrong_questions)} question(s) échouée(s)[/yellow]")
        if Prompt.ask("[dim]Veux-tu revoir les questions échouées ? (o/n)", default="n") == "o":
            show_review(wrong_questions)
    
    # Sauvegarde les résultats
    save_results(tag_filter, score, len(questions), results, mode=mode)
    
    return score, len(questions)

def save_results(tag: str, score: int, total: int, results: list, mode: str = "normal"):
    """Sauvegarde les résultats du quiz."""
    results_dir = Path("quiz_results")
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = results_dir / f"quiz_{tag or 'all'}_{timestamp}.json"
    
    data = {
        "date": datetime.now().isoformat(),
        "tag": tag,
        "score": score,
        "total": total,
        "percentage": (score / total) * 100,
        "mode": mode,
        "questions": results
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    console.print(f"[dim]💾 Résultats sauvegardés : {filename}[/dim]")

def show_review(wrong_questions):
    """Affiche une review des questions échouées."""
    console.print("\n" + "="*60)
    console.print(Panel(
        "[bold white]📖 Révision des questions échouées[/bold white]",
        box=box.DOUBLE_EDGE,
        style="bold yellow"
    ))
    
    for q_num, question, user_answer in wrong_questions:
        console.print(f"\n[bold cyan]Question {q_num}[/bold cyan]")
        console.print(f"[white]{clean_text(question['question'])}[/white]\n")
        
        for idx, option in enumerate(question['options']):
            letter = chr(65 + idx)
            is_correct = idx == question['correct']
            is_user = letter == user_answer
            
            marker = "✓" if is_correct else "✗" if is_user else " "
            color = "green" if is_correct else "red" if is_user else "white"
            console.print(f"  {marker} [{color}]{letter}.[/color] {clean_text(option)}")
        
        console.print(f"[bold cyan]💡 Explication :[/bold cyan]")
        console.print(f"[dim]{clean_text(question['explanation'])}[/dim]\n")

def review_missed_questions(tag_filter: str = None):
    """Review les questions échouées des précédents quiz."""
    results_dir = Path("quiz_results")
    
    if not results_dir.exists():
        console.print("[yellow]Aucun historique de quiz[/yellow]")
        return
    
    # Collecte toutes les questions échouées
    missed = []
    quiz_files = sorted(results_dir.glob("quiz_*.json"), reverse=True)
    
    for qf in quiz_files[:5]:  # 5 derniers quiz
        try:
            with open(qf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for q in data.get('questions', []):
                if not q['correct']:
                    missed.append((data['tag'], q))
        except:
            pass
    
    if not missed:
        console.print("[yellow]Aucune question échouée à réviser[/yellow]")
        return
    
    console.print(Panel(
        f"[bold white]📖 Révision - {len(missed)} questions échouées[/bold white]",
        box=box.DOUBLE_EDGE,
        style="bold yellow"
    ))
    
    score = 0
    for i, (tag, q) in enumerate(missed):
        console.print(f"\n[bold cyan]Question {i+1}/{len(missed)}[/bold cyan]")
        console.print(f"[dim]Tag : {tag}[/dim]")
        console.print(f"[white]{clean_text(q['question'])}[/white]\n")
        
        for idx, option in enumerate(q['options']):
            letter = chr(65 + idx)
            console.print(f"  [yellow]{letter}.[/yellow] {clean_text(option)}")
        
        answer = Prompt.ask("\n[bold]Ta réponse (A/B/C/D)", choices=["A", "B", "C", "D", "a", "b", "c", "d"]).upper()
        answer_idx = ord(answer) - 65
        
        correct = answer_idx == q['correct']
        if correct:
            score += 1
            console.print("[bold green]✅ Correct ![/bold green]")
        else:
            correct_letter = chr(65 + q['correct'])
            console.print(f"[bold red]❌ Faux ! La réponse était {correct_letter}[/bold red]")
        
        console.print(f"[dim]💡 {clean_text(q['explanation'])}[/dim]")
        
        if i < len(missed) - 1:
            Prompt.ask("\n[dim]Appuie sur Entrée pour continuer[/dim]")
    
    console.print("\n" + "="*60)
    pct = (score / len(missed)) * 100
    console.print(Panel(
        f"[bold white]Résultats de la révision[/bold white]\n\n"
        f"[cyan]Score : {score}/{len(missed)} ({pct:.0f}%)[/cyan]\n"
        f"{'[green]Progression bien !' if pct >= 70 else '[yellow]Garde la pratique !'}[/{'green' if pct >= 70 else 'yellow'}]",
        box=box.DOUBLE_EDGE,
        style="bold cyan"
    ))

def show_quiz_history():
    """Affiche l'historique détaillé des quiz avec statistiques."""
    results_dir = Path("quiz_results")
    
    if not results_dir.exists():
        console.print("[yellow]⚠️ Aucun historique de quiz[/yellow]")
        return
    
    quiz_files = sorted(results_dir.glob("quiz_*.json"), reverse=True)
    
    if not quiz_files:
        console.print("[yellow]⚠️ Aucun historique de quiz[/yellow]")
        return
    
    console.print(Panel(
        "[bold white]📊 Historique des quiz[/bold white]",
        box=box.DOUBLE_EDGE,
        style="bold cyan"
    ))
    
    # Table d'historique
    table = Table(box=box.ROUNDED)
    table.add_column("#", style="dim")
    table.add_column("Date", style="cyan")
    table.add_column("Tag", style="yellow")
    table.add_column("Score", style="green")
    table.add_column("Perf", style="magenta")
    
    # Statistiques par tag
    stats_by_tag = defaultdict(lambda: {"scores": [], "totals": [], "times": []})
    
    for idx, qf in enumerate(quiz_files[:15]):
        try:
            with open(qf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            date = datetime.fromisoformat(data['date']).strftime("%d/%m %H:%M")
            tag = data.get('tag', 'Tous') or 'Tous'
            score = data['score']
            total = data['total']
            pct = data['percentage']
            
            # Emojis de performance
            perf_emoji = "🟢" if pct >= 80 else "🟡" if pct >= 60 else "🔴"
            perf_text = f"{perf_emoji} {pct:.0f}%"
            
            table.add_row(
                str(idx + 1),
                date,
                tag,
                f"{score}/{total}",
                perf_text
            )
            
            # Accumule les stats
            stats_by_tag[tag]["scores"].append(score)
            stats_by_tag[tag]["totals"].append(total)
            avg_time = sum(q.get('time', 0) for q in data.get('questions', [])) / max(len(data.get('questions', [])), 1)
            if avg_time > 0:
                stats_by_tag[tag]["times"].append(avg_time)
            
        except Exception as e:
            console.print(f"[red]Erreur {qf.name}: {e}[/red]")
    
    console.print(table)
    
    # Statistiques synthétiques
    if stats_by_tag:
        console.print("\n[bold cyan]📈 Synthèse par tag :[/bold cyan]\n")
        
        synth_table = Table(box=box.ROUNDED)
        synth_table.add_column("Tag", style="yellow")
        synth_table.add_column("Tentatives", style="cyan")
        synth_table.add_column("Meilleur", style="green")
        synth_table.add_column("Moyen", style="yellow")
        synth_table.add_column("Tendance", style="magenta")
        
        for tag in sorted(stats_by_tag.keys()):
            stats = stats_by_tag[tag]
            attempts = len(stats["scores"])
            
            # Calculs
            percentages = [(s/t)*100 for s, t in zip(stats["scores"], stats["totals"])]
            best = max(percentages)
            avg = sum(percentages) / len(percentages)
            
            # Tendance (derniers 3 vs 3 précédents)
            if len(percentages) >= 6:
                recent = sum(percentages[-3:]) / 3
                prev = sum(percentages[-6:-3]) / 3
                trend = "↗️" if recent > prev else "↘️" if recent < prev else "→"
            else:
                trend = "→"
            
            synth_table.add_row(
                tag,
                str(attempts),
                f"{best:.0f}%",
                f"{avg:.0f}%",
                trend
            )
        
        console.print(synth_table)

if __name__ == "__main__":
    # Test
    run_quiz(tag_filter="Certification", num_questions=5)
