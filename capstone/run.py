"""Run the capstone from the command line (a laptop, or `!python` in a Colab cell).

    python -m capstone.run status                      what is wired, and every FALLBACK
    python -m capstone.run ticket INC-005310           one corpus ticket through your pipeline
    python -m capstone.run ticket --text "vpn drops"   a pasted ticket
    python -m capstone.run eval                        the held-out 20, scored by scripts/run_eval.py
    python -m capstone.run eval --resume               ...keeping replies saved before a disconnect
    python -m capstone.run register-adapter            put your adapter (or the pre-baked one)
                                                       behind the "tuned" endpoint (needs Ollama)

Options for all of them:
    --usecase capstone.my_usecase     the file with your five extension points
    --endpoint local|hosted|tuned     override ENDPOINT in the use case file
    --index <file or module:function> override MY_INDEX
    --adapter <folder>                override MY_ADAPTER_DIR
    --out <folder>                    audit logs, saved index, eval runs (on Colab: a Drive folder)
    --no-services                     do not start the ERP / MCP server (no equipment lookup)
    --keep-services                   leave the ERP / MCP server running afterwards (faster next run)

Exit codes: 0 done, 2 could not run (a sentence says why).
"""

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path

from capstone.wiring import DEFAULT_OUT, REPO_ROOT, WIDTH, Capstone, CostCapReached, one_line

import dataset_utils  # noqa: E402  (wiring put notebooks/ on the path)
from config.endpoints import EndpointError  # noqa: E402

DEFAULT_DATASET = REPO_ROOT / "data" / "eval" / "heldout_20.jsonl"
TICKETS = REPO_ROOT / "corpus" / "tickets" / "tickets_raw.jsonl"


def build_parser():
    parser = argparse.ArgumentParser(description="Day 5 capstone scaffold.")
    parser.add_argument("command", choices=["status", "ticket", "eval", "register-adapter"])
    parser.add_argument("ticket_id", nargs="?", help="for `ticket`: a corpus ticket id")
    parser.add_argument("--text", help="for `ticket`: ticket text to run instead of a corpus ticket")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="for `eval`: a pairs file")
    parser.add_argument("--limit", type=int, help="for `eval`: first N tickets only")
    parser.add_argument("--label", help="for `eval`: column name in a comparison")
    parser.add_argument("--resume", action="store_true",
                        help="for `eval`: keep the replies already saved for this run id (after a "
                             "disconnect); without it every ticket is asked again")
    parser.add_argument("--usecase", default="capstone.my_usecase")
    parser.add_argument("--endpoint", choices=["local", "hosted", "tuned"])
    parser.add_argument("--index")
    parser.add_argument("--adapter")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--no-services", action="store_true")
    parser.add_argument("--keep-services", action="store_true")
    parser.add_argument("--erp-port", type=int, default=8000)
    parser.add_argument("--mcp-port", type=int, default=8100)
    return parser


def find_corpus_ticket(ticket_id):
    for ticket in dataset_utils.load_jsonl(TICKETS):
        if ticket["ticket_id"] == ticket_id.upper():
            return {"ticket_id": ticket["ticket_id"], "text": dataset_utils.format_ticket_text(ticket)}
    return None


def pasted_ticket(text):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return {"ticket_id": f"PASTED-{digest}", "text": text}


def show_value(value):
    if value is None or isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=True)
    return str(value)


