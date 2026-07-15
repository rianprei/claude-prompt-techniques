---
name: prompt-techniques
description: Reference + prompt generator. Passive use — name/apply a prompt engineering technique. Active use — generate an optimized prompt for a specific tool (Claude, GPT, Cursor, Midjourney, coding agent) when the request clearly wants a prompt to paste into another tool — includes natural forms like "how do I ask Midjourney for X?".
---

Merged from two sources: own technique list (reference) + [prompt-master](https://github.com/nidhinjs/prompt-master) (active generation).

## Reference mode (passive)
Do not recite the list unless asked. Pick the technique that serves the task.

**Priority (not every technique weighs the same)**:
- **High impact, always consider**: Role, Context, Output Formatting, Few-shot, Grounding, Delimiters.
- **Conditional**: CoT (only NON-reasoning models), ReAct/RAG/Function Calling (only with real tools), Reflexion/CoVe (factual/verifiable task).
- **Experimental/legacy on 2025+ models**: ToT, GoT, simulated MoE, Self-Consistency, layered chaining — gain not proven on modern models, fabrication risk; only on explicit request.
Base: The Prompt Report (arXiv:2406.06608) + official vendor docs — not own evaluation. When applying one,
name it in 1 short line **in the visible reply** (e.g. "Technique: Chain-of-Verification"), not only
in internal reasoning — the user needs to see it for auditability. Only name when the technique
actually influenced the approach; trivial tasks get no label.

Priority tier above already names the ~18 techniques that cover most real usage. Task needs a named
technique outside it (rare — a specific reasoning/decomposition/agent pattern by name) →
[references/taxonomy.md](references/taxonomy.md) has the full category index. Generator mode never needs this file.

**Persuasion** (Meincke et al. 2025 — doubles compliance 33%→72%; compliance = obedience to the instruction, NOT answer quality/accuracy): Authority, Commitment, Scarcity, Social Proof, Unity (Reciprocity/Liking: avoid). Use only for format/process discipline. Detail, ✅/❌ examples and table: [references/persuasion.md](references/persuasion.md). Never to bypass safety.

## Generator mode (active — when the request clearly wants a prompt for another tool)

Triggers: "write/improve/adapt a prompt for X", but also natural forms — "how do I ask
Midjourney for X?", "how do I get Cursor to do Y?", "build something to paste into GPT". Criterion: user wants
text to paste into another tool, not my answer. When unsure, ask in 1 line.

**Hard rule**: do not generate a prompt without confirming the target tool (ask if ambiguous, max 3 questions).
Do not explain prompt engineering theory unless asked. Do not show framework names in the output.
Prefer simple techniques (role, few-shot, grounding) over complex frameworks (Mixture-of-Experts,
Tree/Graph-of-Thought, Self-Consistency, layered prompt chaining) — those have higher fabrication risk
in a single prompt; only use if explicitly requested and the tool supports them.
Never add CoT on reasoning-native models (o3, o4-mini, DeepSeek-R1, Qwen3 thinking) — they already think
internally; CoT degrades output.

**Fast path**: simple, unambiguous request (clear tool, clear task, no exotic format) →
generate directly, no template, no checklist, no questions. The full ceremony below is only for
complex/ambiguous requests. When unsure between the two paths, fast path.
Fast-path mini-autocheck (3 items, mental, does not replace the full long-path self-check):
no CoT if reasoning-native model; defined output format; no vague instruction like "do whatever is needed".

**Before writing** (full path), silently extract **from the user request** (extraction ≠ question): task,
target tool, output format, constraint, input, context, audience, success criterion, example.
Only turn into a question what is critical AND missing (max 3). If the task is genuinely ambiguous and 3 questions
are not enough: generate anyway and declare assumptions at the end ("Assumed: X, Y — correct if wrong"),
instead of silently generating a generic prompt.

**Note on "don't show framework"**: applies to the **generated prompt** (the text the user pastes into the
tool does not carry a "CO-STAR" label). The optimization sentence and passive mode MAY name a technique —
different channels, not a contradiction.

**Self-check before delivering**: review the generated prompt against the tool section in
tool-routing.md. Detected violation (e.g. CoT on reasoning-native model, prose where the tool
wants commas, no stop condition on an agent) → fix silently before showing.

**Unknown/new tool**: if not in tool-routing.md and web search is available,
search "prompt best practices <tool> <year>" before generating; then offer a ready block
for the user to paste into tool-routing.md. Without web search → generic rules + warning.

**Output**: 1 copyable prompt block + `🎯 Target: <tool>` + 1 sentence on what was optimized and why
+ refinement offer: "Test it in the tool and paste the result here if you want me to refine."

**Refinement loop** (when the user returns with the tool's real output): diagnose the failure
with the Diagnostic Checklist from [references/tool-routing.md](references/tool-routing.md) (task/context/format/scope/reasoning/agentic),
adjust ONLY the dimension that failed, deliver a new version. Do not rewrite from scratch.

**Per-tool detail and templates — do not load here, read on demand**:
- [references/tool-routing.md](references/tool-routing.md) — rules specific to Claude/GPT/Cursor/Midjourney/coding agent
- [references/patterns.md](references/patterns.md) — patterns that waste tokens/credits (task/context/format/scope/reasoning/agentic)
- [references/templates.md](references/templates.md) — 13 structural templates A–M (RTF, CO-STAR, RISEN, CRISPE, CoT, Few-Shot, File-Scope, ReAct+Stop, Visual Descriptor, Reference Image Editing, ComfyUI, Prompt Decompiler, Opus Task Brief)

Read only the needed tool/category section, not the whole file.
