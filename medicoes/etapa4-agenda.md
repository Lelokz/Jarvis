# Etapa 4 — medições da Google Agenda

Setembro de 2026. Máquina do Léo: RTX 3060 12GB, Ryzen 5 3400G, 16GB.
Modelo: `qwen3:8b` via Ollama, quente (`keep_alive = "5m"`).

Este arquivo guarda os números que decidiram a etapa. Existe pelo mesmo motivo
que o `etapa0.5-wake-word.md`: log em `logs/` é volátil e está no `.gitignore`,
e o prompt antigo do classificador **foi apagado do código** nesta etapa — sem
transcrevê-lo aqui, o 60/80 não poderia mais ser reproduzido por ninguém.

---

## 1. Converter fala em data — a medição que escolheu o desenho

Dez frases, com hoje sendo **sexta, 04/09/2026, 15:38**.

| caminho | acerto |
|---|---|
| o modelo devolve a data já calculada | **5/10** |
| o modelo extrai a expressão + Python converte | **9/10**, todas as datas certas |

Erros do caminho 1, todos de **aritmética de dia da semana**:

| falado | modelo devolveu | era |
|---|---|---|
| "sexta que vem" | 09-09 (quarta) | 09-11 |
| "segunda de manhã" | 09-12 (sábado) | 09-07 |
| "quinta às dez" | 09-09 (quarta) | 09-10 |
| "terça às sete" | 09-06 (domingo) | 09-08 |
| "daqui a duas horas" | dia seguinte | hoje |

Nenhum se anuncia: o modelo devolve um ISO bem formado e errado.

**A extração da expressão foi 10/10** — verbatim e limpa. No teste por voz real
(log `jarvis-20260910-175233.jsonl`) foram mais **11/11**, incluindo
`"hoje de noite"` e `"hoje às 8 da noite"` de fala corrida.

A única falha do caminho 2 foi `"sexta que vem às três"` → 03:00 em vez de
15:00. Ambiguidade real do português. **Conserto:** hora nua de 1 a 6 sem
período vira tarde (`LIMITE_TARDE = 6`). Ninguém marca dentista às 3 da manhã.

### Estado do resolvedor no fechamento da etapa: 13/14

```
ok  'amanhã de manhã'          2026-09-05 09:00   fala: 'amanhã, sábado às 9'
ok  'sexta que vem'            2026-09-11 09:00   fala: 'sexta'
ok  'sexta que vem às três'    2026-09-11 15:00   fala: 'sexta às 15'
ok  'segunda de manhã'         2026-09-07 09:00   fala: 'segunda às 9'
ok  'quinta às dez'            2026-09-10 10:00   fala: 'quinta às 10'
ok  'terça às sete'            2026-09-08 07:00   fala: 'terça às 7'
ok  'daqui a duas horas'       2026-09-04 17:38   fala: 'hoje às 17h38'
ok  'hoje às 8 da noite'       2026-09-04 20:00   fala: 'hoje às 20'
ok  'amanhã às 14h30'          2026-09-05 14:30   fala: 'amanhã, sábado às 14h30'
ok  'meio-dia de sábado'       2026-09-05 12:00   fala: 'amanhã, sábado às 12'
ok  'dia 2'                    2026-10-02 09:00   fala: 'sexta, dia 2'
X   '31 de dezembro às 23h'    2026-09-04 23:00   <- cai em HOJE (ver limitação)
ok  segunda numa segunda       2026-09-14         (a próxima, não hoje)
ok  amanhã em 31/12            2027-01-01 10:00   (virada de ano)
```

---

## 2. Ancoragem da expressão de tempo — corte em 0.75

O modelo **inventa** `quando` quando a frase não tem data. Medido:

| falado | modelo devolveu | ancoragem |
|---|---|---|
| "marca academia" | `/no_think` (token de controle vazado) | 0.125 |
| "me lembra de ligar pro médico" | `agora` | 0.400 |
| "marca dentista" | `agora` | **0.600** |
| "marca dentista amanhã de manhã" | `amanhã de manhã` | 1.000 |
| "põe na agenda reunião sexta que vem às três" | verbatim | 1.000 |
| "me lembra de tomar remédio daqui a duas horas" | verbatim | 1.000 |

**Por que 0.75 e não os 0.60 dos nomes.** A extração de tempo é fácil para o
modelo: nas dez frases medidas ele copiou verbatim 10/10, dando ancoragem 1.0.
Não há caso legítimo entre 0.60 e 1.0 para proteger. Já as invenções encostam no
corte comum — `"marca dentista"` devolveu `agora`, que pontua **exatos 0.600**
contra o texto falado e passaria por um fio, marcando compromisso para agora sem
ninguém ter pedido.

---

## 3. O classificador de sim/não — o achado que não era da agenda

