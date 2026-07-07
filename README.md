# prompt-techniques

Claude Code skill — referência de prompt engineering + gerador ativo de prompt otimizado por ferramenta-alvo.

Fusão de 2 fontes: lista própria de técnicas (modo referência, passivo) + [prompt-master](https://github.com/nidhinjs/prompt-master) (modo gerador, ativo).

## O que é

Skill instalável em `~/.claude/skills/prompt-techniques/`. Ativa automático em 2 modos:

- **Modo referência (passivo)**: durante qualquer tarefa, Claude nomeia/aplica técnica de prompt engineering relevante no raciocínio (ex: "usando Chain-of-Verification aqui"), sem precisar ser chamada.
- **Modo gerador (ativo)**: só quando pedido explícito ("escreve/melhora/adapta prompt pra X"). Gera prompt pronto pra colar, otimizado pra ferramenta-alvo (Claude, GPT, Cursor, Midjourney, Claude Code, etc).

## Instalação

```bash
git clone https://github.com/rianprei/claude-prompt-techniques ~/.claude/skills/prompt-techniques
```

Ou manual, sem git:

```bash
mkdir -p ~/.claude/skills/prompt-techniques
curl -fL https://raw.githubusercontent.com/rianprei/claude-prompt-techniques/master/SKILL.md \
  -o ~/.claude/skills/prompt-techniques/SKILL.md
mkdir -p ~/.claude/skills/prompt-techniques/references
for f in tool-routing.md patterns.md templates.md; do
  curl -fL "https://raw.githubusercontent.com/rianprei/claude-prompt-techniques/master/references/$f" \
    -o ~/.claude/skills/prompt-techniques/references/$f
done
```

Verificar:

```bash
ls ~/.claude/skills/prompt-techniques/
# SKILL.md  references/
```

Reinicia Claude Code (ou nova sessão) — skill carrega automático, sem config extra.

## Estrutura

```
prompt-techniques/
├── SKILL.md                    # entry point — carregado sempre, mantido lean
└── references/                 # carregado sob demanda, não no init
    ├── tool-routing.md         # regra específica por Claude/GPT/Cursor/Midjourney/agente
    ├── patterns.md             # padrões que desperdiçam token/crédito
    ├── templates.md            # 13 templates estruturais prontos
    └── persuasion.md           # 7 princípios de persuasão p/ compliance (Meincke et al. 2025)
```

`SKILL.md` só referencia os arquivos de `references/` por link — Claude só lê o arquivo/seção que precisa pra tarefa atual (progressive disclosure, economiza contexto).

## Uso — modo referência (passivo)

Nada a fazer. Durante qualquer tarefa normal, se uma técnica de prompt engineering for aplicável (CoT, Self-Consistency, ReAct, RAG, etc), Claude nomeia no raciocínio. Lista completa de categorias em `SKILL.md`.

## Uso — modo gerador (ativo)

Pede explícito:

```
escreve um prompt pra Midjourney gerar [x]
melhora esse prompt pra Cursor: [prompt]
adapta esse prompt de Claude pra GPT-5
```

Fluxo interno:
1. Confirma ferramenta-alvo (pergunta se ambíguo, máx 3 perguntas)
2. Extrai 9 dimensões: task, ferramenta, formato, constraint, input, contexto, audiência, critério de sucesso, exemplo
3. Prefere técnica simples (role, few-shot, grounding) sobre framework pesado (MoE, ToT, GoT, Self-Consistency) — framework pesado só se pedido explícito
4. Nunca adiciona CoT em modelo reasoning-native (o3, o4-mini, DeepSeek-R1, Qwen3 thinking)
5. Lê `references/tool-routing.md` só a seção da ferramenta pedida
6. Lê `references/templates.md` só o template que casa com o tipo de tarefa

Output: 1 bloco de prompt copiável + `🎯 Target: <ferramenta>` + 1 frase do que foi otimizado.

## Ferramentas cobertas (tool-routing.md)

Claude (Opus 4.7/4.8), ChatGPT/GPT-5.x, o3/o4-mini, Gemini 2.x/3, Qwen 2.5 e 3 (thinking), Ollama, Llama/Mistral, DeepSeek-R1, MiniMax, Claude Code, Antigravity, Cursor/Windsurf, Cline, GitHub Copilot, Bolt/v0/Lovable/Figma Make/Google Stitch, Devin/SWE-agent, Perplexity/Manus, Computer-Use/Browser Agents, Midjourney/DALL-E 3/Stable Diffusion/SeeDream, ComfyUI, Meshy/Tripo/Rodin, Unity AI/Blender AI.

## Templates (templates.md)

| Template | Uso |
|---|---|
| A — RTF | tarefa simples one-shot |
| B — CO-STAR | documento profissional |
| C — RISEN | projeto complexo multi-etapa |
| D — CRISPE | trabalho criativo, brand voice |
| E — Chain of Thought | lógica, matemática, debug |
| F — Few-Shot | output estruturado consistente |
| G — File-Scope | Cursor/Windsurf/Copilot |
| H — ReAct + Stop Conditions | Claude Code/Devin, agentes autônomos |
| I — Visual Descriptor | Midjourney/DALL-E/SD/Sora |
| J — Reference Image Editing | edição de imagem existente |
| K — ComfyUI | workflow nodal |
| L — Prompt Decompiler | quebrar/adaptar prompt existente |
| M — Opus 4.7/4.8 Task Brief | tarefa complexa/agentic em Opus |

## Regras fixas (não mudam por pedido do usuário)

- Nunca gera prompt sem confirmar ferramenta-alvo
- Nunca adiciona CoT em modelo reasoning-native
- Nunca mostra nome de framework no output final
- Máx 3 perguntas de esclarecimento antes de gerar
- Framework pesado (MoE, ToT, GoT, Self-Consistency, chaining em camada) só com pedido explícito — risco de fabricação maior em prompt único

## Customizar/estender

- Nova ferramenta: adiciona seção em `references/tool-routing.md` seguindo padrão existente (bullets curtos, regra específica do modelo/versão)
- Novo template: adiciona em `references/templates.md`, referencia letra nova na tabela de conteúdo
- Nova técnica de referência (modo passivo): adiciona na lista de categorias em `SKILL.md`

## Troubleshooting

- **Skill não ativa em modo gerador**: pedido tem que ser explícito ("escreve prompt pra..."), não implícito. Skill não ativa em tarefa de código/doc normal, só nomeia técnica no raciocínio (modo passivo).
- **Referência não carrega**: confirma path relativo em `references/` existe e link em `SKILL.md` bate com nome do arquivo.
- **Ferramenta não reconhecida**: se não estiver em `tool-routing.md`, Claude pergunta ou aplica regra genérica (explicit, output contract, format lock). Adiciona seção nova se for ferramenta recorrente.

## Desinstalar

```bash
rm -rf ~/.claude/skills/prompt-techniques
```

## Créditos

- Modo gerador baseado em [nidhinjs/prompt-master](https://github.com/nidhinjs/prompt-master). Modo referência é lista própria, fundida na mesma skill.
- Fórmula de 7 componentes p/ imagem + modos de expertise inspirados em [Hainrixz/claude-banana](https://github.com/Hainrixz/claude-banana) / [AgriciDaniel/banana-claude](https://github.com/AgriciDaniel/banana-claude).
- Categoria Persuasão + `references/persuasion.md` baseados em [NeoLabHQ/context-engineering-kit](https://github.com/NeoLabHQ/context-engineering-kit) (skill prompt-engineering) e Meincke et al. (2025).
