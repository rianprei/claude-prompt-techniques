# prompt-techniques

**Skill de Claude Code: referência de prompt engineering + gerador de prompts otimizados por ferramenta-alvo.**

Você pede "escreve um prompt pra Midjourney gerar um gato samurai" e recebe um prompt pronto pra colar, com a sintaxe e as regras específicas do Midjourney. Ou trabalha normalmente e o Claude aplica (e nomeia na resposta) a técnica de prompt engineering relevante.

> **Honestidade primeiro:** essa skill é uma agregação curada de fontes upstream (ver [Créditos](#créditos)) + taxonomia própria, organizada pra economizar contexto. **Não tem eval automatizado nem A/B cego** — as regras de routing vêm de docs oficiais e prática da comunidade, não de avaliação formal minha; o que existe é só um protocolo manual de A/B ([`evals/protocol.md`](evals/protocol.md)). Trate como framework de trabalho bem organizado, não como verdade medida. Detalhe em [Limitações](#limitações-conhecidas).

---

## Quick Start (30 segundos)

```bash
git clone https://github.com/rianprei/claude-prompt-techniques ~/.claude/skills/prompt-techniques
```

Abra sessão nova do Claude Code e peça:

```
escreve um prompt pra Midjourney: gato samurai em estilo ukiyo-e
```

Pronto. O resto deste README é detalhe — leia quando precisar.

---

## Índice

- [O que essa skill faz](#o-que-essa-skill-faz)
- [Por que ela existe](#por-que-ela-existe)
- [Instalação](#instalação)
- [Como usar — modo referência (passivo)](#como-usar--modo-referência-passivo)
- [Como usar — modo gerador (ativo)](#como-usar--modo-gerador-ativo)
- [Exemplos práticos](#exemplos-práticos)
- [Arquitetura: por que ela não estoura seu contexto](#arquitetura-por-que-ela-não-estoura-seu-contexto)
- [Ferramentas cobertas](#ferramentas-cobertas)
- [Templates incluídos](#templates-incluídos)
- [Princípios de persuasão](#princípios-de-persuasão)
- [Regras fixas](#regras-fixas)
- [Limitações conhecidas](#limitações-conhecidas)
- [Uso fora do Claude Code](#uso-fora-do-claude-code)
- [Customizar e estender](#customizar-e-estender)
- [Troubleshooting / FAQ](#troubleshooting--faq)
- [Desinstalar](#desinstalar)
- [Créditos](#créditos)

---

## O que essa skill faz

Dois modos numa skill só:

| Modo | Quando ativa | O que faz |
|---|---|---|
| **Referência (passivo)** | Sempre, automático | Quando uma técnica influencia a abordagem, o Claude a nomeia em 1 linha **na resposta visível** (ex: "Técnica: Chain-of-Verification"). Você vê, não fica escondido no raciocínio interno. Tarefa trivial não ganha rótulo. |
| **Gerador (ativo)** | Só quando você pede explicitamente | Gera um prompt pronto pra colar, com regras específicas da ferramenta-alvo (Claude, GPT, Cursor, Midjourney, Claude Code, ElevenLabs, n8n...), e oferece loop de refinamento com o output real. |

Cobre **14 categorias de técnicas** — com **camadas de prioridade** (nem toda técnica pesa igual): alto impacto (role, context, output format, few-shot, grounding), condicionais (CoT só em modelo não-reasoning, ReAct/RAG só com ferramentas reais) e experimentais/legadas em modelos 2025+ (ToT, GoT, Self-Consistency — só sob pedido explícito, risco de fabricação). Base: [The Prompt Report](https://arxiv.org/abs/2406.06608) + docs oficiais dos vendors. Inclui **persuasão** (compliance de instrução — ver caveat na [seção própria](#princípios-de-persuasão)).

Antes de entregar qualquer prompt, a skill faz **self-check** contra as regras da ferramenta-alvo e corrige violações em silêncio. Ferramenta que não está no routing: busca best practices na web (se disponível) e oferece o bloco pronto pra você adicionar ao `tool-routing.md`.

## Por que ela existe

Dois problemas comuns:

1. **Você não é especialista em cada ferramenta de IA.** Prompt bom pra Claude é diferente de prompt bom pra o3 (que degrada se você adicionar "think step by step"), que é diferente de Midjourney (descritores separados por vírgula, não prosa), que é diferente de Stable Diffusion (sintaxe de peso `(word:1.3)`, negative prompt obrigatório). Essa skill sabe as regras de cada uma.

2. **Skills de prompt engineering costumam poluir o contexto.** A maioria joga 5.000+ palavras na janela de contexto em toda sessão. Essa skill usa *progressive disclosure*: o arquivo principal é mínimo, e o detalhe pesado só é lido no momento exato em que é necessário. Detalhe na [seção de arquitetura](#arquitetura-por-que-ela-não-estoura-seu-contexto).

## Instalação

**Pré-requisito:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code) instalado.

**Via git (recomendado — permite atualizar com `git pull`):**

```bash
git clone https://github.com/rianprei/claude-prompt-techniques ~/.claude/skills/prompt-techniques
```

**Sem git:**

```bash
mkdir -p ~/.claude/skills/prompt-techniques/references
base=https://raw.githubusercontent.com/rianprei/claude-prompt-techniques/master
curl -fL $base/SKILL.md -o ~/.claude/skills/prompt-techniques/SKILL.md
for f in tool-routing patterns templates persuasion; do
  curl -fL $base/references/$f.md -o ~/.claude/skills/prompt-techniques/references/$f.md
done
```

**Verificar:**

```bash
ls ~/.claude/skills/prompt-techniques/ ~/.claude/skills/prompt-techniques/references/
# Esperado: SKILL.md, README.md e references/ com 4 arquivos .md
```

**Ativar:** abra uma sessão nova do Claude Code. A skill carrega automaticamente — zero configuração. Pra confirmar, pergunte ao Claude: "qual skill de prompt engineering você tem disponível?"

**Atualizar:**

```bash
cd ~/.claude/skills/prompt-techniques && git pull
```

## Como usar — modo referência (passivo)

Nada a fazer. Funciona sozinho em qualquer tarefa.

Quando uma técnica de prompt engineering influencia de fato a abordagem (debug, análise, verificação factual...), o Claude a nomeia em 1 linha **na resposta visível** — ex: "Técnica: Chain-of-Verification". Você vê o que está em jogo sem abrir raciocínio interno. Tarefa trivial não ganha rótulo, pra não virar ruído.

Se quiser a lista completa de técnicas, pergunte: "lista as categorias de técnicas da skill prompt-techniques".

## Como usar — modo gerador (ativo)

Peça **explicitamente** um prompt. Gatilhos: "escreve um prompt pra...", "melhora esse prompt...", "adapta esse prompt de X pra Y", "cria um prompt que...".

O que acontece internamente:

1. **Confirma a ferramenta-alvo.** Se você não disse pra qual IA é o prompt, o Claude pergunta.
2. **Extrai 9 dimensões do seu pedido** (extração é leitura, não interrogatório): tarefa, ferramenta, formato de saída, restrições, input, contexto, audiência, critério de sucesso, exemplos. Só vira pergunta o que é crítico E ausente — máximo 3. Se 3 não bastam numa tarefa muito ambígua, ele gera mesmo assim e **declara as assunções no final** pra você corrigir, em vez de entregar prompt genérico em silêncio.
3. **Escolhe a técnica mais simples que resolve.** Role assignment, few-shot e grounding antes de frameworks pesados (Tree of Thoughts, Mixture of Experts, Self-Consistency) — os pesados têm risco maior de fabricação e só entram se você pedir.
4. **Aplica as regras da ferramenta-alvo** lendo só a seção relevante de `references/tool-routing.md`.
5. **Usa o template estrutural certo** de `references/templates.md` se o tipo de tarefa casar.
6. **Oferece refinamento:** você testa o prompt na ferramenta e cola o output de volta; o Claude diagnostica a falha (checklist de 6 categorias: task/context/format/scope/reasoning/agentic) e ajusta só a dimensão que falhou. Gerar → testar → refinar, não gerar-e-tchau.

**Formato da resposta:** 1 bloco de prompt copiável + `🎯 Target: <ferramenta>` + 1 frase explicando o que foi otimizado + oferta de refinamento.

**Esclarecimento (pra não parecer contradição):** "sem nome de framework" vale pro **texto do prompt gerado** — o que você cola no Midjourney não vem rotulado "CO-STAR". A frase de otimização e o modo passivo podem nomear técnica normalmente; são canais diferentes.

## Exemplos práticos

**Imagem:**
> "escreve um prompt pro Midjourney: cidade cyberpunk chuvosa vista de cima"

Retorna descritores separados por vírgula (não prosa), sujeito primeiro, depois estilo/mood/iluminação/composição, parâmetros `--ar 16:9 --v 6` no final.

**Modelo de raciocínio:**
> "adapta esse meu prompt do Claude pro o3"

Remove qualquer instrução de "pense passo a passo" (degrada modelos reasoning-native), encurta pra instrução limpa e direta, mantém só objetivo + formato de saída.

**IDE de código:**
> "cria um prompt pro Cursor refatorar minha função de auth"

Usa o template File-Scope: caminho exato do arquivo, nome da função, comportamento atual, mudança desejada, lista do que NÃO tocar, condição "Done when".

**Agente autônomo:**
> "prompt pro Claude Code migrar meu projeto de npm pra pnpm"

Usa template ReAct + Stop Conditions: estado inicial, estado final, ações permitidas, ações proibidas, condições de parada obrigatórias (maior causa de queima de créditos em agentes é loop sem parada).

**Melhorar prompt existente:**
> "melhora: 'me ajuda a escrever um email de vendas'"

Claude pergunta a ferramenta-alvo e o contexto que falta (máx 3 perguntas), depois devolve prompt estruturado com audiência, tom e formato definidos.

## Arquitetura: por que ela não estoura seu contexto

```
prompt-techniques/
├── SKILL.md                    # entry point — pequeno, carregado sempre
└── references/                 # pesados, carregados SÓ sob demanda
    ├── tool-routing.md         # regras específicas de 30+ ferramentas (~460 linhas)
    ├── templates.md            # 13 templates estruturais completos
    ├── patterns.md             # padrões que desperdiçam tokens/créditos
    └── persuasion.md           # 7 princípios de persuasão p/ compliance
evals/
└── protocol.md                 # protocolo manual de A/B + log de re-prompts
```

`SKILL.md` contém só a lista de categorias (modo passivo) e as regras do gerador (modo ativo), com **links** para os arquivos de `references/`. O Claude lê `tool-routing.md` apenas quando você pede um prompt — e só a seção da ferramenta pedida. Isso é *progressive disclosure*: você não paga tokens por conhecimento que não está usando naquele momento.

Comparação: skills que carregam tudo no início custam milhares de tokens por sessão e causam o efeito "lost in the middle" (modelo ignora regras porque o contexto saturou). Aqui o custo fixo por sessão é só o SKILL.md.

## Ferramentas cobertas

Regras específicas em `references/tool-routing.md`:

| Categoria | Ferramentas |
|---|---|
| LLMs de texto | Claude (Opus 4.7/4.8), ChatGPT/GPT-5.x, Gemini 2.x/3 Pro, Qwen 2.5, Llama/Mistral, MiniMax M3/M2.7 |
| Reasoning-native | o3, o4-mini, DeepSeek-R1, Qwen3 thinking (regra: NUNCA adicionar CoT) |
| Local | Ollama (pergunta qual modelo antes de gerar) |
| Agentes de código | Claude Code, Cursor, Windsurf, Cline, GitHub Copilot, Devin, SWE-agent, Antigravity |
| Geradores full-stack | Bolt, v0, Lovable, Figma Make, Google Stitch |
| Pesquisa/orquestração | Perplexity, Manus AI |
| Browser/computer-use | Comet, Atlas, Claude in Chrome |
| Imagem | Midjourney, DALL-E 3, Stable Diffusion, SeeDream, Nano Banana Pro, ComfyUI |
| Vídeo | Sora, Runway, Kling, LTX Video, Dream Machine |
| Voz | ElevenLabs |
| 3D | Meshy, Tripo, Rodin, Unity AI, Blender AI |
| Workflow | Zapier, Make, n8n |

Ferramenta fora da lista: o Claude aplica regras genéricas (instrução explícita, contrato de saída, format lock) ou pergunta.

## Templates incluídos

`references/templates.md` — 13 templates, cada um com exemplo preenchido:

| Template | Melhor pra |
|---|---|
| A — RTF (Role, Task, Format) | tarefa simples one-shot |
| B — CO-STAR | documento profissional, escrita de negócio |
| C — RISEN | projeto complexo multi-etapa |
| D — CRISPE | trabalho criativo, brand voice |
| E — Chain of Thought | lógica, matemática, debug (NUNCA em modelo reasoning) |
| F — Few-Shot | formato mais fácil de mostrar que descrever |
| G — File-Scope | Cursor/Windsurf/Copilot — edição de código |
| H — ReAct + Stop Conditions | Claude Code/Devin — agentes autônomos |
| I — Visual Descriptor | Midjourney/DALL-E/SD/Sora (inclui fórmula de 7 componentes + 9 modos de expertise) |
| J — Reference Image Editing | editar imagem existente (só descreve o delta) |
| K — ComfyUI | workflow nodal (positive + negative separados) |
| L — Prompt Decompiler | quebrar/adaptar/dividir prompt existente |
| M — Opus 4.7/4.8 Task Brief | tarefa complexa/agentic em Claude Opus |

## Princípios de persuasão

`references/persuasion.md` — baseado em Meincke et al. (2025), estudo com N=28.000 conversas: técnicas de persuasão humana **dobraram** a taxa de compliance de LLMs (33% → 72%).

**Aviso importante:** compliance = obediência à instrução, **não** qualidade ou veracidade da resposta. Um prompt mais "obedecido" não é automaticamente um prompt melhor. Por isso o escopo aqui é estreito: disciplina de formato e processo (seguir checklist, anunciar skill, não pular verificação) — não "melhorar respostas" em geral.

Os 7 princípios com exemplos ✅/❌ prontos: **Authority** ("YOU MUST, no exceptions"), **Commitment** (exigir anúncio/escolha explícita), **Scarcity** ("IMMEDIATELY before proceeding"), **Social Proof** ("X without Y = failure. Every time."), **Unity** ("we're colleagues"), mais Reciprocity e Liking (documentados como **evitar** — geram sycophancy).

Inclui tabela de qual combinação usar por tipo de prompt (disciplina/guidance/colaborativo/referência) e teste ético: "a técnica serviria o interesse genuíno do usuário se ele a entendesse por completo?".

**Proibições duras (escopo travado):** o alvo da persuasão é **o modelo em prompts/skills próprios, nunca pessoas**. A skill recusa aplicação em phishing/social engineering, dark patterns de UX/copy, chatbots persuadindo usuários finais e bypass de guardrails — pedido nessas categorias não é gerado.

## Regras fixas

Invioláveis, independente do pedido:

1. **Nunca gera prompt sem confirmar a ferramenta-alvo** — prompt genérico é prompt ruim.
2. **Nunca adiciona CoT em modelo reasoning-native** (o3, o4-mini, DeepSeek-R1, Qwen3 thinking) — eles já pensam internamente; CoT explícito degrada a saída.
3. **Máximo 3 perguntas de esclarecimento** antes de gerar.
4. **Framework pesado só com pedido explícito** — Mixture of Experts, Tree/Graph of Thoughts, Self-Consistency e chaining em camadas têm risco de fabricação maior em prompt único.
5. **Sem nome de framework no output final** — você recebe o prompt, não a aula.
6. **Stop conditions obrigatórias em prompts pra agentes autônomos** — loop sem parada é a maior causa de queima de créditos.

## Customizar e estender

- **Nova ferramenta:** adicione uma seção em `references/tool-routing.md` seguindo o padrão existente (nome em negrito, bullets curtos com regras específicas do modelo/versão).
- **Novo template:** adicione em `references/templates.md` com letra nova + linha na tabela de índice.
- **Nova técnica (modo passivo):** adicione na categoria certa da lista em `SKILL.md`.
- **Regra pessoal fixa:** edite a seção "Modo gerador" do `SKILL.md`.

Mantenha o `SKILL.md` enxuto — detalhe pesado vai pra `references/`, senão você perde o benefício de contexto.

## Limitações conhecidas

Documentadas de propósito — melhor você saber antes de instalar:

1. **Sem benchmarks automatizados.** Não há evals automáticos nem A/B tests cegos dos prompts gerados. As regras vêm de documentação oficial dos vendors e prática da comunidade. O que existe: [`evals/protocol.md`](evals/protocol.md) — protocolo manual de A/B (seu prompt vs. prompt da skill, métrica = re-prompts até funcionar) com log de resultados. Barato, honesto, sem fingir ciência.
2. **Regras de routing envelhecem.** Modelos novos saem toda semana. `tool-routing.md` carrega uma data **"Last verified"**; se a ferramenta/modelo for mais novo que a data ou não estiver listado, a skill aplica regras genéricas e avisa em vez de chutar comportamento de versão. PRs de atualização são bem-vindos.
3. **Nativa do Claude Code.** O carregamento sob demanda depende de `~/.claude/skills/`. Uso parcial em outros agentes é possível — ver [Uso fora do Claude Code](#uso-fora-do-claude-code).
4. **Agregação, não invenção.** O valor está na curadoria, fusão e arquitetura de contexto — as fontes estão todas nos [Créditos](#créditos). Se você prefere as fontes originais separadas, use-as.
5. **Ativação depende de pedido explícito** no modo gerador. É decisão de design (evita a skill sequestrar tarefas normais), com o custo de pedidos vagos não dispararem. Reformule com "escreve/melhora um prompt pra...".
6. **Escopo amplo tem custo.** Cobrir texto/imagem/vídeo/3D/agentes significa que nenhuma seção é tão profunda quanto uma skill dedicada a uma ferramenta só. Se 90% do seu uso é uma ferramenta única, uma skill especializada nela pode servir melhor.
7. **Não instale junto com outra skill de prompt engineering.** Duas skills com trigger parecido = Claude pode ativar a errada ou misturar as duas. Uma por vez.

## Troubleshooting / FAQ

**A skill não ativa quando peço um prompt.**
O pedido precisa ser explícito: "escreve/melhora/adapta/cria um prompt pra X". Pedidos implícitos ("me ajuda com o Midjourney") podem não disparar o modo gerador — reformule.

**A skill ativa demais / interfere em tarefas normais.**
Não deveria: o modo gerador só dispara com pedido explícito de prompt, e o modo passivo só rotula quando a técnica influenciou de fato a abordagem (tarefa trivial não ganha rótulo). Se ainda incomodar, remova a linha da categoria em `SKILL.md`.

**Claude não leu as regras da minha ferramenta.**
Confirme que `references/tool-routing.md` existe e que o link relativo em `SKILL.md` bate com o nome do arquivo. Se a ferramenta não tem seção, adicione uma (ver [Customizar](#customizar-e-estender)).

**Pedi prompt pro o3 e veio com "think step by step".**
Bug — não deveria acontecer (regra fixa nº 2). Confira se seu `SKILL.md` está atualizado (`git pull`).

**Funciona no claude.ai web ou só no Claude Code?**
Skill de Claude Code (depende da pasta `~/.claude/skills/`). No claude.ai web, você pode colar o conteúdo do `SKILL.md` como instrução de projeto, mas perde o carregamento sob demanda das references.

**Preciso reiniciar depois de editar os arquivos?**
Sessão nova do Claude Code garante recarga do `SKILL.md`. As references são lidas do disco na hora do uso, então edições nelas valem imediatamente.

## Uso fora do Claude Code

A skill é markdown puro — funciona parcialmente em qualquer agente que leia arquivos de regras:

- **Cursor**: copie `SKILL.md` pra `.cursor/rules/prompt-techniques.mdc` (ou cole em Rules). Os links relativos de `references/` funcionam se você copiar a pasta pro repo e o agente puder ler arquivos.
- **Cline / Windsurf / Codex CLI**: cole o `SKILL.md` no arquivo de regras do agente (`.clinerules`, `AGENTS.md`, etc.) e mantenha `references/` no repo — agentes com acesso a arquivo conseguem seguir os links sob demanda.
- **claude.ai web / ChatGPT**: cole o `SKILL.md` como instrução de projeto. Sem filesystem, os links de `references/` morrem — cole junto só a seção da ferramenta que você usa (ex: só o bloco Midjourney do `tool-routing.md`).

O que se perde fora do Claude Code: descoberta automática da skill e garantia do carregamento sob demanda. O conteúdo em si é portátil.

## Desinstalar

```bash
rm -rf ~/.claude/skills/prompt-techniques
```

Sem resíduo — a skill não toca em nenhum outro arquivo.

## Créditos

- **Modo gerador** baseado em [nidhinjs/prompt-master](https://github.com/nidhinjs/prompt-master) (tool routing, templates A–M, patterns, intent extraction).
- **Fórmula de 7 componentes para imagem + modos de expertise** inspirados em [Hainrixz/claude-banana](https://github.com/Hainrixz/claude-banana) e [AgriciDaniel/banana-claude](https://github.com/AgriciDaniel/banana-claude).
- **Princípios de persuasão** de [NeoLabHQ/context-engineering-kit](https://github.com/NeoLabHQ/context-engineering-kit) (skill prompt-engineering), fundamentados em Meincke et al. (2025).
- **Modo referência** (taxonomia de 14 categorias de técnicas) é lista própria.

Licenças das fontes upstream aplicam-se ao conteúdo derivado delas.
