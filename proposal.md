# Holdfast: Stable Outcomes, Smarter Prompts

## The problem

Your LLM prompts are everywhere — Python pipelines, Claude Code skills, Cursor rules, Copilot instructions — and they all produce outputs that something else depends on. A downstream system trusts your JSON format. A teammate relies on your coding standards. A compliance process needs to explain why results changed.

Today, improving any of these prompts is a gamble. Change a sentence and maybe the analysis gets sharper — or maybe the output schema silently breaks, a field disappears, a score drifts off scale, and a downstream system fails at 2am. So prompts don't get improved. They get frozen entirely, and quietly rot.

**The destination is fixed. The route should get better.** Nothing in the market enables that.

## What Holdfast does

A **contract** separates the outcome you promise from how you deliver it:

- **Frozen surface**: whatever your downstream systems depend on — an output schema, a response format, a scoring scale, a coding standard. This is your contract. It doesn't change unless you explicitly decide to change it.
- **Evolvable surface**: the prompt, examples, reasoning instructions. This is *how* you deliver the outcome. It improves over time from real evidence.
- **Invariants**: automated proof that every change to the route still arrives at the right destination.

## Two paths, one model

**Python pipelines** — Evidence accumulates automatically from every run. When patterns emerge — score inconsistency, repeated failure modes, quality drift — Holdfast detects them and proposes targeted improvements, while guaranteeing the output contract stays stable.

```python
from holdfast import Contract, log_run

contract = Contract.load("contracts/my-pipeline/")
prompt = contract.get_evolvable("prompt")

result = your_llm_call(prompt, data)

log_run(contract=contract, output=result, passed=validate(result))
```

**AI coding tools** — Your instructions live in CLAUDE.md, .cursorrules, copilot-instructions.md, AGENTS.md. Sync tools keep them identical. Holdfast keeps them *governed* — the architectural decisions and output standards are frozen, the how-to-get-there instructions evolve as you and your tools learn what works. A Claude Code skill reviews your interaction patterns, detects drift, and proposes bounded improvements.

Both paths share the same contract model. Both use the same governance rules. The Python lib collects evidence programmatically. The Claude skill collects evidence from your interaction patterns. Either way, outcomes stay stable while the route improves.

## Why this matters

**Outcomes stay stable.** Your report format, your scoring scale, your API response shape, your team's coding standards — these don't drift. Downstream systems don't break. Compliance can audit what changed and what didn't.

**Quality improves continuously.** The analysis gets sharper, edge cases get handled, consistency improves — all driven by evidence from actual usage, not benchmarks.

**You control the pace.** Each contract has a trust level:

| Mode | Behavior | Use when |
|---|---|---|
| **Monitor** | Detect drift and alert. No changes proposed. | New contracts, high-stakes outputs |
| **Semi-auto** | Detect, propose improvements, human approves | Most production prompts |
| **Auto** | Detect, propose, apply if invariants pass | Mature contracts with strong validation |

You graduate a contract when you trust it. Some stay at monitor forever. That's fine.

## Where this fits in the ecosystem

Production LLM workflows already use multiple tools — and should. Holdfast isn't a replacement for any of them. It fills a specific gap that none of them cover.

**Prompt versioning** (Maxim, Portkey, Humanloop) manages who can edit prompts, tracks history, and handles deployment. You should use these. But they treat prompts as atomic blobs — nothing structurally prevents a version bump from changing the output format alongside the instructions.

**Prompt optimization** (DSPy) makes prompts better against benchmarks at compile time. You should use this too, especially early in development. But it optimizes against test data, not production evidence, and the optimizer can rewrite any part of the prompt — there's no concept of "this part must not change."

**Observability** (LangSmith, Langfuse, Deepchecks) tells you when something went wrong in production. Essential. But it stops at detection — it doesn't propose what to change, and it doesn't guarantee a fix won't break something else.

**Continual learning frameworks** (LangChain/LangSmith, OpenClaw) are building the mechanisms for agents to learn from their own traces — analyzing execution history, proposing harness improvements, updating memory offline. This is where the industry is heading. But the focus is on *what* agents can learn, not on preventing that learning from breaking what already works. An agent that rewrites its own instructions without guardrails is a liability in production.

**Prompt sync** (rulesync, cursor2claude, skills-sync) keeps your instructions identical across Claude, Cursor, Copilot, and Gemini. Useful plumbing. But syncing copies of a file doesn't tell you which parts of that file are load-bearing and which parts should evolve. You can sync a bad change just as easily as a good one.

**Holdfast closes the loop between these tools.** Observability collects traces. Continual learning frameworks use them to propose improvements. Optimization refines prompts. Sync propagates changes. Versioning tracks them. Holdfast adds the missing piece: guaranteeing the outcome contract is preserved while the route to it improves. It works *alongside* the tools you already have, not instead of them.

## Status

Working v0.1 with evidence collection, invariant validation, version snapshots, rollback, and proposal generation. Detection layer, trust modes, and the Claude Code skill are designed, not yet built.

Inspired by research on self-evolving agent skills, particularly [Memento-Skills](https://arxiv.org/abs/2603.18743) (Zhou et al., 2026), which demonstrated that agents can improve by evolving external artifacts rather than retraining models. The idea is compelling — but without guard rails, evolving agents will drift, regress, and break downstream systems. That's a problem for everyone, and an especially serious one for enterprises where outputs feed compliance reporting, business decisions, and other production systems. Holdfast starts from that reality: agents should get better over time, but only within bounds you define and can audit.
