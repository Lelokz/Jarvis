# Etapa 0.5 — medição do wake word `hey_jarvis`

Sessão de teste do Léo em **3 de setembro de 2026, 13:13:27**, com o
`experimento_wakeword.py`. É a medição que decidiu o modelo, a pronúncia e o
limiar registrados no `ESCOPO.md` §4 e §5.

> ## ⚠️ Os dados brutos não existem mais
>
> Estes números são **derivados** do log `logs/wake-20260903-131327.jsonl`, que
> foi **apagado por engano em 3/set/2026** durante a limpeza dos logs de teste
> da Etapa 0.6 — um glob largo demais pegou junto a sessão real. Os 20 `.wav`
> dos "hey Jarvis" do Léo, em `logs/audio-wake/`, foram perdidos no mesmo
> descuido. `logs/` está no `.gitignore`, então não havia cópia em lugar nenhum.
>
> **O que se perdeu:** os 243 frames crus com score e horário individuais, e o
> áudio das 20 falas.
>
> **O que este arquivo preserva:** tudo que a análise extraiu deles — a
> distribuição, a tabela de limiares, o agrupamento por fala e os
> quase-acertos. É o suficiente para revisar a decisão do limiar, mas **não**
> para reanalisar com um critério novo nem para ouvir as gravações.
>
> Este arquivo existe justamente para que os números não dependam mais de um
> log volátil. Ele é versionado.

---

## Configuração da sessão

| | |
|---|---|
| modelo | `hey_jarvis_v0.1.onnx` (openWakeWord 0.6.0) |
| framework | `onnx` |
| `vad_threshold` | 0 — desligado, para medir o falso positivo bruto do modelo |
| limiar de disparo | 0.50 |
| piso de registro | 0.10 |
| refratário | 1.5 s |
| microfone | `default (padrão do sistema)` |

**Protocolo:** 20 falas de "hey Jarvis" na pronúncia inglesa, 10 na pronúncia
abrasileirada ("Járvis"), **intercaladas e não em bloco**, seguidas de 10
minutos falando outras coisas.

---

## Resultado

| | |
|---|---|
| disparos | **20** |
| falas na pronúncia inglesa | 20 → **100% de acerto** |
| falas abrasileiradas | 10 → **0 disparos** |
| falsos positivos em 10 min de fala comum | **0** — nenhum frame sequer passou do piso de 0.10 |
| frames acima do piso | 243 |
| janela em que houve frames | 13:13:32 → 13:15:12 (100 s) |

Os 10 minutos de escuta passiva não geraram **nenhum** frame acima de 0.10.
Isso é mais forte que "sem falso positivo": nada chegou perto. Também é a
fraqueza da amostra — não há um único dado sobre como fala comum se distribui
na faixa 0.10–0.50 (ver o risco na §7 do `ESCOPO.md`).

## Distribuição dos scores ≥ 0.10

```
  mín  0.10      p50  0.40      p90  0.94      máx  0.99
```

## Disparos por limiar

Refratário de 1.5 s aplicado, igual ao ciclo real. O valor em 0.50 confere com
os 20 disparos observados ao vivo, o que valida a simulação.

| limiar | disparos | | limiar | disparos |
|---:|---:|---|---:|---:|
| 0.20 | 32 | | 0.55 | 19 |
| 0.25 | 32 | | 0.60 | 19 |
| 0.30 | 31 | | 0.65 | 19 |
| 0.35 | 26 | | 0.70 | 17 |
| 0.40 | 23 | | 0.75 | 16 |
| 0.45 | **20** | | 0.80 | 15 |
| 0.50 | **20** ← usado | | | |

**Platô de 0.45 a 0.50:** o resultado é idêntico nos dois. Há 0.05 de folga
para baixo antes que mexer no limiar mude qualquer comportamento.

## Os dois grupos de pronúncia

Frames agrupados por rajada (separação > 1 s de silêncio): **30 grupos**,
exatamente as 30 falas.

| | grupos | pico mínimo | pico máximo |
|---|---:|---:|---:|
| dispararam | 17 | 0.658 | 0.988 |
| não dispararam | 13 | 0.141 | 0.409 |

**Lacuna de 0.249** entre 0.409 e 0.658, sem nenhum grupo no meio. A separação
entre as duas pronúncias é limpa.

*(17 grupos disparando com 20 disparos: três rajadas longas contêm duas falas
cada.)*

Picos dos que **não** dispararam, ordenados:

```
0.141  0.184  0.200  0.299  0.309  0.312  0.325
0.362  0.364  0.381  0.400  0.407  0.409
```

O modelo **responde** ao "Járvis" abrasileirado — não é surdo a ele —, mas
pontua 2 a 3 vezes menos. Para pegar 9 das 10 falas em português o limiar teria
de cair para 0.30; as três mais fracas só entrariam com o limiar encostado no
piso.

## Ordem cronológica

```
...SSS....SSSS.SSSS..SS.SSS..S        S = disparou
```

