"""Contract 5, the index interface, as code (docs/contracts.md is the record).

Any retrieval index the capstone uses is an object with two methods:

    index.search(query, k=5, filters=None) -> list of hits
    index.describe()                       -> dict saying what the index is

A hit is a dict with exactly five keys:

    {"doc_id": "INC-004412",
     "chunk_id": "INC-004412#000",
     "text": "the retrieved text",
     "score": 7.41,
     "metadata": {"family": "ticket", "site": "MRB", "title": "...", "equipment_tags": []}}

`check_hits` is what the scaffold runs on every search, so an index that
breaks the contract stops with a sentence naming what is wrong, instead
of failing three steps later inside a prompt.
"""

from typing import Protocol

HIT_KEYS = ["doc_id", "chunk_id", "text", "score", "metadata"]
DESCRIBE_KEYS = ["name", "build_id", "built", "items"]


class Index(Protocol):
    def search(self, query: str, k: int = 5, filters: dict | None = None) -> list[dict]:
        ...

    def describe(self) -> dict:
        ...


class ContractError(ValueError):
    """An index returned something Contract 5 does not allow."""


def check_hits(hits, k):
    """Raise ContractError unless `hits` is a valid Contract 5 search result for this k."""
    if not isinstance(hits, list):
        raise ContractError(f"search() must return a list, got {type(hits).__name__}")
    if len(hits) > k:
        raise ContractError(f"search() returned {len(hits)} hits for k={k}")

    previous_score = None
    for position, hit in enumerate(hits):
        where = f"hit {position}"
        if not isinstance(hit, dict):
            raise ContractError(f"{where} is a {type(hit).__name__}, not a dict")
        if sorted(hit) != sorted(HIT_KEYS):
            raise ContractError(f"{where} has keys {sorted(hit)}; Contract 5 wants exactly {HIT_KEYS}")
        for key in ["doc_id", "chunk_id", "text"]:
            if not isinstance(hit[key], str) or hit[key] == "":
                raise ContractError(f"{where}: {key} must be a non-empty string")
        if not isinstance(hit["score"], (int, float)):
            raise ContractError(f"{where}: score must be a number")
        if not isinstance(hit["metadata"], dict):
            raise ContractError(f"{where}: metadata must be a dict")
        if previous_score is not None and hit["score"] > previous_score:
            raise ContractError(f"{where}: hits must be ordered by descending score")
        previous_score = hit["score"]
    return hits


def check_description(description):
    """Raise ContractError unless describe() returned the keys the scaffold prints."""
    if not isinstance(description, dict):
        raise ContractError("describe() must return a dict")
    missing = [key for key in DESCRIBE_KEYS if key not in description]
    if missing:
        raise ContractError(f"describe() is missing {missing}")
    return description
