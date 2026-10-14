# Gemini image models: IDs, aliases, status, sizes, ratios, limits, prices

Verified on 2026-10-13 against the official pages listed below. Facts only; no vendor text is reproduced. The machine-readable copy is `gemini-image-models.json` in this folder. `scripts/check_repo.py` and `tests/test_image_catalog.py` keep the two files consistent. `scripts/contracts.py` resolves the aliases below for the validator and the studio.

**Check the official page again before using any value.** Model IDs, prices, and shutdown dates change. Anything marked UNKNOWN is not confirmed.

Sources read on 2026-10-13:
- Image generation guide (models, features, per-model tables, prompting guide, limitations, editing and generation templates; updated 2026-10-09): https://ai.google.dev/gemini-api/docs/image-generation
- Model pages (the "Versions" section gives the stage label): `gemini-nano-banana-2.1` (updated 2026-10-06), `gemini-3.1-flash-image` (2026-10-09), `gemini-3.1-flash-lite-image` (2026-09-03), `gemini-3-pro-image` (2026-09-03), `gemini-2.5-flash-image` (2026-09-03), `gemini-4-argon` (2026-10-13). Each is at https://ai.google.dev/gemini-api/docs/models/ followed by the ID.
- Release notes: https://ai.google.dev/gemini-api/docs/changelog (deprecation announcements are made here, according to the deprecations page)
- Pricing (updated 2026-10-13): https://ai.google.dev/gemini-api/docs/pricing
- Deprecations (updated 2026-10-12; Nano Banana table): https://ai.google.dev/gemini-api/docs/deprecations
- DeepMind prompt guide: https://deepmind.google/models/gemini-image/prompt-guide/
- Interactions API reference, generate-content API reference and image understanding page: read again on 2026-10-13 in this pass.

Read on the Cloud blog, dated 2026-03-05: https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana. Its own date is older than the other pages. Facts taken from it are marked "Cloud blog".

## Models

| Model ID | Status | Released | Shutdown | Sizes | Price per image (USD, standard) |
|---|---|---|---|---|---|
| `gemini-nano-banana-2.1` | Current (Stable) | 2026-10-06 | none announced | 1K, 2K, 4K | 1K 0.0336 · 2K 0.0504 · 4K 0.113 |
| `gemini-3.1-flash-image` | Deprecated (release notes, 2026-10-06) | 2026-05-28 | none announced | 512, 1K, 2K, 4K | 512 0.045 · 1K 0.067 · 2K 0.101 · 4K 0.151 |
| `gemini-3.1-flash-lite-image` | Active (model page: Stable) | 2026-06-30 | none announced | 1K | 1K 0.0336 |
| `gemini-3-pro-image` | Active (model page: Stable) | 2026-05-28 | none announced | 1K, 2K, 4K | 1K 0.134 · 2K 0.134 · 4K 0.24 |
| `gemini-2.5-flash-image` | Deprecated (pricing warning; the table lists a date); dates conflict (see below) | 2025-10-02 | 2027-03-15 in the table; 2026-10-02 in the pricing warning (open conflict) | 1K | 1K 0.039 |
| `gemini-3.1-flash-image-preview` | Shut down | 2026-02-26 | 2026-06-25 | none | none |
| `gemini-3-pro-image-preview` | Shut down | 2025-11-20 | 2026-06-25 | none | none |
| `gemini-2.5-flash-image-preview` | Shut down | 2025-05-07 | 2026-01-15 | none | none |
| `gemini-2.0-flash-preview-image-generation` | Shut down | 2025-05-07 | 2025-11-14 | none | none |