As pronúncias foram intercaladas, não feitas em bloco — então os 20/20 não
vieram de um trecho favorável da sessão.

## Grupos, um a um

| # | horário | frames | pico | faixa | disparou |
|---:|---|---:|---:|---|---|
| 1 | 13:13:32 | 3 | 0.141 | 0.102 – 0.141 | não |
| 2 | 13:13:36 | 8 | 0.312 | 0.100 – 0.312 | não |
| 3 | 13:13:39 | 5 | 0.407 | 0.136 – 0.407 | não |
| 4 | 13:13:41 | 8 | 0.977 | 0.250 – 0.977 | **sim** |
| 5 | 13:13:44 | 10 | 0.689 | 0.114 – 0.689 | **sim** |
| 6 | 13:13:46 | 9 | 0.947 | 0.126 – 0.947 | **sim** |
| 7 | 13:13:49 | 2 | 0.362 | 0.319 – 0.362 | não |
| 8 | 13:13:51 | 7 | 0.325 | 0.113 – 0.325 | não |
| 9 | 13:13:56 | 2 | 0.299 | 0.263 – 0.299 | não |
| 10 | 13:13:59 | 2 | 0.381 | 0.125 – 0.381 | não |
| 11 | 13:14:01 | 9 | 0.981 | 0.133 – 0.981 | **sim** |
| 12 | 13:14:04 | 9 | 0.938 | 0.289 – 0.938 | **sim** |
| 13 | 13:14:07 | 5 | 0.823 | 0.111 – 0.823 | **sim** |
| 14 | 13:14:09 | 5 | 0.776 | 0.319 – 0.776 | **sim** |
| 15 | 13:14:14 | 6 | 0.309 | 0.112 – 0.309 | não |
| 16 | 13:14:17 | 7 | 0.977 | 0.204 – 0.977 | **sim** |
| 17 | 13:14:19 | 10 | 0.977 | 0.114 – 0.977 | **sim** |
| 18 | 13:14:22 | 9 | 0.913 | 0.197 – 0.913 | **sim** |
| 19 | 13:14:25 | 7 | 0.709 | 0.194 – 0.709 | **sim** |
| 20 | 13:14:28 | 5 | 0.400 | 0.164 – 0.400 | não |
| 21 | 13:14:30 | 7 | 0.409 | 0.108 – 0.409 | não |
| 22 | 13:14:31 | 20 | 0.902 | 0.103 – 0.902 | **sim** |
| 23 | 13:14:36 | 10 | 0.899 | 0.143 – 0.899 | **sim** |
| 24 | 13:14:49 | 1 | 0.200 | 0.200 – 0.200 | não |
| 25 | 13:14:51 | 42 | 0.988 | 0.128 – 0.988 | **sim** |
| 26 | 13:15:01 | 7 | 0.658 | 0.127 – 0.658 | **sim** |
| 27 | 13:15:04 | 10 | 0.860 | 0.101 – 0.860 | **sim** |
| 28 | 13:15:07 | 8 | 0.364 | 0.103 – 0.364 | não |
| 29 | 13:15:10 | 2 | 0.184 | 0.171 – 0.184 | não |
| 30 | 13:15:11 | 8 | 0.964 | 0.588 – 0.964 | **sim** |

## Quase-acertos

Frames mais altos que vieram de grupos que **nunca** dispararam. Nenhum passou
de 0.409 — folga de 0.091 até o limiar.

| score | horário | grupo |
|---:|---|---:|
| 0.409 | 13:14:30 | 21 |
| 0.407 | 13:13:39 | 3 |
| 0.400 | 13:14:28 | 20 |
| 0.381 | 13:13:59 | 10 |
| 0.364 | 13:15:07 | 28 |
| 0.362 | 13:13:49 | 7 |
| 0.331 | 13:14:30 | 21 |
| 0.325 | 13:13:51 | 8 |
| 0.319 | 13:13:49 | 7 |
| 0.318 | 13:13:39 | 3 |

Pelos horários, todos caem dentro da janela ativa de 100 s e estão intercalados
com os acertos: são as falas abrasileiradas do Léo, não falso positivo.

**Nenhum deles tinha `.wav`.** O `experimento_wakeword.py` da Etapa 0.5 só
gravava áudio quando havia disparo — a pendência que a Etapa 0.6 corrigiu,
passando a gravar todo grupo que passe do piso.

---

## Decisão que saiu daqui

**Modelo `hey_jarvis` pré-treinado, pronúncia inglesa, limiar 0.50.** Sem
treinar modelo customizado.

Baixar para 0.30 pegaria 9 das 10 falas em português, e foi descartado: os 10
minutos de escuta passiva não produziram nada acima de 0.10, então não há
evidência nenhuma sobre a faixa 0.30–0.45 e descer seria às cegas. Soma-se a
assimetria de custo — falso negativo se resolve repetindo a palavra, falso
positivo acorda o Jarvis no meio de um jogo.

O teste que fecharia essa lacuna: rodar `experimento_wakeword.py --piso 0.02`
por uma hora em silêncio.
