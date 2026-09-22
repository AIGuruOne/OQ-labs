# Sizing worksheet: from "how many tickets" to "how big a server" (S8, the talk half)

A paper exercise, no code. Ten minutes for a group of three, with the three
numbers notebook 03 printed in front of you. It answers one question a
manager will ask on Day 5: *"How much machine does this need?"* — and it
teaches the honest answer, which is a range with its assumptions written
down, never a single number.

You do not need to have sized an inference workload before. Every step is
one line of arithmetic and says where its inputs come from. The worked
example at the end uses real measurements from this repo, so you can check
your arithmetic against it.

> Everything here is synthetic and illustrative. The measured numbers are a
> laptop's (or a free Colab T4's), not OQ's production numbers. The
> worksheet is the method; the numbers are placeholders until someone
> measures the real server with `scripts/concurrency_test.py`.

---

## The idea in one paragraph

A model server is a queue with a fixed number of workers. Notebook 03
measured, for one server: how long one request takes alone, how many
callers it can serve at once before replies get slower than you accept
(**the knee**), and how many requests a second it gets through at that
point (**the ceiling**). Sizing is then: work out how many requests a
second your busiest hour brings, divide by what one server does, and round
up. Everything else on this sheet is making the two sides of that division
honest — peaks, not averages; p95, not means; and the difference between
"the model can do it" and "the model can do it while somebody waits".

---

## Section A — what one server does (from notebook 03)

Copy the three numbers from the notebook's final cell, with the note beside
them. Write the machine down every time; a number without its machine is a
rumour.

| A | Measurement | Your value | Where it comes from |
|---|---|---|---|
| A1 | Machine and model measured | | the `server` and `hardware` lines of the final cell |
| A2 | One request alone, seconds (p50 at 1 caller) | | the table, row `1`, column `p50 s` |
| A3 | Reply tokens per request (the cap you used) | | `REPLY_CAP_TOKENS`; 64 in the lab |
| A4 | Latency target you set (p95, seconds) | | TODO 2 |
| A5 | **Knee:** callers at once inside the target | | `callers inside it` |
| A6 | **Ceiling:** requests per second at the knee | | `throughput there` |
| A7 | Requests per hour at the knee = A6 x 3600 | | printed for you |

If A5 is `NONE`, stop here: this machine cannot meet the target for one
caller. Either the target is wrong for the use case, or the machine is;
section E says which levers exist.

## Section B — what the work is (from the use case brief)

Estimate, do not compute. The point is a defensible order of magnitude.

| B | Question | Your value | How to think about it |
|---|---|---|---|
| B1 | Requests per **day** | | tickets a day, or documents a day, or questions a day. Brief 1's ticket triage: count the tickets the desk logs |
| B2 | Hours in which most of them arrive | | an 8-hour office day for tickets; 24 for an integration that never sleeps |
| B3 | Peak factor | | the busiest hour divided by the average hour. 2 is a normal office; 3 to 4 if there is a Monday-morning or post-outage flood; 1 for a batch job you schedule |
| B4 | Requests per **second at peak** = B1 / (B2 x 3600) x B3 | | this is the number the server must survive, not the average |
| B5 | Reply length the use case needs, tokens | | triage JSON: about 60. A drafted email: 200 to 400. A summary of a long document: 500 plus |
| B6 | Who waits? | person / integration / nobody | a person on a screen, an integration with a timeout, or a batch that just has to finish by morning |

## Section C — the arithmetic

| C | Step | Your value | Notes |
|---|---|---|---|
| C1 | Reply-length correction = B5 / A3 | | replies twice as long take roughly twice as long to write; prompt reading is a smaller share. Use 1.0 if B5 is within a third of A3 |
| C2 | Corrected ceiling = A6 / C1 | | requests per second one server does at YOUR reply length, inside the target |
| C3 | Servers needed at peak = B4 / C2, rounded **up** | | this is the headline number. Round up; a queue that is 90% busy has long tails |
| C4 | Headroom = C3 x 1.5, rounded up | | the second answer. Traffic estimates are wrong by a factor of 2 in both directions; 1.5 is the cheap half of that |
| C5 | Hours a day the servers sit idle | | from B2: a 24-hour VM serving an 8-hour day is idle two thirds of the time. Yesterday's cost model has the idle-share line for exactly this |

