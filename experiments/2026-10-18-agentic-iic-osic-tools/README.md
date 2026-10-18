# 2026-10-18 Agentic QA with IIC-OSIC-TOOLS

Claude Opus 5.5 answered all 50 tasks as an agent that could run
xschem, ngspice and the open PDKs from the
[IIC-OSIC-TOOLS](https://github.com/iic-jku/IIC-OSIC-TOOLS) image. The same
model is on the direct-QA leaderboard without tools, so this run measures what
circuit simulation adds.

- Answer model: `claude-opus-5-5`, reasoning effort max, headless Claude Code
  (`claude -p`) 2.1.302, one fresh process per task
- Tools: Read (task inputs only) and Bash restricted to
  `docker exec` into a per-task `hpretl/iic-osic-tools:2026.10` container
  (digest `sha256:306585de35d1…`): ngspice 47, xschem 3.4.8, python3 with
  numpy/scipy/sympy, PDKs sky130A, gf180mcuD, ihp-sg13g2
- Rollouts: 1 × 50 tasks, generation concurrency 5
- Judge: DeepSeek V4 Pro through OpenRouter, reasoning disabled, the same
  command as the direct-QA runs (judge metadata records answers commit
  `0ca2c76`, which froze the answers before grading)

| Run | Overall | Part 1 | Part 2 |
|---|---:|---:|---:|
| **Claude Opus 5.5, agentic + IIC-OSIC-TOOLS (1 rollout)** | **97.00%** | **100.00%** | **92.50%** |
| Claude Opus 5.5 (max), direct QA (3 rollouts) | 95.33% | 100.00% | 88.33% |
| Gemini 4 Argon (high), direct QA, leaderboard #1 | 95.83% | 99.44% | 90.42% |
| GPT-6 Astra (max), direct QA | 95.50% | 100.00% | 88.75% |

Score distribution: 47 fours, 1 three, 1 two, 1 one, no zeros. Direct-QA
Opus 5.5 rollouts ranged 94.5–96.0%, so this single rollout is above that
range, but one rollout is noisy: the gain is 1.67 points, or about 3.3 rubric
points out of 200, concentrated in a few Part 2 tasks.

## Where tools changed the result

Compared with the per-task mean of the three direct-QA Opus 5.5 rollouts:

| Task | Direct (3 rollouts) | Agentic |
|---|---|---:|
| part2-016 optimize for NF, Rin fixed | 2, 4, 2 | 4 |
| part2-010 clocked latch, wider clock devices | 2, 2, 2 | 3 |
| part2-005 small-signal resistance | 4, 2, 4 | 4 |
| part2-014 red inverter (b) | 4, 2, 4 | 4 |
| part2-009 StrongARM, wider M5/M6 | 2, 1, 1 | 1 |

The three answers that lost points:

- **part2-009 (1/4)** concluded the StrongARM latch slows down as M5/M6 widen.
  The golden answer says speed first improves. The agent's sky130 transient
  simulation supported the slow-down at its chosen sizing, and it reported that
  rather than the idealized trend; the judge treats that as the wrong central
  result.
- **part2-010 (3/4)** found the optimum width but opened with "in general the
  speed degrades".
- **part2-019 (2/4)** concluded tail capacitance worsens phase noise; the golden
  answer wants the non-monotonic trade-off.

These are the same Part 2 design-trend questions the direct-QA models miss. In
two of them a real-PDK simulation at one operating point pushed the answer
towards a monotonic conclusion where the question wanted the trade-off.

All 50 agents ran ngspice at least once; none used xschem (they wrote SPICE
decks directly). The sky130 library in this image sets `.option scale=1e-6`,
so the agents were told to give geometry in unitless microns, unlike the
repository's bundled-model skill.

Usage over 50 answers: 2,183,217 output tokens, about $71.72 at list price
(`usage.json`, keyed `"<rollout>:<task_slug>"`, includes the per-task cost
reported by Claude Code). Direct-QA Opus 5.5 used about 1.22 M output tokens
per rollout, so tool use cost about 1.8× the tokens. Judge cost is excluded.

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
4. After the run: the guard log (`harness/guard_log.jsonl.gz`) shows 738
   allowed and 37 denied calls, all benign (27 `ls` of the agent's own input
   directory from the host shell, 10 Reads of Claude Code's own overflow file
   for long tool output). A scan of all 58 answer-agent transcripts found no
   canary, no reference to golden solutions, `netlists/`, `verify.py` or the
   rubric, and no 100-character span of any golden solution in either the
   transcripts or the answers.
5. Answers were committed (`0ca2c76`) before the judge ran; every score's
   `answer_sha256` matches the committed answer.

Disclosures about the orchestrating session, which never passed task content to
the answer agents: while checking file formats it saw 800 characters of a past
model's answer to part1-001 before the run, and the first ~150 characters of
the part1-001 golden solution after the answers were frozen.

Seven Part 2 tasks were interrupted when the batch job hit a 2-hour limit; their
partial work was deleted and each was re-run from scratch, so every published
answer comes from one uninterrupted run.

## Files

- `claude-opus-5-5/model_outputs/claude-opus-5-5-agentic-iic-max-rollout-1.jsonl`:
  answers in the direct-QA row schema plus `mode` and `tools_used`
- `claude-opus-5-5/judge_outputs/deepseek-v4-pro.scores.jsonl` and metadata
- `claude-opus-5-5/usage.json`: tokens, turns, duration and cost per task
- `harness/`: `run_task.sh` (per-task runner), `guard.py` (tool guard),
  `settings.json` (hook config), `brief.md` (the answer agent's instructions)
  and the guard logs

The website data is unchanged: this is a different evaluation mode from the
direct-QA leaderboard.
