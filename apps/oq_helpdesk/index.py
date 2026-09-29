"""A Contract 5 index over the OQ Helpdesk knowledgebase.

Contract 5 (docs/contracts.md, capstone/contract.py) says an index is any object with:

    search(query, k=5, filters=None) -> list of hits, each with exactly five keys
    describe()                       -> {"name", "build_id", "built", "items"}

This is a SECOND implementation of that contract, next to
capstone/reference_index/bm25.py which indexes tickets. Nothing outside this file
knows how retrieval works - which is the point the contract exists to make.

Stdlib only, on purpose: it starts in well under a second and downloads nothing,
so the demo survives a venue network.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent / "kb"

# BM25 constants. k1 damps term frequency, b damps document length.
K1 = 1.5
B = 0.75

# MEASURED on this corpus, 2026-09-29, and the number is the lesson:
#   covered questions, full sentence : 7.98 - 16.79
#   covered questions, one word      : 2.95 - 10.24   ("laptop" scores 2.95)
#   off-corpus questions             : 0.00 -  4.17   ("annual leave" scores 4.17)
# The ranges OVERLAP, so no single absolute BM25 score separates a question this
# knowledgebase covers from one it does not. That is a property of lexical
# retrieval, not a bug to tune away - and it is why notebook 07 moves on to
# embeddings and a reranker.
#
# So this floor is only a "did we retrieve anything at all" guard. The real
# grounding guard is in main.py: the model is given the retrieved text and
# nothing else, and is told to refuse when the text does not answer the question.
# The UI shows every score so a human can see which guard did the work.
SCORE_FLOOR = 2.0

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the","a","an","and","or","is","are","to","of","in","on","for","it","this","that",
         "with","as","at","by","be","not","do","does","how","i","my","you","your","can","if",
         "what","when","why","from","have","has","was","were","will","would","there","then"}


def tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


def parse_article(path: Path) -> dict:
    """Read one KB markdown file into its frontmatter and body."""
    raw = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = raw
    if raw.startswith("---"):
        _, front, body = raw.split("---", 2)
        for line in front.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return {"meta": meta, "body": body.strip(), "path": path}


def chunk_article(article: dict) -> list[dict]:
    """One chunk per '##' section, with the article title prepended.

    The title travels with every chunk on purpose: a section headed 'Steps' is
    meaningless out of context, and retrieval has only the chunk to go on.
    """
    meta, body = article["meta"], article["body"]
    kb_id = meta.get("kb_id", article["path"].stem)
    title = meta.get("title", kb_id)

    parts = re.split(r"\n(?=## )", body)
    chunks = []
    for n, part in enumerate(parts):
        text = part.strip()
        if not text or text.startswith("# "):        # the H1 line alone is not a chunk
            text = re.sub(r"^#\s+.*\n?", "", text).strip()
            if not text:
                continue
        section = text.splitlines()[0].lstrip("# ").strip()
        chunks.append({
            "doc_id": kb_id,
            "chunk_id": f"{kb_id}#{n:03d}",
            "text": f"{title}\n\n{text}",
            "metadata": {
                "family": "kb_article",
                "title": title,
                "section": section,
                "category": meta.get("category", ""),
                "routing_queue": meta.get("routing_queue", ""),
                "systems": [s.strip() for s in meta.get("systems", "").split(",") if s.strip()],
                "updated": meta.get("updated", ""),
                "source": article["path"].name,
            },
        })
    return chunks


class HelpdeskIndex:
    """BM25 over KB article sections. Satisfies Contract 5."""

    def __init__(self, chunks: list[dict], build_info: dict):
        self.chunks = chunks
        self.build_info = build_info
        self._terms = [Counter(tokens(c["text"])) for c in chunks]
        self._lengths = [sum(t.values()) for t in self._terms]
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
        n = len(chunks)
        df: Counter = Counter()
        for t in self._terms:
            df.update(t.keys())
        # BM25 idf, floored at zero so a term in every chunk cannot subtract score
        self._idf = {w: max(0.0, math.log(1 + (n - c + 0.5) / (c + 0.5))) for w, c in df.items()}

    def _score(self, query_terms: list[str], i: int) -> float:
        tf, length, total = self._terms[i], self._lengths[i], 0.0
        for w in query_terms:
            f = tf.get(w, 0)
            if not f:
                continue
            denom = f + K1 * (1 - B + B * (length / self._avg_len if self._avg_len else 1))
            total += self._idf.get(w, 0.0) * (f * (K1 + 1)) / denom
        return total

    def search(self, query: str, k: int = 5, filters: dict | None = None) -> list[dict]:
        query_terms = tokens(query)
        if not query_terms:
            return []
        scored = []
        for i, chunk in enumerate(self.chunks):
            if filters and not self._matches(chunk["metadata"], filters):
                continue
            s = self._score(query_terms, i)
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda pair: (-pair[0], self.chunks[pair[1]]["chunk_id"]))
        hits = []
        for s, i in scored[:k]:
            c = self.chunks[i]
            hits.append({"doc_id": c["doc_id"], "chunk_id": c["chunk_id"], "text": c["text"],
                         "score": round(s, 3), "metadata": dict(c["metadata"])})
        return hits

    @staticmethod
    def _matches(metadata: dict, filters: dict) -> bool:
        for key, want in filters.items():
            got = metadata.get(key)
            if isinstance(got, list):
                if want not in got:
                    return False
            elif got != want:
                return False
        return True

    def describe(self) -> dict:
        return {"name": "oq-helpdesk-bm25", "build_id": self.build_info["build_id"],
                "built": self.build_info["built"], "items": len(self.chunks)}

    def articles(self) -> list[dict]:
        """Every article once, for the UI's 'what is in the knowledgebase' panel."""
        seen, out = set(), []
        for c in self.chunks:
            if c["doc_id"] in seen:
                continue
            seen.add(c["doc_id"])
            out.append({"kb_id": c["doc_id"], "title": c["metadata"]["title"],
                        "category": c["metadata"]["category"],
                        "routing_queue": c["metadata"]["routing_queue"],
                        "systems": c["metadata"]["systems"]})
        return sorted(out, key=lambda a: a["kb_id"])


def build_index(kb_dir: Path | str = KB_DIR) -> HelpdeskIndex:
    kb_dir = Path(kb_dir)
    paths = sorted(kb_dir.glob("*.md"))
    if not paths:
        raise FileNotFoundError(f"no knowledgebase articles in {kb_dir}")
    chunks: list[dict] = []
    digest = hashlib.sha256()
    for p in paths:
        digest.update(p.read_bytes())
        chunks.extend(chunk_article(parse_article(p)))
    info = {"build_id": digest.hexdigest()[:12],
            "built": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return HelpdeskIndex(chunks, info)


if __name__ == "__main__":
    import sys
    idx = build_index()
    print(idx.describe())
    if len(sys.argv) > 1:
        for h in idx.search(" ".join(sys.argv[1:])):
            print(f"  {h['score']:6.2f}  {h['chunk_id']:14s} {h['metadata']['title'][:46]}"
                  f" | {h['metadata']['section'][:24]}")
