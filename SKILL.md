---
name: prompt-techniques
description: Reference + generator de prompt. Uso passivo — nomear/aplicar técnica de prompt engineering. Uso ativo — gerar prompt otimizado pra ferramenta específica (Claude, GPT, Cursor, Midjourney, agente de código) quando pedido explicitamente.
---

Fundido de duas fontes: lista própria de técnicas (referência) + [prompt-master](https://github.com/nidhinjs/prompt-master) (geração ativa).

## Modo referência (passivo)
Não recite lista salvo se pedido. Escolhe a técnica que serve a tarefa.

**Prioridade (nem toda técnica pesa igual)**:
- **Alto impacto, sempre considerar**: Role, Context, Output Formatting, Few-shot, Grounding, Delimiters.
- **Condicional**: CoT (só modelo NÃO-reasoning), ReAct/RAG/Function Calling (só c/ ferramentas reais), Reflexion/CoVe (tarefa factual/verificável).
- **Experimental/legado em modelos 2025+**: ToT, GoT, MoE simulado, Self-Consistency, chaining em camadas — ganho não comprovado em modelo moderno, risco de fabricação; só sob pedido explícito.
Base: The Prompt Report (arXiv:2406.06608) + docs oficiais de vendors — não avaliação própria. Quando aplicar uma,
nomeia em 1 linha curta **na resposta visível** (ex: "Técnica: Chain-of-Verification"), não só
no raciocínio interno — o usuário precisa ver pra ser auditável. Só nomeia quando a técnica
influenciou de fato a abordagem; tarefa trivial não ganha rótulo.

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
**Persuasão** (Meincke et al. 2025 — dobra compliance 33%→72%; compliance = obediência à instrução, NÃO qualidade/precisão da resposta): Authority, Commitment, Scarcity, Social Proof, Unity (Reciprocity/Liking: evitar). Usar só p/ disciplina de formato/processo. Detalhe, exemplos ✅/❌ e tabela: [references/persuasion.md](references/persuasion.md). Nunca p/ contornar segurança.

## Modo gerador (ativo — só quando pedido "escreve/melhora/adapta prompt pra X")

**Regra dura**: não gera prompt sem confirmar ferramenta-alvo (pergunta se ambíguo, máx 3 perguntas).
Não explica teoria de prompt engineering salvo pedido. Não mostra nome de framework no output.
Preferir técnica simples (role, few-shot, grounding) sobre framework complexo (Mixture-of-Experts,
Tree/Graph-of-Thought, Self-Consistency, prompt chaining em camada) — essas têm risco de fabricação maior
em prompt único, só usar se pedido explícito e ferramenta suporta.
Nunca adiciona CoT em modelo reasoning-native (o3, o4-mini, DeepSeek-R1, Qwen3 thinking) — já pensa
internamente, CoT degrada saída.

**Fast path**: pedido simples e não-ambíguo (ferramenta clara, task clara, sem formato exótico) →
gera direto, sem template, sem checklist, sem perguntas. A cerimônia completa abaixo é só p/ pedido
complexo/ambíguo. Na dúvida entre os dois caminhos, fast path.

**Antes de escrever** (caminho completo), extrai silenciosamente **do pedido do usuário** (extração ≠ pergunta): task,
ferramenta-alvo, formato de saída, constraint, input, contexto, audiência, critério de sucesso, exemplo.
Só vira pergunta o que é crítico E ausente (máx 3). Se a tarefa é genuinamente ambígua e 3 perguntas
não bastam: gera mesmo assim declarando as assunções no final ("Assumi: X, Y — corrige se errado"),
em vez de gerar prompt genérico em silêncio.

**Nota sobre "não mostrar framework"**: vale pro **prompt gerado** (o texto que o usuário cola na
ferramenta não carrega rótulo "CO-STAR"). A frase de otimização e o modo passivo PODEM nomear técnica —
são canais diferentes, não é contradição.

**Self-check antes de entregar**: revisa o prompt gerado contra a seção da ferramenta em
tool-routing.md. Violação detectada (ex: CoT em modelo reasoning-native, prosa onde a ferramenta
quer vírgulas, sem stop condition em agente) → corrige em silêncio antes de mostrar.

**Ferramenta desconhecida/nova**: se não está em tool-routing.md e web search está disponível,
busca "prompt best practices <ferramenta> <ano>" antes de gerar; depois oferece o bloco pronto
p/ o usuário colar em tool-routing.md. Sem web search → regras genéricas + aviso.

**Output**: 1 bloco de prompt copiável + `🎯 Target: <ferramenta>` + 1 frase do que foi otimizado e por quê
+ oferta de refinamento: "Testa na ferramenta e cola o resultado aqui se quiser que eu refine."

**Loop de refinamento** (quando o usuário volta com o output real da ferramenta): diagnostica a falha
com o Diagnostic Checklist de [references/tool-routing.md](references/tool-routing.md) (task/context/format/scope/reasoning/agentic),
ajusta SÓ a dimensão que falhou, entrega versão nova. Não reescreve do zero.

**Detalhe por ferramenta e templates — não carregar aqui, ler sob demanda**:
- [references/tool-routing.md](references/tool-routing.md) — regra específica por Claude/GPT/Cursor/Midjourney/agente de código
- [references/patterns.md](references/patterns.md) — padrões que desperdiçam token/crédito (task/context/format/scope/reasoning/agentic)
- [references/templates.md](references/templates.md) — 13 templates estruturais A–M (RTF, CO-STAR, RISEN, CRISPE, CoT, Few-Shot, File-Scope, ReAct+Stop, Visual Descriptor, Reference Image Editing, ComfyUI, Prompt Decompiler, Opus Task Brief)

Ler só a seção da ferramenta/categoria precisa, não o arquivo inteiro.
