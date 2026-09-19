"""Check a generated ticket corpus. Exits non-zero if any check FAILS.

    python scripts/check_tickets.py --tickets corpus/tickets/tickets_raw.jsonl \
        --labels data/finetune/ticket_labels.jsonl \
        --schema data/finetune/ticket_schema.json --samples 12

Checks, in order:
    1. raw tickets follow Contract 1 (docs/contracts.md)
    2. every ground-truth record validates against the section 8B schema
    3. labels are derivable: a labelled system / asset really is in the text
    4. the class mix is imbalanced the intended way
    5. how many accidental near-duplicate bodies there are (reported)
    6. nothing reads as a real OQ site, system, company or person
    7. prints sample tickets in full, for a human to judge realism

Needs jsonschema (pinned in requirements.txt). The generator itself
needs nothing but the standard library.
"""

import argparse
import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ticket_phrases as phrases  # noqa: E402
import ticket_scenarios as bank  # noqa: E402

RAW_KEYS = ["ticket_id", "created", "site", "channel", "subject", "body"]
CHANNELS = ["portal", "email", "phone", "walk_in"]

# Anything here appearing in the corpus is a section 9 breach. Real OQ
# group companies, facilities and places in Oman, the vendors and
# products OQ is publicly known to run (its ERP is SAP, project name
# "e-Symphony"), other operators, and Omani-style family names (the
# corpus uses first names only, so "Al Something" must never appear).
DENYLIST = [
    # the client and its group / partners
    "OQ", "OQ8", "OQGN", "OQEP", "OQBI", "Orpic", "Oman Oil", "OOCEP", "Takamul", "OTTCO", "Oxea",
    "Tracez", "PDO", "Petroleum Development", "OLNG", "Oman LNG", "Abraj", "Hydrom", "Kuwait Petroleum",
    "Shell", "BP", "Occidental", "TotalEnergies", "Aramco", "ADNOC",
    # real places and facilities
    "Oman", "Omani", "Muscat", "Sohar", "Suhar", "Salalah", "Duqm", "Mina Al Fahal", "Fahal", "Musandam",
    "Liwa", "Sur", "Nizwa", "Ibri", "Fahud", "Marmul", "Qalhat", "Jefnain", "Dhofar", "Barka", "Seeb",
    "Raysut", "Bukha", "Khasab", "Ras Markaz", "Yibal", "Saih Rawl", "Mukhaizna", "Rusayl", "Mirbat",
    # real enterprise products and vendors
    "SAP", "HANA", "S/4", "Symphony", "Ariba", "SuccessFactors", "Concur", "Maximo", "ServiceNow",
    "Remedy", "Oracle", "Primavera", "Meridian", "OSIsoft", "PI System", "AspenTech", "Honeywell",
    "Yokogawa", "Emerson", "DeltaV", "Cisco", "AnyConnect", "Citrix", "Okta", "Workday", "Salesforce",
    "Documentum", "SharePoint", "Omantel", "Ooredoo", "Fortinet", "Palo Alto", "Zscaler",
]
# real three-letter codes a site code must never collide with
# (Oman airport codes and common abbreviations of real facilities)
REAL_SITE_CODES = ["MAF", "MCT", "SLL", "OHS", "DQM", "KHS", "MSH", "RMB", "SUH", "FAU", "OMM", "LKW",
                   "TTH", "BYB", "RNM", "JNJ", "AOM", "UKH", "SOH", "SHR", "SAL", "SUR", "LPP", "PDO"]
FAMILY_NAME_PATTERN = re.compile(r"\b(?:Al|Al-|bin|bint)\s?[A-Z][a-z]+")

failures = []


def report(name, problems, total):
    """One PASS/FAIL line per check, plus the first few offenders."""
    status = "PASS" if not problems else "FAIL"
    print(f"[{status}] {name}: {total - len(problems)}/{total} ok")
    for problem in problems[:5]:
        print(f"         {problem}")
    if problems:
        failures.append(name)


