---
description: Set up holdfast tracking for a repeatable task. Use when the user
  says "track my", "use holdfast to track", "set up holdfast", or when you
  notice a repeatable task that could benefit from quality tracking. Also handles
  discovery — passively suggesting tracking for repeatable tasks.
---

# Holdfast — Track

You set up holdfast contracts and log evidence for tracked interactions.

**Core rule:** frozen surfaces don't change. Evolvable surfaces improve
only with evidence and approval.

**Two modes:**
- **Pipeline mode** (`mode: pipeline`) — Python lib writes evidence. Do not write evidence yourself.
- **Claude mode** (`mode: claude`) — you write evidence after tracked interactions. No Python needed.

Check `contract.yaml` for the `mode` field. If missing, assume `pipeline`.

---

## Discovery

When this plugin is installed but no contract exists for the current task
type, nudge the user **once per task type per session**.

Trackable types: code review, test generation, implementation planning,
refactoring, documentation writing, security auditing.

Trigger: you just completed a task matching one of these types and there is
no holdfast contract for it in this project.

Output exactly one line, then move on:

```
holdfast: this looks like a repeatable task (code review). want me to track quality over time? say "use holdfast to track this."
```

Rules:
- One nudge per task type per session. If ignored, don't repeat.
- If `holdfast_discover: false` appears in CLAUDE.md, never nudge.
- If a contract already exists for this task type, skip the nudge — go straight to evidence logging.
- One line. Lowercase. No emoji. Near-zero token cost.

---

## Contract setup (claude mode)

When the user says "use holdfast to track X" or their CLAUDE.md says so:

### 1. Ask two questions

1. **What are you tracking?** — "code reviews", "test generation", etc.
2. **What does good look like?** — This becomes the frozen surface.

If the user is vague, draft the frozen standards yourself and ask for confirmation.

### 2. Create the contract

```
holdfast/contracts/{name}/
  contract.yaml
  frozen/
    standards.md
  evolvable/
    approach.md
  invariants.yaml
  detection.yaml
  .holdfast/
    evidence/
```

**contract.yaml:**
```yaml
name: {name}
version: 1
mode: claude
evolution_mode: semi-auto

frozen:
  standards: "frozen/standards.md"

evolvable:
  approach: "evolvable/approach.md"
```

**invariants.yaml:**
```yaml
- type: contains
  field: outcome
  values: ["accepted", "modified", "rejected"]
  description: "Outcome must be a tracked state"
```

**detection.yaml:**
```yaml
- type: failure_rate
  max_rate: 0.25
  window: 20
  description: "User rejection rate above 25%"

- type: drift
  field: satisfaction
  baseline_window: 10
  recent_window: 10
  max_shift: 1.0
  description: "User satisfaction shifted"
```

### 3. Mention where it lives, move on

---

## Evidence writing (claude mode)

After completing a tracked task, write an evidence file. Silent by default.
If `holdfast_verbose: true` in CLAUDE.md or contract.yaml, print:
`holdfast: logged run-NNNNN`

### When to log

A tracked interaction ends when:
- The user accepts, modifies, or rejects your output
- The user moves to a different topic
- The task is complete

Do not log mid-conversation. Wait for the outcome.

### How to log

1. List files in `{contract_dir}/.holdfast/evidence/`
2. Find the highest `run-NNNNN` number (parse digits after `run-`)
3. Increment by 1, zero-pad to 5 digits
4. Write the evidence file:

```json
{
  "id": "run-NNNNN",
  "contract_name": "{name}",
  "contract_version": {version},
  "timestamp": "{ISO 8601 UTC}",
  "mode": "claude",
  "input_summary": "{brief description of the task}",
  "output": {
    "outcome": "accepted | modified | rejected",
    "satisfaction": {1-5},
    "feedback_summary": "{what the user did with your output}",
    "areas_covered": ["{dimensions you addressed}"],
    "areas_missed": ["{dimensions you missed, if any}"]
  },
  "passed": true,
  "notes": "",
  "tags": []
}
```

### Satisfaction scoring

Assess based on the user's behavior, not by asking them:

| Score | Meaning |
|-------|---------|
| 5 | Accepted without changes |
| 4 | Accepted with minor modifications |
| 3 | Used some parts, rewrote others |
| 2 | Mostly rejected, kept one idea |
| 1 | Rejected entirely |

### Pass/fail

- `passed: true` if outcome is "accepted" or "modified"
- `passed: false` if outcome is "rejected"
