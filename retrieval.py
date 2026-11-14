"""Retrieval (RAG): find the passages in the handbook or the catalog that answer a question.

Two parts:

    INDEXING  (runs once, when the program starts)
        knowledge/handbook.txt, knowledge/catalog.txt
        -> split into passages -> each passage stored in Qdrant twice: by meaning and by exact words

    SEARCHING (runs every time the agent calls search_knowledge)
        question -> 1. hybrid search -> 2. RRF merge -> 3. rerank -> the best 3 passages

Everything runs on this machine: Qdrant in memory, and two small models from fastembed. No server, no key.
The index lives only in memory, so it is built again every time the program starts.
"""

from pathlib import Path
from uuid import uuid4

from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client import QdrantClient, models

FOLDER = Path(__file__).parent / "knowledge"
COLLECTION = "knowledge"        # one collection for both files; each passage is tagged with its source

# The three small models
MEANING_MODEL = "BAAI/bge-small-en-v1.5"       # dense vector: finds "send back" when you search "return"
WORDS_MODEL = "Qdrant/bm25"                    # BM25: finds exact words, such as the model number ZT-55U5
reranker = TextCrossEncoder("Xenova/ms-marco-MiniLM-L-6-v2")   # reads a question and a passage together, gives a score

# The vector database, in memory
qdrant = QdrantClient(":memory:")
qdrant.create_collection(
    COLLECTION,
    vectors_config={"dense": models.VectorParams(size=qdrant.get_embedding_size(MEANING_MODEL), distance=models.Distance.COSINE)},
    sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
)


# ================================================================ INDEXING

def load(source: str, filename: str) -> None:
    """Put one file into Qdrant. One passage per paragraph: a handbook section, or one product in the catalog."""
    text = (FOLDER / filename).read_text()
    passages = [passage.strip() for passage in text.split("\n\n") if passage.strip()]

    points = []
    for passage in passages:
        points.append(models.PointStruct(
            id=str(uuid4()),
            payload={"text": passage, "source": source},             # the text, and where it came from
            vector={
                "dense": models.Document(text=passage, model=MEANING_MODEL),   # by meaning
                "bm25": models.Document(text=passage, model=WORDS_MODEL),      # by exact words
            },
        ))
    qdrant.upsert(COLLECTION, points)


# ================================================================ SEARCHING

def hybrid_search(query: str, source: str) -> list[str]:
    """Steps 1 and 2: a meaning search and a word search, 10 results each, merged by RRF into one top 10."""
    only_this_source = models.Filter(must=[models.FieldCondition(key="source", match=models.MatchValue(value=source))])
    result = qdrant.query_points(
        COLLECTION,
        prefetch=[
            models.Prefetch(query=models.Document(text=query, model=MEANING_MODEL), using="dense", filter=only_this_source, limit=10),
            models.Prefetch(query=models.Document(text=query, model=WORDS_MODEL), using="bm25", filter=only_this_source, limit=10),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),     # RRF: passages ranked high in both lists come first
        limit=10,
    )
    return [point.payload["text"] for point in result.points]


def rerank(query: str, candidates: list[str]) -> list[str]:
    """Step 3: the reranker scores each candidate against the question. Keep the best 3."""
    scores = list(reranker.rerank(query, candidates))
    best = sorted(zip(scores, candidates), reverse=True)[:3]
    return [passage for score, passage in best]


def search(query: str, source: str) -> str:
    """The whole search, inside one source ("handbook" or "catalog"). This is what the tool search_knowledge calls."""
    candidates = hybrid_search(query, source)
    return "\n\n".join(rerank(query, candidates))


# ================================================================ build the index now, when this file is imported

load("handbook", "handbook.txt")
load("catalog", "catalog.txt")


# ================================================================ try it on its own:  python retrieval.py

if __name__ == "__main__":
    for question, source in [("can I return a dress after a week", "handbook"), ("ZT-55U5 refresh rate", "catalog")]:
        print(f"\n===== search({question!r}, {source!r})\n")
        print(search(question, source))
