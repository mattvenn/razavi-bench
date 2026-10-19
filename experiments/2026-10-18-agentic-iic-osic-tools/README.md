# 2026-10-18 Agentic QA with IIC-OSIC-TOOLS

Claude Opus 5.5 answered all 50 tasks, three times, as an agent that could
run xschem, ngspice and the open PDKs from the
[IIC-OSIC-TOOLS](https://github.com/iic-jku/IIC-OSIC-TOOLS) image. The same
model is on the direct-QA leaderboard without tools, so these runs measure what
circuit simulation adds.

- Answer model: `claude-opus-5-5`, reasoning effort max, headless Claude Code
  (`claude -p`) 2.1.302, one fresh process per task
- Tools: Read (task inputs only) and Bash restricted to
  `docker exec` into a per-task `hpretl/iic-osic-tools:2026.10` container
  (digest `sha256:306585de35d1…`): ngspice 47, xschem 3.4.8, python3 with
  numpy/scipy/sympy, PDKs sky130A, gf180mcuD, ihp-sg13g2
- Rollouts: 3 × 50 tasks (rollout 1 with generation concurrency 5, rollouts 2
  and 3 with 4)
- Judge: DeepSeek V4 Pro through OpenRouter, reasoning disabled, the same
  command as the direct-QA runs. Each rollout's answers were committed before
  it was graded, and the judge metadata records that commit (`0ca2c76`,
  `7e4fad2`, `41a6912`)

| Run (3 rollouts each) | Overall | Part 1 | Part 2 | Rollout range |
|---|---:|---:|---:|---:|
| **Claude Opus 5.5, agentic + IIC-OSIC-TOOLS** | **96.50%** | **100.00%** | **91.25%** | 96.0–97.0% |
| Gemini 4 Argon (high), direct QA, leaderboard #1 | 95.83% | 99.44% | 90.42% | 95.5–96.0% |
| GPT-6 Astra (max), direct QA | 95.50% | 100.00% | 88.75% | 94.5–97.0% |
| Claude Opus 5.5 (max), direct QA | 95.33% | 100.00% | 88.33% | 94.5–96.0% |

| Rollout | Overall | Part 1 | Part 2 | Scores (4/3/2/1/0) |
|---|---:|---:|---:|---|
| 1 | 97.00% | 100.00% | 92.50% | 47 / 1 / 1 / 1 / 0 |
| 2 | 96.00% | 100.00% | 90.00% | 47 / 0 / 1 / 2 / 0 |
| 3 | 96.50% | 100.00% | 91.25% | 47 / 0 / 2 / 1 / 0 |

The 3-rollout mean is above every direct-QA entry, and the lowest agentic
rollout (96.0%) equals the best rollout of the same model without tools. The
margin over the leaderboard leader is 0.67 points, about 1.3 rubric points
per 200, and this is a different evaluation mode, so it is not a leaderboard
entry. The results are very stable: 47 tasks scored 4 in all three rollouts,
and every lost point came from the same three Part 2 tasks.

## Where tools changed the result

Per-task scores against the three direct-QA Opus 5.5 rollouts, for every task
whose mean differs:

| Task | Direct QA | Agentic |
|---|---|---|
| part2-016 optimize for NF, Rin fixed | 2, 4, 2 | 4, 4, 4 |
| part2-005 small-signal resistance | 4, 2, 4 | 4, 4, 4 |
| part2-014 red inverter (b) | 4, 2, 4 | 4, 4, 4 |
| part2-010 clocked latch, wider clock devices | 2, 2, 2 | 3, 2, 2 |
| part2-019 tail capacitor and phase noise | 2, 2, 2 | 2, 1, 2 |
| part2-009 StrongARM, wider M5/M6 | 2, 1, 1 | 1, 1, 1 |

Tools made three tasks reliable that direct QA sometimes missed, but did not
fix the design-trend questions, and slightly hurt two of them:

- **part2-009 (1, 1, 1)** concluded every time that the StrongARM latch slows
  down as M5/M6 widen. The golden answer says speed first improves. The agents'
  sky130 transient simulations supported the slow-down at their chosen sizing,
  and they reported that rather than the idealized trend; the judge treats that
  as the wrong central result.
- **part2-010 (3, 2, 2)** found the optimum width but led with "the speed
  degrades".
- **part2-019 (2, 1, 2)** concluded tail capacitance worsens phase noise; the
  golden answer wants the non-monotonic trade-off.

These are the same Part 2 design-trend questions the direct-QA models miss. A
real-PDK simulation at one operating point tends to push the answer towards a
monotonic conclusion where the question wants the trade-off.

All 150 answers ran ngspice at least once; none used xschem (the agents wrote
SPICE decks directly). The sky130 library in this image sets
`.option scale=1e-6`, so the agents were told to give geometry in unitless
microns, unlike the repository's bundled-model skill.

Usage over 150 answers: 6,836,936 output tokens, about $227.46 at list price
(rollouts: $71.72, $77.47, $78.27; `usage.json`, keyed
`"<rollout>:<task_slug>"`, records the per-task cost reported by Claude Code
for the attempt that produced the answer). That is about 2.28 M output tokens
per rollout against 1.22 M for direct-QA Opus 5.5, so tool use cost about 1.9×
the tokens. Attempts that were discarded (below) and the judge are excluded.

### Interrupted and re-run tasks

Every published answer comes from one uninterrupted attempt in a fresh
sandbox; partial work was always deleted before a re-run.

- Rollout 1: seven Part 2 tasks were cut off when the batch job hit a 2-hour
  limit and were re-run.
- Rollout 2: part2-009 and part2-015 hit the 60-minute per-task cap and were
  re-run once.
- Rollout 3: the run was paused twice for usage limits (in-progress tasks were
  discarded), and three tasks were refused by an account spend limit; all were
  re-run. part2-012 hit the 60-minute cap and was re-run once.

No task needed a second re-run, so none is scored as unanswered.

## Blinding

The answer agent could see only each task's `instruction.md` and figure PNGs.
This was enforced, not requested:

1. Inputs were copied by whitelist to `/work/rb/<slug>/in/` outside the
   repository and mounted read-only into the task's container, which ran with
   `--network none`, no Docker socket and no repository mount.
2. Each answer was a separate `claude -p` process started with a cleared
   environment (fresh session, no context from the orchestrating session), only
   the Read and Bash tools, no MCP servers, no user/project settings and a
   PreToolUse hook, `harness/guard.py`. The hook fails closed and allows only
   Read of that task's inputs and Bash of exactly
   `docker exec -i rb-sbx-<slug> bash -s <<'RBEOF' … RBEOF`, a quoted heredoc
   the host shell does not expand.
3. Before the run, a random canary was planted in the repository and in
   `/root`. Crafted escape attempts were all denied by the guard; inside the
   container there was no network, no host path and no socket. Two
   live agents asked to attempt escapes refused
   (`harness/guard_log.redteam.jsonl.gz`).
4. After each rollout, the guard logs show only benign denials: `ls` of the
   agent's own input directory from the host shell, and Reads of Claude Code's
   own files for long or background tool output.

   | Rollout | Allowed | Denied | Transcripts scanned |
   |---|---:|---:|---:|
   | 1 (`harness/guard_log.jsonl.gz`) | 738 | 37 | 58 |
   | 2 (`claude-opus-5-5/guard_log.rollout-2.jsonl.gz`) | 722 | 36 | 52 |
   | 3 (`claude-opus-5-5/guard_log.rollout-3.jsonl.gz`) | 727 | 38 | 59 |

   Scans of every answer-agent transcript, discarded attempts included, found
   no canary, no reference to golden solutions, `netlists/`, `verify.py` or
   the rubric, and no 100-character span of any golden solution in either the
   transcripts or the answers (`claude-opus-5-5/audit-rollout-{2,3}.json`).
5. Each rollout's answers were committed before its judge ran; every score's
   `answer_sha256` matches the committed answer.

Disclosures about the orchestrating session, which never passed task content to
the answer agents: while checking file formats it saw 800 characters of a past
model's answer to part1-001 before the run, and the first ~150 characters of
the part1-001 golden solution after the rollout-1 answers were frozen.

## Running more rollouts

Rollouts 2 and 3 were produced this way. `harness/run_rollout.sh` runs a full
rollout on any Linux machine with Docker,
the `claude` CLI (logged in, or `ANTHROPIC_API_KEY` set), Python 3 and about
20 GB free for the image. It stages the inputs, runs the guard self-test and a
sandbox check before any paid call, answers every task, then writes the answer
JSONL and an audit.

```bash
git clone https://github.com/mattvenn/razavi-bench.git && cd razavi-bench
git checkout claude/intelligent-dijkstra-k16jf4
H=experiments/2026-10-18-agentic-iic-osic-tools/harness
RB_ROOT=$HOME/rb-r4 $H/run_rollout.sh 4 8   # rollout 4, 8 tasks at a time
```

- Concurrency: simulations are CPU-heavy (five agents loaded 4 cores to a
  load average of ~40), so use roughly half the core count.
- Each task may run up to `RB_TASK_TIMEOUT` seconds (default 3600). Re-running
  the same command resumes: tasks with an answer are skipped, and unfinished
  ones restart from an empty `/out`.
- `RB_ROOT` must be outside the repository; each rollout needs its own.
- The script stops if the guard self-test, the sandbox check, any answer, or
  the audit fails. The audit prints only counts.

Commit the answers, then grade and commit the scores (score files are in
`.gitignore` and are added with `-f`, like the other experiments), so the
judge metadata records a commit with the answers frozen:

```bash
M=experiments/2026-10-18-agentic-iic-osic-tools/claude-opus-5-5
N=4
python3 tools/evaluate_answers.py \
  --input $M/model_outputs/claude-opus-5-5-agentic-iic-max-rollout-$N.jsonl \
  --output $M/judge_outputs/deepseek-v4-pro.rollout-$N.scores.jsonl \
  --api-url https://openrouter.ai/api/v1/chat/completions \
  --model deepseek/deepseek-v4-pro --api-key-env OPENROUTER_API_KEY \
  --json-mode --thinking-mode disabled --openrouter-reasoning \
  --max-tokens 8192 --concurrency 5 --resume
```

Rollout 1 ran the first version of this harness, with fixed `/work` paths
(see commit `0ca2c76`); the portable version adds the staging-root setting,
the preflight, the guard copy outside the repository and the build/audit
scripts, with the same guard rules and answerer brief.

## Files

- `claude-opus-5-5/model_outputs/claude-opus-5-5-agentic-iic-max-rollout-{1,2,3}.jsonl`:
  answers in the direct-QA row schema plus `mode` and `tools_used`
- `claude-opus-5-5/judge_outputs/deepseek-v4-pro.scores.jsonl` (rollout 1),
  `deepseek-v4-pro.rollout-{2,3}.scores.jsonl`, each with metadata
- `claude-opus-5-5/usage.json`: tokens, turns, duration and cost per task
- `claude-opus-5-5/audit-rollout-{2,3}.json` and
  `guard_log.rollout-{2,3}.jsonl.gz`: blinding audits and guard logs
- `harness/`: `run_rollout.sh` (one full rollout), `run_task.sh` (one task),
  `guard.py` (tool guard) and `test_guard.py` (its escape tests), `brief.md`
  (the answer agent's instructions), `build_rollout.py`, `audit.py`, and the
  rollout-1 guard logs

The website data is unchanged: this is a different evaluation mode from the
direct-QA leaderboard.
