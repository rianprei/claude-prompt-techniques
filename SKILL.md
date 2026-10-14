---
name: prompt-techniques
description: Use when a prompt engineering technique applies to the current task (name/apply it), or when the request wants a prompt written for a specific tool (Claude, GPT, Cursor, Midjourney, coding agent) to paste elsewhere — includes natural forms like "how do I ask Midjourney for X?" or "how do I get Cursor to do Y?". Also for image prompts for any image model (Midjourney, GPT Image, FLUX, Ideogram, Recraft, Firefly, Seedream, Stable Diffusion, ComfyUI, Nano Banana): generate, improve, adapt or compare.
---

## Reference mode (passive)
Do not recite the list unless asked. Pick the technique that serves the task.

**Priority (not every technique weighs the same)**:
- **High impact, always consider**: Role, Context, Output Formatting, Few-shot, Grounding, Delimiters.
- **Conditional**: CoT (only NON-reasoning models), ReAct/RAG/Function Calling (only with real tools), Reflexion/CoVe (factual/verifiable task).
- **Experimental/legacy on 2025+ models**: ToT, GoT, simulated MoE, Self-Consistency, layered chaining — gain not proven on modern models, fabrication risk; only on explicit request.
Base: inspired by The Prompt Report (arXiv:2406.06608); model-specific rules come from official vendor docs, dated in references/tool-routing.md — not own evaluation. When applying one,
name it in 1 short line **in the visible reply** (e.g. "Technique: Chain-of-Verification"), not only
in internal reasoning — the user needs to see it for auditability. Only name when the technique
actually influenced the approach; trivial tasks get no label.

Priority tier above already names the ~17 techniques that cover most real usage. Task needs a named
technique outside it (rare — a specific reasoning/decomposition/agent pattern by name) →
[references/taxonomy.md](references/taxonomy.md) has the full category index, and [references/technique-catalog.md](references/technique-catalog.md) gives each entry's source and status. Generator mode never needs these files.