def load_jsonl(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


# ---------------------------------------------------------------------
# 1. Contract 1 - raw ticket format
# ---------------------------------------------------------------------


def check_raw_format(tickets):
    problems = []
    for ticket in tickets:
        ticket_id = ticket.get("ticket_id")
        if list(ticket.keys()) != RAW_KEYS:
            problems.append(f"{ticket_id}: keys are {list(ticket.keys())}")
            continue
        if not re.fullmatch(r"INC-\d{6}", ticket_id):
            problems.append(f"{ticket_id}: bad ticket id")
        if not re.fullmatch(r"[A-Z]{3}", ticket["site"]) or ticket["site"] in REAL_SITE_CODES:
            problems.append(f"{ticket_id}: bad site code {ticket['site']}")
        if ticket["channel"] not in CHANNELS:
            problems.append(f"{ticket_id}: bad channel {ticket['channel']}")
        if not ticket["body"].strip():
            problems.append(f"{ticket_id}: empty body")
        try:
            datetime.fromisoformat(ticket["created"])
        except ValueError:
            problems.append(f"{ticket_id}: created is not ISO 8601")
    report("raw tickets follow Contract 1", problems, len(tickets))

    ids = [ticket["ticket_id"] for ticket in tickets]
    bodies = [ticket["body"] for ticket in tickets]
    report("ticket ids unique", ["duplicate ids"] if len(set(ids)) != len(ids) else [], 1)
    report("no two bodies identical", ["duplicate bodies"] if len(set(bodies)) != len(bodies) else [], 1)


# ---------------------------------------------------------------------
# 2. Schema
# ---------------------------------------------------------------------


def check_schema(labels, schema):
    validator = Draft202012Validator(schema)
    problems = []
    for label in labels:
        for error in validator.iter_errors(label["record"]):
            problems.append(f"{label['ticket_id']}: {error.message}")
        if label["record"].get("routing_queue") not in bank.ROUTING_QUEUES:
            problems.append(f"{label['ticket_id']}: unknown routing_queue")
        if list(label["record"].keys()) != schema["required"]:
            problems.append(f"{label['ticket_id']}: field order differs from the spec")
    report("records validate against the 8B schema", problems, len(labels))


# ---------------------------------------------------------------------
# 3. Labels are derivable from the text
# ---------------------------------------------------------------------


def check_labels_derivable(tickets, labels):
    text_by_id = {t["ticket_id"]: (t["subject"] + "\n" + t["body"]) for t in tickets}
    system_problems = []
    asset_problems = []
    for label in labels:
        text = text_by_id[label["ticket_id"]]
        record = label["record"]

        system = record["affected_system"]
        if system is not None:
            aliases = bank.SYSTEM_ALIASES[system]
            if not any(alias.lower() in text.lower() for alias in aliases):
                system_problems.append(f"{label['ticket_id']}: '{system}' is the label but is not in the text")

        asset = record["asset_tag"]
        if asset is not None:
            squeezed = re.sub(r"[\s-]", "", text).upper()
            if asset.replace("-", "") not in squeezed:
                asset_problems.append(f"{label['ticket_id']}: '{asset}' is the label but is not in the text")
    report("labelled affected_system appears in the text", system_problems, len(labels))
    report("labelled asset_tag appears in the text", asset_problems, len(labels))


# ---------------------------------------------------------------------
# 4. Distributions
# ---------------------------------------------------------------------


def print_distribution(title, values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    print(f"\n  {title}")
    for value, count in sorted(counts.items(), key=lambda item: -item[1]):
        share = 100 * count / len(values)
        print(f"    {str(value):<22}{count:>5}  {share:5.1f}%  {'#' * round(share / 2)}")
    return counts


def check_distributions(tickets, labels):
    records = [label["record"] for label in labels]
    category_counts = print_distribution("category", [r["category"] for r in records])
    print_distribution("urgency", [r["urgency"] for r in records])
    print_distribution("impact", [r["impact"] for r in records])
    print_distribution("routing_queue", [r["routing_queue"] for r in records])
    print_distribution("affected_system", [r["affected_system"] for r in records])
    print_distribution("channel", [t["channel"] for t in tickets])
    print_distribution("site", [t["site"] for t in tickets])
    print_distribution("persona (meta)", [label["meta"]["persona"] for label in labels])
    features = [feature for label in labels for feature in label["meta"]["features"]]
    print_distribution("messiness features (meta, share of all feature flags)", features)

    word_counts = sorted(label["meta"]["word_count"] for label in labels)
    middle = word_counts[len(word_counts) // 2]
    print(f"\n  body length in words: min {word_counts[0]}, median {middle}, max {word_counts[-1]}")
    print()

    ranked = sorted(category_counts, key=lambda name: -category_counts[name])
    ratio = category_counts[ranked[0]] / category_counts[ranked[-1]]
    problems = []
    if ranked[0] != "access":
        problems.append(f"top category is {ranked[0]}, expected access")
    if set(ranked[-2:]) != {"erp", "telecom"}:
        problems.append(f"rarest two are {ranked[-2:]}, expected erp and telecom")
    if ratio < 4:
        problems.append(f"top/rarest ratio is only {ratio:.1f}")
    if len(category_counts) != 7:
        problems.append("a category has no tickets at all")
    print(f"  top category / rarest category = {ratio:.1f}x")
    report("category mix is imbalanced the intended way", problems, 1)


# ---------------------------------------------------------------------
# 5. Accidental near-duplicates
# ---------------------------------------------------------------------


def shingles(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {" ".join(words[i:i + 3]) for i in range(max(1, len(words) - 2))}


def check_near_duplicates(tickets, threshold):
    """The Day 2 quality check PLANTS ~20 near-duplicates. If templates
    already produce many by accident, that lesson gets muddy."""
    sets = [shingles(ticket["body"]) for ticket in tickets]
    pairs = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            overlap = len(sets[i] & sets[j])
            if overlap == 0:
                continue
            similarity = overlap / len(sets[i] | sets[j])
            if similarity >= threshold:
                pairs.append((similarity, tickets[i], tickets[j]))
    pairs.sort(key=lambda pair: -pair[0])
    print(f"[INFO] near-duplicate body pairs (3-word shingle Jaccard >= {threshold}): {len(pairs)}")
    for similarity, first, second in pairs[:5]:
        print(f"         {similarity:.2f}  {first['ticket_id']}: {first['body'][:60]!r}")
        print(f"               {second['ticket_id']}: {second['body'][:60]!r}")
    return len(pairs)


# ---------------------------------------------------------------------
# 6. Nothing real
# ---------------------------------------------------------------------


def check_nothing_real(paths):
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in paths)
    problems = []
    for term in DENYLIST:
        pattern = r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])"
        hits = re.findall(pattern, text, flags=re.IGNORECASE)
        if hits:
            problems.append(f"'{term}' appears {len(hits)} time(s)")
    for match in FAMILY_NAME_PATTERN.findall(text):
        problems.append(f"family-name pattern: '{match}'")
    report(f"denylist grep ({len(DENYLIST)} real names + family-name pattern)", problems, len(DENYLIST) + 1)

    used_sites = sorted(set(re.findall(r'"site": "([A-Z]{3})"', text)))
    invented = sorted(phrases.SITE_WEIGHTS)
    report("site codes are the invented ones", [] if used_sites == invented else [f"found {used_sites}"], 1)
    print(f"         sites used: {used_sites}")


# ---------------------------------------------------------------------
# 7. Samples for a human
# ---------------------------------------------------------------------


def print_samples(tickets, labels, how_many, seed):
    ticket_by_id = {ticket["ticket_id"]: ticket for ticket in tickets}
    rng = random.Random(seed)
    shuffled = list(labels)
    rng.shuffle(shuffled)

    # one guaranteed example of each feature a reviewer must see
    must_show = ["very_short", "very_long", "two_problems", "system_unnamed", "error_string",
                 "non_native", "multiline_paste"]
    chosen = []
    for feature in must_show:
        for label in shuffled:
            if feature in label["meta"]["features"] and label not in chosen:
                chosen.append(label)
                break
    for label in shuffled:
        if len(chosen) >= how_many:
            break
        if label not in chosen:
            chosen.append(label)

    for number, label in enumerate(chosen[:how_many], start=1):
        ticket = ticket_by_id[label["ticket_id"]]
        print("=" * 78)
        print(f"SAMPLE {number}  {ticket['ticket_id']}  {ticket['created']}  site={ticket['site']}  "
              f"channel={ticket['channel']}")
        print(f"features: {label['meta']['features']}  persona: {label['meta']['persona']}")
        print(f"SUBJECT: {ticket['subject']!r}")
        print("BODY:")
        print(ticket["body"])
        print("RECORD:", json.dumps(label["record"], ensure_ascii=False))
    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tickets", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=0, help="print this many full tickets")
    parser.add_argument("--sample-seed", type=int, default=7)
    parser.add_argument("--near-dup-threshold", type=float, default=0.8)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    tickets = load_jsonl(args.tickets)
    labels = load_jsonl(args.labels)
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    print(f"Loaded {len(tickets)} tickets and {len(labels)} labels\n")

    same_ids = [t["ticket_id"] for t in tickets] == [label["ticket_id"] for label in labels]
    report("tickets and labels line up one to one", [] if same_ids else ["id mismatch"], 1)
    check_raw_format(tickets)
    check_schema(labels, schema)
    check_labels_derivable(tickets, labels)
    check_distributions(tickets, labels)
    check_near_duplicates(tickets, args.near_dup_threshold)
    check_nothing_real([args.tickets, args.labels])
    if args.samples:
        print_samples(tickets, labels, args.samples, args.sample_seed)

    if failures:
        print(f"\n{len(failures)} check(s) FAILED: {failures}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
