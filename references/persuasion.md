# Persuasion Principles for Prompt Compliance

The 2026 PNAS version by the same group (DOI 10.1073/pnas.2535868123), read through its abstract on 2026-10-13, tested GPT-5 mini, Claude Haiku 4.5 and Gemini 3 Flash: compliance rose from 35.3% to 51.3% across 126,000 conversations. The figures below are the NeoLabHQ kit's description of the 2025 preprint, not checked against it. SSRN blocked the page on 2026-10-12 and 2026-10-13 (a Cloudflare challenge). The Crossref record has no abstract, and neither arXiv nor Semantic Scholar has the paper (checked 2026-10-13).

Source: adapted from NeoLabHQ/context-engineering-kit (GPL-3.0), which cites Meincke, L., Shapiro, D., Duckworth, A., Mollick, E. R., Mollick, L., and Cialdini, R. (2025), "Call Me A Jerk: Persuading AI to Comply with Objectionable Requests", SSRN 5357179 (preregistration: OSF kj863). The study tested seven principles on GPT-4o mini, with two objectionable requests (an insult, and the synthesis of a regulated drug) and N=28,000 conversations. Reported compliance: 33.3% for controls vs. 72.0% with a principle (p < .001). Not tested on Claude models. It measures compliance with the instruction, not answer quality or safety. Use: format and process discipline in prompts and skills. Never to bypass safety.

## The 7 principles

### 1. Authority
Deference to expertise or an official rule. Use plain, firm wording for gates ("Stop and ask before…", "Do not…"). Avoid stacked CAPS ("YOU MUST", "NEVER", "No exceptions"): recent Claude models can overtrigger on emphatic wording. Removes decision fatigue and rationalization.
Use for: discipline skills (TDD, verification), safety-critical practices.
```
✅ Code written before its test: delete it and start over.
❌ Consider writing tests first when feasible.
```

### 2. Commitment
Consistency with a prior declaration. Require announcement ("Announce skill usage"), explicit choice ("Choose A, B, or C"), tracking (TodoWrite for checklist).
Use for: ensuring a skill is followed, multi-step processes, accountability.
```
✅ When you find a skill, announce: "I'm using [Skill Name]"
❌ Consider letting your partner know which skill you're using.
```

### 3. Scarcity
Urgency via temporal/sequential limit: "Before proceeding", "Immediately after X". Prevents "I'll do it later".
Use for: immediate verification, order-sensitive workflow.
```
✅ After completing a task, request code review before proceeding.
❌ You can review code when convenient.
```

### 4. Social Proof
Universal norm: "Every time", "Always", explicit failure mode ("X without Y = failure").
Use for: documenting universal practice, warning about common failure.
```
✅ Checklists without tracking get their steps skipped.
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

Explicit gates reduce rationalization: a clear rule removes the "is this an exception?" question, and an explicit counter-rationalization closes a specific loophole. The evidence for the mechanism comes from the GPT-4o mini study above; it has not been shown for Claude models.

## Ethical test

"Would this technique serve the user's genuine interest if they fully understood it?" Yes → legitimate (discipline, prevent predictable failure). No → manipulation (false urgency, guilt, own gain).

## Hard prohibitions (locked scope)

These principles are for **disciplining an LLM's behavior in your own prompts/skills** — the persuasion target is the model, never people. Refuse application to:
- Phishing, social engineering, or any content aimed at deceiving humans
- Dark patterns in UX/copy (false scarcity, fabricated urgency, guilt)
- Support/sales chatbots persuading end users
- Bypassing any model's guardrails/safety

Request in these categories → do not generate; explain why.