def print_result(result, capstone):
    ticket = result["ticket"]
    context = result["context"]
    print(f"TICKET {ticket['ticket_id']}")
    for line in ticket["text"].splitlines()[:6]:
        if line.strip():
            print("  | " + one_line(line, WIDTH - 4))

    neighbours = context.get("neighbours", [])
    print(f"NEIGHBOURS ({capstone.index_row['info']['name']}): {len(neighbours)}")
    for rank, hit in enumerate(neighbours, start=1):
        print(one_line(f"  {rank}. {hit['doc_id']} score {hit['score']:.2f}  {hit['metadata'].get('title', '')}"))

    equipment = context.get("equipment", [])
    print(f"EQUIPMENT (MCP get_equipment): {len(equipment) or 'no plant tag in the ticket'}")
    for record in equipment:
        if "error" in record:
            print(one_line(f"  {record['tag']}: NOT FOUND / ERROR - {record['error']}"))
        else:
            print(one_line(f"  {record['tag']}: {record['equipment_type']} at {record['site']}, "
                           f"{record['status']}, criticality {record['criticality']}, "
                           f"open work orders {record['open_work_orders']}"))

    print(f"MODEL ({capstone.endpoint_name}: {capstone.llm.model}) {result['seconds']} s, "
          f"{result['tokens_in']} tokens in, {result['tokens_out']} out")
    if result["output"] is None:
        print("  raw reply: " + one_line(result["reply"], WIDTH - 13))
    else:
        for key, value in result["output"].items():
            print(one_line(f"  {key:<17} {show_value(value)}"))
    validation = result["validation"]
    print(f"VALID      {validation['valid']}" +
          ("" if validation["valid"] else "  " + one_line("; ".join(validation["problems"]), 70)))
    decision = result["decision"]
    print(one_line(f"DECISION   {decision['action']}: {decision.get('why', '')}"))
    for key, value in decision.items():
        if key not in ("action", "why"):
            print(one_line(f"  {key:<17} {show_value(value)}"))
    print(one_line(f"AUDIT      trace {result['trace_id']} in {capstone.llm_log.path}"))


def run_eval_through_pipeline(capstone, args):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import run_eval

    rows = dataset_utils.load_jsonl(args.dataset)
    ticket_ids = {row["messages"][1]["content"]: row["ticket_id"] for row in rows}
    decisions = {}

    def ask(messages):
        text = messages[1]["content"]
        ticket = {"ticket_id": ticket_ids.get(text, "UNKNOWN"), "text": text}
        result = capstone.run_ticket(ticket)
        action = result["decision"]["action"]
        decisions[action] = decisions.get(action, 0) + 1
        return result["reply"]          # the harness scores the model's reply, before your checks

    usecase = capstone.usecase
    label = args.label or f"{usecase.PROMPT_VERSION}-{capstone.endpoint_name}"
    run_id = f"capstone_{usecase.PROMPT_VERSION}_{capstone.endpoint_name}"
    try:
        run_eval.run_evaluation(args.dataset, ask, endpoint_name=f"capstone:{capstone.endpoint_name}",
                                model=capstone.llm.model, label=label, out_dir=Path(args.out) / "eval",
                                run_id=run_id, limit=args.limit, resume=args.resume)
    except run_eval.EvalError as error:
        print(f"Stopped: {error}")
        sys.exit(2)
    if decisions:
        print(f"What your decide() did with them: {decisions}")
    else:
        print("No new model calls: every reply came from the saved run (--resume).")


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        usecase = importlib.import_module(args.usecase)
    except Exception as error:      # noqa: BLE001 - a typo in the group's file is the common case
        print(f"Cannot load the use case {args.usecase}: {type(error).__name__}: {error}")
        sys.exit(2)

    start_services = not args.no_services and args.command in ("status", "ticket", "eval")
    try:
        capstone = Capstone(usecase, out_dir=args.out, endpoint=args.endpoint, index_setting=args.index,
                            adapter_setting=args.adapter, start_services=start_services,
                            erp_port=args.erp_port, mcp_port=args.mcp_port)
    except (EndpointError, ValueError) as error:
        print(f"Cannot start: {error}")
        sys.exit(2)

    try:
        capstone.print_status()
        if args.command == "register-adapter":
            ok = capstone.register_chosen_adapter()
            sys.exit(0 if ok else 2)
        if args.command == "ticket":
            if args.text:
                ticket = pasted_ticket(args.text)
            elif args.ticket_id:
                ticket = find_corpus_ticket(args.ticket_id)
                if ticket is None:
                    print(f"No ticket {args.ticket_id} in {TICKETS.name}.")
                    sys.exit(2)
            else:
                print("Give a ticket id (ticket INC-005310) or --text.")
                sys.exit(2)
            print_result(capstone.run_ticket(ticket), capstone)
        if args.command == "eval":
            run_eval_through_pipeline(capstone, args)
    except (EndpointError, CostCapReached) as error:
        print(f"Stopped: {error}")
        sys.exit(2)
    finally:
        if not args.keep_services:
            capstone.close()


if __name__ == "__main__":
    main()
