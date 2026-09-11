# Etapa 5 — medições de mexer em arquivo

Setembro de 2026. Máquina do Léo: RTX 3060 12GB, Ryzen 5 3400G, 16GB.
Modelo: `qwen3:8b` via Ollama, quente (`keep_alive = "5m"`).

Guarda os números que decidiram a etapa, no mesmo padrão do
`etapa0.5-wake-word.md` e do `etapa4-agenda.md`.

**A seção 3 é a razão principal deste arquivo existir.** É o primeiro dado real
sobre o custo de acrescentar função ao núcleo, e toda etapa nova vai querer
consultá-la antes de decidir quantas funções traz.

---

## 1. Extração do nome novo a partir da fala

A pergunta que o plano mandou medir antes de fixar o desenho, no mesmo formato
da data na Etapa 4: o modelo consegue tirar um nome de arquivo de uma frase
falada?

| frase | esperado | devolvido | ancoragem |
|---|---|---|---|
| `Renomeia o relatório para proposta comercial.` | `proposta comercial` | `proposta comercial` | 1.00 |
| `Muda o nome do relatório para proposta comercial.` | `proposta comercial` | `proposta comercial` | 1.00 |
| `Troca o nome do print pra tela de erro.` | `tela de erro` | `tela de erro` | 1.00 |
| `Chama esse arquivo de contrato assinado.` | `contrato assinado` | `contrato assinado` | 1.00 |
| `Renomeia a foto para aniversário da vó.` | `aniversário da vó` | `aniversário da vó` | 1.00 |
| `Renomeia o arquivo de configuração para config antigo.` | `config antigo` | `config antigo` | 1.00 |
| `Renomeia o orçamento pra versão final.` | `versão final` | `versão final` | 1.00 |
| `Renomeia o currículo para currículo 2026.` | `currículo 2026` | `currículo 2026` | 1.00 |
| `Renomeia o relatório.` | *(vazio)* | *(vazio)* | — |
| `Renomeia esse aí pra contrato.` | `contrato` | `contrato` | 1.00 |
| **total** | | **10/10** | |


**10/10 verbatim, ancoragem 1.00 em todas.** Melhor que a extração de data, e
sem nenhuma normalização — ele devolve exatamente as palavras faladas. E devolve
**vazio** corretamente quando o nome novo não foi dito, que é o caso que
importa: inventar ali renomearia o arquivo para algo que o Léo nunca falou.

### A direção perigosa: inventar nome que não foi dito

5 rodadas por frase.

| frase | o que devolveu | ancoragem | a guarda pega? |
|---|---|---|---|
| `Renomeia o relatório.` | *(vazio)* 5/5 | — | não precisa |
| `Renomeia esse arquivo.` | *(vazio)* 5/5 | — | não precisa |
| `Preciso renomear o contrato.` | *(vazio)* 5/5 | — | não precisa |
| `Renomeia aquele arquivo da pasta de downloads.` | `novo nome` / `novo_nome` 2/5 | **0.47** | **sim**, corte 0.60 |
| `Muda o nome do print.` | **`print`** 3/5 | **1.00** | **NÃO** |

**O caso que a ancoragem não tem como pegar.** O modelo copia o nome do **alvo**
para o campo do nome novo. A palavra está mesmo na frase, então pontua 1.00 —
não há o que barrar. É o mesmo formato do bug da Etapa 4: a ancoragem detecta
**invenção**, não **palavra errada**.

Guarda dirigida, em `nucleo._renomear`: nome novo igual ao alvo não é nome novo,
é o modelo preenchendo campo obrigatório com o que tinha à mão. Vira a pergunta
"Para o quê?".

### "Esse aí" virando alvo

`"Renomeia esse aí."` devolvia `alvo='esse aí'` em vez de vazio. O Jarvis
procurava isso no disco, não achava, e respondia *"não achei nada chamado esse
aí"* — mandando o Léo repetir um nome que ele nunca disse.

Resolvido com uma lista fechada de demonstrativos em `arquivos.py`
(`APONTAM_SEM_NOMEAR`), da mesma natureza do `_SUPERFLUAS` do `atalhos.py`:
limpeza mecânica de português, não julgamento, e portanto não é trabalho para o
modelo.

```
'esse aí'        -> aponta sem nomear      'relatorio zx9'  -> nomeia
'esse arquivo'   -> aponta sem nomear      'o relatório'    -> nomeia
'aquele lá'      -> aponta sem nomear      'esse contrato'  -> nomeia
```

---

## 2. Roteamento com 9 funções

5 rodadas por frase. É o conjunto que decide se a etapa está de pé — a lição
da Etapa 2 diz que cada função nova amplia o que o modelo pode confundir com
o que já existe.

### As 15 frases da Etapa 1

