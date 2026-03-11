FROM python:3.12-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installe les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie le code source
COPY config.py query.py quiz.py knowledge_graph.py ingest.py ./
COPY lib/ ./lib/

# Variables d'environnement par défaut
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV QDRANT_URL=http://qdrant:6333

# Point d'entrée
CMD ["python", "query.py"]
