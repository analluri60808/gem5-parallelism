# gem5 ILP experiments — Part 2

Simulation source for pipelining, branch prediction, multiple issue, and SMT. Author: **analluri60808**.

## Source

- `part2/configs/five_stage.py`: educational fetch/decode/execute/memory/writeback model using gem5 events.
- `part2/configs/ilp.py`: x86 O3 configuration with width, predictor, and SMT controls.
- `part2/workloads/`: six freestanding microbenchmarks.
- `part2/patches/disable-predictor.patch`: sequential-fetch predictor bypass.
- `part2/scripts/run.py`: compile, simulate, and validate native checksums.
- `part2/scripts/analyze.py`: derive throughput, trace latency, and resource counters.

## Reproduce

Requires Linux/WSL, GCC, Python 3, and gem5 25.1.0.1 at revision `cbc94c1a773e94118070294750dbe2c9c75898cb`. Apply the included patch to a clean gem5 checkout and build `build/X86/gem5.opt`. Do not apply the patch twice.

From this repository's root:

```bash
export GEM5_ROOT=/path/to/gem5
export ILP_BATCH=my-new-run
python3 part2/scripts/run.py --gem5-root "$GEM5_ROOT" --batch "$ILP_BATCH"
python3 part2/scripts/analyze.py
"$GEM5_ROOT/build/X86/gem5.opt" --outdir=part2/results/my-five-stage part2/configs/five_stage.py
```

Use a new batch name for each run. Generated files are ignored by Git. Submission papers, charts, screenshots, and results are stored outside this repository.

The educational model is separate from O3. Width-one O3 remains out of order. Predictor bypass fetches sequentially instead of stalling until branch resolution. O3 latency measures committed micro-operations and differs from CPI. SMT uses two contexts on one core, with BTB indexing explicitly configured for the active thread count.
