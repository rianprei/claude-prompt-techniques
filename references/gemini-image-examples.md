# Nano Banana briefs: copyable examples

Read this file with the Nano Banana profile in [tool-routing.md](tool-routing.md) and the model facts in [gemini-image-models.md](gemini-image-models.md). Each example gives the user's request, the request fields, and a prompt to paste. The prompts follow the profile's rules. A test runs the validator on every prompt below and checks that each aspect ratio is one the named model accepts.

Languages: the user requests are in Brazilian Portuguese. The pasted prompts are in Portuguese, except the multi-reference example, which is in English. Text that must appear inside the image is always in quotation marks, in the language it must appear in.

## 1. Generation from scratch

**Input:** "Faça uma imagem para o post de lançamento de uma cafeteria de bairro. Formato de Instagram em pé."

**Fields:** model `gemini-nano-banana-2.1` · aspect ratio `4:5` · size `1K`

Shows: subject and action first, a light source, the camera position, and a clear area for the title added later.

```text
Gere uma foto de uma xícara de cerâmica branca com café coado recém-servido, sobre uma mesa de madeira clara, ao lado de um pão de queijo partido ao meio. A luz da manhã entra pela janela da esquerda e cria sombras suaves. O enquadramento é de nível da mesa, com a xícara em primeiro plano e a janela desfocada ao fundo. Deixe o terço superior do quadro em tom creme, liso, para receber o título depois. Post vertical de Instagram.
```

## 2. Localized edit with preservation

**Input:** "Na foto anexada da sala, troque só o sofá azul por um sofá de couro caramelo. Não mexa em mais nada."

**Fields:** model `gemini-nano-banana-2.1` · aspect ratio `4:3` (same as the photo) · size `2K`

Shows: the reference is named as provided, the change is one element, and the preservation clause lists what stays.

```text
Usando a foto anexada da sala, troque apenas o sofá azul por um sofá de couro caramelo, de encosto reto e capitonê. Mantenha exatamente igual todo o resto da imagem: as almofadas, o tapete, a mesa de centro, a iluminação e o enquadramento.
```

## 3. Several references with roles

**Input:** "Quero uma cena de cafeteria com a personagem da imagem 1, a garrafa da imagem 2 e a paleta de cores da imagem 3."

**Fields:** model `gemini-nano-banana-2.1` · aspect ratio `4:3` · size `2K` · references: 3, in this order (character, product, palette)

Shows: each reference is numbered and given one role. The prompt is in English, as the model follows English instructions well. The text in the scene is not involved here.

```text
Create a cozy morning scene in a small city cafe. Image 1 is the character: keep her face, hair and round glasses exactly the same. Image 2 is the product: a glass bottle of cold brew with the label unchanged. Image 3 gives the palette only: use its warm terracotta and sage tones for the walls, the cushions and the menu board. She sits at the window table and holds the bottle, lit by soft sunlight from the left, medium shot at eye level.
```

## 4. A consistent character across scenes

**Input:** "Quero a mesma personagem, a Dona Lia, em três cenas: cozinhando, no mercado e dormindo no sofá."

**Fields:** model `gemini-nano-banana-2.1` · aspect ratio `16:9` · size `1K` · the first image is kept as the reference for the next turns, in the same conversation

Shows: the character gets a name and fixed attributes in the first request. The later requests repeat the name and the attributes, and state what must stay the same.

Turn 1:
```text
Uma ilustração em aquarela de Dona Lia, uma senhora de 60 anos, cabelo grisalho preso em coque baixo, óculos de armação redonda dourada e avental xadrez azul e branco. Ela está numa cozinha de casa de vila, mexendo uma panela de sopa com uma colher de pau, com luz quente da janela à direita. Plano médio, nível dos olhos, com espaço livre à esquerda.
```

Turn 2, with the first image attached in the same conversation:
```text
Mesma personagem: Dona Lia, com o mesmo rosto, o mesmo coque, os mesmos óculos redondos dourados e o mesmo avental xadrez. Agora ela está num mercado de bairro, escolhendo tomates numa banca de madeira, com sacolas de tecido no braço. Mantenha o mesmo estilo de aquarela e a mesma paleta quente da cena anterior. Plano médio, luz do dia.
```

## 5. Art with text in Portuguese

**Input:** "Um cartaz de festa junina com o texto 'Arraiá do Bairro 2026' e os horários do evento."

**Fields:** model `gemini-nano-banana-2.1` · aspect ratio `3:4` · size `2K`

Shows: each text is in quotation marks, with its font and placement. The language of the text is named.

```text
Um cartaz vertical de festa junina, com bandeirinhas coloridas penduradas numa corda no topo e um céu noturno azul-escuro com estrelas. Uma fogueira aparece desfocada à direita. No centro, o texto "ARRAIÁ DO BAIRRO 2026" em letras grandes, serifadas, amarelo-ouro com contorno vermelho. Logo abaixo, em letras menores e brancas, o texto "Sábado, 20h, praça central". Estilo de gravura com textura de papel. Idioma dos textos: português do Brasil.
```

## 6. Background image for a website

**Input:** "Preciso de um fundo para o topo do site da clínica. As cores do CSS são azul-petróleo (#0E5E6F) e off-white (#F4F1EA)."

**Fields:** model `gemini-nano-banana-2.1` · aspect ratio `16:9` · size `2K`

Shows: the palette comes from the project, and the empty area matches the layout where the text will sit.

```text
Fundo panorâmico para o topo de um site de clínica odontológica: um consultório limpo e luminoso, com janela grande e cortinas de linho off-white (#F4F1EA), e uma poltrona clínica de couro azul-petróleo (#0E5E6F) desfocada ao fundo. Luz natural suave da esquerda, plano amplo, nível dos olhos. A metade direita do quadro fica vazia, em off-white liso, com espaço para o título e o botão do site. Pessoas não aparecem no quadro. Formato de banner de site.
```

## 7. Infographic slide with three steps

**Input:** "Slide com três etapas do processo de reciclagem: coleta, triagem e novo uso."

**Fields:** model `gemini-nano-banana-2.1` · aspect ratio `16:9` · size `2K`

Shows: the structure comes first (title, blocks, order), each block has its exact text in quotation marks, and the reading direction is stated.

```text
Infográfico de slide com três etapas em linha, lidas da esquerda para a direita. Título no topo, em letras grandes e sem serifa: "COMO A RECICLAGEM FUNCIONA". Etapa 1, "COLETA", com ícone de caixa de papelão e o texto "Separação em casa". Etapa 2, "TRIAGEM", com ícone de esteira e o texto "Máquinas separam plástico e papel". Etapa 3, "NOVO USO", com ícone de rolo de papel e o texto "Matéria-prima volta à fábrica". Setas finas ligam as etapas. Cores verde-folha, branco e cinza-grafite, com hierarquia clara e texto legível. Idioma dos textos: português do Brasil.
```

## 8. Refining an unsatisfactory result

**Input:** "A primeira versão ficou com o fundo cinza e o rosto mudou. Quero o fundo azul-cobalto e o rosto igual ao da primeira."

**Fields:** model `gemini-nano-banana-2.1` · aspect ratio `4:3` · size `2K`, the same as the first request, sent in the same conversation

Shows: one change in one turn. The preservation clause names what must not change, and the request does not rebuild the scene.

```text
Na imagem anterior, troque apenas o fundo cinza por azul-cobalto liso, sem gradiente. Mantenha exatamente igual o rosto, a expressão, o cabelo, a roupa e a iluminação. Não altere o enquadramento.
```
