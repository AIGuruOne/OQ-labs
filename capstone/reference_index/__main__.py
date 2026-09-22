"""Build or query the reference index from the command line.

    python -m capstone.reference_index build --out checkpoints/local/capstone/reference_index.json
    python -m capstone.reference_index search "vpn keeps dropping" --k 5
    python -m capstone.reference_index search "pump screen red" --filter site=MRB

`search` builds the index in memory when --index is not given (0.2 s).
Output is ASCII, at most 100 columns.
"""

import argparse
import sys
import time
from pathlib import Path

from capstone.contract import check_description, check_hits
from capstone.reference_index.bm25 import DEFAULT_EXCLUDE, DEFAULT_SOURCE, build_index, load_index

WIDTH = 100


def ascii_line(text, width):
    flat = " ".join(str(text).split())
    flat = flat.encode("ascii", "replace").decode("ascii")
    return flat if len(flat) <= width else flat[:width - 3] + "..."


def parse_filters(pairs):
    filters = {}
    for pair in pairs or []:
        if "=" not in pair:
            sys.exit(f"--filter wants key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        filters[key] = value
    return filters or None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reference index (Contract 5) over the ticket corpus.")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="build the index and save it as JSON")
    build.add_argument("--source", default=str(DEFAULT_SOURCE))
    build.add_argument("--exclude", default=str(DEFAULT_EXCLUDE),
                       help="pairs file whose tickets are left out ('' = none); default: the held-out 20")
    build.add_argument("--out", required=True)

    search = commands.add_parser("search", help="run one query and print the hits")
    search.add_argument("query")
    search.add_argument("--k", type=int, default=5)
    search.add_argument("--filter", action="append", metavar="KEY=VALUE")
    search.add_argument("--index", help="a saved index; default: build one in memory")

    args = parser.parse_args(argv)

    if args.command == "build":
        started = time.perf_counter()
        index = build_index(args.source, exclude=args.exclude or None)
        path = index.save(args.out)
        seconds = time.perf_counter() - started
        info = check_description(index.describe())
        print(f"Built {info['name']} build {info['build_id']}: {info['items']} tickets "
              f"({info['excluded']} held out) in {seconds:.2f} s")
        print(f"Saved {path} ({Path(path).stat().st_size:,} bytes)")
        return

    index = load_index(args.index) if args.index else build_index()
    filters = parse_filters(args.filter)
    try:
        hits = check_hits(index.search(args.query, k=args.k, filters=filters), args.k)
    except ValueError as err:
        print(f"Search refused: {err}")
        sys.exit(2)
    print(f"{len(hits)} hits for {args.query!r}" + (f" with {filters}" if filters else ""))
    for rank, hit in enumerate(hits, start=1):
        meta = hit["metadata"]
        print(f"{rank}. {hit['doc_id']}  score {hit['score']:.2f}  site {meta.get('site')}  "
              f"tags {meta.get('equipment_tags')}")
        print("   " + ascii_line(hit["text"], WIDTH - 3))


if __name__ == "__main__":
    main()
