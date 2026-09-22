"""How a DIFFERENT retrieval pipeline is wrapped to Contract 5.

The scaffold only ever calls `index.search(query, k, filters)` and
`index.describe()`. Any pipeline - the Day 3 hybrid search, a vector
database, a vendor search API - plugs in by wrapping its own output in
that shape. This file does it for a deliberately different pipeline:
word-overlap similarity (`dataset_utils.text_similarity`, the measure
notebook 04 uses to find near-duplicates), which returns
(ticket_id, similarity) pairs, not hits.

THE ADAPTER IS ONE LINE, in `search()` below:

    hits = [self.to_hit(ticket_id, similarity) for ticket_id, similarity in other_pipeline(...)]

Everything else here is the other pipeline itself, plus describe().

Try it without touching the scaffold:

    python -m capstone.reference_index.adapter_example "vpn drops after update"
    python -m capstone.run ticket INC-005310 --index capstone.reference_index.adapter_example:make_index
"""

import sys
from pathlib import Path

from capstone.contract import check_description, check_hits
from capstone.reference_index.bm25 import (DEFAULT_EXCLUDE, DEFAULT_SOURCE, FILTER_KEYS, matches,
                                           read_ids, sha256_of_file, ticket_to_item)

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "notebooks"))
import dataset_utils  # noqa: E402  (notebooks/ is not a package)


# ---------------------------------------------------------------------------
# The "other" pipeline. It knows nothing about Contract 5.
# ---------------------------------------------------------------------------

def load_tickets(source=DEFAULT_SOURCE, exclude=DEFAULT_EXCLUDE):
    excluded_ids = set(read_ids(exclude)) if exclude else set()
    tickets = dataset_utils.load_jsonl(source)
    return {ticket["ticket_id"]: ticket for ticket in tickets if ticket["ticket_id"] not in excluded_ids}


def word_overlap_search(query, tickets, top_n):
    """Returns [(ticket_id, similarity), ...], best first. Its own shape, not Contract 5's."""
    pairs = []
    for ticket_id, ticket in tickets.items():
        text = f"{ticket['subject']} {ticket['body']}"
        similarity = dataset_utils.text_similarity(query, text)
        if similarity > 0:
            pairs.append((ticket_id, round(similarity, 4)))
    pairs.sort(key=lambda pair: (-pair[1], pair[0]))
    return pairs[:top_n]


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

class WordOverlapIndex:
    def __init__(self, source=DEFAULT_SOURCE, exclude=DEFAULT_EXCLUDE):
        self.tickets = load_tickets(source, exclude)
        self.source_sha256 = sha256_of_file(source)

    def to_hit(self, ticket_id, similarity):
        item = ticket_to_item(self.tickets[ticket_id])       # reuse the reference hit layout
        return {**item, "score": similarity}

    def search(self, query, k=5, filters=None):
        unknown = [key for key in (filters or {}) if key not in FILTER_KEYS]
        if unknown:
            raise ValueError(f"Unknown filter key(s) {unknown}. This index filters on: {FILTER_KEYS}")
        # Ask the other pipeline for everything, so a filter cannot leave us short of k.
        candidates = word_overlap_search(query, self.tickets, top_n=len(self.tickets))
        # THE ONE LINE: the other pipeline's (ticket_id, similarity) pairs -> Contract 5 hits.
        hits = [self.to_hit(ticket_id, similarity) for ticket_id, similarity in candidates]
        hits = [hit for hit in hits if matches(hit["metadata"], filters or {})]
        return hits[:k]

    def describe(self):
        return {
            "name": "adapter-example-word-overlap",
            "build_id": self.source_sha256[:12],
            "built": "at load (nothing is saved)",
            "items": len(self.tickets),
            "source": "corpus/tickets/tickets_raw.jsonl",
        }


def make_index():
    """What `--index capstone.reference_index.adapter_example:make_index` calls."""
    return WordOverlapIndex()


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "vpn drops after update"
    index = make_index()
    info = check_description(index.describe())
    hits = check_hits(index.search(query, k=5), 5)
    print(f"{info['name']} ({info['items']} tickets): {len(hits)} hits for {query!r}, "
          f"each a valid Contract 5 hit")
    for rank, hit in enumerate(hits, start=1):
        subject = hit["metadata"]["title"].encode("ascii", "replace").decode("ascii")
        print(f"{rank}. {hit['doc_id']}  score {hit['score']:.3f}  {subject[:70]}")