Notes:
- "None announced" means the deprecations table read on 2026-10-13 gives no shutdown date ("No shutdown date announced"). It does not promise the model stays available.
- The 3.1 Flash status follows the release notes of 2026-10-06, which announce the deprecation and name `gemini-nano-banana-2.1` as the migration target. Its model page, updated three days later, still says "Stable". The catalog uses the announcement.
- The model pages label `gemini-nano-banana-2.1`, `gemini-3.1-flash-image`, `gemini-3.1-flash-lite-image`, `gemini-3-pro-image` and `gemini-2.5-flash-image` "Stable". No page labels any of them as a preview. The 2.5 page is older than the deprecation pages.
- Release dates come from the "Nano Banana models" table of the deprecations page. The release notes give the same GA dates: 2026-05-28 for 3.1 Flash and Pro, and 2026-06-30 for Lite.
- Batch price is 50% of the standard price (pricing page). The batch figures on the page are rounded (0.022 for 0.5K, where half of 0.045 is 0.0225). The studio uses the standard price.
- Imagen models (`imagen-4.0-*`) are not Gemini image models and are outside this catalog. The deprecations table gives 2026-08-17 as their shutdown date, which has passed.

## Enumerations

**Aspect ratios (14, the union of all image models):** 1:1, 1:4, 4:1, 1:8, 8:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9.

Each model accepts its own list (guide per-model tables and features section, 2026-10-13):

| Model | Ratios | Basis |
|---|---|---|
| `gemini-nano-banana-2.1` | 1:1, 1:4, 4:1, 1:8, 8:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 | per-model pixel table |
| `gemini-3.1-flash-image` | 1:1, 1:4, 4:1, 1:8, 8:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 | per-model pixel table |
| `gemini-3.1-flash-lite-image` | 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 | features section ("adds ... aspect ratios"); no pixel table for this model |
| `gemini-3-pro-image` | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 | per-model pixel table. No 1:4, 4:1, 1:8, 8:1 |
| `gemini-2.5-flash-image` | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 | per-model table |

The Lite model page also says "Supports a discrete set of 14 aspect ratios". That would include 1:4, 4:1, 1:8 and 8:1. The catalog keeps the ten listed ratios (see Open conflicts).

Ratios such as 3:1, 11:4.5, 9:19.5, 1:2 and 2:1 are not in any list. Map them to the nearest value that the chosen model accepts, and say so in the prompt. The validator reports the nearest one.

Without an aspect ratio, the guide says the output matches the input image's size when an input image is given, and is a 1:1 square otherwise. Set the ratio in the `response_format` field, not only in the prompt text.

**Image sizes:** `512`, `1K`, `2K`, `4K`. Pixel sizes per ratio are in the guide's tables. For 1K, the 2.1 and 3.1 Flash models output 1024x1024 for 1:1, and Nano Banana 2.1 outputs 1376x768 for 16:9.
- `512` is documented only for `gemini-3.1-flash-image`. The guide says "Gemini 3.1 Flash Image adds the smaller 512px (0.5K) resolution (not supported on Gemini Nano Banana 2.1)". It writes the label as "512px (0.5K)" and once as "512px (05.K)". That model is deprecated, so the studio does not offer 512 px.
- The JSON value for 512 is `512`: the Interactions API reference lists `image_size` values `512`, `1K`, `2K` and `4K`, and the generate-content reference lists the enum names (read again 2026-10-13). No live call was made.
- `gemini-3.1-flash-lite-image` takes 1K only. Its model page says: "Supported image_size values: 1024px (1K). (Note: 2K and 4K are unsupported)."
- The `K` must be uppercase: `1K`, not `1k`. The guide says lowercase values "will be rejected".
- The API enum names are IMAGE_SIZE_FIVE_TWELVE, IMAGE_SIZE_ONE_K, IMAGE_SIZE_TWO_K and IMAGE_SIZE_FOUR_K.
- Output tokens per image (guide tables): 1K 1120, 2K 1680, 4K 2520 for 2.1 and 3.1 Flash; 512px 747 for 3.1 Flash; Pro 1K and 2K 1120, 4K 2000; 2.5 Flash Image 1290.
- Inline request limit: 20 MB for the whole request (image understanding page, read again 2026-10-13). The studio counts base64 characters plus the prompt bytes against it.

