# Gemini image models: IDs, aliases, status, sizes, ratios, limits, prices

Verified on 2026-10-13 against the official pages listed below. Facts only; no vendor text is reproduced. The machine-readable copy is `gemini-image-models.json` in this folder. `scripts/check_repo.py` and `tests/test_image_catalog.py` keep the two files consistent. `scripts/contracts.py` resolves the aliases below for the validator and the studio.

**Check the official page again before using any value.** Model IDs, prices, and shutdown dates change. Anything marked UNKNOWN is not confirmed.

Sources read on 2026-10-13:
- Image generation guide (models, features, per-model tables, prompting guide, limitations, editing and generation templates): https://ai.google.dev/gemini-api/docs/image-generation
- Model page, Nano Banana 2.1 (status "Stable", limits, capabilities): https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1
- Pricing: https://ai.google.dev/gemini-api/docs/pricing
- Deprecations (Nano Banana table): https://ai.google.dev/gemini-api/docs/deprecations
- DeepMind prompt guide: https://deepmind.google/models/gemini-image/prompt-guide/

Read in an earlier pass on 2026-10-13, not read again today: the generate-content and Interactions API references, and the image understanding page (see `sources` in the JSON).

Read on the Cloud blog, dated 2026-03-05: https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana. Its own date is older than the other pages. Facts taken from it are marked "Cloud blog".

## Models

| Model ID | Status | Released | Shutdown | Sizes | Price per image (USD, standard) |
|---|---|---|---|---|---|
| `gemini-nano-banana-2.1` | Current (Stable) | 2026-10-06 | none listed | 1K, 2K, 4K | 1K 0.0336 · 2K 0.0504 · 4K 0.113 |
| `gemini-3.1-flash-image` | Active | 2026-05-28 | none listed | 512, 1K, 2K, 4K | 512 0.045 · 1K 0.067 · 2K 0.101 · 4K 0.151 |
| `gemini-3.1-flash-lite-image` | Active | 2026-06-30 | none listed | 1K | 1K 0.0336 |
| `gemini-3-pro-image` | Active | 2026-05-28 | none listed | 1K, 2K, 4K | 1K 0.134 · 2K 0.134 · 4K 0.24 |
| `gemini-2.5-flash-image` | Deprecated | 2025-10-02 | 2027-03-15 in the table; 2026-10-02 in the pricing warning (open conflict) | 1K | 1K 0.039 |
| `gemini-3.1-flash-image-preview` | Shut down | 2026-02-26 | 2026-06-25 | none | none |
| `gemini-3-pro-image-preview` | Shut down | 2025-11-20 | 2026-06-25 | none | none |
| `gemini-2.5-flash-image-preview` | Shut down | 2025-05-07 | 2026-01-15 | none | none |
| `gemini-2.0-flash-preview-image-generation` | Shut down | 2025-05-07 | 2025-11-14 | none | none |

Notes:
- "None listed" means the deprecations table read on 2026-10-13 shows no shutdown date. It does not promise the model stays available.
- The model page labels `gemini-nano-banana-2.1` as "Stable". The pages read do not state whether the other current IDs are preview or GA.
- Release dates come from the "Nano Banana models" table of the deprecations page. The earlier pass did not have them for 3.1 Flash, Lite and Pro.
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

Ratios such as 3:1, 11:4.5, 9:19.5, 1:2 and 2:1 are not in any list. Map them to the nearest value that the chosen model accepts, and say so in the prompt. The validator reports the nearest one.

Without an aspect ratio, the guide says the output matches the input image's size when an input image is given, and is a 1:1 square otherwise. Set the ratio in the `response_format` field, not only in the prompt text.

**Image sizes:** `512`, `1K`, `2K`, `4K`. Pixel sizes per ratio are in the guide's tables. For 1K, the 2.1 and 3.1 Flash models output 1024x1024 for 1:1, and Nano Banana 2.1 outputs 1376x768 for 16:9.
- `512` is documented only for `gemini-3.1-flash-image`. The guide says "Gemini 3.1 Flash Image adds the smaller 512px (0.5K) resolution (not supported on Gemini Nano Banana 2.1)". It writes the label as "512px (0.5K)" and once as "512px (05.K)".
- The JSON value for 512 is `512`: the Interactions API reference lists `image_size` values `512`, `1K`, `2K`, `4K`, and the generate-content reference lists the same for `imageSize` (read 2026-10-13). No live call was made.
- The `K` must be uppercase: `1K`, not `1k`. The guide says lowercase values "will be rejected".
- The API enum names are IMAGE_SIZE_FIVE_TWELVE, IMAGE_SIZE_ONE_K, IMAGE_SIZE_TWO_K and IMAGE_SIZE_FOUR_K.
- Output tokens per image (guide tables): 1K 1120, 2K 1680, 4K 2520 for 2.1 and 3.1 Flash; 512px 747 for 3.1 Flash; Pro 1K and 2K 1120, 4K 2000; 2.5 Flash Image 1290.
- Inline request limit: 20 MB for the whole request (image understanding page). The studio counts base64 characters plus the prompt bytes against it.

## Aliases: commercial names to model IDs

