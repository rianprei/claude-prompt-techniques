# Prompt Templates Reference

Full template library for the prompt-techniques skill. Read the relevant template when the user's task type matches. Do not load all templates at once — only the one you need.

## Table of Contents

| Template | Best For |
|----------|----------|
| [A — RTF](#template-a--rtf) | Simple one-shot tasks |
| [B — CO-STAR](#template-b--co-star) | Professional documents, business writing |
| [C — RISEN](#template-c--risen) | Complex multi-step projects |
| [D — CRISPE](#template-d--crispe) | Creative work, brand voice |
| [E — Auditable Reasoning](#template-e--auditable-reasoning) | Logic, math, analysis, debugging |
| [F — Few-Shot](#template-f--few-shot) | Consistent structured output, pattern replication |
| [G — File-Scope](#template-g--file-scope) | Cursor, Windsurf, Copilot — code editing AI |
| [H — ReAct + Stop Conditions](#template-h--react--stop-conditions) | Claude Code, Devin — autonomous agents |
| [I — Visual Descriptor](#template-i--visual-descriptor) | Midjourney, GPT Image, Stable Diffusion, Sora |
| [J — Reference Image Editing](#template-j--reference-image-editing) | Editing an existing image with a reference |
| [K — ComfyUI](#template-k--comfyui) | ComfyUI node-based image workflows |
| [L — Prompt Decompiler](#template-l--prompt-decompiler) | Breaking down, adapting, or splitting existing prompts |
| [M — Claude Task Brief](#template-m--claude-task-brief) | Complex, multi-step, or agentic task on current Claude models |
| [N — Nano Banana Brief](#template-n--nano-banana-brief) | New image with Nano Banana / Gemini Image, with optional named references |
| [O — Visual Brief (multi-model adapter)](#template-o--visual-brief-multi-model-adapter) | One image brief, adapted to Midjourney, GPT Image, FLUX, Ideogram, Recraft, Firefly, Seedream, Stable Diffusion, SDXL or ComfyUI |

---

## Template A — RTF

*Role, Task, Format. Use for fast one-shot tasks where the request is clear and simple.*

```
Role: [One sentence defining who the AI is]
Task: [Precise verb + what to produce]
Format: [Exact output format and length]
```

**Example:**
```
Role: You are a senior technical writer.
Task: Write a one-paragraph description of what a REST API is.
Format: Plain prose, 3 sentences maximum, no jargon, suitable for a non-technical audience.
```

---

## Template B — CO-STAR

*Context, Objective, Style, Tone, Audience, Response. Use for professional documents, business writing, reports, and marketing content where full context control matters.*

```
Context: [Background the AI needs to understand the situation]
Objective: [Exact goal — what success looks like]
Style: [Writing style: formal / conversational / technical / narrative]
Tone: [Emotional register: authoritative / empathetic / urgent / neutral]
Audience: [Who reads this — their knowledge level and expectations]
Response: [Format, length, and structure of the output]
```

**Example:**
```
Context: I am a founder pitching a B2B SaaS tool that automates expense reporting for mid-size companies.
Objective: Write a cold email that gets a reply from a CFO.
Style: Direct and conversational, not salesy.
Tone: Confident but not pushy.
Audience: CFO at a 200-person company, busy, skeptical of vendor emails.
Response: 5 sentences max. Subject line included. No bullet points.
```

---

## Template C — RISEN

*Role, Instructions, Steps, End Goal, Narrowing. Use for complex projects, multi-step tasks, and any output that requires a clear sequence of actions.*

```
Role: [Expert identity the AI should adopt]
Instructions: [Overall task in plain terms]
Steps:
  1. [First action]
  2. [Second action]
  3. [Continue as needed]
End Goal: [What the final output must achieve]
Narrowing: [Constraints, scope limits, what to exclude]
```

**Example:**
```
Role: You are a product manager with 10 years of experience in mobile apps.
Instructions: Write a product requirements document for a habit tracking feature.
Steps:
  1. Define the problem statement in one paragraph
  2. List user stories in the format "As a [user], I want [goal] so that [reason]"
  3. Define acceptance criteria for each story
  4. List out-of-scope items explicitly
End Goal: A PRD that an engineering team can begin sprint planning from immediately.
Narrowing: No technical implementation details. No wireframes. Under 600 words total.
```

---

## Template D — CRISPE

*Capacity, Role, Insight, Statement, Personality, Experiment. Use for creative work, brand voice writing, and any task where personality, tone, and iteration matter.*

```
Capacity: [What capability or expertise the AI should have]
Role: [Specific persona to adopt]
Insight: [Key background insight that shapes the response]
Statement: [The core task or question]
Personality: [Tone and style — witty / authoritative / casual / sharp]
Experiment: [Request variants or alternatives to explore]
```

**Example:**
```
Capacity: Expert copywriter specializing in SaaS product launches.
Role: Brand voice for a productivity tool aimed at developers.
Insight: Developers hate marketing speak and respond to honesty and specificity.
Statement: Write the hero headline and sub-headline for the landing page.
Personality: Sharp, dry, confident — no adjectives, no exclamation marks.
Experiment: Give 3 variants ranging from minimal to bold.
```

---

## Template E — Auditable Reasoning

*Use for logic-heavy tasks, math, debugging, and multi-factor analysis where the result must be checkable. Works on every model. It asks for conclusions, assumptions, evidence, and checks, not for private reasoning.*

**Models without native thinking only** (GPT-6 Luna with reasoning effort `none`, and models whose card says thinking is off): add "Think through this step by step before answering." and put the final answer in `<answer>` tags so it can be extracted. Claude models with thinking off by default (Opus 4.6–4.8, Sonnet 4.6) use the same fallback. Never add it to GPT-6 Astra, GPT-6.1 Sol, DeepSeek V4 with thinking on, or to o1/o3/o4-mini/DeepSeek-R1/Qwen3-thinking. On Claude 5.x, rely on thinking and `effort`: a prompt that asks for reasoning in `<thinking>` tags can be declined.

```
[Task statement]

Return:
1. Conclusion
2. Assumptions
3. Evidence or intermediate results needed to audit the conclusion
4. Verification checks performed
5. Remaining uncertainty, if any

Keep the rationale concise and decision-relevant.
```

**When to use:**
- Debugging where the cause is not obvious
- Comparing two technical approaches
- Any math or calculation
- Analysis where a wrong first impression is likely

**When NOT to use:**
- Simple tasks where the answer is clear (unnecessary overhead)
- Reasoning-native models (GPT-6 Astra and GPT-6.1 Sol, DeepSeek V4 in thinking mode, Claude 5.x with thinking on): they think internally, so step-by-step instructions hurt
- Creative tasks (structured audit fields can flatten natural voice)

---

## Template F — Few-Shot

*Use when the output format is easier to show than describe. Examples outperform written instructions for format-sensitive tasks every time.*

```
[Task instruction]

Here are examples of the exact format needed:

<examples>
  <example>
    <input>[example input 1]</input>
    <output>[example output 1]</output>
  </example>
  <example>
    <input>[example input 2]</input>
    <output>[example output 2]</output>
  </example>
</examples>

Now apply this exact pattern to: [actual input]
```

**Rules:**
- 2 to 5 examples is the sweet spot. More rarely helps and wastes tokens.
- Examples must include edge cases, not just easy cases.
- Use XML tags to wrap examples — Claude parses XML reliably.
- If you have been re-prompting for the same formatting correction twice, switch to few-shot instead of rewriting instructions.

---

## Template G — File-Scope

*Use for Cursor, Windsurf, GitHub Copilot, and any AI that edits code inside a codebase. The most common failure mode here is editing the wrong file or breaking existing logic — this template prevents both.*

```
File: [exact/path/to/file.ext]
Function/Component: [exact name]

Current Behavior:
[What this code does right now — be specific]

Desired Change:
[What it should do after the edit — be specific]

Scope:
Only modify [function / component / section].
Do NOT touch: [list everything to leave unchanged]

Constraints:
- Language/framework: [specify version]
- Do not add dependencies not in [package.json / requirements.txt]
- Preserve existing [type signatures / API contracts / variable names]

Done When:
[Exact condition that confirms the change worked correctly]
```

---

## Template H — ReAct + Stop Conditions

*Use for Claude Code, Devin, AutoGPT, and any AI that takes autonomous actions. Runaway loops and scope explosion are the biggest credit killers in agentic workflows — stop conditions are not optional.*

```
Objective:
[Single, unambiguous goal in one sentence]

Starting State:
[Current file structure / codebase state / environment]

Target State:
[What should exist when the agent is done]

Allowed Actions:
- [Specific action the agent may take]
- Install only packages listed in [requirements.txt / package.json]

Forbidden Actions:
- Do NOT modify files outside [directory/scope]
- Do NOT run the dev server or deploy
- Do NOT push to git
- Do NOT delete files without showing a diff first
- Do NOT make architecture decisions without human approval

Stop Conditions:
Pause and ask for human review when:
- A file would be permanently deleted
- A new external service or API needs to be integrated
- Two valid implementation paths exist and the choice affects architecture
- An error cannot be resolved in 2 attempts
- The task requires changes outside the stated scope

Checkpoints:
After each major step, output: ✅ [what was completed]
At the end, output a full summary of every file changed.
```

---

## Template I — Visual Descriptor

*Use for Midjourney, GPT Image, Stable Diffusion, Sora, Runway, and any image or video generation tool.*

```
Subject: [Main subject — specific, not vague]
Action/Pose: [What the subject is doing]
Setting: [Where the scene takes place]
Style: [photorealistic / cinematic / anime / oil painting / vector / etc.]
Mood: [dramatic / serene / eerie / joyful / etc.]
Lighting: [golden hour / studio / neon / overcast / candlelight / etc.]
Color Palette: [dominant colors or named palette]
Composition: [wide shot / close-up / aerial / Dutch angle / etc.]
Aspect Ratio: [16:9 / 1:1 / 9:16 / 4:3]
Negative Prompts: [blurry, watermark, extra fingers, distortion, low quality]
Style Reference: [artist / film / aesthetic reference if applicable]
Texture: [surface and material feel — worn leather, soft fur, brushed metal, steam]
Locked Attributes: [any color/material/count the user stated as non-negotiable — see rule below]
```

**Locked Attributes — mandatory field whenever the request names a specific color, material,
or count for an object.** Image models default to the most common real-world version of an
object, and a plain adjective loses that fight (e.g. "golden katana" can render as a dark,
desaturated bronze that reads as steel in shadow — the katana shape carries a strong
steel/silver prior, and a bare color adjective without a brightness/saturation cue lets the
model pick a muted tone that technically matches the hue but not the intent). For each locked
attribute:
- State it twice: once in the main description, once again near the end of the prompt —
  position near the end carries more weight than an early, buried mention.
- Pair it with an explicit negative, AND lock brightness/saturation, not just hue: "the blade
  is bright, polished, reflective gold — NOT silver, NOT steel-colored, NOT dark bronze, NOT
  tarnished, NOT brass" beats "a golden blade" alone. Hue without a brightness/saturation cue
  still leaves room for a dull, shadow-toned result that verifies as "gold" in hex but reads
  as gray to the eye.
- For an exact multiplier ("3x the size of X"), don't rely on the raw number — image models
  render scale unreliably from multipliers. Anchor it to a visual comparison instead: not
  "a sword 3x the cat's length" but "a sword as long as the cat is tall plus its own body
  length again, clearly dwarfing the cat holding it."

**Expertise modes** (shape which fields dominate): cinema (lighting + composition), product (lighting + texture, clean background), portrait (subject + lighting), fashion (style + composition), UI/web (composition + palette), logo (subject + style, flat), landscape (setting + lighting), abstract (style + palette), infographic (composition + palette, add "accurate readable text").

**Vocabulary anchors** — a named real-world term beats a vague adjective in the Camera/Lighting/Style
fields; use these as a starting point, not an exhaustive list:
- Camera/lens: `shot on RED V-Raptor`, `ARRI Alexa`, `35mm`, `85mm portrait`, `f/1.2 shallow DOF`, `anamorphic lens flare`
- Lighting: `golden hour`, `Rembrandt lighting`, `rim light`, `volumetric god rays`, `studio three-point lighting`
- Film stock (photoreal look): `Kodak Portra 400` (warm skin tones), `Fuji Velvia 50` (saturated landscapes), `Ilford HP5` (B&W grain)

**Tool-specific syntax:**
- **Midjourney**: Comma-separated descriptors, not prose. Parameters go at the end, after a space: `--ar` (whole numbers), `--raw` (more of the prompt, less default styling). `--v` takes the current version, V8.2 by default; do not hardcode a version. Verified syntax: references/image-targets.md (midjourney).
- **Stable Diffusion 1.5 / SDXL**: the weight syntax and CFG values from earlier notes were not verified on 2026-10-14, so they are not used here. Negative prompts are a separate block in ComfyUI (Template K). See references/image-targets.md (sdxl: UNKNOWN).
- **Sora 2 / video** (rule written for Sora, not re-verified for Sora 2): Add camera movement (slow dolly, static shot, crane up), duration in seconds, and cut style.

---

## Template J — Reference Image Editing

*Use when the user has an existing image they want to modify. Completely different from generation — never describe the whole scene from scratch, only describe the change.*

**Before writing the prompt, always tell the user:**
"Attach your reference image to [tool name] before sending this prompt."

**Detect the tool's editing capability:**
- Midjourney V8.2 (default since 2026-07-24): the Edit model (`--edit`, with up to four image URLs) replaces Omni Reference, Character Reference and the Retexture tool (Version page, read 2026-10-14).
- GPT Image (API): send the source image to the edit call with a prompt that says what to change and what to keep. ChatGPT's own image tool was not read.
- Stable Diffusion 1.5 / SDXL (older checkpoints): the edit workflow was not verified on 2026-10-14 (see references/image-targets.md, sdxl: UNKNOWN). No strength value is given here.

```
Reference image: [attached / URL]
What to keep exactly the same: [list everything that must not change]
What to change: [specific edit only — be precise]
How much to change: [subtle / moderate / significant]
Style consistency: maintain the exact style, lighting, and mood of the reference
Negative prompt: [what to avoid introducing]
```

**Example:**
```
Reference image: [attached portrait photo]
What to keep exactly the same: face, hair, clothing, background, lighting
What to change: head angle — rotate from facing left to facing straight forward
How much to change: subtle, preserve all facial features exactly
Style consistency: maintain photorealistic style, same lighting direction
Negative prompt: no new elements, no style changes, no background changes
```

**Multi-image composition variant** — user attaches 2+ reference images to combine, not one to
edit (check each tool's current multi-reference syntax; not re-verified here):
```
Reference images: [image 1 — what it contributes], [image 2 — what it contributes], ...
Combination: [exactly what comes from which image — subject from image 1, background from
  image 2, style from image 3, etc. — one clause per image, no ambiguity about source]
Relationship: [how the combined elements interact — scale, position, lighting must reconcile]
Negative prompt: [what to avoid introducing]
```

For Nano Banana / Gemini Image (up to 14 references per request, see [gemini-image-models.md](gemini-image-models.md)), give each reference a name and a role (identity, style, composition, palette or product), with one clause per reference in the order sent. In a multi-turn edit, send one change per turn in the same conversation, and keep the preservation clause in each turn. Routing rules: [tool-routing.md](tool-routing.md), the Nano Banana profile.

**Outpainting / aspect expansion variant** — growing the canvas beyond the original image, not
editing content inside it (different operation from both variants above):
```
Target aspect ratio: [e.g. 16:9]
Extend: [which sides — left/right/top/bottom]
Context awareness: match the original lighting, weather, texture, and grain exactly
Logical completion: any object cut off at the original border (a shoulder, a branch, a building
  edge) must be completed naturally by inference, not left ambiguous
Do not distort or regenerate the original center image
```

---

## Template K — ComfyUI

*Use for ComfyUI node-based workflows. Always output Positive and Negative prompts as separate blocks. Ask for the checkpoint model before writing — syntax and token limits differ per model.*

**Ask first if not stated:**
"Which checkpoint model are you using? (Stable Diffusion 3.5, SDXL, FLUX 3, FLUX.2, or other)"

**Model-specific notes:**
- SD 1.5 (legacy): the ComfyUI text-to-image examples are SD 1.5. Token limits and weight syntax were not re-verified here.
- SDXL: not verified on 2026-10-14. See references/image-targets.md.
- FLUX 3 Image: send the image in `images` with a prompt that describes the change. A single edit needs no box; the service may add one and returns the expanded prompt in `result.prompt`. FLUX.2 has no negative prompts. FLUX.1 Kontext is a previous-generation model: describe only the change. Verified details: references/image-targets.md.

```
POSITIVE PROMPT:
[subject], [style], [mood], [lighting], [composition], [quality boosters: highly detailed, sharp focus, 8k]

NEGATIVE PROMPT (SD/SDXL; leave empty for FLUX.1 dev):
[what to exclude: blurry, low quality, watermark, extra limbs, bad anatomy, distorted, oversaturated]

CHECKPOINT: [model name]
SAMPLER: Euler a (recommended starting point)
CFG SCALE: 7 for SD/SDXL (higher = stricter adherence); FLUX.1 dev: 1.0
STEPS: 20-30
RESOLUTION: [width x height — multiple of 64 for SD/SDXL]
```

---

## Template L — Prompt Decompiler

*Use when the user pastes an existing prompt and wants to break it down, adapt it for a different tool, simplify it, or understand its structure. This is analysis and adaptation, not building from scratch.*

**Detect which Decompiler task is needed:**
- **Break down** — explain what each part of the prompt does
- **Adapt** — rewrite for a different tool while preserving intent
- **Simplify** — remove redundancy and tighten without losing meaning
- **Split** — divide a complex one-shot prompt into a cleaner sequence

**For Adapt tasks, always ask:**
"What tool is the original prompt from, and what tool are you adapting it for?"

**Match the fix to the prompt's existing sophistication — don't downgrade or over-build:**
- Already has role, explicit constraints, examples, and anti-patterns named? It's Expert-level —
  tighten and remove ambiguity only. Adding a persona/format template it didn't ask for is not
  a fix, it's noise.
- Bare one-liner, no structure at all? Add the next layer up (role + explicit output shape),
  not the full ceremony in one jump — match the gap between current and next level, not current
  and maximum.

**Never rewrite technical parameters — copy them verbatim into the output, EXCEPT secrets:**
code fences and inline code, exact numbers/flags/paths (`--ar 16:9`, `v2.3.0`), model IDs and
proper nouns, error messages and stack traces, URLs and email addresses. A flag that looks like
a typo may be exactly what the target tool requires — if genuinely ambiguous, leave it untouched
and flag it in the output note instead of guessing. Exception, no matter what: API keys, tokens,
signed URLs, passwords, connection strings — strip these even inside a verbatim block and replace
with a placeholder, same as Credential Safety in tool-routing.md. This applies even if that
section wasn't loaded — don't rely on it being in context.

**Break down output format:**
```
Original prompt: [paste]

Structure analysis:
- Role/Identity: [what role is assigned and why]
- Task: [what action is being requested]
- Constraints: [what limits are set]
- Format: [what output shape is expected]
- Weaknesses: [what is missing or could cause wrong output]

Recommended fix: [rewritten version with gaps filled]
```

**Adapt output format:**
```
Original ([source tool]): [original prompt]

Adapted for [target tool]:
[rewritten prompt using target tool syntax and best practices]

Key changes made:
- [change 1 and why]
- [change 2 and why]
```

**Split output format:**
```
Original prompt: [paste]

This prompt is doing [N] things. Split into [N] sequential prompts:

Prompt 1 — [what it handles]:
[prompt block]

Prompt 2 — [what it handles]:
[prompt block]

Run these in order. Each output feeds the next.
```
---

## Template M — Claude Task Brief

*Use for any complex, multi-step, or agentic task on current Claude models — claude.ai, API, or Claude Code. These read prompts literally and produce narrow output when context is missing. This template front-loads everything so the first turn is the only turn.*

```
## Objective
[What needs to be built, fixed, or produced — one clear sentence. Add WHY if it affects approach.]

## Context
[What exists now — relevant files, current behavior, stack already in place, what was tried and failed]

## Target State
[What done looks like — specific files changed, behavior produced, tests passing. Binary where possible.]

## Scope
- Work only in: [specific files and directories]
- Do NOT touch: [forbidden files — .env, package-lock.json, configs, anything outside scope]

## Constraints
- [Stack version, naming conventions, no new dependencies without asking]
- Only make changes directly requested. Do not add features, abstractions, or files beyond what was asked.

## Acceptance Criteria
- [ ] [Binary check 1]
- [ ] [Binary check 2]
- [ ] [Binary check 3]

## Stop Conditions
Stop and ask before:
- Deleting any file
- Adding any dependency
- Modifying database schema or migrations
- Touching anything outside Scope

## Progress
After each completed step: ✅ [what was done] — [file(s) affected]. Back every completion claim with the tool output or changed file it rests on.
```

**Thinking depth** — add only when needed, delete otherwise:
- Hard multi-step task: `"Think carefully before starting."`
- Simple targeted change: `"Respond directly; this is a scoped change."`
- Default: say nothing — adaptive thinking calibrates itself.

**Claude Code only — add Session Strategy block when relevant:**
```
## Session Strategy
[Pick one:]
- New session — unrelated to prior context, start fresh
- Continue — prior context still needed
- Subagent — spin off for [file-heavy research / verification] so intermediate output stays out of main context
- Compact first — run /compact [focus on X] then begin
```

**When to use:** Current Claude models on any surface — claude.ai, API, Claude Code — when the task is complex, multi-file, ambiguous, or agentic. Not needed for simple one-shot tasks.

---

## Template N — Nano Banana Brief

*Use for Nano Banana / Gemini Image (Nano Banana 2.1, Nano Banana 2, Nano Banana 2 Lite, Nano Banana Pro) when the image is new. For an edit of an existing image, use Template J. Model IDs, ratios and limits: [gemini-image-models.md](gemini-image-models.md). Routing: the Nano Banana profile in [tool-routing.md](tool-routing.md).*

```
Operation: Generate
Model: [model ID from the catalog]
Aspect ratio (request field): [a ratio that model accepts]
Image size (request field): [1K | 2K | 4K; 512 only for gemini-3.1-flash-image, which is deprecated]

Prompt:
[One narrative paragraph. Subject and action first; then setting and time; then composition
(shot type, subject position, negative space for text); then style (medium, lens, light, grading).
Positive wording: describe what should be there.]
[Text in the image, if any: the exact words in quotation marks, the typography (font style,
weight, color), where the text goes, and its language.]
[Destination in words, for example "widescreen backdrop" or "vertical social post".]

References (in the order sent; delete this block when there are none):
1. [name]: [role: identity | product | style | composition | palette | background]. Keep exactly: [what must not change]
```

**Example** (an original brief, not from Google's examples):
```
Operation: Generate
Model: gemini-nano-banana-2.1
Aspect ratio (request field): 4:5
Image size (request field): 1K

Prompt:
A photo of a hand-thrown olive-green ceramic vase holding three dried eucalyptus stems, standing on a pale oak shelf. Soft window light comes from the left, and the shot is taken at eye level with a 50mm lens, with shallow depth of field. The top third of the frame stays empty, off-white, with room for a headline. Vertical social post.
```

**Rules:**
- Use only the ratios and sizes that the model accepts (catalog). Set them in the request fields, not only in the prompt text.
- Keep the prompt to the fields the task needs. Describe what should be in the picture, not what to leave out.
- Text in the picture goes in quotation marks, in the language the user asked for. Copy longer than a headline is written first, in its own turn.
- More than one reference: name each one, and give each one a role.

**When to use:** A new image from text, with or without named references, on any Nano Banana / Gemini Image model.

---

## Template O — Visual Brief (multi-model adapter)

*Use for an image prompt for a target other than Nano Banana: Midjourney, GPT Image, FLUX (FLUX 3, FLUX.2, Kontext), Ideogram, Recraft, Firefly, Seedream, Stable Diffusion 3.5, SDXL or ComfyUI. Nano Banana keeps Template N. Each target's facts, sources and status are in [image-targets.md](image-targets.md).*

Write the brief once, in these fields, and adapt it to the target's form. Do not paste one verbose prompt into every tool: each target reads a different form, and some take settings that a prompt cannot carry.

| Field | What goes there |
|---|---|
| `subject`, `action` | what is in the picture and what it does |
| `environment`, `composition`, `perspective` | where it is, how it is framed, and from where it is seen |
| `medium` | the medium or style, for example "product photograph" or "watercolour" |
| `lighting`, `color`, `materials` | light, palette, surfaces |
| `text` | each piece of exact text, with `placement` and `typography`; `replaces` is for a text edit only |
| `constraints` | exclusions ("no watermark") or positive invariants; the renderer decides how each target takes them |
| `aspect_ratio` | `W:H` with whole numbers, or `auto`; decimals are refused |
| `references` | each reference with a `role`: style, subject, structure or background |
| `edit` | the change, and what to keep (`preserve`); edits only |
| `boxes` | FLUX 3 only: element boxes, `[top, left, bottom, right]` in 0–1000 |
| `options` | target settings (model, quality, resolution, seed); each is checked against what that target documents |

**Rules**

- Settings are native fields or parameters, never prompt text. The one exception is Midjourney: its parameters are typed at the end of the prompt bar, and the renderer shows them apart from the prompt.
- Exclusions follow each target's negative mechanism (the mechanism field in image-targets.md). Midjourney takes them as `--no`. ComfyUI has a separate negative block. Recraft's API has a negative field only for V2 and V3. Where there is no negative field, the exclusion stays in the prompt as a sentence, and the warning asks for a positive rewrite, which controls better.
- A target whose syntax is not verified gets a portable prompt and a warning. Nothing is invented: no weights, no parameters, no fields.
- A bare family name can match several targets ("flux", "stable diffusion"). Ask which version, because the answer changes the prompt. If the person does not know, use the generic fallback and say so.
- Nano Banana is not rendered here. The renderer returns a redirect to Template N and the Studio.

**Render it**

    python3 scripts/image_prompt.py render --target <name> --brief brief.json
    python3 scripts/image_prompt.py resolve "<name the person used>"

The output is JSON: `prompt`, `native_parameters` or `native_settings`, `negative_prompt` with its mechanism, `warnings`, `limitations`, `sources`. Read the warnings before you hand the prompt over.

### Worked example: one brief, five targets

The same brief, rendered by `scripts/image_prompt.py`. The prompt text and the native settings are shown apart, because they are sent apart (or, for Midjourney, typed apart). Warnings are in the JSON output; they are not copied here.

Brief:

```json
{
  "subject": "a ceramic teapot",
  "environment": "a pale oak table by a window",
  "composition": "centred, with empty space above",
  "perspective": "eye level",
  "lighting": "soft morning light from the left",
  "color": "terracotta and cream",
  "medium": "product photograph",
  "materials": "glazed stoneware",
  "aspect_ratio": "4:5",
  "text": [
    {
      "content": "TEA",
      "placement": "on a small paper label on the side",
      "typography": "small serif capitals"
    }
  ],
  "constraints": [
    "no watermark",
    "no extra text"
  ]
}
```

#### Midjourney

Prompt:

```text
a ceramic teapot, a pale oak table by a window, product photograph, soft morning light from the left, terracotta and cream, glazed stoneware, centred, with empty space above, eye level, "TEA" on a small paper label on the side, small serif capitals
```

Native parameters, typed after the prompt in the prompt bar: `--ar 4:5 --no watermark, extra text`

#### GPT Image 2.5 (API)

Prompt:

```text
Style: product photograph
Scene: a pale oak table by a window; eye level; centred, with empty space above; soft morning light from the left; terracotta and cream
Subject: a ceramic teapot (glazed stoneware)
Text: "TEA" on a small paper label on the side, small serif capitals
Constraints: no watermark; no extra text.
```

Native settings (sent as fields, not in the prompt): `model`: gpt-image-2.5-sunburst; `endpoint`: images.generate; `size`: null (4:5 is not one of the recommended sizes, so the renderer warns and leaves the size to you); `quality`: auto; `output_format`: png

#### FLUX 3 Image (API)

Prompt:

```text
Product photograph. A ceramic teapot, a pale oak table by a window. Soft morning light from the left. Terracotta and cream. Glazed stoneware. Centred, with empty space above. Eye level. No watermark, no extra text. The text reads "TEA" on a small paper label on the side, set in small serif capitals.
```

Native settings (sent as fields, not in the prompt): `aspect_ratio`: 4:5

#### Ideogram 4.5 (API v2)

Prompt:

```text
a ceramic teapot, a pale oak table by a window, product photograph, soft morning light from the left, terracotta and cream, glazed stoneware, centred, with empty space above, eye level. The text reads "TEA" on a small paper label on the side, small serif capitals. No watermark, no extra text.
```

Native settings (sent as fields, not in the prompt): `endpoint`: /v2/image/generate/ideogram-4-5; `rendering_quality`: high (no background is sent unless the brief sets one)

#### ComfyUI (positive and negative blocks)

Prompt:

```text
a ceramic teapot, a pale oak table by a window, product photograph, soft morning light from the left, terracotta and cream, glazed stoneware, centred, with empty space above, eye level. The text reads "TEA" on a small paper label on the side, small serif capitals
```

Negative prompt, in its own block: `watermark, extra text` (no "no" in a negative block: the exclusion is the item itself)

Node settings: node_inputs: Positive Prompt -> KSampler positive; Negative Prompt -> KSampler negative; cfg: set on the sampler node; the value depends on the checkpoint and is not given here
