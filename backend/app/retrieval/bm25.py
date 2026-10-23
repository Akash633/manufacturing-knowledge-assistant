import re
import math
from typing import List, Dict, Any, Tuple
from collections import Counter
from app.core.config import settings
from app.core.logging import logger

def tokenize_manufacturing_text(text: str) -> List[str]:
    """
    Shop-floor aware tokenizer preserving hyphenated part codes, numbers, and tolerances.
    e.g. 'DEMO-CNC-01', 'ISO-VG-68', '1200 mm/min', '0.005mm'
    """
    # Normalize lower but keep alphanumeric + hyphen + dot patterns
    clean = re.sub(r"[^\w\s\.-]", " ", text.lower())
    tokens = [t.strip(".-") for t in clean.split() if len(t.strip(".-")) > 0]
    return tokens

class PureBM25Okapi:
    """
    Pure Python BM25Okapi implementation to guarantee zero external dependency failure.
    Uses Okapi BM25 formula with k1 and b parameters.
    """
    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lengths = [len(doc) for doc in corpus]
        self.avg_dl = sum(self.doc_lengths) / self.corpus_size if self.corpus_size > 0 else 1.0
        self.doc_freqs: Dict[str, int] = Counter()
        self.term_freqs: List[Counter] = []

        for doc in corpus:
            tf = Counter(doc)
            self.term_freqs.append(tf)
            for term in tf.keys():
                self.doc_freqs[term] += 1

        self.idf: Dict[str, float] = {}
        for term, freq in self.doc_freqs.items():
            # Standard Lucene/BM25 IDF with smoothing
            self.idf[term] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query_tokens: List[str]) -> List[float]:
        scores = [0.0] * self.corpus_size
        for term in query_tokens:
            if term not in self.idf:
                continue
            idf_val = self.idf[term]
            for idx, tf in enumerate(self.term_freqs):
                count = tf.get(term, 0)
                if count == 0:
                    continue
                dl = self.doc_lengths[idx]
                denom = count + self.k1 * (1.0 - self.b + self.b * (dl / self.avg_dl))
                scores[idx] += idf_val * ((count * (self.k1 + 1.0)) / denom)
        return scores


class BM25Engine:
    """
    High-performance BM25 retrieval engine with domain tokenization.
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunk_ids: List[str] = []
        self.corpus_tokens: List[List[str]] = []
        self._engine: Any = None

    def index_chunks(self, chunks: List[Dict[str, Any]]):
        self.chunk_ids = [c["id"] for c in chunks]
        self.corpus_tokens = [tokenize_manufacturing_text(c["content"]) for c in chunks]

        if not self.corpus_tokens:
            self._engine = None
            return

        try:
            from rank_bm25 import BM25Okapi
            self._engine = BM25Okapi(self.corpus_tokens, k1=self.k1, b=self.b)
        except Exception as e:
            logger.debug(f"Using pure-Python BM25Okapi fallback: {e}")
            self._engine = PureBM25Okapi(self.corpus_tokens, k1=self.k1, b=self.b)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float, int]]:
        """
        Returns list of tuples: (chunk_id, bm25_score, rank_1_indexed)
        """
        if not self._engine or not self.chunk_ids:
            return []

        tokens = tokenize_manufacturing_text(query)
        if not tokens:
            return []

        scores = self._engine.get_scores(tokens)
        scored_pairs = [(self.chunk_ids[i], float(scores[i])) for i in range(len(self.chunk_ids))]
        # Sort by score descending
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        results = []
        for rank, (cid, score) in enumerate(scored_pairs[:top_k], start=1):
            if score > 0.0001:
                results.append((cid, score, rank))

        return results

bm25_engine = BM25Engine(k1=settings.BM25_K1, b=settings.BM25_B)