The names below come from the guide's "Model selection" section (2026-10-13). A commercial name is not an API ID. Write the ID in the request and the name in the explanation.

| Name the user may write | Model ID | Note |
|---|---|---|
| "Nano Banana 2.1", "Gemini Nano Banana 2.1" | `gemini-nano-banana-2.1` | Default for new projects |
| "Nano Banana 2", "Gemini 3.1 Flash Image" | `gemini-3.1-flash-image` | The previous model. The only one with 512 px |
| "Nano Banana 2 Lite", "Gemini 3.1 Flash Lite Image" | `gemini-3.1-flash-lite-image` | Cheapest and fastest. 1K only |
| "Nano Banana Pro", "Gemini 3 Pro Image" | `gemini-3-pro-image` | Premium, for complex layouts and professional assets |
| "Gemini 2.5 Flash Image" | `gemini-2.5-flash-image` | Deprecated. Its migration path is Nano Banana 2 Lite |
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

The guide's limit is up to 14 reference images in total per request.

| Model | Object references | Character references | Style references |
|---|---|---|---|
| `gemini-nano-banana-2.1`, `gemini-3.1-flash-image` | 10 | 4 | not listed |
| `gemini-3.1-flash-lite-image` | 14 | not listed | not listed |
| `gemini-3-pro-image` | 6 | 5 | 3 |
| `gemini-2.5-flash-image` | works best with up to 3 images in total (Limitations) | | |

Conflict: the Limitations section says Pro "supports 5 images with high fidelity, and up to 14 images in total". The table is used here.

Real people from web search: the guide says `gemini-nano-banana-2.1` and `gemini-3.1-flash-image` do not support real-world images of people from Google Search grounding "at this time".

Video input (video-to-image): `gemini-nano-banana-2.1`, `gemini-3.1-flash-image` and `gemini-3.1-flash-lite-image` only. Not for Pro.

## Grounding

- Google Search grounding: `gemini-nano-banana-2.1`, `gemini-3.1-flash-image` and `gemini-3-pro-image`. Not `gemini-3.1-flash-lite-image` ("Not supported by Gemini 3.1 Flash Lite Image model", features section).
- Google Image Search grounding: only `gemini-nano-banana-2.1` and `gemini-3.1-flash-image` ("only available", guide).
- Pricing: 5,000 free search requests per month, shared across Gemini 3 and newer models; then USD 14 per 1,000 requests (pricing page).

## Inputs, languages and limits

- Best-performance languages: EN, ar-EG, de-DE, es-MX, fr-FR, hi-IN, id-ID, it-IT, ja-JP, ko-KR, pt-BR, ru-RU, ua-UA, vi-VN, zh-CN (guide, Limitations).
- Audio input: not supported for image generation.
- Input token limit: 131,072 for `gemini-nano-banana-2.1` (model page) and `gemini-3.1-flash-image` (Cloud blog). 65,536 for `gemini-3-pro-image` (Cloud blog). Unknown for Lite.
- Output token limit: 32,768 for `gemini-nano-banana-2.1` (model page); 32,768 for 3.1 Flash and Pro (Cloud blog).
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
- Send the key in the `x-goog-api-key` header, as the guide does. Never in the URL.
- The generate-content endpoint (`models/{model}:generateContent`) is documented in the API reference (earlier pass).

## Safety and provenance

- Finish reasons in the API reference: `PROHIBITED_CONTENT`, `IMAGE_SAFETY` and `IMAGE_PROHIBITED_CONTENT`. When a prompt is blocked, ask the user before changing it. Do not rephrase it to get past the filter.
- Rights: the guide reminds users to have the necessary rights to any images they upload.
- SynthID: "All generated images include a SynthID watermark" (guide, 2026-10-13).
- C2PA: conflict. The Cloud blog (2026-03-05) says all generated images include C2PA Content Credentials. The current guide does not mention C2PA. Do not promise it.

## Open conflicts and gaps (UNKNOWN)

- Shutdown date of `gemini-2.5-flash-image`: 2027-03-15 in the deprecations table; 2026-10-02 in the pricing warning. No date is treated as confirmed.
- Replacement of `gemini-2.5-flash-image`: the deprecations table and the guide name Nano Banana 2 Lite; the pricing warning names Nano Banana 2 or Nano Banana 2 Lite.
- Pro reference limits: the table (6, 5, 3) and the Limitations text (5 with high fidelity, up to 14 in total) differ.
- Lite aspect ratios: taken from the features section, with no pixel table.
- Input token limit for Lite: not stated. For Pro: 65,536 from the Cloud blog only.
- Preview or GA label for `gemini-3.1-flash-image`, `gemini-3.1-flash-lite-image` and `gemini-3-pro-image`: not stated on the pages read.
- Live call to confirm the 512 px JSON value and the response fields of the Interactions API: not done, because the owner declined paid tests.
- Rate limits: the pricing page says they are "subject to change". No numbers in the pages read.
- Text rendering limits (characters, phrases): no official numbers. Do not state them as facts.
- Prompt length guidance and "banned keyword" lists: no official source found. Do not state them as facts.
- The Gemini 4 Argon banner on the model page and the Cloud blog is outside the image catalog and was not investigated.