Descoberto medindo o custo de outra coisa. **Afeta toda confirmação do sistema,
não só a da agenda** — inclusive a da busca da Etapa 2.

O prompt nunca recebia **a pergunta que estava sendo respondida**. Sem ela, o
modelo empurra pedido novo para NAO.

Custo da chamada, modelo quente: **0,06 a 0,10 s**.

### Prompt antigo (apagado do código, preservado aqui)

```
O usuário está respondendo a uma pergunta de sim ou não. Responda com uma
palavra só:
SIM — ele concordou. Em português falado isso inclui 'pode', 'manda', 'isso',
'beleza', 'claro', 'vai lá', 'bora' e 'aham', não só 'sim'.
NAO — ele negou, discordou ou corrigiu. Use NAO também quando ele nega e já diz
o que queria, como em 'não, eu quis dizer outra coisa' ou 'nada disso, quero X'.
OUTRO — ele ignorou a pergunta e falou de um assunto sem relação.
```

O novo está em `jarvis/nucleo/cerebro.py`, em `confirmar()`. A diferença é
incluir a pergunta e mandar preferir OUTRO na dúvida.

### 5 rodadas × 16 frases, pergunta pendente = "dentista amanhã, sexta. Pode?"

| frase | esperado | sem a pergunta | com a pergunta |
|---|---|---|---|
| `Pode.` | SIM | **5/5** | **5/5** |
| `Sim` | SIM | **5/5** | **5/5** |
| `Manda` | SIM | **5/5** | **5/5** |
| `Beleza` | SIM | **5/5** | **5/5** |
| `Isso` | SIM | **5/5** | **5/5** |
| `aham` | SIM | **5/5** | **5/5** |
| `Não.` | NAO | **5/5** | **5/5** |
| `não, deixa pra lá` | NAO | **5/5** | **5/5** |
| `não, era terça` | NAO | **5/5** | **5/5** |
| `abre o loft` | OUTRO | 0/5 (NAO) | **5/5** |
| `toca uma música` | OUTRO | 0/5 (NAO) | **5/5** |
| `qual a temperatura da GPU?` | OUTRO | 1/5 (NAO) | **5/5** |
| `que horas são?` | OUTRO | 0/5 (NAO) | **5/5** |
| `o que eu tenho hoje?` | OUTRO | **5/5** | **5/5** |
| `Fudge` | OUTRO | **5/5** | **5/5** |
| `A CIDADE NO BRASIL` | OUTRO | 4/5 (SIM) | **5/5** |
| **total** | | **60/80** | **80/80** |

*(Rodadas diferentes deram 60/80 e 61/80 sem a pergunta; com ela, 80/80 nas
duas. A variação é de uma frase.)*

**As quatro frases que quebravam são exatamente os pedidos novos.** Na prática
isso significava: com um evento esperando confirmação, dizer `"abre o loft"`
**cancelava o evento e não abria o Loft** — o NAO caía em "deixa pra lá" e a
saída de emergência do OUTRO, que existe justamente para tratar a fala como
pedido novo, quase nunca disparava.

---

## 4. Detector de confirmação órfã — e a armadilha da maiúscula

Quando o Léo diz "pode" e não há nada pendente, cair no `nao_sei` o fez sair de
uma conversa **acreditando ter marcado um dentista que nunca foi criado**.

O detector novo (`resposta_solta()`) roda só no caminho em que o núcleo já ia
dizer `nao_sei`, então não custa latência no uso normal.

### 5 rodadas × 21 frases

| frase | esperado | sem a nota | com a nota |
|---|---|---|---|
| `pode` | SOLTA | **5/5** | **5/5** |
| `Pode.` | SOLTA | **5/5** | **5/5** |
| `Sim` | SOLTA | **5/5** | **5/5** |
| `Manda` | SOLTA | **5/5** | **5/5** |
| `Beleza` | SOLTA | **5/5** | **5/5** |
| `Isso` | SOLTA | **5/5** | **5/5** |
| `aham` | SOLTA | **5/5** | **5/5** |
| `claro` | SOLTA | **5/5** | **5/5** |
| `não` | SOLTA | 2/5 | **5/5** |
| `Não` | SOLTA | 0/5 | **5/5** |
| `Não.` | SOLTA | 0/5 | **5/5** |
| `nao` | SOLTA | 0/5 | **5/5** |
| `deixa pra lá` | SOLTA | **5/5** | **5/5** |
| `obrigado` | OUTRO | **5/5** | **5/5** |
| `tudo bem?` | OUTRO | **5/5** | **5/5** |
| `que horas são?` | OUTRO | **5/5** | **5/5** |
| `bom dia` | OUTRO | **5/5** | **5/5** |
| `Fudge` | OUTRO | **5/5** | **5/5** |
| `A CIDADE NO BRASIL` | OUTRO | **5/5** | **5/5** |
| `me conta uma piada` | OUTRO | **5/5** | **5/5** |
| `você é legal` | OUTRO | **5/5** | **5/5** |
| **total** | | **87/105** | **105/105** |

