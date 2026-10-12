# Gemini image models: IDs, status, sizes, prices

Verified on 2026-10-12 against the official pages listed below. Facts only; no vendor text is reproduced. The machine-readable copy is `gemini-image-models.json` in this folder. `scripts/check_repo.py` and `tests/test_image_catalog.py` keep the two files consistent.

**Check the official page again before using any value.** Model IDs, prices, and shutdown dates change. Anything marked UNKNOWN is not confirmed.

Sources read:
- Image generation guide: https://ai.google.dev/gemini-api/docs/image-generation
- API reference, generateContent: https://ai.google.dev/api/generate-content
- Pricing: https://ai.google.dev/gemini-api/docs/pricing
- Deprecations: https://ai.google.dev/gemini-api/docs/deprecations
- Prompting guide, dated 2026-03-05: https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana

## Models

| Model ID | Status | Released | Shutdown | Sizes | Price per image (USD, standard) |
|---|---|---|---|---|---|
| `gemini-nano-banana-2.1` | Current | 2026-10-06 | none listed | 1K, 2K, 4K | 1K 0.0336 · 2K 0.0504 · 4K 0.113 |
| `gemini-3.1-flash-image` | Active | UNKNOWN | none listed | 512, 1K, 2K, 4K | 512 0.045 · 1K 0.067 · 2K 0.101 · 4K 0.151 |
| `gemini-3.1-flash-lite-image` | Active | UNKNOWN | none listed | 1K | 1K 0.0336 |
| `gemini-3-pro-image` | Active | UNKNOWN | none listed | 1K, 2K, 4K | 1K 0.134 · 2K 0.134 · 4K 0.24 |
| `gemini-2.5-flash-image` | Deprecated | 2025-10-02 | 2027-03-15 in the table; 2026-10-02 on the pricing page (open conflict) | 1K | 1K 0.039 |
| `gemini-3.1-flash-image-preview` | Shut down | 2026-02-26 | 2026-06-25 | none | none |
| `gemini-3-pro-image-preview` | Shut down | 2025-11-20 | 2026-06-25 | none | none |
| `gemini-2.5-flash-image-preview` | Shut down | 2025-05-07 | 2026-01-15 | none | none |

Notes:
- "None listed" means the deprecations table read on 2026-10-12 shows no shutdown date. It does not promise the model stays available.
- Whether `gemini-nano-banana-2.1` is labelled preview or GA is UNKNOWN in the pages read.
- Batch price is 50% of the standard price (pricing page: "Batch API (50% cost reduction)").
- The replacement for `gemini-2.5-flash-image` is `gemini-3.1-flash-lite-image` in the deprecations table, and Gemini 3.1 Flash Image on the pricing page. Open conflict.
- Replacements for the shut-down previews: `gemini-nano-banana-2.1` for the 3.1 Flash and 2.5 previews, and `gemini-3-pro-image` for the Pro preview.

## Enumerations

**Aspect ratios (14):** 1:1, 1:4, 4:1, 1:8, 8:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9.

Ratios such as 3:1, 11:4.5, 9:19.5, 1:2 and 2:1 are not in this list. Map them to the nearest value and say so.

**Image sizes:** `512`, `1K`, `2K`, `4K`.
- `512` is documented only for `gemini-3.1-flash-image`, written as "512px (0.5K)".
- The `K` must be uppercase: `1K`, not `1k`.
- The API enum names are IMAGE_SIZE_FIVE_TWELVE, IMAGE_SIZE_ONE_K, IMAGE_SIZE_TWO_K and IMAGE_SIZE_FOUR_K.
- The JSON value for 512 is UNKNOWN. Confirm it with a test call before relying on it.

**Thinking levels:** `MINIMAL`, `LOW`, `MEDIUM`, `HIGH` (uppercase enum in the API reference). The default depends on the model. Sending `thinkingLevel` to a model older than Gemini 3 returns an error. According to the image guide, thinking cannot be turned off through the API (not re-checked in this pass).

## Reference images

| Model | Object references | Character references | Style references |
|---|---|---|---|
| `gemini-nano-banana-2.1`, `gemini-3.1-flash-image` | 10 | 4 | not listed |
| `gemini-3.1-flash-lite-image` | 14 | not listed | not listed |
| `gemini-3-pro-image` | 6 | 5 | 3 |

The guide gives the limits as "up to 14 / 10 / 6 images of objects", "up to 4 / 5 images of characters" and "up to 3 images as style references". The mapping of these limits to models was not re-checked in this pass. Re-check it before relying on it.

## Inputs and languages

- Input token limit: 131,072 tokens for `gemini-3.1-flash-image` (prompting guide, 2026-03-05). Limits for the other models: UNKNOWN in the pages read.
- Video input: supported by `gemini-nano-banana-2.1`, `gemini-3.1-flash-image` and `gemini-3.1-flash-lite-image`. Not listed for `gemini-3-pro-image`.
- Languages with the best performance: EN, ar-EG, de-DE, es-MX, fr-FR, hi-IN, id-ID, it-IT, ja-JP, ko-KR, pt-BR, ru-RU, ua-UA, vi-VN, zh-CN.

## Prompting facts from the official pages

- Describe the scene in narrative form. The prompting guide says a plain list of keywords is not enough.
- The API reference has no negative-prompt field. The guide recommends semantic negative prompts: describe what should be there. Example from the guide: "an empty, deserted street with no signs of traffic", instead of "no cars".
- For complex scenes, describe the steps in order, then refine with follow-up turns.
- Camera vocabulary (wide-angle, macro, low-angle) is documented as a way to control composition.

## Grounding and pricing extras

- Search grounding: 5,000 free requests per month, shared across Gemini 3 and newer models. After that, USD 14 per 1,000 requests (pricing page).
- Which image models support search grounding was not re-checked in this pass. Verify before relying on it.

## Safety

Finish reasons in the API reference: `PROHIBITED_CONTENT`, `IMAGE_SAFETY` and `IMAGE_PROHIBITED_CONTENT`. A prompt can also be blocked by a terminology list. When a prompt is blocked, ask the user before changing it. Do not rephrase it to get past the filter.

## Endpoints and authentication

- The API reference documents `models/{model}:generateContent`.
- The image guide shows the Interactions endpoint (`/v1beta/interactions`) in its examples.
- Send the key in the `x-goog-api-key` header, as the guide does.

## Open conflicts and gaps (UNKNOWN)

- Shutdown date of `gemini-2.5-flash-image` (see the table).
- C2PA: not confirmed in this pass. Do not promise it. SynthID: not re-checked in this pass.
- JSON value for 512 px.
- Rate limits: the pricing page says they are "subject to change". No numbers in the pages read.
- Text rendering limits (characters, phrases): no official numbers found. Do not state them as facts.
- Prompt length guidance and "banned keyword" lists: no official source found. Do not state them as facts.