## Aliases: commercial names to model IDs

The names below come from the guide's "Model selection" section (2026-10-13). A commercial name is not an API ID. Write the ID in the request and the name in the explanation.

| Name the user may write | Model ID | Note |
|---|---|---|
| "Nano Banana 2.1", "Gemini Nano Banana 2.1" | `gemini-nano-banana-2.1` | Default for new projects |
| "Nano Banana 2", "Gemini 3.1 Flash Image" | `gemini-3.1-flash-image` | Deprecated on 2026-10-06 (release notes). The only one with 512 px. The studio does not offer it for new briefs |
| "Nano Banana 2 Lite", "Gemini 3.1 Flash Lite Image" | `gemini-3.1-flash-lite-image` | Cheapest and fastest. 1K only |
| "Nano Banana Pro", "Gemini 3 Pro Image" | `gemini-3-pro-image` | Premium, for complex layouts and professional assets |
| "Gemini 2.5 Flash Image" | `gemini-2.5-flash-image` | Deprecated; the dates conflict (see below). The table's replacement is Nano Banana 2 Lite |
| "Nano Banana 2 preview", "Nano Banana Pro preview", "Nano Banana preview" | shut-down previews | Say they were shut down; name the replacement |
| "Nano Banana" or "Gemini Image" with no number | none | The family. Use `gemini-nano-banana-2.1` and say which one was used |

Rules the code applies (`scripts/contracts.py`):
- "Nano Banana 2" is not read inside "Nano Banana 2.1", "Nano Banana 2 Lite" or "Nano Banana 2.10".
- A bare "Nano Banana" never means the 2025 model.
- A request that names two models at once is ambiguous. Ask, or pick the one the task needs and say why.

## Thinking

Thinking is on for the Gemini 3 image models and cannot be turned off in the API (guide, 2026-10-13). The model may create up to two interim images to test the composition; they are not charged. Thinking tokens are billed.

| Model | Levels the guide lists | Default |
|---|---|---|
| `gemini-nano-banana-2.1` | MINIMAL, MEDIUM, HIGH | MEDIUM |
| `gemini-3.1-flash-image` | MINIMAL, HIGH | MINIMAL |
| `gemini-3.1-flash-lite-image` | MINIMAL, HIGH | MINIMAL |
| `gemini-3-pro-image` | not listed for control | thinking on |
| `gemini-2.5-flash-image` | not listed (thinking levels are not documented in the pages read) | not documented |

The guide's example sends `generation_config: { "thinking_level": "high" }` (lowercase). The API reference enum is uppercase: MINIMAL, LOW, MEDIUM, HIGH. Sending `thinkingLevel` to a model older than Gemini 3 returns an error.

## Reference images

The guide's limit is up to 14 reference images in total per request. Each model's per-type limits add up to that total.

| Model | Object references | Character references | Style references |
|---|---|---|---|
| `gemini-nano-banana-2.1`, `gemini-3.1-flash-image` | 10 | 4 | not listed |
| `gemini-3.1-flash-lite-image` | 14 | not listed | not listed |
| `gemini-3-pro-image` | 6 | 5 | 3 |
| `gemini-2.5-flash-image` | works best with up to 3 images in total (Limitations) | | |

Resolved: the Limitations section says Pro "supports 5 images with high fidelity, and up to 14 images in total". Its 5 matches the character count, not the 6 high-fidelity objects in the table, so the sentence disagrees with the table. The per-type table is used, and 6 + 5 + 3 = 14.

Real people from web search: the guide says `gemini-nano-banana-2.1` and `gemini-3.1-flash-image` do not support real-world images of people from Google Search grounding "at this time".

Video input (video-to-image): `gemini-nano-banana-2.1`, `gemini-3.1-flash-image` and `gemini-3.1-flash-lite-image` only. Not for Pro.

## Grounding