| frase | esperado | 9 ferramentas |
|---|---|---|
| `abre o loft` | `abrir` | **5/5** |
| `abre gravações` | `abrir` | **5/5** |
| `abre o projeto loft` | `abrir` | **5/5** |
| `abre o projeto loft pra mim` | `abrir` | **5/5** |
| `põe o loft na tela` | `abrir` | **5/5** |
| `abre a pasta de gravações` | `abrir` | **5/5** |
| `dá uma aberta no loft aí` | `abrir` | **5/5** |
| `abre o lofti` | `abrir` | **5/5** |
| `abre gravasoes` | `abrir` | **5/5** |
| `abre o projeto lofit` | `abrir` | **5/5** |
| `que horas são?` | *(nenhuma)* | **5/5** |
| `tudo bem?` | *(nenhuma)* | **5/5** |
| `obrigado` | *(nenhuma)* | **5/5** |
| `toca uma música` | `tocar` | **5/5** |
| `qual a temperatura da GPU?` | `status_pc` | **5/5** |
| **total** |  | **75/75** |

**75/75.** Nenhuma das frases antigas caiu com três funções novas na mesa.

### Os pares novos, e os perigosos

| frase | esperado | 9 ferramentas |
|---|---|---|
| `Renomeia o relatório para proposta comercial.` | `renomear` | **5/5** |
| `Muda o nome do print pra tela de erro.` | `renomear` | **5/5** |
| `Troca o nome do contrato.` | `renomear` | **5/5** |
| `Chama esse arquivo de acordo final.` | `renomear` | **5/5** |
| `Cria uma pasta chamada notas na documentos.` | `criar_pasta` | **5/5** |
| `Faz uma pasta de recibos na downloads.` | `criar_pasta` | **5/5** |
| `Desfaz.` | `desfazer` | **5/5** |
| `Desfaz isso, não era pra ter feito.` | `desfazer` | **5/5** |
| `Volta atrás.` | `desfazer` | **5/5** |
| `Abre o relatório.` | `abrir` | **5/5** |
| `Cria um evento amanhã às 9 chamado dentista.` | `criar_evento` | **5/5** |
| `Cria um lembrete pro médico amanhã.` | `criar_evento` | **5/5** |
| `O que eu tenho hoje?` | `agenda_do_dia` | **5/5** |
| `Toca uma música.` | `tocar` | **5/5** |
| `Pausa.` | `midia` | **5/5** |
| **total** |  | **75/75** |

**75/75.** O par que mais preocupava era `criar_pasta` contra `criar_evento` —
mesmo verbo, destinos completamente diferentes — e ele não errou nenhuma vez.

### O conserto do verbo "procura"

| frase | esperado | acerto |
|---|---|---|
| `procura o arquivo de configuração` | `abrir` | **5/5** |
| `procura o relatório` | `abrir` | **5/5** |
| `acha a pasta de gravações` | `abrir` | **5/5** |
| `cadê o loft?` | `abrir` | **5/5** |
| `encontra o currículo` | `abrir` | **5/5** |
| `procura o relatório e renomeia pra proposta` | `renomear` | **5/5** |
| `procura o contrato pra eu renomear` | `renomear` | **5/5** |
| `abre música` | `abrir` | **5/5** |
| `toca uma música` | `tocar` | **5/5** |
| `abre o loft` | `abrir` | **5/5** |
| **total** | | **50/50** |

---

## 3. O custo de acrescentar função — 6 contra 9 ferramentas

**É o primeiro dado real sobre isso no projeto.** A lição registrada na Etapa 2
dizia que cada função nova amplia o que o modelo pode confundir, mas nunca
tinha sido medida: até aqui só se observava que a regressão continuava passando.

### Como medir isso sem se enganar

A comparação óbvia — rodar o conjunto de roteamento inteiro nas duas
configurações — **não mede nada**. As frases das funções novas dão 0/5 com 6
ferramentas por construção, não por confusão: a função não existe ali. Somar
isso produz um "30/75 contra 75/75" que parece um resultado e não é.

A comparação honesta usa **só as frases cuja função existe nas duas
configurações**. Essas o modelo poderia acertar dos dois lados, e qualquer queda
é custo real da concorrência.

**10 rodadas por frase**, e não 5: o efeito é da ordem de uma frase em dez, e 5
rodadas não o enxergam de forma confiável — foi exatamente o que aconteceu na
primeira medição desta etapa, que deu 150/150 e escondeu o que está abaixo.

### O resultado

