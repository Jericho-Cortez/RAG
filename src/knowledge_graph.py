# knowledge_graph.py - Module Graphe de Connaissances
import re
import json
import sys
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Tuple, Dict, Set

# Add parent directory to path for root config.py imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import networkx as nx
from pyvis.network import Network
from qdrant_client import QdrantClient
from rich.console import Console
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

class KnowledgeGraph:
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_URL)
        self.llm_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
        self.graph = nx.Graph()
        self.entities = set()
        self.relations = []
        
    def extract_entities_llm(self, text: str) -> List[str]:
        """Extrait les entités/concepts d'un texte avec LLM."""
        
        prompt = f"""Extrais UNIQUEMENT les concepts techniques importants de ce texte.

TEXTE :
{text[:800]}

RÈGLES :
- Concepts informatiques/réseaux/sécurité uniquement
- Acronymes (SSH, TCP, IP, VPN, DNS, etc.)
- Technologies (firewall, routeur, switch, etc.)
- Protocoles et standards
- Pas de verbes ou mots communs
- Format : liste séparée par virgules
- Maximum 10 concepts

EXEMPLE : SSH, TCP, Firewall, VPN, DNS, Port 22

Réponds UNIQUEMENT avec la liste, sans explication."""

        try:
            response = self.llm_client.chat.completions.create(
                model=MODEL_PRECISE["name"],
                messages=[
                    {"role": "system", "content": "Tu es un extracteur de concepts techniques. Réponds uniquement avec une liste CSV."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse la liste
            entities = [e.strip() for e in content.split(',') if e.strip()]
            
            # Normalise (majuscules pour acronymes, title case pour le reste)
            normalized = []
            for entity in entities:
                if entity.isupper() and len(entity) <= 5:
                    normalized.append(entity)
                else:
                    normalized.append(entity.title())
            
            return normalized[:10]  # Max 10
            
        except Exception as e:
            console.print(f"[red]Erreur extraction entités: {e}[/red]")
            return []
    
    def extract_entities_regex(self, text: str) -> List[str]:
        """Extraction rapide par regex (backup)."""
        
        # Patterns communs en cybersécurité/réseau
        patterns = [
            r'\b(?:SSH|TCP|UDP|IP|DNS|HTTP|HTTPS|FTP|SMTP|VPN|NAT|DHCP|ARP|ICMP|TLS|SSL)\b',
            r'\b(?:firewall|routeur|switch|proxy|gateway|serveur|client)\b',
            r'\b(?:port\s+\d+)\b',
            r'\b(?:attaque|vulnérabilité|exploit|malware|ransomware|phishing)\b',
            r'\b(?:authentification|chiffrement|hash|certificat|clé)\b',
        ]
        
        entities = set()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities.update(m.upper() if m.isupper() else m.title() for m in matches)
        
        return list(entities)
    
    def build_graph_from_chunks(self, tag_filter: str = None, max_chunks: int = 200):
        """Construit le graphe à partir des chunks Qdrant."""
        
        console.print(f"[cyan]🔍 Récupération des chunks...[/cyan]")
        
        # Récupère les chunks
        if tag_filter:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            filter_param = Filter(
                must=[FieldCondition(key="tag", match=MatchValue(value=tag_filter))]
            )
            scroll_result = self.client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=filter_param,
                limit=max_chunks,
                with_payload=True
            )
        else:
            scroll_result = self.client.scroll(
                collection_name=COLLECTION_NAME,
                limit=max_chunks,
                with_payload=True
            )
        
        chunks = scroll_result[0]
        
        if not chunks:
            console.print("[red]❌ Aucun chunk trouvé[/red]")
            return False
        
        console.print(f"[green]✓ {len(chunks)} chunks récupérés[/green]")
        console.print(f"[cyan]🧠 Extraction des concepts...[/cyan]")
        
        # Extraction des entités par chunk
        chunk_entities = []
        entity_counter = Counter()
        
        for i, chunk in enumerate(chunks):
            if i % 20 == 0:
                console.print(f"[dim]Progression : {i}/{len(chunks)}...[/dim]", end="\r")
            
            text = clean_text(chunk.payload['text'])
            
            # Combine LLM et regex
            entities_llm = self.extract_entities_llm(text)
            entities_regex = self.extract_entities_regex(text)
            
            # Fusion et déduplication
            entities = list(set(entities_llm + entities_regex))
            
            if entities:
                chunk_entities.append({
                    'entities': entities,
                    'file': chunk.payload.get('file', 'Unknown'),
                    'tag': chunk.payload.get('tag', 'General')
                })
                
                # Compte les occurrences
                entity_counter.update(entities)
                self.entities.update(entities)
        
        console.print()  # Nouvelle ligne
        console.print(f"[green]✓ {len(self.entities)} concepts uniques extraits[/green]")
        
        # Construit le graphe
        console.print(f"[cyan]🕸️  Construction du graphe...[/cyan]")
        
        # Ajoute les nœuds avec poids (fréquence)
        for entity, count in entity_counter.items():
            self.graph.add_node(
                entity,
                weight=count,
                size=min(count * 3, 50)  # Taille visuelle
            )
        
        # Crée les relations (co-occurrence dans un même chunk)
        edge_counter = Counter()
        
        for chunk_data in chunk_entities:
            entities = chunk_data['entities']
            
            # Relie tous les concepts du même chunk
            for i, e1 in enumerate(entities):
                for e2 in entities[i+1:]:
                    edge = tuple(sorted([e1, e2]))
                    edge_counter[edge] += 1
        
        # Ajoute les arêtes avec poids
        for (e1, e2), weight in edge_counter.items():
            if weight >= 2:  # Minimum 2 co-occurrences
                self.graph.add_edge(e1, e2, weight=weight)
        
        console.print(f"[green]✓ Graphe construit : {self.graph.number_of_nodes()} nœuds, {self.graph.number_of_edges()} relations[/green]")
        
        return True
    
    def visualize_interactive(self, output_file: str = "knowledge_graph.html"):
        """Génère une visualisation interactive HTML."""
        
        if self.graph.number_of_nodes() == 0:
            console.print("[red]❌ Graphe vide[/red]")
            return
        
        console.print(f"[cyan]🎨 Génération de la visualisation...[/cyan]")
        
        # Crée le graphe PyVis
        net = Network(
            height="800px",
            width="100%",
            bgcolor="#1e1e1e",
            font_color="white",
            notebook=False
        )
        
        # Configure la physique
        net.barnes_hut(
            gravity=-8000,
            central_gravity=0.3,
            spring_length=200,
            spring_strength=0.001,
            damping=0.09
        )
        
        # Ajoute les nœuds avec couleurs selon centralité
        centrality = nx.degree_centrality(self.graph)
        max_centrality = max(centrality.values()) if centrality else 1
        
        for node in self.graph.nodes():
            weight = self.graph.nodes[node].get('weight', 1)
            cent = centrality.get(node, 0)
            
            # Couleur selon importance (vert = important, bleu = moins)
            color_value = int((cent / max_centrality) * 255)
            color = f"#{255-color_value:02x}{color_value:02x}80"
            
            net.add_node(
                node,
                label=node,
                title=f"{node}\nOccurrences: {weight}\nConnexions: {self.graph.degree(node)}",
                size=10 + weight * 2,
                color=color
            )
        
        # Ajoute les arêtes
        for e1, e2, data in self.graph.edges(data=True):
            weight = data.get('weight', 1)
            net.add_edge(
                e1, e2,
                value=weight,
                title=f"Co-occurrences: {weight}"
            )
        
        # Sauvegarde
        output_path = Path(output_file)
        net.save_graph(str(output_path))
        
        console.print(f"[green]✅ Graphe sauvegardé : {output_path.absolute()}[/green]")
        console.print(f"[cyan]🌐 Ouvre le fichier dans ton navigateur pour visualiser[/cyan]")
        
        return output_path
    
    def find_path(self, entity1: str, entity2: str) -> List[str]:
        """Trouve le chemin le plus court entre deux concepts."""
        
        # Normalise les entités
        e1 = self._find_entity(entity1)
        e2 = self._find_entity(entity2)
        
        if not e1:
            console.print(f"[red]❌ Concept '{entity1}' non trouvé[/red]")
            return []
        
        if not e2:
            console.print(f"[red]❌ Concept '{entity2}' non trouvé[/red]")
            return []
        
        try:
            path = nx.shortest_path(self.graph, e1, e2)
            return path
        except nx.NetworkXNoPath:
            console.print(f"[yellow]⚠ Aucun chemin entre {e1} et {e2}[/yellow]")
            return []
        except nx.NodeNotFound as e:
            console.print(f"[red]❌ Nœud non trouvé : {e}[/red]")
            return []
    
    def _find_entity(self, query: str) -> str:
        """Trouve une entité par correspondance partielle."""
        query_lower = query.lower()
        
        # Recherche exacte
        for entity in self.entities:
            if entity.lower() == query_lower:
                return entity
        
        # Recherche partielle
        for entity in self.entities:
            if query_lower in entity.lower():
                return entity
        
        return None
    
    def get_stats(self) -> Dict:
        """Retourne les statistiques du graphe."""
        
        if self.graph.number_of_nodes() == 0:
            return {}
        
        centrality = nx.degree_centrality(self.graph)
        top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:10]
        
        stats = {
            'nodes': self.graph.number_of_nodes(),
            'edges': self.graph.number_of_edges(),
            'density': nx.density(self.graph),
            'components': nx.number_connected_components(self.graph),
            'top_concepts': top_nodes
        }
        
        return stats
    
    def save_graph(self, filename: str = "knowledge_graph.json"):
        """Sauvegarde le graphe en JSON."""
        
        data = {
            'nodes': [
                {
                    'id': node,
                    'weight': self.graph.nodes[node].get('weight', 1)
                }
                for node in self.graph.nodes()
            ],
            'edges': [
                {
                    'source': e1,
                    'target': e2,
                    'weight': data.get('weight', 1)
                }
                for e1, e2, data in self.graph.edges(data=True)
            ]
        }
        
        output_path = Path(filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]💾 Graphe sauvegardé : {output_path}[/green]")

def run_graph_command(args: list):
    """Point d'entrée pour les commandes de graphe."""
    
    kg = KnowledgeGraph()
    
    # Parse les arguments
    tag_filter = None
    for arg in args:
        if arg.startswith('@'):
            tag_filter = arg[1:].strip('"')
    
    # Construit le graphe
    success = kg.build_graph_from_chunks(tag_filter=tag_filter, max_chunks=200)
    
    if not success:
        return
    
    # Affiche les stats
    stats = kg.get_stats()
    
    console.print(Panel(
        f"[bold white]Statistiques du Graphe[/bold white]\n\n"
        f"[cyan]Concepts : {stats['nodes']}[/cyan]\n"
        f"[cyan]Relations : {stats['edges']}[/cyan]\n"
        f"[cyan]Densité : {stats['density']:.3f}[/cyan]\n"
        f"[cyan]Composantes : {stats['components']}[/cyan]\n\n"
        f"[bold yellow]Top concepts :[/bold yellow]\n" +
        "\n".join([f"  {i+1}. {node} ({score:.3f})" for i, (node, score) in enumerate(stats['top_concepts'][:5])]),
        box=box.DOUBLE_EDGE,
        style="bold cyan"
    ))
    
    # Génère la visualisation
    output_file = f"knowledge_graph_{tag_filter or 'all'}.html"
    kg.visualize_interactive(output_file)
    
    # Sauvegarde en JSON
    kg.save_graph(f"knowledge_graph_{tag_filter or 'all'}.json")
    
    return kg

def run_path_command(entity1: str, entity2: str, kg: KnowledgeGraph = None):
    """Trouve le chemin entre deux concepts."""
    
    if kg is None:
        console.print("[yellow]⚠ Graphe non chargé, construction en cours...[/yellow]")
        kg = KnowledgeGraph()
        kg.build_graph_from_chunks(max_chunks=200)
    
    path = kg.find_path(entity1, entity2)
    
    if path:
        console.print(f"\n[bold green]✅ Chemin trouvé ({len(path)-1} étapes) :[/bold green]\n")
        
        for i, concept in enumerate(path):
            if i < len(path) - 1:
                console.print(f"  [cyan]{concept}[/cyan]")
                console.print("    ↓")
            else:
                console.print(f"  [green]{concept}[/green]")

if __name__ == "__main__":
    # Test
    run_graph_command(["@Certification"])
