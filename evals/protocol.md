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

## Toda claim carrega sua limitação junto, não separada

Se um resultado do log virar afirmação em README/SKILL.md ("a skill reduz re-prompts em X%"),
a limitação anda junto na mesma frase, não num rodapé genérico. Formato: **claim + condição em
que ela vale + o que ela não prova**. Ex: "3 de 3 testes com Midjourney tiveram 0 re-prompts
via skill vs. 1-2 manual — N=3, mesmo avaliador sem cegamento, não prova generalização pra
outras ferramentas." Uma claim sem essas duas cláusulas anexadas não entra em doc público —
fica só no log.
