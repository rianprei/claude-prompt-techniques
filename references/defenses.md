# Defenses for prompts that process untrusted content

Use this when the generated prompt will read web pages, documents, emails, tool output, or other content that a user or a third party controls. Conceptual only: this file names defense categories and their trade-offs. It contains no attack strings and no bypass steps.

## Principle first

- **Keep untrusted content away from sensitive decisions.** Tool calls, credentials, and actions must not depend only on what the model read from untrusted content. Give the model the narrowest scope the task allows (least privilege).
- **Treat output as untrusted when it drives an action.** Check it outside the model: schema validation, allow-lists, or a human approval step.
- **Layer the defenses.** The Valhall README says these mitigations "should be a last resort, never to be heavily relied on or treated as a catch-all. They will fail." Use at least two layers, and keep the trust boundary.

Source: Valhall-ai/prompt-injection-mitigations (Apache-2.0), README read 2026-10-12. The walled-garden idea (contain untrusted state so that only trusted users can be affected) comes from the same README.

## Defense categories

| Defense | What it does (concept) | Trade-off | Source status |
|---|---|---|---|
| Paraphrasing | A model rewrites the untrusted input, keeping its detail, before the main prompt reads it. | Extra model call; the rewrite can change meaning. Low time and cost. | Valhall README (secondary) |
| Threat-intel sanitization | Matches known injection patterns with string search, vector search, or embeddings, and removes the matches. | High upkeep; catches only known patterns. | Valhall README (secondary) |
| Mutation and repair | Perturbs the input, has a model repair it, and repeats; keeps the repaired text. | High time and cost; can damage legitimate content. | Valhall README (secondary) |
| Relevance filtering | Splits the input into items and drops the items that do not change the task's meaning. | High cost; can drop context the task needs. | Valhall README (secondary) |
| Type enforcement | Constrains the output to a strict schema, so injected text cannot change the format of an action. | Schema validity is not semantic safety. Low cost. | Valhall README (secondary); Structured Outputs in tool-routing.md |
| Model diversification | Compares two models' outputs and rejects or retries when they disagree. | Double cost; disagreement is not proof of an attack. | Valhall README (secondary) |
| Characterization | Flags inputs that resemble known techniques, using retrieval or a trained classifier. | High cost; misses new forms. | Valhall README (secondary) |
| Canary tokens | Puts a unique marker in the instructions and flags output that contains it. | Detects leakage after it happens; does not prevent it. | Valhall README (secondary) |
| Spotlighting | Marks untrusted input (for example, by delimiting or encoding it) so the model treats it as data. | Reduces the risk; does not remove it. | arXiv:2403.14720 (Hines et al., 2024), verified 2026-10-12 |
| Instruction hierarchy | Ranks instruction sources (system over user over tool output). | The original method is training-based; the prompt-level version is an approximation. | arXiv:2404.13208 (Wallace et al., 2024), verified 2026-10-12 |
| Sandwich | Restates the core constraint after the untrusted block (see tool-routing.md). | Adds tokens; not a guarantee. | Repo rule; no external source checked |
| Least privilege | Limits which tools and data the model can reach. | Can block legitimate work; needs design. | OWASP LLM01 (search summary only; not read in full) |

## How to use

- Pick at least two layers that fit the task's cost and latency.
- Start with the boundary, and add filters on top of it, not in place of it.
- For any generated prompt with untrusted content, apply the sandwich rule in [tool-routing.md](tool-routing.md).
