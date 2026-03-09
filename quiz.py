# quiz.py - Module Quiz pour CORHack RAG
import random
import json
from pathlib import Path
from datetime import datetime
from qdrant_client import QdrantClient
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
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

def generate_question(llm_client: OpenAI, context: str) -> dict:
    """Génère une question QCM à partir d'un contexte."""
    
    prompt = f"""À partir de ce contenu de cours, génère UNE question QCM de révision.

CONTENU DU COURS :
{context}

FORMAT REQUIS (JSON strict) :
{{
  "question": "Question claire et précise",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct": 0,
  "explanation": "Explication de la bonne réponse"
}}

RÈGLES :
- Question claire testant la compréhension
- 4 options réalistes (A, B, C, D)
- "correct" est l'index (0-3) de la bonne réponse
- Explication courte et pédagogique
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
            max_tokens=500
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
        
        return question_data
        
    except Exception as e:
        console.print(f"[red]Erreur génération question: {e}[/red]")
        return None

def run_quiz(tag_filter: str = None, num_questions: int = 10):
    """Lance un quiz interactif."""
    
    client = QdrantClient(url=QDRANT_URL)
    llm_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    
    # Récupère des chunks
    console.print(f"[cyan]🔍 Récupération de contenu pour le quiz...[/cyan]")
    
    if tag_filter:
        chunks = retrieve_chunks_by_tag(client, tag_filter, limit=num_questions * 3)
    else:
        # Sans filtre, récupère aléatoirement
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
    
    # Génère les questions
    console.print(f"[cyan]🧠 Génération de {num_questions} questions...[/cyan]\n")
    
    questions = []
    for i, chunk in enumerate(selected_chunks):
        console.print(f"[dim]Question {i+1}/{num_questions}...[/dim]", end="\r")
        context = clean_text(chunk.payload['text'])
        question = generate_question(llm_client, context)
        
        if question:
            question['source'] = clean_text(chunk.payload.get('file', 'Unknown'))
            questions.append(question)
        
        if len(questions) >= num_questions:
            break
    
    console.print()  # Nouvelle ligne
    
    if not questions:
        console.print("[red]❌ Échec de la génération des questions[/red]")
        return
    
    # Lance le quiz
    console.print(Panel(
        f"[bold white]Quiz de révision[/bold white]\n"
        f"[cyan]{len(questions)} questions[/cyan]\n"
        f"[dim]Tag : {tag_filter or 'Tous'}[/dim]",
        box=box.DOUBLE_EDGE,
        style="bold green"
    ))
    
    score = 0
    results = []
    
    for i, q in enumerate(questions):
        console.print(f"\n[bold cyan]Question {i+1}/{len(questions)}[/bold cyan]")
        console.print(f"[white]{clean_text(q['question'])}[/white]\n")
        
        # Affiche les options
        for idx, option in enumerate(q['options']):
            letter = chr(65 + idx)  # A, B, C, D
            console.print(f"  [yellow]{letter}.[/yellow] {clean_text(option)}")
        
        # Demande la réponse
        while True:
            answer = Prompt.ask("\n[bold]Ta réponse (A/B/C/D)", choices=["A", "B", "C", "D", "a", "b", "c", "d"])
            answer_idx = ord(answer.upper()) - 65
            break
        
        # Vérifie la réponse
        correct = answer_idx == q['correct']
        if correct:
            score += 1
            console.print("[bold green]✅ Correct ![/bold green]")
        else:
            correct_letter = chr(65 + q['correct'])
            console.print(f"[bold red]❌ Faux ! La bonne réponse était {correct_letter}[/bold red]")
        
        # Affiche l'explication
        console.print(f"[dim]💡 {clean_text(q['explanation'])}[/dim]")
        console.print(f"[dim]📄 Source : {q['source']}[/dim]")
        
        results.append({
            "question": q['question'],
            "user_answer": answer.upper(),
            "correct_answer": chr(65 + q['correct']),
            "correct": correct,
            "source": q['source']
        })
        
        # Pause entre questions
        if i < len(questions) - 1:
            Prompt.ask("\n[dim]Appuie sur Entrée pour continuer[/dim]")
    
    # Résultats finaux
    percentage = (score / len(questions)) * 100
    
    console.print("\n" + "="*60)
    console.print(Panel(
        f"[bold white]Résultats du Quiz[/bold white]\n\n"
        f"[cyan]Score : {score}/{len(questions)} ({percentage:.1f}%)[/cyan]\n"
        f"{'[green]🎉 Excellent !' if percentage >= 80 else '[yellow]💪 Continue !' if percentage >= 60 else '[red]📖 Révise encore !'}[/{'green' if percentage >= 80 else 'yellow' if percentage >= 60 else 'red'}]",
        box=box.DOUBLE_EDGE,
        style="bold cyan"
    ))
    
    # Sauvegarde les résultats
    save_results(tag_filter, score, len(questions), results)
    
    return score, len(questions)

def save_results(tag: str, score: int, total: int, results: list):
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
        "questions": results
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    console.print(f"[dim]💾 Résultats sauvegardés : {filename}[/dim]")

def show_quiz_history():
    """Affiche l'historique des quiz."""
    results_dir = Path("quiz_results")
    
    if not results_dir.exists():
        console.print("[yellow]Aucun historique de quiz[/yellow]")
        return
    
    quiz_files = sorted(results_dir.glob("quiz_*.json"), reverse=True)
    
    if not quiz_files:
        console.print("[yellow]Aucun historique de quiz[/yellow]")
        return
    
    console.print("[bold cyan]📊 Historique des quiz :[/bold cyan]\n")
    
    for qf in quiz_files[:10]:  # Derniers 10 quiz
        try:
            with open(qf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            date = datetime.fromisoformat(data['date']).strftime("%d/%m/%Y %H:%M")
            tag = data.get('tag', 'Tous')
            score = data['score']
            total = data['total']
            pct = data['percentage']
            
            emoji = "🟢" if pct >= 80 else "🟡" if pct >= 60 else "🔴"
            console.print(f"{emoji} [{date}] {tag} : {score}/{total} ({pct:.0f}%)")
            
        except Exception as e:
            console.print(f"[red]Erreur lecture {qf.name}: {e}[/red]")

if __name__ == "__main__":
    # Test
    run_quiz(tag_filter="Certification", num_questions=5)
