# Persuasion Principles for Prompt Compliance

Fonte: NeoLabHQ/context-engineering-kit (baseado em Meincke et al. 2025 — 7 princípios testados em N=28.000 conversas; persuasão dobrou compliance: 33% → 72%, p < .001). Uso: aumentar compliance de instrução/formato em prompts e skills. Nunca p/ contornar segurança.

## Os 7 princípios

### 1. Authority
Deferência a expertise/regra oficial. Linguagem imperativa: "YOU MUST", "Never", "Always", "No exceptions". Elimina fadiga de decisão e racionalização.
Usar: skills de disciplina (TDD, verificação), práticas safety-critical.
```
✅ Write code before test? Delete it. Start over. No exceptions.
❌ Consider writing tests first when feasible.
```

### 2. Commitment
Consistência com declaração prévia. Exigir anúncio ("Announce skill usage"), escolha explícita ("Choose A, B, or C"), tracking (TodoWrite p/ checklist).
Usar: garantir que skill é seguida, processos multi-etapa, accountability.
```
✅ When you find a skill, you MUST announce: "I'm using [Skill Name]"
❌ Consider letting your partner know which skill you're using.
```

### 3. Scarcity
Urgência por limite temporal/sequencial: "Before proceeding", "Immediately after X". Previne "faço depois".
Usar: verificação imediata, workflow sensível a ordem.
```
✅ After completing a task, IMMEDIATELY request code review before proceeding.
❌ You can review code when convenient.
```

### 4. Social Proof
Norma universal: "Every time", "Always", modo de falha explícito ("X without Y = failure").
Usar: documentar prática universal, avisar falha comum.
```
✅ Checklists without TodoWrite tracking = steps get skipped. Every time.
❌ Some people find TodoWrite helpful for checklists.
```

### 5. Unity
Identidade compartilhada: "our codebase", "we're colleagues", "we both want quality".
Usar: workflow colaborativo, cultura de feedback honesto.
```
✅ We're colleagues working together. I need your honest technical judgment.
❌ You should probably tell me if I'm wrong.
```

### 6. Reciprocity
Obrigação de retribuir. **Usar raramente** — soa manipulativo, outros princípios funcionam melhor.

### 7. Liking
Preferência por quem gostamos. **NÃO usar p/ compliance** — cria sycophancy, conflita com feedback honesto.

## Combinação por tipo de prompt

| Tipo de prompt | Usar | Evitar |
|---|---|---|
| Disciplina (regras duras) | Authority + Commitment + Social Proof | Liking, Reciprocity |
| Guidance/técnica | Authority moderado + Unity | Authority pesado |
| Colaborativo | Unity + Commitment | Authority, Liking |
| Referência pura | Só clareza | Toda persuasão |

Não combinar todos os 7 num prompt.

## Por que funciona

Bright-line rules reduzem racionalização: "YOU MUST" remove fadiga de decisão; linguagem absoluta elimina "isso é exceção?"; contra-racionalização explícita fecha brecha específica.

## Teste ético

"Essa técnica serviria o interesse genuíno do usuário se ele a entendesse por completo?" Sim → legítimo (disciplina, prevenir falha previsível). Não → manipulação (falsa urgência, culpa, ganho próprio).

## Proibições duras (escopo travado)

Esses princípios são p/ **disciplinar o comportamento de um LLM em prompts/skills próprios** — o alvo da persuasão é o modelo, nunca pessoas. Recusar aplicação em:
- Phishing, social engineering ou qualquer conteúdo dirigido a enganar humanos
- Dark patterns em UX/copy (falsa escassez, urgência fabricada, culpa)
- Chatbots de suporte/vendas persuadindo usuários finais
- Contornar guardrails/segurança de qualquer modelo

Pedido nessas categorias → não gerar, explicar o porquê.