> ### O detalhe que só aparece no uso real
>
> **`'não'` classificava certo e `'Não'` não.** Não era pontuação — era
> **maiúscula**. E o Whisper **sempre capitaliza a primeira palavra da frase**,
> então em produção a negação solta erraria **sempre**, nunca no laboratório.
>
> Todas as formas de negação estavam quebradas: `Não` 0/5, `Não.` 0/5,
> `nao` 0/5, e `não` instável em 2/5. As afirmações iam todas bem — o viés era
> só contra o "não".
>
> A correção é uma frase no prompt: *"Pontuação e maiúsculas não mudam nada:
> 'Não.' é o mesmo que 'não'. Uma negação sozinha é SOLTA mesmo sem nada para
> negar."*

---

## 5. A hora que a confirmação calava

Achado no log do teste por voz, na linha `17:53:25`:

```json
{
  "dito":       "Agora marca a dedista para hoje de noite.",
  "argumentos": {"quando": "hoje de noite", "titulo": "dedista"},
  "ancoragem_quando": 1.0,
  "quando": {"falado": "hoje de noite",
             "resolvido": "2026-09-10T19:00:00",
             "descricao": "hoje"}
}
```

**A extração e a conversão acertaram.** Quem jogou a hora fora foi a frase de
confirmação: `_resolver_hora` marcava hora vinda de **período** como não
explícita, e a descrição só fala a hora quando ela é explícita.

Era mais largo que o caso do log:

| expressão | criava em | confirmava |
|---|---|---|
| `hoje de noite` | 19:00 | "hoje" |
| `amanhã de manhã` | 09:00 | "amanhã, sexta" |
| `sexta à tarde` | 14:00 | "amanhã, sexta" |
| `amanhã` | 09:00 **inventado** | "amanhã, sexta" |

`amanhã de manhã` é a frase da verificação **aprovada** da etapa: criava às 9h
e nunca dizia isso.

Duas coisas diferentes estavam colapsadas numa flag só, e foram separadas:

- **Período é hora dita** — quem fala "de noite" disse quando quer. Agora a
  confirmação fala: *"dedista hoje às 19. Pode?"*
- **Nada dito é palpite** — "marca dentista amanhã" pergunta *"Que horas?"*,
  guarda o dia e junta com a resposta.

---

## 6. Listagem — o corte pelo relógio

Pergunta feita às **17:53:46**, com 5 eventos no dia:

| | evento | no momento da pergunta | |
|---|---|---|---|
| 1 | 07:30 Escola | já tinha passado **10h16** | ← falado |
| 2 | 15:00 Khan Academy | já tinha passado 2h54 | ← falado |
| 3 | 16:30 Estudos | já tinha passado 1h24 | ← falado |
| 4 | 19:00 AULA - SENAI | faltava 1h06 | cortado |
| 5 | 20:00 Dentista | faltava 2h06 | cortado |

Listava os três **primeiros do dia**, contados da meia-noite, enquanto a frase
prometia "os próximos". Escondeu **100% do que ainda ia acontecer**.

Corrigido: hoje corta pelo relógio, dia futuro não (lá o dia inteiro está pela
frente), e evento de dia inteiro nunca é cortado — ele começa 00:00 e sumiria
no primeiro minuto do dia.

---

## 7. Roteamento e regressão no fechamento

| o quê | resultado |
|---|---|
| 15 frases da Etapa 1 | **15/15** |
| pares novos da etapa (17 frases) | **17/17** |
| conjunto largo, 11 frases × 5 rodadas | **50/55** — ver abaixo |
| `abridança.ppxt` × 20 | **0 ações** (exigido 0) |
| listagem, 8 casos isolados | **8/8** |
| guarda de ancoragem, 4 frases sem data | **4/4** perguntam |
| `verificar_linha.py` | OK — o núcleo não conhece áudio |
| `etapa0.py --autoteste` | PASSOU |
| `assistente.py --teste-ciclo` | PASSOU |

As duas funções novas levaram o núcleo de 4 para 6 sem custo medível de
roteamento — o salto de concorrência que a lição da Etapa 2 previa não se
materializou aqui.

**A única falha do conjunto largo não é da Etapa 4.** Dez das onze frases deram
5/5; `"procura o arquivo de configuração"` deu **0/5**, sempre devolvendo
função nenhuma. O verbo "procura" não está na descrição do `abrir` — que lista
"abre", "mostra", "acessa" e "põe na tela" — e a busca da Etapa 2 é o segundo
degrau do `abrir`, sem verbo próprio. Pré-existente, registrado no `ESCOPO.md`
§5 como limitação.
