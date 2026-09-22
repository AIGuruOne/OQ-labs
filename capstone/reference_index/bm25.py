"""The reference index: BM25 keyword search over the ticket corpus.

A REFERENCE implementation of Contract 5, so the Day 5 capstone runs end
to end on data this repo already has. It is not the Day 3 retrieval
pipeline and does not try to be: no embeddings, no chunking (a ticket is
one chunk), no rerank. Standard library only - nothing to install.

Why BM25: tickets are short and full of exact tokens (LAP-04412,
P-1201A, GateKey VPN) that keyword search matches exactly. The tokenizer
below keeps a tag like P-1201A as ONE token, so a search for the tag
finds the tag and not every ticket with "1201" in it.

    index = build_index()                         # ~0.2 s for 600 tickets
    hits = index.search("vpn drops after update", k=5)
    hits = index.search("pump screen red", k=3, filters={"site": "MRB"})
    index.save("reference_index.json")            # and load_index(path) later

The held-out 20 (data/eval/heldout_20.jsonl) are LEFT OUT by default,
so an eval on them cannot retrieve the answer to its own question.
"""

import datetime
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT / "corpus" / "tickets" / "tickets_raw.jsonl"
DEFAULT_EXCLUDE = REPO_ROOT / "data" / "eval" / "heldout_20.jsonl"

INDEX_NAME = "reference-bm25-tickets"
ALGORITHM = "bm25 k1=1.5 b=0.75, tag-aware tokens, one chunk per ticket"
K1 = 1.5
B = 0.75

# A tag (P-1201A, HX-3040, LAP-04412, INC-004412, WO-118305) is one token;
# everything else splits on anything that is not a letter or digit.
TOKEN_PATTERN = re.compile(r"[a-z]{1,4}-\d{4,6}[a-z]?|[a-z0-9]+")
PLANT_TAG_PATTERN = re.compile(r"\b[A-Z]{1,3}-\d{4}[A-Z]?\b")

# The keys `filters` may use: Contract 1 ticket fields, plus family and tags.
FILTER_KEYS = ["family", "site", "channel", "equipment_tags"]


def tokens(text):
    return TOKEN_PATTERN.findall(text.lower())


def plant_tags_in(text):
    """Equipment tags (P-1201A) in a text, in order of first appearance, no repeats."""
    found = []
    for tag in PLANT_TAG_PATTERN.findall(text):
        if tag not in found:
            found.append(tag)
    return found


def sha256_of_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ticket_to_item(ticket):
    """One ticket -> one indexed item (the hit a search returns, minus the score)."""
    subject = ticket["subject"].strip() or "(no subject)"
    text = f"{subject}\n\n{ticket['body']}"
    return {
        "doc_id": ticket["ticket_id"],
        "chunk_id": f"{ticket['ticket_id']}#000",
        "text": text,
        "metadata": {
            "family": "ticket",
            "site": ticket["site"],
            "channel": ticket["channel"],
            "created": ticket["created"],
            "title": subject,
            "equipment_tags": plant_tags_in(text),
        },
    }


def check_filters(filters):
    if filters is None:
        return {}
    unknown = [key for key in filters if key not in FILTER_KEYS]
    if unknown:
        raise ValueError(f"Unknown filter key(s) {unknown}. This index filters on: {FILTER_KEYS}")
    return filters


def matches(metadata, filters):
    for key, wanted in filters.items():
        value = metadata.get(key)
        if isinstance(value, list):
            if wanted not in value:
                return False
        elif value != wanted:
            return False
    return True


