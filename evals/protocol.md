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

Status em 2026-10-13: nenhum teste registrado. A rodada A/B exige chamadas aos modelos e um avaliador humano. O responsável excluiu testes com o Gemini nesta rodada, então ela não foi executada.

## O que o log responde com o tempo

- Skill ganha em qual categoria de ferramenta e perde em qual
- Quais seções de tool-routing.md estão desatualizadas (B perde consistente numa ferramenta → revisar seção)
- Se o fast path gera prompt pior que o caminho completo

## O que isso NÃO é

Não é benchmark científico: N pequeno, avaliador é você, sem cegamento. É trilha de evidência pessoal — suficiente pra decidir se a skill paga o próprio custo no SEU uso.

## Testes automatizados (o que existe)

`evals/golden_cases.json` tem 31 prompts fixos, cada um com o resultado esperado do validador (`scripts/validate_prompt.py`). Eles testam o validador: se uma regra mudar sem querer, um caso quebra. Não medem se a ferramenta-alvo responde bem; isso continua sendo o A/B manual acima. Rode com `python3 -m unittest discover -s tests -v`. Também existem `tests/test_image_catalog.py` (confere a consistência interna do catálogo de modelos de imagem: IDs, preços, proporções e tamanhos, e entre o JSON e o Markdown) e `tests/test_check_repo.py` (testa os contratos de `scripts/check_repo.py`). Nenhum desses testes chama a API: eles conferem consistência interna, não se o modelo ainda aceita o valor.

## Avaliação de imagens (casos fixos)

`evals/image_cases.json` tem 8 pedidos fixos para o Nano Banana: 6 de geração e 2 de edição. Cada caso lista os critérios que uma pessoa avalia: fidelidade, composição, texto, identidade, preservação e restrições. Um caso é um pedido, não um resultado. Cada execução paga precisa da sua própria aprovação, e nada nesse arquivo chama a API.

- Rodar: `python3 -m studio plan --case ID`. Caso de edição: `plan --case ID --from RUN_ID`. Depois, o fluxo de aprovação de [`studio/README.md`](../studio/README.md).
- Avaliar: `rate RUN --rating N --criterion NOME=N`, com nota de 1 a 5 por critério. Vale a nota mais recente.
- Comparar: `compare ID` agrupa as execuções por variante (modelo, proporção, tamanho, nível de pensamento, geração ou edição) e mostra contagens e médias. Não aponta vencedor.
- O que as checagens automáticas medem: formato, largura, altura, bytes, proporção dentro de 2 % (tolerância local). Não medem fidelidade, legibilidade do texto nem identidade. Essas são julgamentos de uma pessoa.
- Não tire conclusão de superioridade com `n` pequeno. Uma diferença de médias com uma ou duas execuções por variante não é evidência.
- Execuções com o provedor fake são excluídas da comparação.

Limite desta rodada: nenhum caso foi executado na API, porque a chave não estava configurada. Os testes cobrem o caminho com transporte simulado.

## Toda claim carrega sua limitação junto, não separada

Se um resultado do log virar afirmação em README/SKILL.md ("a skill reduz re-prompts em X%"),
a limitação anda junto na mesma frase, não num rodapé genérico. Formato: **claim + condição em
que ela vale + o que ela não prova**. Ex: "3 de 3 testes com Midjourney tiveram 0 re-prompts
via skill vs. 1-2 manual — N=3, mesmo avaliador sem cegamento, não prova generalização pra
outras ferramentas." Uma claim sem essas duas cláusulas anexadas não entra em doc público —
fica só no log.