C3 and C4 are the answers. Write both, with A1 beside them.

## Section D — the sanity checks (do not skip)

Answer YES or NO. Every NO is a sentence for the architecture spec.

| D | Check | Y/N | If NO |
|---|---|---|---|
| D1 | Is A2 (one request alone) already under the target A4? | | no server count fixes a single slow request: a smaller model, a shorter reply, a faster GPU, or a looser target |
| D2 | Was A4 chosen for B6 (who waits)? | | a person: 2 to 5 s. An integration: its timeout, usually 10 to 30 s. Nobody: throughput is all that matters and A4 can be minutes |
| D3 | Is C3 small enough to be a "host" answer at all? | | if the answer is many servers, the "host" column of the decision matrix has just got expensive; re-run the cost model with C4 machines |
| D4 | Would a bigger model (the one you actually want) still pass D1? | | the lab measured a 1B model. An 8B model on the same GPU is several times slower per token. Measure it before promising it |
| D5 | Does the number of callers at once (A5) match reality? | | 16 service-desk agents each waiting on a reply is 16 callers; a nightly batch is 1 caller with a long queue, and can run past the knee on purpose |
| D6 | Did you measure on the machine you will buy? | | the lab's numbers are a laptop's or a free T4's. Notebook 03's script takes `--base-url`: point it at the real VM before anyone signs anything |

## Section E — the levers, in the order to pull them

When the answer is "too many servers" or "too slow", these are the options,
cheapest first. Each one changes a number in section A, so re-measure after
pulling it.

1. **Shorter replies** (B5 down): the cheapest lever there is. A triage record does not need prose.
2. **Let the server batch** (`OLLAMA_NUM_PARALLEL` above 1, or a serving engine that batches continuously): moves the knee out and raises the ceiling. Measured in this repo on the build laptop, 4 slots took the ceiling from 0.25 to 0.9 requests a second, and p95 still climbed past the knee. Costs memory per slot.
3. **A faster accelerator** (A2 down): a T4 answers this model in under a second where the laptop takes three. Measure; do not extrapolate from a spec sheet.
4. **More servers behind a load balancer** (C3 up): linear cost, linear capacity, and the operational work of running a fleet. This is what a vendor API is: the "buy" column, which yesterday's cost model priced at under $14 a month for desk volume.
5. **A smaller model**: last, because it changes the quality numbers S12 will measure, and a faster wrong answer is not a win.

---

## Worked example: ticket triage (brief 1) on the build laptop

Measured 2026-09-22 with `solutions/03_concurrency.ipynb`: Windows 11
laptop, no NVIDIA GPU (Ollama put all of the model on the integrated AMD
graphics that day; on a day it only got 62% of it, every latency was about
a third longer), Ollama 0.12.10 with its default of one request at a time,
`llama3.2:1b`, 64-token replies, 16 requests per level. The retained run's
table (the solution notebook shows the same numbers):

```
concurrency  requests    ok  failed   p50 s   p95 s   max s   req/s  tokens/s
----------------------------------------------------------------------------------
          1        16    16       0    3.00    3.19    3.42    0.33      19.0
          2        16    16       0    2.95    3.33    3.71    0.65      37.3
          4        16    16       0    3.32    4.54    5.15    1.05      59.9
          8        16    16       0    6.77    7.80    8.46    1.03      59.0
         16        16    16       0    8.41   14.01   15.02    1.06      60.9
```

**Section A.**

