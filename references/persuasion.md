# Persuasion Principles for Prompt Compliance

Source: NeoLabHQ/context-engineering-kit (based on Meincke et al. 2025 — 7 principles tested on N=28,000 conversations; persuasion doubled compliance: 33% → 72%, p < .001). Use: increase instruction/format compliance in prompts and skills. Never to bypass safety.

## The 7 principles

### 1. Authority
Deference to expertise/official rule. Imperative language: "YOU MUST", "Never", "Always", "No exceptions". Removes decision fatigue and rationalization.
Use for: discipline skills (TDD, verification), safety-critical practices.
```
✅ Write code before test? Delete it. Start over. No exceptions.
❌ Consider writing tests first when feasible.
```

### 2. Commitment
Consistency with a prior declaration. Require announcement ("Announce skill usage"), explicit choice ("Choose A, B, or C"), tracking (TodoWrite for checklist).
Use for: ensuring a skill is followed, multi-step processes, accountability.
```
✅ When you find a skill, you MUST announce: "I'm using [Skill Name]"
❌ Consider letting your partner know which skill you're using.
```

### 3. Scarcity
Urgency via temporal/sequential limit: "Before proceeding", "Immediately after X". Prevents "I'll do it later".
Use for: immediate verification, order-sensitive workflow.
```
✅ After completing a task, IMMEDIATELY request code review before proceeding.
❌ You can review code when convenient.
```

### 4. Social Proof
Universal norm: "Every time", "Always", explicit failure mode ("X without Y = failure").
Use for: documenting universal practice, warning about common failure.
```
✅ Checklists without TodoWrite tracking = steps get skipped. Every time.
❌ Some people find TodoWrite helpful for checklists.
```

### 5. Unity
Shared identity: "our codebase", "we're colleagues", "we both want quality".
Use for: collaborative workflow, honest feedback culture.
```
✅ We're colleagues working together. I need your honest technical judgment.
❌ You should probably tell me if I'm wrong.
```

### 6. Reciprocity
Obligation to reciprocate. **Use rarely** — sounds manipulative; other principles work better.

### 7. Liking
Preference for people we like. **Do NOT use for compliance** — creates sycophancy, conflicts with honest feedback.

## Combination by prompt type

| Prompt type | Use | Avoid |
|---|---|---|
| Discipline (hard rules) | Authority + Commitment + Social Proof | Liking, Reciprocity |
| Guidance/technique | Moderate Authority + Unity | Heavy Authority |
| Collaborative | Unity + Commitment | Authority, Liking |
| Pure reference | Clarity only | All persuasion |

Do not combine all 7 in one prompt.

## Why it works

Bright-line rules reduce rationalization: "YOU MUST" removes decision fatigue; absolute language eliminates "is this an exception?"; explicit counter-rationalization closes a specific loophole.

## Ethical test

"Would this technique serve the user's genuine interest if they fully understood it?" Yes → legitimate (discipline, prevent predictable failure). No → manipulation (false urgency, guilt, own gain).

## Hard prohibitions (locked scope)

These principles are for **disciplining an LLM's behavior in your own prompts/skills** — the persuasion target is the model, never people. Refuse application to:
- Phishing, social engineering, or any content aimed at deceiving humans
- Dark patterns in UX/copy (false scarcity, fabricated urgency, guilt)
- Support/sales chatbots persuading end users
- Bypassing any model's guardrails/safety

Request in these categories → do not generate; explain why.
