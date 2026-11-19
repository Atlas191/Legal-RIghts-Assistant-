"""Hybrid retrieval engine: dense (ChromaDB) + BM25 keyword, merged with Reciprocal Rank Fusion.
Returns structured results. No printing, no input() — pure data layer."""
import re
from collections import defaultdict
from rank_bm25 import BM25Okapi
from kb_utils import load_chunks, tokenize

DB_DIR = "./chroma_db"
MAX_RESULTS = 3          # upper limit, not a target: fewer are shown when the rest are weak
DENSE_K = BM25_K = 10
RRF_K = 60

# ---- Relevance settings (calibrated with DEBUG = True) ----
DIST_HARD_OFFTOPIC = 0.95 # dense distance above this = clearly unrelated semantically
DIST_SOFT_OFFTOPIC = 0.75 # moderate distance: off-topic only if keywords ALSO miss
BM25_ZERO = 0.5           # BM25 below this means zero meaningful keyword overlap
DIST_GAP = 0.10          # keep a lower result only if within this distance of the best one
BM25_KEEP_FRAC = 0.5     # ...or if its keyword score is at least this fraction of the best
LOOKUP_MAX_TOKENS = 2    # 1-2 word queries (e.g. "498A") are treated as exact lookups


def build_search(vectorstore, chunks):
    bm25 = BM25Okapi([tokenize(c.page_content) for c in chunks])
    by_id = {c.metadata["child_id"]: i for i, c in enumerate(chunks)}

    def search(query):
        q_tokens = tokenize(query)
        dense = vectorstore.similarity_search_with_score(query, k=DENSE_K)
        bm_scores = bm25.get_scores(q_tokens)
        bm_top = sorted(range(len(chunks)), key=lambda i: bm_scores[i], reverse=True)[:BM25_K]
        max_bm25 = float(max(bm_scores)) if len(bm_scores) else 0.0
        best_dist = dense[0][1] if dense else 9.0

        is_statute_lookup = bool(
            re.fullmatch(r"(?i)\s*((section|sec|ipc|bns|bnss|s\.?)\s*)?\d{1,3}[a-z]{0,2}\s*", query)
            and max_bm25 > 0
        )

        if not is_statute_lookup:
            if best_dist > 0.75 and max_bm25 < 5.0:
                return [], dict(off_topic=True, best_dist=best_dist, max_bm25=max_bm25)
            if best_dist > 0.90 and len(q_tokens) > LOOKUP_MAX_TOKENS:
                return [], dict(off_topic=True, best_dist=best_dist, max_bm25=max_bm25)
            if best_dist > 0.80 and max_bm25 < 8.0 and len(q_tokens) > LOOKUP_MAX_TOKENS:
                return [], dict(off_topic=True, best_dist=best_dist, max_bm25=max_bm25)

        # Reciprocal Rank Fusion over child chunks
        fused = defaultdict(float)
        dense_dist = {}
        for rank, (doc, dist) in enumerate(dense):
            cid = doc.metadata["child_id"]
            fused[cid] += 1 / (RRF_K + rank + 1)
            dense_dist[cid] = dist
        for rank, i in enumerate(bm_top):
            if bm_scores[i] > 0:
                fused[chunks[i].metadata["child_id"]] += 1 / (RRF_K + rank + 1)

        # Expand to parent sections and collect each parent's best dense / BM25 evidence
        parents = {}
        for cid, f in sorted(fused.items(), key=lambda kv: kv[1], reverse=True):
            meta = chunks[by_id[cid]].metadata
            p = parents.setdefault(meta["parent_id"], dict(meta=meta, dist=None, bm25=0.0, fused=f))
            if cid in dense_dist:
                p["dist"] = dense_dist[cid] if p["dist"] is None else min(p["dist"], dense_dist[cid])
            p["bm25"] = max(p["bm25"], float(bm_scores[by_id[cid]]))
        ranked = list(parents.values())

        lookup = len(q_tokens) <= LOOKUP_MAX_TOKENS
        kept = []
        for n, p in enumerate(ranked):
            bm_ok = p["bm25"] >= BM25_KEEP_FRAC * max_bm25 and p["bm25"] > 0
            dense_ok = (p["dist"] is not None and p["dist"] <= DIST_HARD_OFFTOPIC
                        and p["dist"] <= best_dist + DIST_GAP)
            if n == 0 or (bm_ok if lookup else (bm_ok or dense_ok)):
                kept.append(p)
            if len(kept) == MAX_RESULTS:
                break
        return kept, dict(off_topic=False, best_dist=best_dist, max_bm25=max_bm25)

    return search


def load_search():
    """Load embeddings, Chroma, and chunks once; return the search function."""
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    store = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    return build_search(store, load_chunks())


def retrieve(search, query):
    """Run a query and return a structured dict (no printing)."""
    kept, info = search(query)
    results = []
    for p in kept:
        m = p["meta"]
        body = m["parent_text"].split("\n", 1)[1] if "\n" in m["parent_text"] else m["parent_text"]
        results.append({
            "id": m["parent_id"],
            "heading": m["heading"],
            "act": m["act"],
            "section": m["section"],
            "formerly_ipc": m["formerly_ipc"],
            "source_file": m["source_file"],
            "text": body,
        })
    return {
        "off_topic": info["off_topic"],
        "best_dist": info["best_dist"],
        "max_bm25": info["max_bm25"],
        "results": results,
    }