| frase | esperado | 6 ferramentas | 9 ferramentas | |
|---|---|---|---|---|
| `abre o loft` | `abrir` | 10/10 | 10/10 |  |
| `abre gravações` | `abrir` | 10/10 | 10/10 |  |
| `abre o lofti` | `abrir` | 10/10 | 10/10 |  |
| `põe o loft na tela` | `abrir` | 10/10 | 10/10 |  |
| `dá uma aberta no loft aí` | `abrir` | 10/10 | 10/10 |  |
| `Abre o relatório.` | `abrir` | 10/10 | 10/10 |  |
| `que horas são?` | *(nenhuma)* | 10/10 | 10/10 |  |
| `tudo bem?` | *(nenhuma)* | 10/10 | 10/10 |  |
| `obrigado` | *(nenhuma)* | 10/10 | 10/10 |  |
| `toca uma música` | `tocar` | 10/10 | 10/10 |  |
| `Toca uma música.` | `tocar` | 10/10 | 10/10 |  |
| `Pausa.` | `midia` | 10/10 | 10/10 |  |
| `pausa` | `midia` | 10/10 | 10/10 |  |
| `Continua.` | `midia` | 10/10 | 0/10 | **−10** |
| `Próxima.` | `midia` | 10/10 | 10/10 |  |
| `aumenta o volume` | `midia` | 10/10 | 10/10 |  |
| `qual a temperatura da GPU?` | `status_pc` | 10/10 | 10/10 |  |
| `Cria um evento amanhã às 9 chamado dentista.` | `criar_evento` | 10/10 | 10/10 |  |
| `Cria um lembrete pro médico amanhã.` | `criar_evento` | 10/10 | 10/10 |  |
| `marca dentista amanhã de manhã` | `criar_evento` | 10/10 | 10/10 |  |
| `O que eu tenho hoje?` | `agenda_do_dia` | 10/10 | 10/10 |  |
| `o que tem na agenda amanhã` | `agenda_do_dia` | 10/10 | 10/10 |  |
| **total** | | **220/220** | **210/220** | |

### O que isto diz

**220/220 contra 210/220.** As dez que caíram são **uma frase só**, e ela caiu
por inteiro.

**`"Continua."` foi de 10/10 para 0/10.** Não é degradação, é perda total do
comando: vai para `None` em 7 de 8, ou seja, o Jarvis responde "isso eu ainda
não sei fazer" a um comando de mídia que funcionava na Etapa 4.

**E a causa é a maiúscula, de novo:**

| forma | 6 ferramentas | 9 ferramentas |
|---|---|---|
| `"Continua."` | midia 8/8 | **None 7/8** |
| `"continua"` | midia 8/8 | midia 8/8 |
| `"Continua a música."` | midia 8/8 | midia 8/8 |

É a terceira vez que a capitalização decide um resultado neste projeto — depois
do `'não'` contra `'Não'` na Etapa 4, e do `'pausa'` contra `'Pausa.'` aqui. E
**o Whisper sempre capitaliza a primeira palavra**, então a forma que quebra é
justamente a que chega no uso real. A forma que funciona é a que ninguém fala.

> **O padrão, agora com três casos:** o custo de acrescentar função não se
> distribui por igual. Ele se concentra nas frases **mais curtas** — uma
> palavra, sem objeto, sem contexto —, porque são as que dão menos evidência ao
> modelo, e é onde uma alternativa nova cabe mais fácil.
>
> Comando de mídia é exatamente esse formato: "pausa", "continua", "próxima".
> Toda etapa nova deve medir **esses** antes de fechar, com 10 rodadas e na
> forma capitalizada que o Whisper produz.

**Não foi corrigido nesta rodada.** Mexer na lista de verbos foi o que quebrou
`"abre música"` na Etapa 3, e pede rodada própria com a regressão das 15 frases
junto. Registrado como limitação conhecida no `ESCOPO.md` §5.

---

## 4. Verificação da etapa

| o quê | resultado |
|---|---|
| `arquivos.py` isolado, em pasta temporária | **20/20** |
| Conversa ponta a ponta | **12/12** |
| `criar_pasta` | **5/5** |
| Extração do nome novo | **10/10** |
| Roteamento com 9 funções, 5 rodadas | **150/150** |
| O conserto do "procura", 5 rodadas | **50/50** |
| `abridança.ppxt` x 20 | **0 ações** |
| `verificar_linha.py` | OK — o núcleo não conhece áudio |
| `etapa0.py --autoteste` | PASSOU |
| `assistente.py --teste-ciclo` | PASSOU |

As 20 recusas do teste isolado: nome ocupado, arquivo fora da lista branca, fuga
por `..`, symlink, pasta como alvo, nome vazio, nome só com espaço, nome só com
pontos, nome só com barra, arquivo inexistente, barra no meio virando espaço em
vez de subpasta, `"versão 2.5"` não virando extensão `.5`, extensão preservada,
extensão dita pelo Léo respeitada, `reverter` devolvendo o nome exato com acento
e separadores, `reverter` recusando nome reocupado, e as três do `criar_pasta`.

**Nenhum arquivo real do Léo foi tocado em teste.** Tudo em pasta temporária,
com a busca e a lista branca apontadas para lá — e o `criar_pasta` com uma
tabela de atalhos falsa, para não criar nada na Downloads de verdade.
