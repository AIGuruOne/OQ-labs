# Pre-baked output of notebook 03 (Day 2 S8), plus two contrast runs

All measured on the build machine on 2026-09-22 with
`scripts/concurrency_test.py`: Windows 11, no NVIDIA GPU, Ollama 0.12.10,
`llama3.2:1b`, 16 requests a level, 64-token replies, 60 s timeout,
prompts = the 20 held-out tickets with the house system prompt. If Ollama
cannot be installed in the room, these are what the notebook would have
produced; the retained outputs in `solutions/03_concurrency.ipynb` show
the same run cell by cell, which is the thing to put on the projector.

| File | Written by | What it shows |
|---|---|---|
| `03_single.json` | the baseline cell | one request alone, the server's own clock: load 0.17 s, prompt 0.69 s (349 tokens), reply 0.64 s (64 tokens), **100 tokens/s**, 100% of the model on the integrated AMD GPU |
| `03_load_llama3.2_1b_1-2-4-8-16_summary.json` | TODO 1 (the retained run) | the server the notebook started, `Parallel:1`: p95 **3.19 s at 1 caller -> 14.01 s at 16** (4.4x); throughput 0.33 -> 0.65 -> 1.05 req/s and **flat from 4 callers on**; 0 failed |
| `03_load_llama3.2_1b_1-2-4-8-16_requests.jsonl` | the same run | one row per request (80): level, seconds, ok, status, reply tokens. Sort by level to see the queue: at 16 callers the replies land 0.95 s apart |
| `03_capacity.json` | TODO 2 | target p95 <= 10 s -> **8 callers, 1.03 req/s, 3,708 requests/hour** - the three numbers the sizing worksheet's worked example uses |

Two contrast runs of the script by hand, 2026-09-22. **Numbers only: their
summary files were not kept** (found missing at the P16 freeze check); the
rows in `docs/timing_log.md` are the record.

| Run | What it showed |
|---|---|
| `--base-url` a scratch server started with `OLLAMA_NUM_PARALLEL=4` (CPU only that time: the integrated GPU had no memory left) | p95 4.24 -> 17.6 s; throughput 0.25 -> 0.9 req/s, flat from 8 callers. Batching moves the knee and raises the ceiling; it does not remove either |
| `--endpoint hosted --levels 1,4,16 --requests 8` (gpt-4o-mini) | p95 2.84 / 2.09 / 2.46 s at 1 / 4 / 16 callers; throughput 0.45 -> 3.25 req/s and still rising. A fleet behind a load balancer |

Two earlier runs of the notebook the same day, when the integrated GPU
held only 62% of the model, gave the same shape with every latency about
a third longer (p95 4.58 -> 34.1 s, knee at 4 callers, 1,584 requests/hour);
`docs/timing_log.md` has both. Quote the shape, not the numbers: the header
of the notebook says why.

To show the final summary without a model: copy `03_single.json` and
`03_capacity.json` into `CHECKPOINT_DIR` (`checkpoints/local/` locally)
and the load-test summary into `CHECKPOINT_DIR/concurrency/`, then run the
settings cell, the baseline cell, TODO 1 (it loads the saved summary
instead of sending 80 requests), the chart, the table and TODO 2. The
server cell always talks to Ollama; with none at all, skip it and read
the solution notebook's outputs instead.