**Persuasion** (Meincke et al.: the 2026 PNAS abstract reports compliance rising from 35.3% to 51.3% on three models; the 2025 preprint's figures are not verified and are not used here; details in references/persuasion.md; compliance = obedience to the instruction, NOT answer quality/accuracy): Authority, Commitment, Scarcity, Social Proof, Unity (Reciprocity/Liking: avoid). Use only for format/process discipline, in plain wording: stacked CAPS ("YOU MUST", "NEVER") can make recent Claude models overtrigger. Detail, ✅/❌ examples and table: [references/persuasion.md](references/persuasion.md). Never to bypass safety.

## Generator mode (active — when the request clearly wants a prompt for another tool)

Triggers: "write/improve/adapt a prompt for X", but also natural forms — "how do I ask
Midjourney for X?", "how do I get Cursor to do Y?", "build something to paste into GPT". Criterion: user wants
text to paste into another tool, not my answer. When unsure, ask in 1 line.

**Hard rule**: do not generate a prompt without confirming the target tool (ask if ambiguous, max 3 questions).
Do not explain prompt engineering theory unless asked. Do not show framework names in the output.
Prefer simple techniques (role, few-shot, grounding) over complex frameworks (Mixture-of-Experts,
Tree/Graph-of-Thought, Self-Consistency, layered prompt chaining) — those have higher fabrication risk
in a single prompt; only use if explicitly requested and the tool supports them.
**Image prompts for another model.** Write the brief once (Template O: subject, environment, composition, medium, lighting, colour, text, constraints, references, edit), then adapt it to the named target with `scripts/image_prompt.py`, run from the skill folder (the one that holds this file). Each target's syntax, negative mechanism and native settings are in [references/image-targets.md](references/image-targets.md), with the status of each fact (VERIFIED, PARTIAL, UNKNOWN) and its source. Name the target from the request ("Midjourney", "gpt image", "flux 3", "Ideogram"); ask only when the name fits several targets ("flux", "stable diffusion"). For a comparison, render the same brief for each named target. Never invent a parameter: a target without verified syntax gets a portable prompt and a warning.

Never add CoT on reasoning-native models (GPT-6 family, DeepSeek V4 in thinking mode, Claude 5.x with thinking on) —
they already think internally; CoT degrades output.

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
Full path only, add 1 line: `Score: N/6 axes addressed (task/context/format/scope/reasoning/agentic)`
— same 6 axes as the refinement loop below. It is a self-assessment showing which axes the prompt covers, not a measured score. Skip
on fast path — it's the whole point of taking the fast path. For a target with its own session
state (Claude Code, Cursor, Copilot): count an axis as addressed if the target's own environment
already supplies it (open file, git diff, project structure) — a short prompt isn't missing
context just because it doesn't restate what the tool can already see. For a one-shot target
with no environment (Midjourney, GPT, GPT Image): nothing is implicit, every axis must be explicit
in the prompt itself.

**Refinement loop** (when the user returns with the tool's real output): diagnose the failure
with the pattern list from [references/patterns.md](references/patterns.md) (task/context/format/scope/reasoning/agentic),
adjust ONLY the dimension that failed, deliver a new version. Do not rewrite from scratch.

## Image generation with Nano Banana (studio, from the shell)

Run these commands from the skill folder (the one that holds this file): `cd` there first. Use when the request is to generate, edit or refine an image with Nano Banana, not only to write its prompt. Always in this order:
1. `python3 -m studio plan ...` (or `--case ID`, or `--from RUN_ID --edit "what to change"`). It spends nothing. Show the user the model, ratio, size, nominal cost, prompt, reference hashes and warnings.
2. Run `approve <brief_sha256> --confirm <first 8 characters>` only after the user has agreed in this conversation. Never pass `--confirm` without that answer.
3. `run <brief_sha256> --approval <approval_id>`. One approval is one paid call. Never loop generation; for another attempt, plan again and ask again.
4. Open the file at `output_path` with your file viewer (it shows PNG and JPEG) and say what you see.
5. To correct: `plan --from RUN_ID --edit "..."`, which keeps everything not named. To record: `review` (with a note) and `rate` (with `--criterion NAME=N`).

Limits, what is not verified and the file layout: [studio/README.md](studio/README.md). Models and thinking levels: [references/gemini-image-models.md](references/gemini-image-models.md).

**Per-tool detail and templates — do not load here, read on demand**:
- [references/tool-routing.md](references/tool-routing.md) — rules specific to Claude/GPT/Cursor/Midjourney/coding agent, and the Nano Banana / Gemini Image profile (routing by name, scene and edit briefs, references, text, web assets)
- [references/patterns.md](references/patterns.md) — patterns that waste tokens/credits (task/context/format/scope/reasoning/agentic)
- [references/templates.md](references/templates.md) — 15 structural templates A–O (RTF, CO-STAR, RISEN, CRISPE, Auditable Reasoning, Few-Shot, File-Scope, ReAct+Stop, Visual Descriptor, Reference Image Editing, ComfyUI, Prompt Decompiler, Claude Task Brief, Nano Banana Brief, Visual Brief for other image models)
- [references/image-targets.md](references/image-targets.md) — image targets other than Nano Banana: status, sources, aliases, negative-prompt mechanism and native settings per target (read 2026-10-14)
- [references/defenses.md](references/defenses.md) — defenses for prompts that process untrusted content (conceptual; categories and trade-offs)
- [references/technique-catalog.md](references/technique-catalog.md) — detailed technique catalog: source, status, novelty and kind for each entry
- [references/image-styles.md](references/image-styles.md) — style names for image prompts (Midjourney, GPT Image, Flux, ComfyUI)
- [references/gemini-image-models.md](references/gemini-image-models.md) — Gemini image model IDs, commercial aliases, status, sizes, per-model ratios, reference limits, thinking levels and prices (verified 2026-10-13; check the official page before use)
- [references/gemini-image-examples.md](references/gemini-image-examples.md) — copyable Nano Banana briefs for generation, edits, references, consistency, in-image text, web assets, infographics and refinement (Portuguese and English)

Read only the needed tool/category section, not the whole file.