class TicketIndex:
    """BM25 over a list of items. Implements Contract 5: search() and describe()."""

    def __init__(self, items, build_info):
        self.items = items
        self.build_info = build_info

        # The statistics BM25 needs, computed once.
        self.term_counts = [Counter(tokens(item["text"])) for item in items]
        self.lengths = [sum(counts.values()) for counts in self.term_counts]
        self.average_length = sum(self.lengths) / max(len(items), 1)
        document_frequency = Counter()
        for counts in self.term_counts:
            document_frequency.update(counts.keys())
        total = len(items)
        self.idf = {}
        for term, frequency in document_frequency.items():
            self.idf[term] = math.log(1 + (total - frequency + 0.5) / (frequency + 0.5))

    def score(self, query_terms, position):
        counts = self.term_counts[position]
        length_factor = K1 * (1 - B + B * self.lengths[position] / self.average_length)
        total = 0.0
        for term in query_terms:
            in_doc = counts.get(term, 0)
            if in_doc == 0:
                continue
            total += self.idf[term] * in_doc * (K1 + 1) / (in_doc + length_factor)
        return total

    def search(self, query, k=5, filters=None):
        filters = check_filters(filters)
        query_terms = set(tokens(query))

        scored = []
        for position, item in enumerate(self.items):
            if not matches(item["metadata"], filters):
                continue
            score = self.score(query_terms, position)
            if score > 0:
                scored.append((round(score, 4), item["doc_id"], position))

        # Highest score first; equal scores in doc_id order, so a search is repeatable.
        scored.sort(key=lambda entry: (-entry[0], entry[1]))

        hits = []
        for score, doc_id, position in scored[:k]:
            item = self.items[position]
            hit = {
                "doc_id": item["doc_id"],
                "chunk_id": item["chunk_id"],
                "text": item["text"],
                "score": score,
                "metadata": dict(item["metadata"]),
            }
            hits.append(hit)
        return hits

    def describe(self):
        return dict(self.build_info)

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        saved = {"build_info": self.build_info, "items": self.items}
        path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
        return path


def load_index(path):
    saved = json.loads(Path(path).read_text(encoding="utf-8"))
    return TicketIndex(saved["items"], saved["build_info"])


def read_ids(pairs_path):
    ids = []
    with open(pairs_path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                ids.append(json.loads(line)["ticket_id"])
    return ids


def build_id_for(source_sha256, excluded_ids):
    """Same source + same exclusions + same algorithm = same build id, on any machine."""
    fingerprint = json.dumps([source_sha256, sorted(excluded_ids), ALGORITHM])
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:12]


def build_index(source=DEFAULT_SOURCE, exclude=DEFAULT_EXCLUDE, index_log=None):
    """Build the index from a tickets JSONL file.

    exclude    a pairs file whose ticket_ids are left out (default: the
               held-out 20), or None to index everything
    index_log  an open-for-append log (wiring.AuditLog) or None; gets one
               `index_write` line per item (governance template 5.1.3)
    """
    source = Path(source)
    excluded_ids = read_ids(exclude) if exclude else []
    source_sha256 = sha256_of_file(source)

    items = []
    item_lines = []
    with open(source, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            ticket = json.loads(line)
            if ticket["ticket_id"] in excluded_ids:
                continue
            items.append(ticket_to_item(ticket))
            item_lines.append(line_number)

    try:
        source_shown = source.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        source_shown = str(source)
    build_info = {
        "name": INDEX_NAME,
        "build_id": build_id_for(source_sha256, excluded_ids),
        "built": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "items": len(items),
        "source": source_shown,
        "source_sha256": source_sha256,
        "excluded": len(excluded_ids),
        "algorithm": ALGORITHM,
    }
    index = TicketIndex(items, build_info)

    if index_log is not None:
        for item, line_number in zip(items, item_lines):
            index_log.write({
                "event": "index_write",
                "trace_id": build_info["build_id"],
                "action": "add",
                "doc_id": item["doc_id"],
                "chunk_id": item["chunk_id"],
                "source": {"path": source_shown, "sha256": source_sha256, "line": line_number},
                "produced_by": "human",
                "score_line": None,
                "approval": {"required": False},
                "index_build_id": build_info["build_id"],
            })
    return index
