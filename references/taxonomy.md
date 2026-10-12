# Technique taxonomy

Full name index by category. Consult only when the task needs a named technique
outside SKILL.md's Priority/Conditional/Experimental tiers — most real usage is
covered there and never reaches this file. Each entry with its source and status is in [technique-catalog.md](technique-catalog.md).

**Basics**: Zero-shot, Few-shot, One-shot, Role/Persona, Instruction, Context, Delimiters (XML/MD/tags), Output Formatting, Negative Prompting, Templates, Cross-Lingual Prompting, Chain-of-Translation, Output Priming (prefill; API-only, 400 on Claude 4.6+ — see tool-routing.md).
**Reasoning**: Chain-of-Thought (CoT), Zero/Few-shot CoT, Self-Consistency, Universal Self-Consistency, Least-to-Most, Tree of Thoughts, Graph of Thoughts, Skeleton-of-Thought, Plan-and-Solve, Analogical, Step-back, Thread-of-Thought, Chain-of-Draft, Chain-of-Symbol, Contrastive CoT, Multi-Chain Reasoning, Tabular CoT, Self-Ask, Rephrase-and-Respond, Meta-Cognitive Prompting, Take-a-deep-breath phrase (OPRO).
**Decomposition**: Prompt Chaining, Task Decomposition, Decomposed Prompting (Khot et al. 2022), Sequential/Recursive Prompting, Progressive Refinement.
**Self-correction**: Self-Refine, Reflexion, Self-Critique, Chain-of-Verification (CoVe), ReAct, PAL.
**Multiple answers**: Best-of-N, Majority Voting, Ensemble, Debate (Du et al. 2023), Multi-Agent, CAMEL, MetaGPT.
**Tools**: Function Calling, Tool Use, RAG, Query Rewriting (Ma et al. 2023), Context Injection, Grounding, External Memory, HyDE, IRCoT, Self-RAG (trained), ART, ToRA, TaskWeaver, ReWOO, RAP, LATS, Self-Debugging.
**Optimization**: APE, OPRO (Yang et al. 2023), DSPy, TextGrad, EvoPrompt, Promptbreeder, Batch Prompting (Cheng et al. 2023), Prompt Compression (LLMLingua, LongLLMLingua, LLMLingua-2), Meta Prompting, Prompt Generation/Mutation, Prefix/P-Tuning.
**Code**: Program-of-Thought, Code Prompting, Execution-based Prompting.
**Agents**: Agent Prompting, Planning Agents, Tool-Augmented Agents, Multi-Agent Systems.
**Safety**: Defensive Prompting, Jailbreak Resistance, Prompt Injection Defense, Input Sanitization, Guardrails, Spotlighting (Hines et al. 2024), Instruction Hierarchy (Wallace et al. 2024; training-based), Sandwich Defense, Canary Tokens, Least Privilege, Red Teaming (Perez et al. 2022; conceptual only). Full defense table: references/defenses.md.
**Evaluation**: Prompt/Benchmark/Automatic/Human Evaluation, A/B Testing, LLM-as-a-Judge (Zheng et al. 2023), G-Eval (Liu et al. 2023), Verbalized Confidence (Tian et al. 2023), Hallucination Detection (SelfCheckGPT, Manakul et al. 2023).
**Multimodal**: Image/Vision/Multimodal Prompting, Image+Text Reasoning, Set-of-Mark (Yang et al. 2023). Image style names: references/image-styles.md.
**Experimental**: Active Prompt, DSP, Generated Knowledge, Faithful CoT, Tree Search, Selection-Inference, Emotion Prompting.
**Vendor features** (VENDOR, not prompt text): Structured Outputs, Prompt Caching, Context Compaction.
**Training-time** (TRAINING-TIME): AutoPrompt, Sentinel-token chunking (Luo et al. 2024), Self-RAG (Asai et al. 2023).

**Exemplars**: Exemplar Ordering (Lu et al. 2021), Learned Exemplar Retrieval (EPR, Rubin et al. 2021), Similarity-based Selection (KNN), Contextual Calibration (Zhao et al. 2021; label distribution), Exemplar Augmentation (source not checked).

**White et al. pattern catalog (2023)**: 16 patterns in 6 categories. Input Semantics: Meta Language Creation. Output Customization: Output Automater, Persona, Visualization Generator, Recipe, Template. Error Identification: Fact Check List, Reflection. Prompt Improvement: Question Refinement, Alternative Approaches, Cognitive Verifier, Refusal Breaker. Interaction: Flipped Interaction, Game Play, Infinite Generation. Context Control: Context Manager. Clarification Questions (roughly Flipped Interaction) is an amerob name, not a White pattern name.

Inspired by The Prompt Report (arXiv:2406.06608). This list is not a reproduction of that taxonomy; model-specific rules live in tool-routing.md.

## Sources for the 2026-10-12 additions

Checked on arXiv (title, first author, and date read in session):

- 2210.02406 (Khot et al., 2022-10-05): Decomposed Prompting: A Modular Approach for Solving Complex Tasks
- 2102.09690 (Zhao et al., 2021-02-19): Calibrate Before Use: Improving Few-Shot Performance of Language Models. The abstract uses the term "contextual calibration".
- 2305.14975 (Tian et al., 2023-05-24): Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from Language Models Fine-Tuned with Human Feedback
- 2301.08721 (Cheng et al., 2023-01-19): Batch Prompting: Efficient Inference with Large Language Model APIs
- 2303.08896 (Manakul et al., 2023-03-15): SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models
- 2202.03286 (Perez et al., 2022-02-07): Red Teaming Language Models with Language Models
- 2302.11382 (White et al., 2023-02-21): A Prompt Pattern Catalog to Enhance Prompt Engineering with ChatGPT. Categories and patterns read in Table I.
- 2309.03409 (Yang et al., 2023-09-07): Large Language Models as Optimizers
- 2305.14283 (Ma et al., 2023-05-23): Query Rewriting for Retrieval-Augmented Large Language Models
- 2112.08633 (Rubin et al., 2021-12-16): Learning To Retrieve Prompts for In-Context Learning
- 2104.08786 (Lu et al., 2021-04-18): Fantastically Ordered Prompts and Where to Find Them: Overcoming Few-Shot Prompt Order Sensitivity
- 2403.14720 (Hines et al., 2024-03-20): Defending Against Indirect Prompt Injection Attacks With Spotlighting
- 2404.13208 (Wallace et al., 2024-04-19): The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions
- 2306.05685 (Zheng et al., 2023-06-09): Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena

The rows added on 2026-10-12 (ReWOO, RAP, LATS, Self-Debugging, HyDE, IRCoT, Self-RAG, the LLMLingua family, OPRO, DSPy, TextGrad, EvoPrompt, Promptbreeder, G-Eval, multi-agent debate, CAMEL, MetaGPT, Set-of-Mark, Sentinel tokens, Graph of Thoughts, Anthropic compaction) have their sources and checks in [technique-catalog.md](technique-catalog.md), sections 1 and 2.

Not verified. Do not cite these as established:
- Output Priming: named in amerob and in FareedKhan's cheatsheet; no primary source found. The prefill form is API-only and returns 400 on Claude 4.6+.
- Exemplar Augmentation: named in amerob only.
- In-Context Instruction Learning: an arXiv title search on 2026-10-12 found no match. Not added.
- Clarification Questions: an amerob name. Flipped Interaction is the closest White et al. pattern; that is a mapping, not a source.
- Google API context compaction: no page was checked (technique-catalog.md, section 3).
- "Take a deep breath" as a general reasoning improvement: only OPRO's single GSM8K setting is verified (technique-catalog.md, section 3).