- Google Search grounding: `gemini-nano-banana-2.1`, `gemini-3.1-flash-image` and `gemini-3-pro-image`. Not `gemini-3.1-flash-lite-image` ("Not supported by Gemini 3.1 Flash Lite Image model", features section).
- Google Image Search grounding: only `gemini-nano-banana-2.1` and `gemini-3.1-flash-image` ("only available", guide).
- Pricing: 5,000 free search requests per month, shared across Gemini 3 and newer models; then USD 14 per 1,000 requests (pricing page).

## Inputs, languages and limits

- Best-performance languages: EN, ar-EG, de-DE, es-MX, fr-FR, hi-IN, id-ID, it-IT, ja-JP, ko-KR, pt-BR, ru-RU, ua-UA, vi-VN, zh-CN (guide, Limitations).
- Audio input: not supported for image generation.
- Input token limit (model pages, read 2026-10-13): 131,072 for `gemini-nano-banana-2.1` and `gemini-3.1-flash-image`; 65,536 for `gemini-3.1-flash-lite-image`, `gemini-3-pro-image` and `gemini-2.5-flash-image`.
- Output token limit (model pages): 32,768 for `gemini-nano-banana-2.1`, `gemini-3.1-flash-image`, `gemini-3-pro-image` and `gemini-2.5-flash-image`; 4,096 for `gemini-3.1-flash-lite-image`.
- Limitation: "The model won't always follow the exact number of image outputs that the user explicitly asks for" (guide). When the count matters, send one request per image.
- Limitation: "When generating text for an image, Gemini works best if you first generate the text and then ask for an image with the text" (guide).

## Prompt structure

**Text-to-image formula:** [Subject] + [Action] + [Location/context] + [Composition] + [Style]

**Generation with reference images:** [Reference images] + [Relationship instruction] + [New scenario]

Source: Cloud blog (2026-03-05), section "Image generation". The image guide has no formula line. Its templates name the parts in their own order: the photorealistic template is shot type, subject, setting, lighting, camera angle and lens.

## Prompting facts from the official pages

- Describe the scene in narrative form. A plain list of keywords is not enough (Cloud blog).
- Start the prompt with a strong verb that names the main operation (Cloud blog).
- Describe the wanted scene positively. The guide recommends "semantic negative prompts": "an empty, deserted street with no signs of traffic", instead of "no cars". The API reference has no negative-prompt field (earlier pass).
- Exact text: enclose the words in quotation marks, and describe the typography, for example "bold sans-serif" or "neon cursive signage" (DeepMind guide; Cloud blog).
- Camera vocabulary (wide-angle, macro, low angle) controls the composition (guide).
- Consistency: give each character or object a distinct name, and upload clear references (DeepMind guide).
- Iteration: follow-up turns in the same conversation. The guide's example: "Keep everything the same, but change the character's expression to be more serious" (best practices).
- Editing: "Keep everything else in the image exactly the same, preserving the original style, lighting, and composition" (guide, inpainting template).
- Production specs: name the aspect ratio and the destination format, for example "widescreen backdrop" or "vertical social post" (DeepMind guide).
- Video as reference: a public YouTube URL or an uploaded file, for the three models above (guide).

## Endpoints, request shape and authentication

- Interactions endpoint: `POST https://generativelanguage.googleapis.com/v1beta/interactions` (guide examples, 2026-10-13).
- `input` is an array of parts: `{"type": "text", "text": ...}` and `{"type": "image", "data": <base64>, "mime_type": ...}`.
- `response_format` takes `{"type": "image", "aspect_ratio": ..., "image_size": ...}`. Without `type: "image"` the response includes text too. The guide says it "defaults to returning both text and image responses".
- Response shape (Interactions API reference, read again 2026-10-13): the interaction object has `steps`. A step of `type: "model_output"` carries `content` blocks. An image block has `data` (base64) and `mime_type` (enum). No live call was made, so the shape is confirmed by the reference only.
- Multi-turn editing (guide, "Multi-turn image editing", read 2026-10-13): the request adds a top-level `previous_interaction_id` set to the `id` of the earlier interaction. The API reference describes `id` as "a unique identifier for the interaction completion" and `previous_interaction_id` as "the ID of the previous interaction, if any". The pages read do not say how long the server keeps an interaction, or whether `store` is on by default (the reference describes `store` as "whether to store the response and request for later retrieval"). The studio sends the parent's image as a reference too, so an edit does not depend on that.
- Send the key in the `x-goog-api-key` header, as the guide does. Never in the URL.
- The generate-content endpoint (`models/{model}:generateContent`) is documented in the API reference (earlier pass).

