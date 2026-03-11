# ingest.py - CORHack RAG Ingestion Engine
# Support: Markdown (.md) + PDF (.pdf) avec extraction intelligente
import re
import os
import json
import hashlib
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import ollama
from config import *
from rich.console import Console
from rich.progress import track

# Support PDF avec fallback intelligent
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = "pymupdf"
except ImportError:
    try:
        import PyPDF2
        PDF_SUPPORT = "pypdf2"
    except ImportError:
        PDF_SUPPORT = False

console = Console()

# Env vars écrasent config.py si définies
VAULT_PATH      = os.getenv("VAULT_PATH", VAULT_PATH)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", COLLECTION_NAME)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extrait le texte d'un PDF avec la meilleure méthode disponible (PyMuPDF > PyPDF2)."""
    if PDF_SUPPORT == "pymupdf":
        return _extract_pdf_pymupdf(pdf_path)
    elif PDF_SUPPORT == "pypdf2":
        return _extract_pdf_pypdf2(pdf_path)
    else:
        console.print(f"[yellow]⚠ Aucune libraire PDF installée. Installe pymupdf ou PyPDF2[/yellow]")
        return ""


def _extract_pdf_pymupdf(pdf_path: Path) -> str:
    """Extraction ultra-rapide avec PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()
            
            # Nettoyer et formatter
            if text.strip():
                text = re.sub(r'\n\s*\n', '\n\n', text)  # Normaliser les sauts de ligne
                text = re.sub(r' +', ' ', text)  # Réduire les espaces multiples
                text_parts.append(f"[Page {page_num + 1}]\n{text.strip()}")
        
        doc.close()
        return "\n\n".join(text_parts)
    except Exception as e:
        console.print(f"[yellow]⚠ Erreur PyMuPDF {pdf_path.name}: {e}[/yellow]")
        return _extract_pdf_pypdf2(pdf_path) if PDF_SUPPORT == "pypdf2" else ""


def _extract_pdf_pypdf2(pdf_path: Path) -> str:
    """Extraction fallback avec PyPDF2."""
    try:
        import PyPDF2
        text_parts = []
        
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text = page.extract_text()
                
                if text.strip():
                    text = re.sub(r'\n\s*\n', '\n\n', text)
                    text = re.sub(r' +', ' ', text)
                    text_parts.append(f"[Page {page_num + 1}]\n{text.strip()}")
        
        return "\n\n".join(text_parts)
    except Exception as e:
        console.print(f"[yellow]⚠ Erreur extraction PDF {pdf_path.name}: {e}[/yellow]")
        return ""


def detect_tag(file_path: Path) -> str:
    """Détecte le tag depuis le chemin du fichier."""
    parts = file_path.relative_to(Path(VAULT_PATH)).parts
    if len(parts) == 1:
        return "General"
    folder = parts[0]
    if "Certification" in folder or "EHEv1" in folder:
        return "Certification"
    if "Dictionnaire" in folder and len(parts) > 1:
        return f"Dictionnaire_{parts[1]}"
    if "Cours" in folder and len(parts) > 1:
        sub = parts[1]
        if "Jour" in sub:
            return sub
        return "QCM" if "QCM" in sub else folder
    return folder.replace(" ", "_")


def chunk_text(text: str, max_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Découpe le texte en chunks avec chevauchement."""
    sections = re.split(r'\n(?=#{1,3} )', text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_size:
            chunks.append(section)
        else:
            for i in range(0, len(section), max_size - overlap):
                chunk = section[i:i + max_size].strip()
                if chunk:
                    chunks.append(chunk)
    return chunks


def get_embedding(text: str) -> list[float]:
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


def _stable_id(file_path: str, chunk_index: int) -> int:
    """Génère un ID stable basé sur le chemin du fichier et l'index du chunk."""
    h = hashlib.md5(f"{file_path}::{chunk_index}".encode()).hexdigest()
    return int(h[:15], 16)


def _ensure_collection(client: QdrantClient):
    """Crée la collection si elle n'existe pas."""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )
        console.print(f"[green]✓ Collection '{COLLECTION_NAME}' créée[/green]")


def _delete_file_chunks(client: QdrantClient, file_path: str):
    """Supprime tous les chunks d'un fichier donné."""
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="file_path", match=MatchValue(value=file_path))]
        ),
    )


