# prompt-engineering-master

**Skill de Claude Code: referência de prompt engineering + gerador de prompts otimizados por ferramenta-alvo.**

Você pede "escreve um prompt pra Midjourney gerar um gato samurai" e recebe um prompt pronto pra colar, com a sintaxe e as regras específicas do Midjourney. Ou trabalha normalmente e o Claude aplica (e nomeia na resposta) a técnica de prompt engineering relevante.

> **Honestidade primeiro:** essa skill é uma agregação curada de fontes upstream (ver [Créditos](#créditos)) + taxonomia própria, organizada pra economizar contexto. **Não tem eval automatizado da qualidade dos prompts gerados nem A/B cego.** Tem um validador estático e testes que checam o próprio validador ([Validação e testes](#validação-e-testes)). As regras de routing vêm de docs oficiais e prática da comunidade, não de avaliação formal minha; o protocolo manual de A/B está em [`evals/protocol.md`](evals/protocol.md). Trate como framework de trabalho bem organizado, não como verdade medida. Detalhe em [Limitações](#limitações-conhecidas).

---

## Quick Start (30 segundos)

```bash
git clone https://github.com/rianprei/prompt-engineering-master ~/.claude/skills/prompt-techniques
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
- [Validação e testes](#validação-e-testes)
- [Studio (página local e linha de comando, com aprovação por execução paga)](#studio-página-local-e-linha-de-comando-com-aprovação-por-execução-paga)
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
| **Referência (passivo)** | Automático, quando a skill é carregada | Quando uma técnica influencia a abordagem, o Claude a nomeia em 1 linha **na resposta visível** (ex: "Técnica: Chain-of-Verification"). Você vê, não fica escondido no raciocínio interno. Tarefa trivial não ganha rótulo. |
| **Gerador (ativo)** | Só quando você pede explicitamente | Gera um prompt pronto pra colar, com regras específicas da ferramenta-alvo (Claude, GPT, Cursor, Midjourney, Claude Code, ElevenLabs, n8n...), e oferece loop de refinamento com o output real. |

Cobre **19 categorias de técnicas**, mais o catálogo de padrões de White et al. (2023) — com **camadas de prioridade** (nem toda técnica pesa igual): alto impacto (role, context, output format, few-shot, grounding), condicionais (CoT só em modelo não-reasoning, ReAct/RAG só com ferramentas reais) e experimentais/legadas em modelos 2025+ (ToT, GoT, Self-Consistency — só sob pedido explícito, risco de fabricação). Inspirada em [The Prompt Report](https://arxiv.org/abs/2406.06608); as regras por modelo vêm das docs oficiais dos fornecedores, com a data de verificação em `references/tool-routing.md`. Inclui **persuasão** (compliance de instrução — ver caveat na [seção própria](#princípios-de-persuasão)).

Antes de entregar qualquer prompt, a skill instrui o modelo a conferir o próprio prompt contra as regras da ferramenta-alvo e corrigir violações antes de mostrá-lo. Isso é uma instrução ao modelo, não um validador automático: o `scripts/validate_prompt.py` é uma ferramenta separada, que você roda à mão. Ferramenta que não está no routing: busca best practices na web (se disponível) e oferece o bloco pronto pra você adicionar ao `tool-routing.md`.

## Por que ela existe

Dois problemas comuns:

1. **Você não é especialista em cada ferramenta de IA.** Prompt bom pra Claude é diferente de prompt bom pra GPT-6 Astra (que degrada se você adicionar "think step by step"), que é diferente de Midjourney (descritores separados por vírgula, não prosa), que é diferente de Stable Diffusion (sintaxe de peso `(word:1.3)`, negative prompt obrigatório). Essa skill sabe as regras de cada uma.

2. **Skills de prompt engineering costumam poluir o contexto.** A maioria joga 5.000+ palavras na janela de contexto em toda sessão. Essa skill usa *progressive disclosure*: o arquivo principal é mínimo, e o detalhe pesado só é lido no momento exato em que é necessário. Detalhe na [seção de arquitetura](#arquitetura-por-que-ela-não-estoura-seu-contexto).

## Instalação

**Pré-requisito:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code) instalado.

**Via git (recomendado — permite atualizar com `git pull`):**

```bash
git clone https://github.com/rianprei/prompt-engineering-master ~/.claude/skills/prompt-techniques
```

**Sem git:**

```bash
mkdir -p ~/.claude/skills/prompt-techniques/references
base=https://raw.githubusercontent.com/rianprei/prompt-engineering-master/master
curl -fL $base/SKILL.md -o ~/.claude/skills/prompt-techniques/SKILL.md
curl -fL $base/README.md -o ~/.claude/skills/prompt-techniques/README.md
curl -fL $base/LICENSE -o ~/.claude/skills/prompt-techniques/LICENSE
curl -fL $base/NOTICE -o ~/.claude/skills/prompt-techniques/NOTICE
for f in tool-routing patterns templates persuasion taxonomy technique-catalog defenses image-styles gemini-image-models gemini-image-examples; do
  curl -fL $base/references/$f.md -o ~/.claude/skills/prompt-techniques/references/$f.md
done
```

Sem git, a instalação traz o skill, a licença e o NOTICE: `SKILL.md`, `README.md`, `LICENSE`, `NOTICE` e os 10 arquivos `.md` de `references/`. Ficam de fora `scripts/`, `studio/`, `tests/`, `evals/` e `references/gemini-image-models.json`, que só os scripts, o Studio e os testes usam; para eles, use a instalação via git.

**Verificar:**

```bash
ls ~/.claude/skills/prompt-techniques/ ~/.claude/skills/prompt-techniques/references/
# Esperado: SKILL.md, README.md, LICENSE, NOTICE e references/ com 10 arquivos .md
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
6. **Oferece refinamento:** você testa o prompt na ferramenta e cola o output de volta; o Claude diagnostica a falha via `references/patterns.md` (6 eixos: task/context/format/scope/reasoning/agentic) e ajusta só a dimensão que falhou. Gerar → testar → refinar, não gerar-e-tchau.

**Formato da resposta:** 1 bloco de prompt copiável + `🎯 Target: <ferramenta>` + 1 frase explicando o que foi otimizado + oferta de refinamento. Fluxo completo (não fast-path) também mostra `Score: N/6 eixos` (mesmos 6 do refinamento) — autoavaliação que mostra quais eixos o prompt cobre, não uma medição.

**Esclarecimento (pra não parecer contradição):** "sem nome de framework" vale pro **texto do prompt gerado** — o que você cola no Midjourney não vem rotulado "CO-STAR". A frase de otimização e o modo passivo podem nomear técnica normalmente; são canais diferentes.

## Exemplos práticos

**Imagem:**
> "escreve um prompt pro Midjourney: cidade cyberpunk chuvosa vista de cima"

Retorna descritores separados por vírgula (não prosa), sujeito primeiro, depois estilo/mood/iluminação/composição, parâmetros `--ar 16:9 --v <atual>` no final (não fixa versão — confira a atual).

**Modelo de raciocínio:**
> "adapta esse meu prompt do Claude pro GPT-6 Astra"

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
├── scripts/
│   ├── contracts.py            # catálogo, IDs, proporções e regex compartilhados
│   ├── validate_prompt.py      # checa um prompt contra as regras do skill
│   └── check_repo.py           # checa links e âncoras locais, formatação, marcadores de pendência, numeração e contratos de modelo e chave; avisa se o catálogo tem mais de 90 dias
├── studio/                     # página local e CLI: brief, aprovação de uso única, revisão, avaliação (README próprio)
├── tests/                      # unittest: validador, golden cases, catálogo, contagens, contratos e studio
├── references/                 # pesados, carregados SÓ sob demanda
│   ├── tool-routing.md         # regras por ferramenta e modelo
│   ├── templates.md            # 14 templates estruturais completos
│   ├── patterns.md             # padrões que desperdiçam tokens/créditos
│   ├── taxonomy.md             # taxonomia: 288 nomes em 19 categorias + catálogo de White et al.
│   ├── technique-catalog.md    # catálogo detalhado: fonte, status, novidade e tipo de cada técnica
│   ├── persuasion.md           # 7 princípios de persuasão p/ compliance
│   ├── defenses.md             # defesas para conteúdo não confiável (conceitual)
│   ├── image-styles.md         # nomes de estilo para prompts de imagem
│   ├── gemini-image-models.md  # IDs, aliases, status, tamanhos, proporções por modelo, limites e preços (2026-10-13)
│   ├── gemini-image-examples.md # briefs prontos do Nano Banana (pt-BR e EN), validados pelo teste
│   └── gemini-image-models.json # mesmos dados em JSON, lidos pelos testes e pelo studio
├── evals/
│   ├── protocol.md             # protocolo manual de A/B + log de re-prompts
│   └── golden_cases.json       # 31 casos fixos para o validador
└── .githooks/
    └── pre-commit              # opcional: checador + testes antes do commit
```

`SKILL.md` contém só a camada de prioridade (modo passivo) e as regras do gerador (modo ativo), com **links** para os arquivos de `references/` — a taxonomia completa (288 nomes em 19 categorias, mais o catálogo de White et al.) mora em `references/taxonomy.md`, e a fonte e o status de cada entrada estão em `references/technique-catalog.md`. O Claude lê `tool-routing.md` ou `taxonomy.md` só quando precisa (pedido de prompt, ou técnica fora da camada de prioridade). Isso é *progressive disclosure*: você não paga tokens por conhecimento que não está usando naquele momento.

Comparação: skills que carregam tudo no início custam milhares de tokens por sessão e causam o efeito "lost in the middle" (modelo ignora regras porque o contexto saturou). Aqui o custo fixo por sessão é só o SKILL.md.

## Ferramentas cobertas

Regras específicas em `references/tool-routing.md`:

| Categoria | Ferramentas |
|---|---|
| LLMs de texto | Claude (família 5.x), ChatGPT/GPT-6 (Astra, Sol, Luna), Grok 4.7, Gemini 4 Argon e 3.8 Flash, Qwen 3.8, Llama 4, Mistral Large 4, DeepSeek V4, MiniMax M3 |
| Reasoning-native | GPT-6 Astra e GPT-6.1 Sol, DeepSeek V4 (thinking por padrão), Claude 5.x com thinking ligado (regra: NUNCA adicionar CoT) |
| Local | Ollama (pergunta qual modelo antes de gerar) |
| Agentes de código | Claude Code, Codex CLI, Cursor, Windsurf, Cline, GitHub Copilot, Devin, SWE-agent, Antigravity |
| Geradores full-stack | Bolt, v0, Lovable, Figma Make, Google Stitch |
| Pesquisa/orquestração | Perplexity, Manus AI |
| Browser/computer-use | Comet, Atlas, Claude in Chrome |
| Imagem | Midjourney V8.2, GPT Image 2.5 (gpt-image-2.5-sunburst, gpt-image-2.5-flare), Stable Diffusion 3.5, Seedream 5.0 Pro, Nano Banana / Gemini Image (2.1, 2 Lite, Pro; 2 descontinuado em 2026-10-06), FLUX 3, Ideogram 4.5 (e 4.0), ComfyUI |
| Vídeo | Sora 2, Runway Gen-4.5, Kling 4.0, LTX-2.5, Ray3.2 (Dream Machine), Seedance 2.5 |
| Voz | ElevenLabs |
| Música | Suno |
| 3D | Meshy, Tripo, Rodin, Unity AI, Blender AI |
| Workflow | Zapier, Make, n8n |

Ferramenta fora da lista: o Claude aplica regras genéricas (instrução explícita, contrato de saída, format lock) ou pergunta.

## Templates incluídos

`references/templates.md` — 14 templates, cada um com exemplo preenchido:

| Template | Melhor pra |
|---|---|
| A — RTF (Role, Task, Format) | tarefa simples one-shot |
| B — CO-STAR | documento profissional, escrita de negócio |
| C — RISEN | projeto complexo multi-etapa |
| D — CRISPE | trabalho criativo, brand voice |
| E — Auditable Reasoning | lógica, matemática, debug (pede conclusão, premissas, evidências e checagens; CoT manual só em modelo sem thinking) |
| F — Few-Shot | formato mais fácil de mostrar que descrever |
| G — File-Scope | Cursor/Windsurf/Copilot — edição de código |
| H — ReAct + Stop Conditions | Claude Code/Devin — agentes autônomos |
| I — Visual Descriptor | Midjourney/GPT Image/SD/Sora (campos de descrição visual + 9 modos de expertise) |
| J — Reference Image Editing | editar imagem existente (só descreve o delta, com cláusula de preservação); também combina referências com papel nomeado |
| K — ComfyUI | workflow nodal (positive + negative separados) |
| L — Prompt Decompiler | quebrar/adaptar/dividir prompt existente |
| M — Claude Task Brief | tarefa complexa/agentic em modelos Claude atuais |
| N — Nano Banana Brief | imagem nova no Nano Banana / Gemini Image, com referências nomeadas (opcional) |

## Princípios de persuasão

`references/persuasion.md` — baseado em Meincke et al., "Call Me A Jerk" (SSRN 5357179, 2025; título e autores conferidos no Crossref em 2026-10-13). A descrição de terceiros (NeoLabHQ) dá **33,3% para 72,0%** no **GPT-4o mini**, com N=28.000; esses números não foram conferidos no preprint: o SSRN bloqueou a página (desafio do Cloudflare) em 2026-10-12 e 2026-10-13, o Crossref não tem resumo, e o arXiv e o Semantic Scholar não têm o artigo. A versão revisada por pares do mesmo grupo (PNAS, 2026, DOI 10.1073/pnas.2535868123) testou GPT-5 mini, Claude Haiku 4.5 e Gemini 3 Flash: a compliance foi de 35,3% para 51,3% em 126.000 conversas, segundo o resumo lido. Mede compliance com a instrução, não qualidade da resposta.

**Aviso importante:** compliance = obediência à instrução, **não** qualidade ou veracidade da resposta. Um prompt mais "obedecido" não é automaticamente um prompt melhor. Por isso o escopo aqui é estreito: disciplina de formato e processo (seguir checklist, anunciar skill, não pular verificação) — não "melhorar respostas" em geral.

Os 7 princípios com exemplos ✅/❌ prontos: **Authority** (linguagem firme, sem CAPS), **Commitment** (exigir anúncio/escolha explícita), **Scarcity** (prazo explícito, sem CAPS), **Social Proof** ("X sem Y = falha"), **Unity** ("we're colleagues"), mais Reciprocity e Liking (documentados como **evitar** — geram sycophancy).

Inclui tabela de qual combinação usar por tipo de prompt (disciplina/guidance/colaborativo/referência) e teste ético: "a técnica serviria o interesse genuíno do usuário se ele a entendesse por completo?".

**Proibições duras (escopo travado):** o alvo da persuasão é **o modelo em prompts/skills próprios, nunca pessoas**. A skill recusa aplicação em phishing/social engineering, dark patterns de UX/copy, chatbots persuadindo usuários finais e bypass de guardrails — pedido nessas categorias não é gerado.

## Regras fixas

Regras do gerador, válidas em todo pedido. São instruções ao modelo. O validador só as verifica, por heurística textual, nas regras 2 e 6 (`check_cot` e `check_agent_stop`); as demais não têm verificação automática:

1. **Nunca gera prompt sem confirmar a ferramenta-alvo** — prompt genérico é prompt ruim.
2. **Nunca adiciona CoT em modelo reasoning-native** (GPT-6 Astra e GPT-6.1 Sol, DeepSeek V4, Claude 5.x com thinking) — eles já pensam internamente; CoT explícito degrada a saída.
3. **Máximo 3 perguntas de esclarecimento** antes de gerar.
4. **Framework pesado só com pedido explícito** — Mixture of Experts, Tree/Graph of Thoughts, Self-Consistency e chaining em camadas têm risco de fabricação maior em prompt único.
5. **Sem nome de framework no output final** — você recebe o prompt, não a aula.
6. **Stop conditions obrigatórias em prompts pra agentes autônomos** — loop sem parada é a maior causa de queima de créditos.

## Customizar e estender

- **Nova ferramenta:** adicione uma seção em `references/tool-routing.md` seguindo o padrão existente (nome em negrito, bullets curtos com regras específicas do modelo/versão).
- **Novo template:** adicione em `references/templates.md` com letra nova + linha na tabela de índice.
- **Nova regra de validação:** adicione a checagem em `scripts/validate_prompt.py`, um caso em `evals/golden_cases.json` e rode `python3 -m unittest discover -s tests`.
- **Nova técnica (modo passivo):** alto impacto → camada de Prioridade em `SKILL.md`; senão, categoria certa em `references/taxonomy.md`. Com fonte verificada, uma linha em `references/technique-catalog.md`.
- **Regra pessoal fixa:** edite a seção "Modo gerador" do `SKILL.md`.
- **Idioma:** `SKILL.md` e `references/` são lidos pelo modelo e ficam em inglês; `README.md` e `evals/` são para você e ficam em português.

Mantenha o `SKILL.md` enxuto — detalhe pesado vai pra `references/`, senão você perde o benefício de contexto.

## Validação e testes

Tudo em biblioteca padrão do Python, sem pacotes externos. Os scripts vêm do clone via git (a instalação sem git não traz `scripts/`):

```bash
# Checa um prompt contra as regras do skill: CoT em modelo reasoning-native,
# bloco de pensamento em Claude 5.x, prefill, CAPS empilhados, formato ausente,
# agente sem condição de parada, linguagem vaga, chave em URL, modelo de preview ou desligado
# e, para imagem, proporção que o modelo não aceita, alias de Nano Banana resolvido para o ID, texto sem aspas e lista longa de negações.
python3 scripts/validate_prompt.py --target gpt-6-astra prompt.txt

# Checa links e âncoras locais, formatação, marcadores de pendência, numeração de padrões e templates, IDs de modelo contra o catálogo e chave fora da URL, e avisa se o catálogo tiver mais de 90 dias. URLs externas não são checadas.
python3 scripts/check_repo.py

# Roda os testes: validador, 31 golden cases, catálogo de imagem (com concordância Markdown/JSON), exemplos do Nano Banana, contagens, contratos, checagem do repositório e studio.
python3 -m unittest discover -s tests -v
```

- **O que o validador não faz:** não julga se a resposta do modelo é boa. Ele lê só o texto do prompt. A qualidade continua no A/B manual de [`evals/protocol.md`](evals/protocol.md).
- **Golden cases** (`evals/golden_cases.json`): 31 prompts fixos, cada um com o resultado esperado do validador. Eles testam o validador, não as respostas dos modelos. Se um caso quebrar, ou a regra mudou de propósito (atualize o caso) ou houve regressão.
- **Catálogo de imagem e contratos** (`references/gemini-image-models.json`): IDs, status, tamanhos, proporções e preços do Nano Banana, com data de verificação (2026-10-13). Os testes conferem que IDs, preços e proporções do JSON aparecem no Markdown, que proporções, tamanhos e níveis de pensamento são os valores listados na documentação lida em 2026-10-13 (cada modelo tem a sua lista de proporções; os aliases resolvem para um só ID), e que a data de verificação é a mesma nos dois arquivos. O `check_repo.py` bloqueia ID de modelo fora do catálogo, ID desligado fora dele e chave em query string. Os testes não chamam a API: se o modelo ainda aceita um valor, só uma chamada real confirma.
- **Limites conhecidos:** a maioria dos sinais é em inglês, com algumas formas em português (passo a passo, não, sem, formato, lista). Em prompts em português, as checagens de agente, CAPS e linguagem vaga não disparam, então a ausência de aviso não prova que o prompt está certo. A detecção de negação conta as negações antes da frase, dentro da mesma cláusula, e uma negação anula outra: "Não pule a checagem passo a passo" pede raciocínio e é marcado em modelo reasoning-native. Uma negação depois da frase não é lida.
- **Hook opcional:** `git config core.hooksPath .githooks` (uma vez por clone) faz o `check_repo.py` e os testes rodarem antes de cada commit. Não é ativado sozinho.

## Studio (página local e linha de comando, com aprovação por execução paga)

Gera imagens com Nano Banana por uma página local ou pela linha de comando, que o Claude Code usa. Monta o brief, mostra o plano e o custo nominal, e só chama a API paga depois que você aprova aquele brief exato. A aprovação é de uso único, vale 30 minutos e é gasta antes da chamada. Você confirma digitando os 8 primeiros caracteres do hash do plano. A CLI não consegue verificar quem digitou, por isso a regra de pedir sua confirmação está no `SKILL.md`. Detalhes e limites estão em [`studio/README.md`](studio/README.md).

```bash
python3 -m studio serve --fake-provider      # página com imagens de teste, sem rede e sem custo
GEMINI_API_KEY=... python3 -m studio serve   # página com a API real; a chave é lida em cada execução
python3 -m studio cases                      # casos fixos; não gasta nada
python3 -m studio plan --prompt "..." --model gemini-nano-banana-2.1 --aspect-ratio 1:1 --size 1K
python3 -m studio approve <hash> --confirm <8 primeiros caracteres>   # só depois que você aprovar
python3 -m studio run <hash> --approval <approval_id>                 # gasta essa aprovação
```

A edição de uma imagem gerada usa `plan --from <run_id> --edit "o que mudar"`: o resto é mantido, e a imagem anterior entra como referência. Cada execução paga tem a sua própria aprovação.

- Escuta só em 127.0.0.1. O token por processo protege contra outros sites: eles não leem a página que o contém nem enviam o cabeçalho sem CORS. Não protege contra processos locais: a página com o token é servida em `GET /`, então qualquer processo ou usuário que alcance 127.0.0.1 pode emitir aprovações e usar a API paga com a sua chave. Use o Studio em máquina de usuário único. A chave nunca vai para a página nem para uma URL.
- Precisa de locks POSIX (`fcntl`): em Windows o store recusa operar. Plataforma e catálogo: [`studio/README.md`](studio/README.md).
- Estado: edição a partir de uma imagem gerada, avaliação por critérios, casos fixos e comparação por variante estão implementados e cobertos por testes com transporte simulado. Nenhuma chamada real à API foi feita, porque a chave não estava configurada. O formato da resposta segue a referência da API (`steps`, com blocos `image`; lida em 2026-10-13). Só uma chamada real confirma que o serviço devolve esse formato para pedidos de imagem e que a edição encadeada (`--chain`) se comporta como o exemplo oficial.

## Limitações conhecidas

Documentadas de propósito — melhor você saber antes de instalar:

1. **Sem benchmarks automatizados da qualidade.** Não há evals automáticos nem A/B tests cegos dos prompts gerados. O validador e os golden cases testam só as regras do próprio skill ([Validação e testes](#validação-e-testes)). As regras vêm de documentação oficial dos vendors e prática da comunidade. O que existe: [`evals/protocol.md`](evals/protocol.md) — protocolo manual de A/B (seu prompt vs. prompt da skill, métrica = re-prompts até funcionar) com log de resultados, ainda sem nenhum registro. Barato, honesto, sem fingir ciência.
2. **Regras de routing envelhecem.** Modelos novos saem toda semana. `tool-routing.md` carrega uma data **"Last verified"**; se a ferramenta/modelo for mais novo que a data ou não estiver listado, a skill aplica regras genéricas e avisa em vez de chutar comportamento de versão. PRs de atualização são bem-vindos.
3. **Nativa do Claude Code.** O carregamento sob demanda depende de `~/.claude/skills/`. Uso parcial em outros agentes é possível — ver [Uso fora do Claude Code](#uso-fora-do-claude-code).
4. **Agregação, não invenção.** O valor está na curadoria, fusão e arquitetura de contexto — as fontes estão todas nos [Créditos](#créditos). Se você prefere as fontes originais separadas, use-as.
5. **Ativação depende de pedido explícito** no modo gerador. É decisão de design (evita a skill sequestrar tarefas normais), com o custo de pedidos vagos não dispararem. Reformule com "escreve/melhora um prompt pra...".
6. **Escopo amplo tem custo.** Cobrir texto/imagem/vídeo/3D/agentes significa que nenhuma seção é tão profunda quanto uma skill dedicada a uma ferramenta só. Se 90% do seu uso é uma ferramenta única, uma skill especializada nela pode servir melhor.
7. **Não instale junto com outra skill de prompt engineering.** Duas skills com trigger parecido = Claude pode ativar a errada ou misturar as duas. Uma por vez.

## Troubleshooting / FAQ

**A skill não ativa quando peço um prompt.**
O pedido precisa ser explícito: "escreve/melhora/adapta/cria um prompt pra X". Formas naturais como "como peço ao Midjourney X?" disparam; pedidos vagos ("me ajuda com o Midjourney") podem não disparar. Reformule.

**A skill ativa demais / interfere em tarefas normais.**
Não deveria: o modo gerador só dispara com pedido explícito de prompt, e o modo passivo só rotula quando a técnica influenciou de fato a abordagem (tarefa trivial não ganha rótulo). Se ainda incomodar, remova a linha da categoria em `SKILL.md`.

**Claude não leu as regras da minha ferramenta.**
Confirme que `references/tool-routing.md` existe e que o link relativo em `SKILL.md` bate com o nome do arquivo. Se a ferramenta não tem seção, adicione uma (ver [Customizar](#customizar-e-estender)).

**Pedi prompt pro GPT-6 Astra e veio com "think step by step".**
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

O Studio guarda, fora da pasta da skill, em `~/.local/share/prompt-techniques-studio/` (ou em `$XDG_DATA_HOME/prompt-techniques-studio/`), os briefs, as imagens de referência, as imagens geradas, o histórico das execuções e as aprovações.

**Antes de desinstalar, copie esse diretório se quiser manter as imagens geradas.** O comando abaixo apaga só a skill; ele não apaga os dados do Studio. Para removê-los também, apague esse diretório à parte. Se você usou `--data-dir` com outro caminho, esse caminho também não é removido.

```bash
rm -rf ~/.claude/skills/prompt-techniques
```

## Créditos

- **Modo gerador** baseado em [nidhinjs/prompt-master](https://github.com/nidhinjs/prompt-master) (tool routing, templates A–N, patterns, intent extraction), licença MIT.
- **Modos de expertise de imagem** (Template I) inspirados em [Hainrixz/claude-banana](https://github.com/Hainrixz/claude-banana), que tem nove modos de domínio no seu catálogo.
- **Princípios de persuasão** de [NeoLabHQ/context-engineering-kit](https://github.com/NeoLabHQ/context-engineering-kit) (skill prompt-engineering), fundamentados em Meincke et al. (2025). Licença do upstream: GPL-3.0.
- **Modo referência** (taxonomia de técnicas) é taxonomia própria, inspirada em The Prompt Report (Schulhoff et al., 2024) e no catálogo de padrões de White et al. (2023).
- **Adições de 2026-10-12** (defesas, validador, nomes de estilo de imagem e nomes de técnicas): ideias de [Valhall-ai/prompt-injection-mitigations](https://github.com/Valhall-ai/prompt-injection-mitigations), [drxvb/apex-prompt-architect](https://github.com/drxvb/apex-prompt-architect), [Hainrixz/claude-banana](https://github.com/Hainrixz/claude-banana), [amerob/ultimate-prompt-engineering-playbook](https://github.com/amerob/ultimate-prompt-engineering-playbook), [FareedKhan-dev/prompt-engineering-cheatsheet](https://github.com/FareedKhan-dev/prompt-engineering-cheatsheet), [KalyanKS-NLP/Prompt-Engineering-Techniques-Hub](https://github.com/KalyanKS-NLP/Prompt-Engineering-Techniques-Hub), [cicero-im/prompting](https://github.com/cicero-im/prompting) e [corralm/awesome-prompting](https://github.com/corralm/awesome-prompting). Licenças e detalhes em `NOTICE`.
- **Catálogo de modelos de imagem**: fatos (IDs, datas, tamanhos, proporções e preços) da documentação oficial do Google, lida em 2026-10-13. Nenhum texto copiado. Atribuição no `NOTICE`.

Licença do projeto: GPL-3.0 (arquivo `LICENSE`). Avisos e atribuições de terceiros: arquivo `NOTICE`.