## Safety and provenance

- Finish reasons in the API reference: `PROHIBITED_CONTENT`, `IMAGE_SAFETY` and `IMAGE_PROHIBITED_CONTENT`. When a prompt is blocked, ask the user before changing it. Do not rephrase it to get past the filter.
- Rights: the guide reminds users to have the necessary rights to any images they upload.
- SynthID: "All generated images include a SynthID watermark" (guide, updated 2026-10-09).
- C2PA: stated for `gemini-3.1-flash-lite-image` on its model page ("SynthID watermarking (Always On) + C2PA", updated 2026-09-03) and in the Cloud blog (2026-03-05: "All generated images include C2PA Content Credentials"). The guide and the other model pages read on 2026-10-13 do not mention it. Do not promise C2PA. Say SynthID by default.

## Open conflicts and gaps

- Shutdown date of `gemini-2.5-flash-image`: the deprecations table gives 2027-03-15, and its note says the table's dates are the earliest possible shutdown dates. The pricing warning gives 2026-10-02, which is earlier than that lower bound and has passed. The warning also names Gemini 3.1 Flash Image as a migration target, although the 2026-10-06 release note deprecated it. The catalog does not use the warning's date, and treats no date as confirmed.
- Status of `gemini-2.5-flash-image`: the deprecations table (updated 2026-10-12) lists a shutdown date for it, and the pricing warning (2026-10-13) says it "is deprecated". The release notes of 2026-09-18 say the 2.5 models "are not deprecated" and that access is limited to users who used them before. The release notes have no deprecation entry for this model. The model page (2026-09-03) says Stable.
- Aspect ratios of `gemini-3.1-flash-lite-image`: the features section and the model page list the same ten ratios, but the model page also says "a discrete set of 14". The catalog keeps the ten. Confirm before offering 1:4, 4:1, 1:8 or 8:1 for Lite.
- Live call to confirm the 512 px value and the response fields: not done, because the owner declined paid tests. The reference documents agree with the catalog.
- Rate limits: the pricing page says they are "subject to change". No numbers in the pages read.
- Text rendering limits (characters, phrases): no official numbers. Do not state them as facts.
- Prompt length guidance and "banned keyword" lists: no official source found. Do not state them as facts.

## Resolved in this pass (2026-10-13)

- Reference limits of Pro: the per-type table is used (6 + 5 + 3 = 14). The Limitations sentence disagrees with the table's object count.
- Preview or GA labels: the model pages say "Stable" for 2.1, 3.1 Flash, 3.1 Flash Lite, 3 Pro and 2.5 Flash Image. The 3.1 Flash label is superseded by its deprecation (release notes, 2026-10-06).
- Input and output token limits of Lite: 65,536 and 4,096 (model page). They were unknown.
- Input and output token limits of Pro: 65,536 and 32,768 (model page), consistent with the Cloud blog.
- The 512 px JSON value: confirmed by the Interactions and generate-content reference documents (not a live call).
- Inline request limit of 20 MB: confirmed on the image understanding page.
- Gemini 4 Argon (`gemini-4-argon`) is not an image model. Its model page says image generation is "Not supported", and its pricing has no image price. It is outside this catalog.
- Earlier error in this catalog: `gemini-3.1-flash-image` was listed as active. The release notes deprecated it on 2026-10-06.