| A | Value |
|---|---|
| A1 | build laptop, integrated GPU, Ollama 0.12.10, 1 request at a time, `llama3.2:1b` |
| A2 | 3.00 s |
| A3 | 64 tokens |
| A4 | 10 s (an integration's timeout: the ticketing system calls the model, nobody watches) |
| A5 | 8 callers (p95 7.80 s; 16 callers gave 14.01 s) |
| A6 | 1.03 requests/s |
| A7 | 3,708 requests/hour |

**Section B.** The synthetic desk in `corpus/tickets/` has 600 tickets; a
real desk for a company this size logs in the region of 200 tickets a
working day, so take that as the estimate.

| B | Value |
|---|---|
| B1 | 200 tickets a day |
| B2 | 8 hours (they arrive during the working day) |
| B3 | 3 (Monday mornings and the hour after an outage) |
| B4 | 200 / (8 x 3600) x 3 = **0.021 requests/s at peak** (about 75 an hour) |
| B5 | 60 tokens (the triage JSON: `dataset_utils.SYSTEM_PROMPT` asks for one object; the cost model measured a mean reply of 57 tokens) |
| B6 | integration |

**Section C.**

| C | Value |
|---|---|
| C1 | 60 / 64 = 0.94, within a third, so **1.0** |
| C2 | 1.03 / 1.0 = 1.03 requests/s |
| C3 | 0.021 / 1.03 = 0.020, rounded up = **1 server** (used 2% of the time at peak) |
| C4 | 1 x 1.5 = 1.5, rounded up = **2 servers** for headroom, or 1 with a queue and an alert |
| C5 | 16 of 24 hours idle: the cost model's idle-share line, and the reason its answer was "buy" at this volume |

**Section D.**

| D | Answer |
|---|---|
| D1 | YES: 3.0 s is under 10 s. (Set the target at 2 s for a person watching and the answer flips to NO on this laptop; on a T4, where a reply takes under a second, it would not.) |
| D2 | YES: nobody watches triage; the integration's timeout is the target |
| D3 | YES: one machine, and it is idle most of the day; the cost model priced the equivalent VM at about $1,434 a month against under $14 for the API |
| D4 | NOT MEASURED: an 8B model was never run in this repo. Do not promise it from this sheet |
| D5 | YES for the integration (one caller with a queue). NO if 16 agents get a "triage now" button: that is 16 callers, past the knee, p95 14 s |
| D6 | NO: this is a laptop. Point `scripts/concurrency_test.py --base-url http://<vm>:11434/v1 --model <model>` at the real VM |

**The answer, as it should be written in the spec:** *"At 200 tickets a day
with a 3x peak, triage needs 0.02 requests a second. One server of the
measured class handles 1.03 inside a 10 s p95, so one server with a queue
is enough and two is comfortable. The measurement is a laptop's; re-measure
on the tenant VM before sizing it, and re-measure again if the model
changes. At this volume the vendor API is cheaper by two orders of
magnitude and hosting is justified only by the residency gate."*

That last sentence is the point of the whole sheet: capacity was never the
reason to host. Yesterday's decision matrix said so, and now the arithmetic
does too.

---

## What this sheet does not do

- It does not size for **prompt length**. A long document in the prompt
  costs reading time (0.7 s for 349 tokens on the laptop above) that grows
  with the document; Day 3's retrieval labs make prompts long. Re-measure
  with representative prompts.
- It does not model **bursts inside a second**. The load test is a closed
  loop (N callers who each wait); a webhook storm is open-loop and needs a
  queue in front of the server, which is a Day 5 architecture question.
- It does not know about **GPU memory**. Slots, context length and model
  size all consume it; a server that is out of memory does not slow down,
  it refuses. `ollama ps` shows the share in use.
- It is **not a quote**. It gives a count of a measured machine class. The
  cost model turns that count into money.

Filled examples: the worked example above is the only one so far. The first
group to fill this sheet for a different brief on Day 2 should hand it to
Ritesh; it becomes the second example.