def _index_files(client: QdrantClient, file_paths: list[Path]) -> int:
    """Indexe une liste de fichiers et retourne le nombre de chunks créés."""
    points = []
    # Valider et filtrer les chemins existants
    valid_files = [f for f in file_paths if f.exists() and f.is_file()]
    if not valid_files:
        console.print("[yellow]⚠ Aucun fichier valide à indexer[/yellow]")
        return 0
    
    for md_file in track(valid_files, description="[green]Indexation en cours..."):
        try:
            # Déterminer le format du fichier et extraire le texte
            if md_file.suffix.lower() == '.pdf':
                text = extract_pdf_text(md_file)
                if not text:
                    continue
            else:  # .md
                text = md_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            console.print(f"[yellow]⚠ Impossible de lire {md_file.name}: {e}[/yellow]")
            continue

        tag = detect_tag(md_file)
        chunks = chunk_text(text)

        for idx, chunk in enumerate(chunks):
            if len(chunk.strip()) < 30:
                continue
            embedding = get_embedding(chunk)
            points.append(
                PointStruct(
                    id=_stable_id(str(md_file), idx),
                    vector=embedding,
                    payload={
                        "text": chunk,
                        "file": md_file.name,
                        "file_path": str(md_file),
                        "tag": tag,
                        "vault": str(Path(VAULT_PATH).name),
                    },
                )
            )

    batch_size = 50
    for i in range(0, len(points), batch_size):
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points[i:i + batch_size]
        )
    return len(points)


def ingest_incremental(changed_files: list[str], deleted_files: list[str] | None = None):
    """Indexation incrémentale : ne traite que les fichiers modifiés/supprimés."""
    client = QdrantClient(url=QDRANT_URL)
    _ensure_collection(client)

    # Nettoyer et valider les chemins
    changed_files = [f for f in changed_files if f.strip() and not f.startswith('\\')]
    deleted_files = [f for f in (deleted_files or []) if f.strip() and not f.startswith('\\')]

    # Supprimer les chunks des fichiers supprimés
    if deleted_files:
        for fp in deleted_files:
            _delete_file_chunks(client, fp)
        console.print(f"[yellow]🗑  {len(deleted_files)} fichier(s) supprimé(s) de l'index[/yellow]")

    if not changed_files:
        console.print("[green]✓ Rien à réindexer[/green]")
        return

    # Supprimer les anciens chunks des fichiers modifiés avant réindexation
    for fp in changed_files:
        _delete_file_chunks(client, fp)

    file_paths = [Path(f) for f in changed_files]
    valid_count = len([f for f in file_paths if f.exists()])
    console.print(f"[cyan]📄 {valid_count} fichier(s) valide(s) à réindexer[/cyan]")

    count = _index_files(client, file_paths)
    console.print(f"\n[bold green]✅ Indexation incrémentale terminée : {count} chunks mis à jour ![/bold green]")


def ingest_vault():
    """Indexation complète (première fois ou /index)."""
    client = QdrantClient(url=QDRANT_URL)

    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        console.print(f"[yellow]⚠ Collection '{COLLECTION_NAME}' existante → suppression et réindexation[/yellow]")
        client.delete_collection(COLLECTION_NAME)

    _ensure_collection(client)

    md_files = list(Path(VAULT_PATH).rglob("*.md"))
    pdf_files = list(Path(VAULT_PATH).rglob("*.pdf"))
    all_files = md_files + pdf_files
    
    console.print(f"[cyan]📄 {len(md_files)} fichiers .md trouvés[/cyan]")
    console.print(f"[cyan]📄 {len(pdf_files)} fichiers .pdf trouvés[/cyan]")
    console.print(f"[cyan]📄 Total: {len(all_files)} fichiers dans {VAULT_PATH}[/cyan]\n")

    if not all_files:
        console.print("[red]❌ Aucun fichier .md ou .pdf trouvé ! Vérifie le chemin du vault.[/red]")
        return

    if PDF_SUPPORT and pdf_files:
        pdf_engine = "PyMuPDF ⚡" if PDF_SUPPORT == "pymupdf" else "PyPDF2"
        console.print(f"[green]✓ Support PDF activé ({pdf_engine})[/green]\n")
    elif pdf_files:
        console.print("[yellow]⚠ Fichiers PDF trouvés mais aucune libraire PDF installée[/yellow]")
        console.print("[yellow]  → Installe avec: pip install pymupdf[/yellow]\n")

    count = _index_files(client, all_files)
    console.print(f"\n[bold green]✅ Indexation terminée : {count} chunks stockés dans '{COLLECTION_NAME}' ![/bold green]")


if __name__ == "__main__":
    # Mode incrémental si fichier temp est défini
    index_file = os.getenv("CORHACK_INDEX_FILE", "")
    
    if index_file and os.path.exists(index_file):
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            changed = data.get("changed", [])
            deleted = data.get("deleted", [])
            ingest_incremental(changed, deleted)
        except Exception as e:
            console.print(f"[red]Erreur lecture fichier index: {e}[/red]")
            ingest_vault()
    else:
        ingest_vault()
