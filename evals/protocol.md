# Protocolo de avaliação manual

Sem infra de eval automatizado — avaliação aqui é manual, barata e honesta. Serve p/ duas coisas: comparar prompt gerado vs. seu prompt manual, e medir se a skill reduz retrabalho.

## Métrica principal

**Re-prompts até resultado aceitável.** Binária por tentativa: funcionou na 1ª colada (0 re-prompts) ou não. Menos re-prompts = prompt melhor. Não use "achei melhor" — conte tentativas.

## Protocolo A/B (1 tarefa, ~5 min)

1. Escreva seu prompt manual pra tarefa (versão A). Não mostre pra skill.
2. Peça à skill o prompt pra mesma tarefa (versão B).
3. Rode A e B na ferramenta-alvo, mesma sessão limpa cada.
4. Registre no log abaixo: re-prompts de cada, qual output você usaria.
5. Empate ou A ganhou → registre também. Resultado negativo é dado, não falha do protocolo.

## Log de resultados

Adicione 1 linha por teste em `evals/results.md` (crie se não existir):

```
| data | ferramenta | tarefa (curta) | re-prompts A (manual) | re-prompts B (skill) | vencedor | nota |
```

## O que o log responde com o tempo

- Skill ganha em qual categoria de ferramenta e perde em qual
- Quais seções de tool-routing.md estão desatualizadas (B perde consistente numa ferramenta → revisar seção)
- Se o fast path gera prompt pior que o caminho completo

## O que isso NÃO é

Não é benchmark científico: N pequeno, avaliador é você, sem cegamento. É trilha de evidência pessoal — suficiente pra decidir se a skill paga o próprio custo no SEU uso.
