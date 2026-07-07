---
name: prompt-techniques
description: Reference + generator de prompt. Uso passivo — nomear/aplicar técnica de prompt engineering. Uso ativo — gerar prompt otimizado pra ferramenta específica (Claude, GPT, Cursor, Midjourney, agente de código) quando pedido explicitamente.
---

Fundido de duas fontes: lista própria de técnicas (referência) + [prompt-master](https://github.com/nidhinjs/prompt-master) (geração ativa).

## Modo referência (passivo)
Não recite lista salvo se pedido. Escolhe a técnica que serve a tarefa. Nomeia explicitamente
no raciocínio (ex: "usando Chain-of-Verification aqui") em vez de aplicar em silêncio — auditável.

**Básicas**: Zero-shot, Few-shot, One-shot, Role/Persona, Instruction, Context, Delimiters (XML/MD/tags), Output Formatting, Negative Prompting, Templates.
**Raciocínio**: Chain-of-Thought (CoT), Zero/Few-shot CoT, Self-Consistency, Least-to-Most, Tree of Thoughts, Graph of Thoughts, Skeleton-of-Thought, Plan-and-Solve, Analogical, Step-back, Thread-of-Thought.
**Decomposição**: Prompt Chaining, Task Decomposition, Sequential/Recursive Prompting, Progressive Refinement.
**Autocorreção**: Self-Refine, Reflexion, Self-Critique, Chain-of-Verification (CoVe), ReAct, PAL.
**Múltiplas respostas**: Best-of-N, Majority Voting, Ensemble, Debate, Multi-Agent.
**Ferramentas**: Function Calling, Tool Use, RAG, Context Injection, Grounding, External Memory.
**Otimização**: APE, Prompt Optimization/Compression, Meta Prompting, Prompt Generation/Mutation, Prefix/P-Tuning.
**Código**: Program-of-Thought, Code Prompting, Execution-based Prompting.
**Agentes**: Agent Prompting, Planning Agents, Tool-Augmented Agents, Multi-Agent Systems.
**Segurança**: Defensive Prompting, Jailbreak Resistance, Prompt Injection Defense, Input Sanitization, Guardrails.
**Avaliação**: Prompt/Benchmark/Automatic/Human Evaluation, A/B Testing.
**Multimodal**: Image/Vision/Multimodal Prompting, Image+Text Reasoning.
**Experimentais**: Active Prompt, DSP, Generated Knowledge, Faithful CoT, Tree Search, Selection-Inference, Emotion Prompting.
**Persuasão** (Meincke et al. 2025 — dobra compliance 33%→72%): Authority, Commitment, Scarcity, Social Proof, Unity (Reciprocity/Liking: evitar). Detalhe, exemplos ✅/❌ e tabela de combinação por tipo de prompt: [references/persuasion.md](references/persuasion.md). Nunca p/ contornar segurança.

## Modo gerador (ativo — só quando pedido "escreve/melhora/adapta prompt pra X")

**Regra dura**: não gera prompt sem confirmar ferramenta-alvo (pergunta se ambíguo, máx 3 perguntas).
Não explica teoria de prompt engineering salvo pedido. Não mostra nome de framework no output.
Preferir técnica simples (role, few-shot, grounding) sobre framework complexo (Mixture-of-Experts,
Tree/Graph-of-Thought, Self-Consistency, prompt chaining em camada) — essas têm risco de fabricação maior
em prompt único, só usar se pedido explícito e ferramenta suporta.
Nunca adiciona CoT em modelo reasoning-native (o3, o4-mini, DeepSeek-R1, Qwen3 thinking) — já pensa
internamente, CoT degrada saída.

**Antes de escrever**, extrai silenciosamente: task, ferramenta-alvo, formato de saída, constraint,
input, contexto, audiência, critério de sucesso, exemplo. Dimensão crítica faltando → pergunta (máx 3 total).

**Output**: 1 bloco de prompt copiável + `🎯 Target: <ferramenta>` + 1 frase do que foi otimizado e por quê.

**Detalhe por ferramenta e templates — não carregar aqui, ler sob demanda**:
- [references/tool-routing.md](references/tool-routing.md) — regra específica por Claude/GPT/Cursor/Midjourney/agente de código
- [references/patterns.md](references/patterns.md) — padrões que desperdiçam token/crédito (task/context/format/scope/reasoning/agentic)
- [references/templates.md](references/templates.md) — 9 templates estruturais (RTF, CO-STAR, RISEN, CRISPE, CoT, Few-Shot, File-Scope, ReAct+Stop, Visual Descriptor)

Ler só a seção da ferramenta/categoria precisa, não o arquivo inteiro.
