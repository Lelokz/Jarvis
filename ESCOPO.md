# JARVIS — Documento de Escopo

> Este arquivo é a fonte de verdade do projeto. Qualquer agente de IA que
> for mexer no código deve ler este documento **inteiro** antes de escrever
> qualquer linha. Se algo aqui conflitar com um pedido, pergunte antes de
> implementar.

Versão: 3.1. Sistema: **Linux Mint Cinnamon**.
Pasta: `~/Projetos/Jarvis`. Repositório Git privado no GitHub.
Etapas 0 a 5 aprovadas (set/2026). Da Etapa 5.5 em diante, nada feito.

---

## 1. O que é

Assistente pessoal por voz que roda no PC do Léo (Linux Mint Cinnamon,
RTX 3060 12GB, Ryzen 5 3400G, 16GB RAM) e executa ações **dentro do
computador dele**. Referência de comportamento: o Jarvis do Homem de Ferro,
sem a parte de braços robóticos.

O objetivo não é um chatbot com microfone. É uma coisa que **faz** — abre,
busca, move, anota, avisa.

---

## 2. Regras invioláveis

Estas regras valem para todas as etapas. Não são negociáveis por
conveniência de implementação.

1. **O modelo NUNCA gera código ou comando de shell para ser executado.**
   Ele escolhe de uma lista fechada de funções escritas à mão e passa
   parâmetros. Não existe `exec`, `eval`, nem string indo pro PowerShell.
2. **Nada de chutar.** Se a intenção não estiver clara, ou se a busca
   devolver mais de um resultado, ele **pergunta em voz alta**. Silêncio
   também não é resposta aceitável.
3. **Ação destrutiva exige confirmação falada.** Mover, renomear,
   sobrescrever ou apagar → ele diz o que vai fazer e espera "pode".
   **A pergunta vale mais que a lista, e é obrigatória em TODA função nova:
   *esta ação pode machucar ou destruir alguma coisa?* Se sim, passa pela
   confirmação.** A lista acima é exemplo, não fronteira — foi por lê-la como
   fronteira que o volume ficou de fora e foi a 100 no ouvido do Léo.
4. **Ele não apaga arquivo.** Não nesta versão. Mover para a lixeira, no
   máximo, e só depois da Etapa 5 estar sólida.
5. **Toda ação executada vai pro log.** Sempre dá pra saber o que ele fez.
6. **O STT nunca roda sem VAD na frente.** O Whisper alucina texto em
   trechos de silêncio e ruído — num assistente sempre ligado, isso vira
   comando fantasma. Só transcrever quando houver fala detectada.
7. **Funcionar bem > arquitetura elegante.** Latência baixa é prioridade.

---

## 3. Persona

- **Nome:** Jarvis. Voz masculina.
- **Tom:** conversa de pessoa normal. Não é formal, não é robótico, e
  **não é cheio de gíria**. Sem "mano", "cria", "é nóis". Fala como alguém
  falaria com um amigo, sem forçar.
- **Respostas curtas.** É voz, não texto. Confirmação de ação é uma frase,
  não um parágrafo.
- **Trocável:** a persona (nome, voz, jeito de falar) fica num arquivo de
  configuração separado, porque o Léo pretende trocar por uma personagem
  feminina no futuro. Nada de nome chumbado no código.

---

## 4. Arquitetura

```
[microfone sempre ligado]
        ↓
  wake word ("hey Jarvis")      ← leve, roda na CPU, sempre ativo
        ↓
  saudação falada → abre janela de 30s
        ↓
  fala → texto (Whisper)        ← residente na VRAM, não recarrega
        ↓
  LLM local extrai só o NOME do que foi pedido
        ↓
  Python procura em atalhos.toml (casamento aproximado)
        ↓
  achou → executa pelo `tipo`   |   não achou → pergunta
        ↓                            (código Python nosso, lista fechada)
  resposta → fala (Piper)
        ↓
  janela de 30s reinicia quando ELE termina de responder
        ↓
  sem fala → volta a dormir (o Whisper continua carregado)
```

**Ciclo de vida:** dormindo (só o wake word) → acordado (30s, renovável a
cada resposta) → dormindo. **Só o ciclo lógico dorme; o Whisper não.**

Esta parte mudou na Etapa 0.6. O plano original era carregar os modelos ao
acordar e descarregar ao dormir, para não segurar VRAM enquanto o Léo joga. A
Etapa 0 mediu o custo disso: ~6,4s de carga mais ~1,9s de aquecimento. Pagar
quase 8 segundos toda vez que ele é chamado destrói a sensação de resposta, que
é justamente o que a Etapa 0 existiu para proteger. O Whisper passa a ser
carregado uma vez na subida e fica.

**Custo medido:** ~1,5GB de VRAM em uso total com o Whisper residente
(`large-v3-turbo`, int8), de 12GB. O assistente imprime esse número na subida.

**Isto vale para o Whisper, não para o LLM.** O `qwen3:8b` da Etapa 1 é outra
ordem de grandeza de VRAM, e se ele fica residente, se descarrega, ou se usa o
keep-alive do Ollama é decisão daquela etapa — com medição própria, não por
analogia com esta.

**Núcleo e clientes** (decidido em set/2026). O Jarvis vai ser acessível
remotamente no futuro — do celular, talvez do relógio. O PC continua sendo onde
tudo roda; os outros aparelhos são controles remotos que falam com ele pela
rede.

Isso não se constrói agora, mas tem uma consequência que é de agora: **o
sistema nasce partido em dois.**

```
┌─ NÚCLEO ──────────────────────────────────────┐
│  texto entra → decide a função → executa      │
│  → texto sai                                  │
│                                               │
│  não sabe o que é microfone, voz, wake word,  │
│  nem rede                                     │
└───────────────────────────────────────────────┘
        ▲
        │  hoje: chamada de função direta
        │
┌─ CLIENTES ────────────────────────────────────┐
│  • loop de voz (assistente.py) — o primeiro   │
│  • celular, relógio — depois                  │
└───────────────────────────────────────────────┘
```

**Nada de transporte de rede nem API HTTP por enquanto.** Só a linha interna.
O motivo de traçá-la desde já: se as funções nascerem costuradas dentro do loop
de voz, separar depois é reescrever; nascendo do lado certo, cada cliente novo
custa pouco.

Onde a linha passa:

| núcleo | cliente de voz |
|---|---|
| `jarvis/nucleo/` — da Etapa 1 em diante | `assistente.py` |
| decidir a função, casar atalhos, executar | `microfone.py`, `vad.py`, `stt.py`, `tts.py`, `wakeword.py` |
| log das ações (§2.5) | log de áudio e de wake word |

O núcleo **não imprime e não fala**: devolve texto, e o cliente decide se
sintetiza, mostra na tela ou manda notificação.

**Áudio:** ao responder, abaixa o volume dos outros programas (ducking) e
devolve depois. Ele pode falar por cima do jogo. No Linux isso é feito via
PipeWire, ajustando o volume por fluxo (sink-input).

**Stack decidida** (pesquisada em ago/2026):
- **Wake word:** openWakeWord v0.6.0, modelo pré-treinado `hey_jarvis`,
  limiar 0.50, **pronúncia inglesa**. Verificado e aprovado na Etapa 0.5
  (set/2026) — ver §5. Não treinamos modelo customizado: o pronto resolve.
  Roda na CPU em ONNX, custando **2,8ms por frame de 80ms** (~3,5% de um
  núcleo em tempo real), o que cabe num processo sempre ligado.
  **Restrição de instalação:** o `tflite-runtime` é dependência dura no
  Linux e não tem wheel para cp312, então `pip install openwakeword`
  falha no nosso Python 3.12. Instala-se com `--no-deps` mais `requests`,
  `scipy` e `scikit-learn` à mão, usando `inference_framework="onnx"` —
  aí o import do tflite nunca é acionado. Detalhes em
  `requirements-wakeword.txt`
- **VAD (detector de voz):** Silero, via pacote `pysilero-vad` (set/2026).
  Obrigatório, antes do STT — ver risco na §7. Escolhido no lugar do pacote
  `silero-vad` oficial porque aquele exige torch + torchaudio (~2,5GB) como
  dependência dura; o `pysilero-vad` é o mesmo modelo Silero empacotado em
  5MB pelo time do Rhasspy/Piper, sem torch. Menos disco e nada disputando
  VRAM com o Whisper
- **STT:** faster-whisper, modelo `large-v3-turbo`, na GPU com int8.
  Escolhido por ser ~4x mais rápido que whisper.cpp na GPU e por ser
  multilíngue de verdade (Parakeet e Canary são só inglês)
- **LLM:** `qwen3:8b` via Ollama. Escolhido por tool calling nativo no
  chat template, melhor desempenho local em testes de function calling
  (85%, empatando com modelos 5x maiores), e suporte multilíngue forte —
  o que importa muito para PT-BR. Se tropeçar, subir para `qwen3:14b`
  (cabe nos 12GB)
- **TTS:** Piper, vozes PT-BR masculinas (cadu, edresson, faber, jeff).
  Escolhido pela latência mais baixa. É o mais robótico do mercado —
  se incomodar, o upgrade é Kokoro-82M (mais natural, 2-3GB).
  **Peça deliberadamente trocável:** manter atrás de uma interface
- **Coisas do dia a dia:** `atalhos.toml` (set/2026). Uma tabela escrita à mão
  com o que o Léo abre todo dia, cada entrada com um `tipo` que diz **como**
  abrir:
  ```toml
  "loft"          = { tipo = "site",   alvo = "https://loftchat.com.br" }
  "projeto loft"  = { tipo = "vscode", alvo = "~/Projetos/Loft" }
  "gravações"     = { tipo = "pasta",  alvo = "/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Estudio/Gravacoes" }
  ```
  O modelo **só extrai o nome** do que foi pedido; o Python procura na tabela
  com casamento aproximado, para tolerar erro de transcrição do Whisper. Achou,
  executa pelo `tipo`. Não achou, pergunta ou cai numa busca genérica.
  Escolhido por três motivos: tira a ambiguidade das coisas do dia a dia de
  cima do modelo — que é o risco Alto da §7 —, o Léo edita sem mexer em código,
  e faz a Etapa 7 ("ensinar coisas novas") virar escrever uma linha aqui em vez
  de um subsistema
- **Busca de arquivos:** `plocate` (índice do sistema) ou `fd`
- **Controle de volume por app (ducking):** PipeWire / `pactl`
- **Linguagem:** Python

---

## 5. Etapas

Ordem obrigatória. Nada de pular. Cada etapa só começa depois que a
anterior foi testada manualmente pelo Léo e aprovada — **o teste dele é a
fonte de verdade.**

### Etapa 0 — Esqueleto de voz (sem wake word)
Ele ouve, transcreve o que foi dito e repete de volta. **Zero ações.**
Serve para medir a latência real do ciclo completo e validar o PT-BR do
Whisper.

A cadeia é `microfone → VAD (Silero) → STT (faster-whisper) → TTS (Piper)`.
O wake word ficou **de fora de propósito** e virou a Etapa 0.5: na época ele
era o único item da stack ainda não verificado, e amarrar a medição de
latência a uma peça não testada contaminaria justamente o número que esta
etapa existe para produzir. (Verificado depois, na Etapa 0.5.)

Critério de aprovação: latência aceitável na prática, transcrição confiável.

**APROVADA — set/2026**, no teste manual do Léo:

- **STT em 0,30s para 2,72s de fala**, na GPU (confirmada em uso)
- Transcrição do português correta, ortografia certa
- **30 segundos em silêncio sem transcrever nada** — o comando fantasma
  da §7 não apareceu; o VAD na frente do STT fez o trabalho
- Cadeia ouvir → transcrever → falar funcionando de ponta a ponta

Com isso, o risco de latência da §7 **não se confirmou**, e a arquitetura
do §4 segue de pé para as próximas etapas.

**Pendência conhecida, não bloqueante:** o Piper lê mal o que não é frase
corrida — letra solta ("mm" vira o nome da letra M), número com vírgula
sai pausado demais, e palavra rara ele engole ou pronuncia errado. Não
vira tarefa agora porque no uso real quem escreve o texto falado é o
sistema, não o Léo: a entrada é sempre frase corrida. Só volta a importar
se um dia o Jarvis tiver de ler conteúdo bruto em voz alta.

### Etapa 0.5 — Wake word: escolha da peça
Só depois da Etapa 0 aprovada. Verificar o openWakeWord e decidir **qual peça
usar**: modelo, pronúncia e limiar, escolhidos com medição e não por intuição.

Etapa de experimento, não de implementação. Roda num script isolado, sem tocar
no `etapa0.py`. Ligar o wake word na cadeia é a Etapa 0.6.

Critério de aprovação: acorda quando chamado, e não acorda sozinho.

**APROVADA — set/2026.** Rodada como experimento isolado
(`experimento_wakeword.py`), sem integrar ao loop. Os dois critérios
bateram:

- **Acorda quando chamado:** 20 falas de "hey Jarvis" na pronúncia
  inglesa, 20 disparos. **100%.** As pronúncias foram intercaladas, não
  feitas em bloco — então o resultado não veio de um trecho favorável da
  sessão.
- **Não acorda sozinho:** 10 minutos falando outras coisas, **zero frames
  acima do piso de 0.10**. Nenhum falso positivo, e nada que chegasse
  perto.

**Decisão: pronúncia inglesa, limiar 0.50.**

O modelo **responde** ao "Járvis" abrasileirado — não é surdo a ele —, mas
pontuando 2 a 3 vezes menos: os picos das falas em português ficam entre
**0.141 e 0.409**, contra **0.658 a 0.988** da versão inglesa. Há uma
lacuna de **0.249** sem nenhum grupo no meio: a separação é limpa.

Baixar o limiar para 0.30 pegaria 9 das 10 falas em português, e foi
**descartado**. O motivo não é o custo do falso negativo: é que os 10
minutos de escuta passiva não geraram nenhum frame acima de 0.10, então
**não existe evidência nenhuma sobre como fala comum se distribui na faixa
0.30–0.45**. Descer o limiar seria às cegas. Some-se a assimetria de
custo: falso negativo se resolve repetindo a palavra; falso positivo
acorda o Jarvis no meio de um jogo. Sendo o erro barato de um lado e caro
do outro, ser conservador é o certo.

**0.50 está num platô:** de 0.45 a 0.50 o número de disparos é idêntico
(20). Há 0.05 de folga antes que mexer no limiar mude qualquer
comportamento.

Os números completos da sessão — distribuição, tabela de disparos por limiar de
0.20 a 0.80, os 30 grupos um a um e os quase-acertos — estão em
[`medicoes/etapa0.5-wake-word.md`](medicoes/etapa0.5-wake-word.md).

### Etapa 0.6 — Integração do wake word
A peça já foi escolhida e medida na Etapa 0.5. Esta etapa é ligá-la: pôr o
openWakeWord na frente da cadeia do `etapa0.py` — rodando na CPU, sempre ativo,
disparando o resto só quando ouvir o nome — e montar o ciclo de vida
dormindo → acordado → dormindo descrito na §4, com a janela de 30s renovável a
cada fala.

É aqui que a arquitetura da §4 deixa de ser desenho e vira comportamento: até a
Etapa 0.5, o Jarvis não dorme nem acorda — ele só escuta o tempo todo.

Critério de aprovação, os três juntos:

1. **Acorda quando chamado com jogo ou música tocando.** Silêncio de
   laboratório não vale: o uso real é com barulho por cima.
2. **Escuta pela janela definida no escopo** — os 30s da §4, renováveis a cada
   fala.
3. **Volta a dormir sozinho**, sem o Léo precisar fazer nada.

**Pendência herdada da Etapa 0.5, a resolver aqui:** o
`experimento_wakeword.py` só grava `.wav` quando há disparo, o que impede
auditar os quase-acertos — justamente os frames mais informativos quando se
investiga por que algo *não* disparou. Resolver nesta etapa, porque a partir da
integração o áudio dos disparos deixa de ser dado de teste e vira **dado de
operação**: é com ele que se explica um acordar indevido no meio de um jogo,
meses depois, quando ninguém lembrar do contexto. — **Feito:** o
`assistente.py` grava todo grupo cujo pico passe do piso de 0.10, tenha
disparado ou não, com teto de arquivos em `logs/audio-wake/`.

**APROVADA — set/2026**, no teste manual do Léo. Os três critérios bateram, e o
ciclo foi repetido várias vezes seguidas com comportamento igual.

Duas descobertas do uso real:

**As duas pronúncias funcionam.** "hey Jarvis" à inglesa e "Járvis" à
brasileira, ambas acordam — com o limiar 0.50, o mesmo da medição. Isso
**contradiz a Etapa 0.5**, onde as 10 falas em português deram zero disparos,
com picos de 0.141 a 0.409.

A medição da 0.5 foi conservadora, provavelmente por variação de distância ou
entonação no experimento. Não foi mudança de código: antes de registrar isto,
o limiar carregado em execução foi conferido (0.50, sem override) e os dois
caminhos de alimentação do modelo foram comparados com o mesmo áudio em 7
alinhamentos — o do experimento (blocos de 1280 direto) e o do assistente (512
acumulados) — dando média 0,146 contra 0,149, sem viés sistemático.

**30 minutos dormindo, com som no PC e o Léo falando outras coisas, sem nenhum
despertar indevido.** Amostra três vezes maior que os 10 minutos da 0.5, e
agora com barulho por cima.

### Etapa 1 — Abrir coisas
Primeiro tool calling. Risco baixo: se errar, abre a coisa errada e pronto.

**O modelo enxerga uma função só: `abrir(nome)`.** Ele extrai o nome do que foi
pedido, e nada mais. Quem decide **como** abrir é o `tipo` da entrada no
`atalhos.toml` (§4) — site, pasta, VS Code —, não o modelo. Trocar três funções
por uma é deliberado: o §7 marca "modelo errando tool calling em português"
como risco Alto, e cada escolha a menos é uma chance a menos de errar.

Também é a etapa em que o **núcleo** da §4 nasce: `jarvis/nucleo/` recebe
texto, decide, executa e devolve texto, sem saber que existe microfone. O
`assistente.py` vira o primeiro cliente.

Não achou o nome na tabela: candidato próximo → pergunta em voz alta ("você
quis dizer gravações?"); nada perto → diz que não conhece. Busca genérica é a
Etapa 2.

**Antes de qualquer código desta etapa**, resolver a pendência §8.6: testar o
tool calling do `qwen3:8b` em português, isolado e por texto. Se falhar feio, a
arquitetura muda. — **Feito**, com 15/15. Ver abaixo.

**APROVADA — set/2026**, no teste manual do Léo: "abre o loft" abre o Brave,
"abre o projeto loft" abre o VS Code, e atalho inexistente responde direito.

O que foi medido, num experimento isolado e por texto
(`experimento_toolcalling.py`, dados em `medicoes/`):

- **Tool calling do `qwen3:8b` em português: 15/15 na decisão, zero resoluções
  erradas.** Nunca chamou `abrir` para "que horas são?" ou "toca uma música", e
  nunca deixou de chamar quando devia. **Isto resolve a §8.6, aberta desde o
  escopo inicial: a arquitetura de lista fechada se sustenta.**
- **Lista de nomes no prompt:** 70% de resolução direta contra 60% sem ela, e
  0,49s de latência média contra 0,91s, com muito menos variação. A tabela
  segue sendo a fonte da verdade e o casamento em Python segue validando — o
  prompt só ajuda o modelo a extrair o nome já perto da forma canônica.
- **STT com `initial_prompt` + `hotwords` alimentados pelo `atalhos.toml`:**
  3/15 → 9/15 de nomes sobrevivendo à fala rápida, com latência estável
  (0,269s → 0,260s). `beam_size` **fica em 1** — medido, não ajuda com o
  vocabulário ligado e custa até 24% mais tempo. Detalhes em
  [`medicoes/etapa1-stt.md`](medicoes/etapa1-stt.md).
- **Carga do LLM:** ~0,5s quente, ~6s frio. `keep_alive = "5m"`.
- **VRAM com os dois modelos:** 7,0GB de 12GB; cai para ~1,5GB quando o Ollama
  solta o `qwen3`.

**Duas limitações conhecidas, não bloqueantes:**

**O corte do casamento em 0.92.** Semelhança de caracteres não separa erro do
Whisper de palavra diferente parecida: "gravitações" pontua 0.90 contra
"gravações", **acima** de "gravasoes" com 0.89, que é o erro legítimo. Nenhum
limiar acerta os dois. O corte alto faz 3 de 10 comandos pedirem confirmação em
vez de agir direto. Aceito pela assimetria de custo: errar a pergunta custa uma
palavra, errar a ação abre a coisa errada.

**Ideia registrada, não implementada:** o vocabulário do `initial_prompt`
carrega hoje só os nomes do `atalhos.toml`. Nomes de arquivo dos projetos do
Léo poderiam entrar também — no teste com voz real, "wake word" virou "wake
world" e a busca falhou por uma letra, coisa que o vocabulário teria evitado.
Fica para quando incomodar o bastante.

**A medição do STT foi em áudio sintetizado no Piper**, porque o microfone
estava mutado. Os números absolutos são pessimistas — voz sintética, velocidade
exagerada e palavra inglesa dita por voz portuguesa. A comparação entre
configurações é que vale.

### Etapa 2 — Buscar
O Jarvis não precisa saber onde as coisas ficam. Ele precisa saber procurar.
- `buscar_arquivo(nome)` → lista de caminhos
- `buscar_pasta(nome)` → lista de caminhos
- **Desambiguação obrigatória:** achou mais de um, pergunta qual.

**APROVADA — set/2026**, no teste por voz do Léo.

O que decidiu a etapa não foi a busca funcionar, foi ela devolver **pouco**:

- **Exclusões de ruído.** `downloads` caía de 95 para **2**; `readme` de 3003
  para **29**; `config` de 6377 para **189**. Os dois primeiros batiam no teto
  de 200 antes, então os números velhos escondiam o tamanho do problema. O
  ruído dominante era tema de ícone (`.icons`, 84 dos 95) e prefixo Wine/Steam.
- **Pastas do dia a dia no `atalhos.toml`.** Downloads, Documentos, Imagens,
  Vídeos, Área de trabalho e Músicas resolvem pela tabela, instantâneo, sem
  tocar no disco. A busca existe para o que o Léo **não** previu; essas ele
  prevê. Mais três apelidos, porque "imagem", "vídeo" e "desktop" ficariam
  abaixo do corte de 0.92 e virariam pergunta.
- **A busca sobrevive à pista ruim.** Pista que não casa mantém os candidatos e
  pede outra, em vez de apagar tudo. Errar a pista é o caso comum — o desenho
  anterior punia exatamente ele, e foi o que matou a desambiguação no primeiro
  teste.
- **As frases explicam o que pedem.** "Achei três. Em qual pasta?" foi entendido
  como "qual pasta você quer de dentro daí". Agora: *"Achei 3 com esse nome, em
  lugares diferentes: um em Downloads, um em Loft e um em tests. Em qual
  deles?"* — diz que é o mesmo nome, em lugares distintos, e que a resposta é o
  lugar. Ficam no `config.toml`, editáveis.

**Latência.** O `keep_alive` de 5 min fazia o primeiro comando após uma pausa
custar ~8s de recarga do LLM. O assistente passa a mandar o Ollama carregar o
modelo **no instante em que o wake word dispara**, em segundo plano: a saudação
e a fala do comando já gastam esse tempo. Medido com o Ollama frio de verdade:
**8,18s → 0,73s, 91% da recarga escondida**, sem segurar VRAM enquanto ele
dorme.

**Correção de uma métrica que mentia.** A `latencia_percebida_s` existe desde a
Etapa 0 para medir o que o Léo sente, mas não contava o tempo do núcleo — que
não existia quando ela foi escrita. Marcava 1,15s numa fala sentida como 8s,
porque a recarga do LLM caía justamente nesse vão. O `Tempos` ganhou
`nucleo_s`, e toda decisão de latência daqui para frente sai de um número que
fecha.

### A lição que vai voltar a cada função nova

Pôr `"músicas"` na tabela fez **"toca uma música" abrir a pasta Músicas** — um
comando de mídia da Etapa 3 executando ação da Etapa 1. As 15 frases de
regressão caíram para 14/15 e pegaram isso.

O erro não era do casamento aproximado (nota 0.923, legítima): era o **modelo
escolhendo a ferramenta errada**. A correção foi ensiná-lo a decidir **pelo
verbo, não pelo assunto** — "abre", "mostra", "acessa" e "põe na tela" são
abrir; "toca", "reproduz", "ouve" e "pausa" não são.

**Isto vai se repetir a cada etapa que acrescentar função.** Toda entrada nova
na tabela amplia o que o modelo pode confundir com o que já existe, e o teste
de regressão das frases é o que pega. Uma primeira tentativa de correção baniu
o substantivo "música" e quebrou `"abre música"` — a instrução tem que mirar o
verbo.

**Capacidade futura, registrada e não implementada:** pedir algo **dentro** de
um lugar — "abre a pasta screenshots que está dentro de downloads". Hoje a
busca procura coisas *chamadas* X, não coisas *dentro* de X; foi o que fez o
Léo responder "Screenshots" a uma lista de candidatos que só continha arquivos
chamados "downloads". É funcionalidade nova, não conserto.

### Etapa 3 — Mídia e status do PC
Tudo leitura ou reversível. Seguro.
- `tocar(o_que, onde)` — YouTube, no mpv (só áudio) ou no navegador
- `midia(acao)` — pausar, continuar, próxima, anterior, volume
- `status_pc()` — por enquanto só temperatura e uso da GPU

**Três funções e não sete.** Controle não cabe dentro de `tocar`: aquele recebe
texto livre — o nome de uma música —, e controle **não tem objeto**, age no que
já estiver tocando. Forçar `tocar("pausar")` faria o parâmetro significar duas
coisas, que é a raiz do bug do "músicas" registrado na Etapa 2. Mas cinco
funções separadas (`pausar`, `continuar`, `próxima`…) seriam cinco concorrentes
novos pela atenção do modelo. Uma `midia(acao)` com `enum` fechado no schema é o
meio: o modelo escolhe entre quatro funções, e o parâmetro é uma lista fixa.

**APROVADA — set/2026**, no teste por voz do Léo: "toca uma música" pergunta
qual, "toca X no YouTube" toca direto, os controles acertam o player certo com
outra coisa tocando, o volume mexe no sistema e o status da GPU responde.

- **Roteamento entre as 4 funções: 15/15.** O maior salto de concorrência desde
  que o modelo entrou não quebrou nada.
- **As 15 frases da Etapa 1: 15/15**, com duas mudando de gabarito como
  previsto — "toca uma música" e "qual a temperatura da GPU" agora têm dono.
- **Do comando ao primeiro som: 1,99s**, sendo 1,47s a busca no YouTube.
- **Volume pelo sistema, via `pactl`**, em todos os casos: número, "mais",
  "menos" e "mudo".

**O mpv como padrão foi decisão acertada no uso real.** Tocar o áudio direto,
sem abrir aba, é o comportamento certo enquanto há jogo ou outra coisa na tela.
O caminho pelo navegador fica para quando o Léo disser "no YouTube".

**Três limitações conhecidas, nenhuma bloqueante:**

**Às vezes toca a música errada.** Pega o primeiro resultado da busca do
YouTube, que nem sempre é a versão desejada — pode vir cover, ao vivo ou vídeo
de reação. É ordenação do YouTube, não erro de roteamento. Se incomodar, as
saídas seriam dizer o título antes de tocar, ou aceitar "não, a próxima".

**A fonte local ficou fora**, porque não há música na máquina: a varredura da
home e do HD inteiros achou **um único MP3**. Quando houver música em
`~/Músicas` ou no HD, acrescentar é pequeno.

**O mpv mente sobre `CanGoNext`** — responde `true` mesmo com um vídeo só na
fila, enquanto o Brave responde `false` corretamente. A guarda que dependia
dessa propriedade deixava o Jarvis dizer "Próxima." sem nada acontecer.

> **O padrão que fica: não confiar no que o player declara.** Troca de faixa
> passou a ser verificada **por observação** — guardar o que está tocando,
> chamar o método, comparar. Não mudou, ele diz que não tem. Funciona com
> qualquer player, honesto ou não, e é o mesmo princípio de medir em vez de
> presumir que vale para o resto do projeto.

Uma segunda armadilha do mesmo tipo apareceu antes: o desempate entre dois
players era **alfabético**, e "brave" vem antes de "mpv" — mandar tocar uma
música e dizer "pausa" pausaria o vídeo do navegador. A ordem agora é: tocando
e iniciado por nós → qualquer um tocando → iniciado por nós mesmo pausado → o
resto.

### Etapa 4 — Google Agenda
Só cria coisa nova. Não toca em nada existente.
- `criar_evento(titulo, quando)`
- `agenda_do_dia(quando)`

**Mudança de escopo, decidida pelo Léo em set/2026.** Esta etapa era
`criar_nota(texto)` e `criar_lembrete(texto, quando)` num bloco de notas local.
Virou Google Agenda porque **nota que só existe no PC quase não seria usada** —
o que ele quer é o lembrete chegando no celular.

**A razão maior, e é a que faz valer o trabalho:** Agenda, Drive e Google Fotos
usam o **mesmo projeto no Google Cloud e o mesmo login**. Esta etapa é a
fundação para os três. Depois dela, cada serviço novo custa só mais uma
permissão declarada — não um sistema de autenticação novo. É por isso que vale
fazer bem feito agora, e não do jeito mais rápido.

**Apagar evento fica de fora**, de propósito: é ação destrutiva e a §2.3 exige
confirmação falada. O resto tem que estar de pé antes de mexer em algo que
destrói.

**A armadilha do OAuth, resolvida com a documentação do Google.** App com status
de publicação **"Testing"** tem a autorização expirando em **7 dias**, o que
obrigaria a reautorizar toda semana. A citação que decide:

> *"A Google Cloud Platform project with an OAuth consent screen configured for
> an external user type and a publishing status of 'Testing' is issued a refresh
> token expiring in 7 days"*

**A expiração depende do status de publicação, não da verificação** — o que
contradiz vários tutoriais que afirmam ser preciso passar pela verificação do
Google. Publicar em produção é um botão, e o app fica "não verificado", com uma
tela de aviso que se atravessa uma vez. O teto de 100 usuários que forçaria
verificação é irrelevante com um usuário.

**Escopo pedido:** `.../auth/calendar.events` — o mais estreito que cria e lê
eventos. É "sensível", mas não "restrito", que é a categoria que forçaria
auditoria de segurança.

> ### ⚠ Limitação conhecida: o app ficou em "Testing"
>
> **Publicar não deu.** O botão fica bloqueado porque o Google exige, na seção
> Branding, uma **URL de página inicial** e uma **URL de política de
> privacidade** — e o Jarvis não tem site. O app ficou em **Testing**, com o Léo
> adicionado como usuário de teste.
>
> **Consequência:** a autorização pode expirar em **7 dias**, obrigando a rodar
> `autorizar_google.py` de novo. Não quebra nada além disso: quando expira, a
> chamada falha e é só reautorizar.
>
> **O que resolveria:** duas URLs públicas — uma página inicial e uma política
> de privacidade. O caminho mais barato é o **GitHub Pages**, que o Léo já tem
> conta: um repositório com `index.html` e `privacidade.html` dá as duas de
> graça. Preenchidas, o botão Publicar destrava, o app vai para produção **sem
> verificação** e a expiração de 7 dias some.
>
> **Adiado de propósito.** O Léo quer primeiro ver se agenda por voz é útil o
> bastante para valer a briga com as URLs. Se for, é meia hora de trabalho; se
> não for, foi meia hora economizada. Reautorizar semanalmente é o custo de
> descobrir.

**Converter fala em data e hora — medido antes de decidir.** Duas opções: o
modelo devolver a data já calculada, ou devolver a expressão como foi falada e
o Python converter. Dez frases, com hoje sendo sexta 04/09:

| caminho | acerto |
|---|---|
| o modelo calcula | **5/10** |
| o modelo extrai + Python converte | **9/10**, todas as datas certas |

Os erros do modelo são **todos de aritmética de dia da semana**: "sexta que vem"
virou quarta, "segunda" virou sábado, "terça" virou domingo. E nenhum se
anuncia — ele devolve um ISO bem formado e errado, que parece certo. A extração
da expressão, em contraste, foi 10/10.

**Fica o caminho 2.** O `quando.py` mora separado do `agenda.py` de propósito:
converter fala em data serve para lembrete, alarme e qualquer coisa futura com
hora, e não é assunto do Google.

**Isto sai da máquina, e é a primeira vez.** Todas as etapas anteriores eram
locais. Aqui há rede, credencial e uma conta de verdade — errar escreve na
agenda que o celular do Léo mostra. As credenciais (`credenciais_google.json` e
`token_google.json`) ficam no `.gitignore`.

**APROVADA — set/2026.** Criar e listar funcionam por voz, e a notificação
chega no celular — que era a razão de a etapa ter trocado de escopo. Números
completos em `medicoes/etapa4-agenda.md`.

- **Roteamento: os pares novos da etapa deram 17/17** e as 15 frases da
  Etapa 1 seguem **15/15**. O salto de 4 para 6 funções não custou nada de
  roteamento — a lição da Etapa 2 previa custo e desta vez ele não apareceu.
- Num conjunto mais largo, medido 5 vezes, deu **50/55**: dez frases em 5/5 e
  **`"procura o arquivo de configuração"` em 0/5**, consistente. Não é
  instabilidade nem regressão — o verbo "procura" **nunca** esteve na lista do
  `abrir`, que é "abre", "mostra", "acessa" e "põe na tela". A busca da Etapa 2
  se alcança dizendo **"abre X"** quando X não está no `atalhos.toml`. Ver a
  limitação registrada abaixo.
- **`abridança.ppxt` × 20: zero ações.** A guarda de ancoragem da Etapa 1
  continua de pé.
- **Resolvedor de datas: 13/14**, incluindo virada de mês, virada de ano e
  "segunda numa segunda" (que é a próxima, não hoje).

**A guarda de ancoragem foi estendida para a expressão de tempo, com corte em
0.75 — mais alto que os 0.60 dos nomes.** O modelo inventa `quando` quando a
frase não tem data: "marca academia" devolveu `/no_think` (um token de controle
vazado) e "marca dentista" devolveu `agora`. O corte é mais exigente porque a
extração de tempo é **fácil** para o modelo — 10/10 verbatim nas frases
medidas, e mais 11/11 no teste por voz real —, então não há caso legítimo entre
0.60 e 1.0 para proteger. Já as invenções encostam no corte comum: `agora`
pontua **exatos 0.600** contra o texto falado e passaria por um fio, marcando
compromisso para agora sem ninguém ter pedido.

**A confirmação precisou aprender a falar a hora.** No teste por voz,
"marca a dedista para hoje de noite" resolvia 19:00 corretamente e confirmava
só *"dedista hoje"* — porque hora vinda de **período** era tratada como não
explícita. Pegava até `"amanhã de manhã"`, que é a frase da verificação
aprovada desta etapa: criava às 9h e nunca dizia isso. Separado em dois casos:
período **é** hora dita e vai falada; nada dito é palpite e agora **pergunta**
("Que horas?") em vez de marcar às 9h calado.

**Listar passou a cortar pelo relógio.** A primeira versão lia os três
**primeiros do dia**, contados da meia-noite, enquanto a frase prometia "os
próximos" — às 17h53, com 5 compromissos, leu os 3 que já tinham acontecido (um
deles 10h antes) e escondeu **os 2 únicos que ainda iam acontecer**. Hoje corta
pelo horário atual; dia futuro não corta, porque lá o dia inteiro está pela
frente; evento de dia inteiro nunca é cortado, já que começa 00:00 e sumiria no
primeiro minuto do dia. E "por hoje acabou" é frase própria: dizer "você não
tem nada hoje" às 22h seria falso sobre o dia.

**Três limitações conhecidas** (além do modo Testing, no bloco acima):

**Nome de mês não é entendido.** O `_resolver_dia` entende "dia 31" mas não
"31 de dezembro" — a expressão cai em **hoje**, com a hora certa. Fica assim de
propósito: data com nome de mês por voz é caso raro, e **a confirmação denuncia
o erro antes de virar evento**, porque ela agora fala a hora e o dia ("hoje às
23"). É o desenho funcionando — a confirmação existe para isto.

**Não há saída falada das perguntas pendentes.** Em "Para quando?" e
"Que horas?", a próxima fala é tratada como resposta, sempre: dizer "deixa pra
lá" vira tentativa de data e ele pergunta de novo. Não cria nada de errado — a
pergunta da hora bloqueia a criação —, mas prende a conversa até a janela de 30s
fechar e o `reiniciar_conversa()` limpar o estado. O conserto seria passar essas
falas pelo `resposta_solta()` antes de tratá-las como resposta.

**Apagar e editar ficam de fora.** Marcou errado e confirmou, conserta no
celular. Apagar é destrutivo e a §2.3 exige confirmação falada; entra quando o
resto estiver rodado no uso real.

> **Achado de fora da etapa, registrado para não se perder:** não dá para pedir
> busca com o verbo **"procura"**. `"procura o arquivo de configuração"` não
> casa com função nenhuma — 0/5 em 5 rodadas —, porque a descrição do `abrir`
> lista só "abre", "mostra", "acessa" e "põe na tela". A busca da Etapa 2 é o
> **segundo degrau** do `abrir`, alcançado quando o nome não está na tabela, e
> nunca ganhou verbo próprio. É pré-existente à Etapa 4 e é conserto de uma
> linha na descrição — mas mexer na lista de verbos foi o que quebrou
> `"abre música"` na Etapa 3, então pede regressão das 15 frases junto.

### O achado que não era da agenda: o classificador de sim/não

**Apareceu medindo o custo de outra coisa, e valia mais que a etapa inteira.**
O classificador de sim/não **nunca recebia a pergunta que estava sendo
respondida** — o prompt só dizia "o usuário está respondendo a uma pergunta de
sim ou não". Sem a pergunta, o modelo empurra **pedido novo** para NAO.

Isto não é da agenda: é de **toda confirmação do sistema**, incluindo a
desambiguação da busca da Etapa 2, que usa o mesmo classificador desde então.

| 5 rodadas × 16 frases | sem a pergunta | com a pergunta |
|---|---|---|
| total | **60/80** | **80/80** |
| `abre o loft` | 0/5 | 5/5 |
| `toca uma música` | 0/5 | 5/5 |
| `que horas são?` | 0/5 | 5/5 |
| `qual a temperatura da GPU?` | 1/5 | 5/5 |

As frases que quebravam são **exatamente os pedidos novos**. Na prática: com
algo esperando confirmação, dizer "abre o loft" **cancelava o pendente e não
abria o Loft** — o NAO virava "deixa pra lá", e a saída de emergência do OUTRO,
que existe justamente para tratar a fala como pedido novo, quase nunca
disparava.

> ### E o detalhe que só erraria no uso real: a maiúscula
>
> No detector de confirmação órfã, **`'não'` classificava certo e `'Não'`
> não.** Não era pontuação — era **maiúscula**. E o Whisper **sempre
> capitaliza a primeira palavra da frase**, então em produção a negação solta
> erraria **sempre**, e nunca no laboratório.
>
> Todas as formas de negação estavam quebradas: `Não` 0/5, `Não.` 0/5,
> `nao` 0/5, `não` instável em 2/5. As afirmações iam todas bem — o viés era só
> contra o "não". Com uma frase no prompt dizendo que pontuação e maiúsculas
> não mudam nada: **105/105**.
>
> **O padrão que fica:** frase de teste escrita à mão não é a frase que chega.
> O que chega passou pelo Whisper, que capitaliza, pontua e às vezes troca
> palavra. Medir com texto limpo mede a coisa errada.

**A confirmação não pode morrer em silêncio.** No teste por voz, duas falas sem
relação mataram um dentista pendente sem avisar, e o "pode" seguinte caiu em
`nao_sei` — o Léo saiu da conversa **acreditando ter marcado um compromisso que
nunca existiu**. Compromisso que você acredita ter e não tem é o pior resultado
possível numa agenda: pior que dar erro. Duas correções: descartar agora **diz
o que caiu** ("Descartei dentista amanhã, sexta às 9.") na mesma fala em que
atende o pedido novo, e confirmar sem nada pendente responde "não tem nada
esperando confirmação" em vez de `nao_sei`.

### Etapa 5 — Mexer em arquivo ⚠️
A primeira etapa destrutiva. Só depois que a busca (Etapa 2) estiver sólida.
- `criar_pasta(nome, dentro_de)`
- `renomear(caminho, novo_nome)` — **confirmação falada obrigatória**
- `desfazer()` — volta a última renomeação

**Fatiada em duas, decisão do Léo (set/2026).** `mover_arquivo` e
`copiar_arquivo` saíram daqui e viraram a **Etapa 5.5**, que só começa depois
que a máquina de confirmação estiver provada no uso real.

Até aqui, errar significava **abrir a coisa errada** — custo zero, é só fechar.
A partir daqui, errar significa **perder arquivo**. Fatiar deixa a etapa com uma
função destrutiva só (`renomear`) e uma inofensiva (`criar_pasta`), as duas
agindo **dentro de uma pasta só**: não há origem-e-destino, não há travessia de
sistema de arquivos, não há cópia parcial. É o menor raio de explosão possível
para provar a confirmação falada antes de ampliar.

**Três consequências de graça:**

1. **Nada de sistema de arquivos cruzado.** A máquina tem dois — `/` e o HD em
   `/mnt/cab...`, este a 90%. Mover entre eles é copiar-e-apagar: não é atômico,
   pode falhar pela metade e o desfazer vira uma segunda cópia. Renomear é um
   `os.rename` no mesmo diretório, atômico, cujo desfazer é outro `os.rename`.
2. **A armadilha do `plocate` foi adiada junto.** Pasta recém-criada não está no
   índice, que atualiza uma vez por dia, e a busca só cai no `find` quando o
   `plocate` devolve zero **depois** dos filtros. "Cria a pasta Notas" + "move o
   relatório pra Notas" é o caso de uso óbvio, e era o que quebraria primeiro.
3. **Zero código de apagar no núcleo.** Nada, em lugar nenhum, remove coisa. A
   §2.4 não é respeitada por disciplina — é respeitada por ausência.

**Onde ele pode mexer é uma lista branca**, no `[arquivos]` do `config.toml`.
É o `atalhos.toml` desta etapa: a busca varre `~` e o HD inteiros porque existe
para **achar**, e achar em todo lugar é certo; **agir** em todo lugar não é.
Caminho alvo fora da lista, ou que só chegue lá por symlink ou `..`, é recusado.

**Pasta nunca é alvo de `renomear`.** Renomear uma pasta com 3000 arquivos
dentro é uma confirmação para 3000 consequências, e não há como ouvir o que tem
lá dentro. Pasta só aparece como o `dentro_de` do `criar_pasta`.

**Duas regras que não se negociam:**

**Nunca sobrescrever.** Renomear para um nome que já existe na pasta destrói o
que estava lá, e **nenhuma confirmação pega isso** — o Léo não sabe que havia
algo com aquele nome. É o único caminho de perda silenciosa de dado na etapa.
Nome ocupado → recusa, dizendo qual é.

**A extensão é preservada sozinha.** "renomeia para proposta comercial" vira
`proposta comercial.pdf`, não `proposta comercial`. Arquivo sem extensão para de
abrir, e é uma quebra silenciosa: o arquivo continua lá, com o nome certo, e não
funciona.

> ### ⚠ O risco não estava onde este documento apontava
>
> A versão anterior desta seção tratava `mover_arquivo` como o perigo. Olhando
> o código, o perigo é outro e já existe: **quando a busca sobra exatamente 1
> resultado, o núcleo age imediatamente, sem confirmar.** É o desenho certo para
> abrir — você pediu, achou um só, abre. Seria fatal para renomear, e é o
> caminho em que o Léo tem **menos** informação: ele nunca ouviu a lista, não
> sabe que só havia um candidato nem qual era.
>
> Por isso a ação destrutiva **não reusa** o caminho da busca. Ela tem estado
> pendente próprio, no molde do `_evento_pendente` da Etapa 4, e a confirmação
> é obrigatória **inclusive com um candidato só**.

**A lixeira fica fora, e não é a mesma coisa que apagar.** A §2.4 já dizia
*"mover para a lixeira, no máximo, e só depois da Etapa 5 estar sólida"* — já a
classificou como teto do permitido e já a sequenciou depois desta etapa. O `gio`
já está instalado e tem `--list`, que mostra os locais originais, e `--restore`,
que devolve o arquivo ao lugar de onde saiu.

> **A inversão que vale registrar:** a lixeira guarda a origem e tem desfazer
> nativo. `mover_arquivo` não tem nenhum dos dois. A operação que o nome faz
> parecer perigosa é **mais reversível** que a que o documento tratava como
> comum. A lixeira fica fora por disciplina de sequência, não por risco — e o
> desfazer desta etapa é desenhado para ela encaixar depois sem redesenho.

**APROVADA — set/2026**, no teste por voz do Léo, nos seis casos: renomear com
confirmação (e **ele reconheceu o nome do arquivo de ouvido**, que era a
pergunta em aberto), renomear sem dizer o nome novo, descarte em voz alta ao
mudar de assunto no meio da confirmação, desfazer, criar pasta, e a recusa de
arquivo fora da lista branca.

- **Extração do nome novo: 10/10 verbatim**, ancoragem 1.00, e vazio corretamente
  quando o nome não foi dito.
- **Roteamento com 9 funções: 150/150** em 5 rodadas — incluindo as 15 frases da
  Etapa 1 em **75/75**. O maior salto de concorrência do projeto, de 6 para 9,
  não derrubou nada.
- **Recusas do teste isolado: 20/20** — nome ocupado, fora da lista branca, fuga
  por `..`, symlink, pasta como alvo, nome vazio, nome só com pontos, nome só
  com barra, arquivo inexistente, e `"versão 2.5"` **não** virando extensão.
- **`abridança.ppxt` × 20: zero ações.** A guarda de ancoragem da Etapa 1 segue
  de pé com três funções novas na mesa.

### A lição do "procura": a instrução mora na ferramenta que deve GANHAR

Vale muito além desta etapa, e é contraintuitiva o bastante para ficar em
destaque.

O verbo "procura" não casava com função nenhuma (0/5, achado ao fechar a Etapa
4). Acrescentá-lo à lista de verbos do `abrir` resolveu — 0/5 → 5/5 — e criou um
conflito previsto: `"procura o relatório e renomeia pra proposta"` passou a ir
para `abrir`, quando o que o Léo quer feito é renomear.

**A mesma regra, escrita nos dois lugares, deu resultados opostos:**

| onde a instrução foi escrita | acerto |
|---|---|
| na descrição do `abrir` — *"mas 'procura X para renomear' é `renomear`, não isto"* | **0/5** |
| na descrição do `renomear` — *"use ISTO sempre que a frase contiver 'renomear', inclusive quando começar com 'procura'"* | **5/5** |

**Instrução de renúncia não funciona; instrução de reivindicação funciona.**
Dizer a uma ferramenta que ela não deve pegar um caso não a impede de pegar —
o modelo já decidiu por ela quando lê o primeiro verbo da frase. Dizer à outra
que aquele caso é dela, sim. Toda vez que duas funções disputarem uma frase, a
regra vai na que deve vencer.

> **A descrição antiga do `abrir`, preservada porque foi substituída** e sem ela
> o 0/5 não pode mais ser reproduzido:
>
> *"Abre uma coisa no computador do usuário: um site, uma pasta ou um projeto.
> Use apenas quando o usuário pedir para abrir, mostrar ou acessar alguma
> coisa.\nQuem decide é o VERBO, não o assunto: 'abre', 'mostra', 'acessa' e
> 'põe na tela' são abrir."*

### Três achados da medição desta etapa

**O modelo copia o nome do alvo para o campo do nome novo.** `"Muda o nome do
print"` devolve `nome_novo='print'` em **3 de 5 rodadas**, com ancoragem
**1.00** — a palavra está mesmo na frase, então a guarda não tem o que barrar.
É o mesmo formato do bug da Etapa 4: a ancoragem detecta **invenção**, não
**palavra errada**. Guarda dirigida: nome novo igual ao alvo não é nome novo,
e vira a pergunta "Para o quê?".

*(A outra invenção, essa a guarda pega: `'novo nome'` e `'novo_nome'` pontuam
0.47, bem abaixo do corte de 0.60.)*

**"Esse aí" virou alvo.** `"Renomeia esse aí."` devolvia `alvo='esse aí'` em vez
de vazio, e o Jarvis respondia *"não achei nada chamado esse aí"* — mandando o
Léo repetir um nome que ele nunca disse. Resolvido com uma lista fechada de
demonstrativos, da mesma natureza do `_SUPERFLUAS` que já existia: limpeza
mecânica de português, não julgamento, e portanto não é trabalho para o modelo.

**O custo de ir para 9 funções, medido.** A lição da Etapa 2 diz que cada função
nova amplia o que o modelo pode confundir. Desta vez apareceu, e é pequeno:

| frase | 6 ferramentas | 9 ferramentas |
|---|---|---|
| `"Pausa."` (cru) | 10/10 | **9/10** |
| `"pausa"` | 10/10 | 10/10 |
| `"Pausa a música."` | 10/10 | 10/10 |

Só a forma crua de uma palavra só, e **a falha é `None`, não ação errada** — ele
diz "isso eu não sei fazer" e o Léo repete. É o tipo de degradação aceitável;
uma que trocasse de função não seria.

### Duas limitações conhecidas

**O desfazer morre quando ele dorme.** O estado vive no núcleo, junto das
confirmações pendentes, e o `reiniciar_conversa()` limpa tudo. Renomear, sair
por 40 segundos e voltar com "desfaz" não funciona. Foi escolha consciente do
Léo — histórico em disco é bem mais código —, e é o que a Etapa 5.5 e a lixeira
vão querer depois.

**O `dentro_de` do `criar_pasta` resolve só pela tabela de atalhos**, não pela
busca. Pasta que não está no `atalhos.toml` ele não sabe onde é, e responde
"dentro de qual pasta?". Foi de propósito: acrescentar uma segunda
desambiguação a uma operação inofensiva custaria mais estado no núcleo do que
o problema merece. Se incomodar, a saída barata é pôr a pasta no `atalhos.toml`.

### O conserto do roteamento de mídia — e o que ele ensinou

**Rodada própria, set/2026**, depois de um diagnóstico das 106 falas por voz
registradas até aqui. O diagnóstico é o motivo desta seção existir e vale mais
que o conserto: o Léo estava convencido de que o gargalo era o STT, e o número
mostrou **roteamento por um fator de 2,6** — 21 falhas do sistema contra 8 de
transcrição. A confusão fazia sentido: ele fala "Para", o Whisper acerta, e o
Jarvis diz que não sabe. A sensação é idêntica à de erro de transcrição.

Três comandos de mídia de uma palavra estavam quebrados, com transcrição
perfeita nos três: `"Para!"` e `"Continua."` em `None` 5/5, e `"Dá play."` indo
para `tocar` e perguntando "qual música?" quando ele só queria despausar.

**A lição do "procura" se confirmou pela segunda vez.** A descrição do `midia`
era renúncia pura — *"não serve para começar a tocar algo, para isso use
`tocar`"*. Trocada por reivindicação:

| | renúncia | reivindicação |
|---|---|---|
| `"Continua."` | 0/5 | **5/5** |
| `"Dá play."` | 0/5 | **5/5** |
| `"Para a música."` | `tocar` 5/5 — **ação errada** | `midia:pausar` **5/5** |
| `"Para!"` | 0/5 | **1/5** ✗ |

> **E apareceu o limite da lição.** `"Para!"` resiste à reivindicação, e o
> motivo não é de instrução: **"para" é preposição em português**. O modelo não
> consegue lê-la como imperativo isolado, por melhor que seja o prompt. Há
> palavras que prompt nenhum resolve.

**A segunda peça: lista fechada, antes do modelo.** Comando de mídia cru — a
fala inteira é o comando, sem objeto — é casado contra uma tabela de 17 entradas
em `midia.COMANDOS_CRUS`, sem passar pelo LLM. É o mesmo desenho do `_estreitar`
da Etapa 2, pelo mesmo motivo.

> **O padrão que fica: dá para consertar roteamento DIMINUINDO a superfície.**
> Toda etapa até aqui resolvia confusão de função escrevendo mais prompt, o que
> aumenta a superfície e foi o que custou o `"Continua."` na Etapa 5. A lista
> faz o contrário: as falas mais frequentes param de chegar ao modelo. Quando o
> comando é uma palavra de uma lista fechada, mandá-lo ao modelo é dar a ele
> uma chance de errar em troca de nada.
>
> **Bônus medido: 0,46s de núcleo nos logs reais viraram 0,0ms.** Num comando
> que se dá com música tocando, meio segundo é a diferença entre responder e
> obedecer.

**O que a medição impediu.** A primeira versão da lista mapeava `volta →
anterior`. Medindo o conjunto de guarda junto, `"Volta."` ia para `desfazer`
5/5 — e está certo, porque "volta atrás" é a frase da Etapa 5. A lista teria
roubado o desfazer **de forma determinística**, que é a pior espécie: sem
oscilação para denunciar. `volta` ficou de fora.

**A ordem no `processar` é a defesa, e é deliberada.** A lista é consultada
depois dos dez estados pendentes e antes do modelo. Provado, 8/8: "pausa" como
pista de busca estreita a busca, "para" como nome novo de arquivo vira nome, e
só com nada pendente é que viram comando de mídia. O casamento é contra a fala
**inteira**, então `"renomeia o relatório para proposta"` nunca casa com `para`.

**Medido no fechamento:** 15/15 nos três quebrados, 50/50 nas formas com frase,
75/75 nas frases da Etapa 1, 50/50 no roteamento com 9 funções, 30/30 nos pares
que já brigaram (incluindo `"Volta."`), 8/8 na ordem do `processar`, 23/23 no
`comando_cru` isolado.

### O volume que foi a 100, e a pergunta que faltava

**Set/2026, e machucou.** O Léo disse *"Pode dar play agora."* com música
tocando e o sistema pôs o som em **100**. O log mostra a mesma frase falhando de
dois jeitos em 50 segundos:

```
22:22:08  'Pode dar play agora.'  ->  {acao:'volume', valor:'100'}   de 40 para 100
22:22:58  'Pode dar play agora.'  ->  {acao:'volume', valor:'mais'}  de 50 para 60
```

`'100'` é invenção pura: não existe "100" naquela frase.

**Medido: a família inteira estava quebrada.** 8 rodadas por frase, 7 de 13
variantes de "dá play" produziam mudança de volume. E a fronteira não era
comprimento — `"Pode dar o play agora?"` acertava 8/8 enquanto `"Dá o play."`
errava 5/8. Era instabilidade, então enumerar formas não resolveria.

**Três defeitos somados, e só o terceiro é de desenho:**

1. `re.search(r"\d+")` em texto livre — qualquer dígito virava volume absoluto.
2. `(alvo or "mais")` — sem valor, o padrão era **aumentar**.
3. **O volume nunca passou pela máquina de confirmação.**

> ### A pergunta que faltava, e que vale para toda função nova
>
> Os dois primeiros são bugs. O terceiro é **falha de desenho**: a máquina de
> confirmação falada existe desde a Etapa 4, é usada para renomear arquivo
> desde a Etapa 5, e ninguém percebeu que **volume alto merece o mesmo
> tratamento**.
>
> A §2.3 lista "mover, renomear, sobrescrever ou apagar". Ler isso como
> fronteira em vez de exemplo foi o erro. A regra passou a ser uma pergunta,
> obrigatória em toda função nova:
>
> **Esta ação pode machucar ou destruir alguma coisa? Se sim, passa pela
> confirmação.**
>
> Volume alto machuca. Não destrói arquivo, não é irreversível, e ainda assim é
> a única coisa neste projeto que causou dor física. A pergunta pega isso; a
> lista não pegava.

**O conserto, em três camadas.** Roteamento (a lista fechada cresceu e cobre a
família "dá play" inteira, 13/13 em 8 rodadas), número lido **da transcrição** e
não do que o modelo devolveu, e confirmação falada acima de 70.

**O corte é 70 porque é o número do Léo:** ele usa o volume entre **50 e 60** no
dia a dia, e **acima de 70 já dói o ouvido**. Não é um redondo escolhido por
estética.

O parâmetro `valor` saiu do schema do `midia`. Ele não é mais lido por ninguém,
e deixar no schema um campo ignorado é armadilha para quem ler depois — além de
ser uma coisa a menos para o modelo inventar.

### "Tocando" antes de tocar — e o aquecimento que atrapalhava em silêncio

Na mesma sessão: o Léo pediu música, esperou, nada tocou, pediu outra, e **as
duas tocaram juntas**. Depois "pausa" pausou uma e "pausa" de novo pausou a
outra. Três processos `mpv` ainda estavam vivos 20 minutos depois.

**A resposta falada não provava nada.** O `tocar_audio` chamava `Popen` e a
linha seguinte já devolvia "Tocando {título}" — antes de o mpv resolver a URL,
conectar ou emitir uma amostra.

**E esperar o player declarar também não serve.** Medido com `--ao=null`:

```
0.45s   entra no barramento, PlaybackStatus = Playing   posição 0.00s
3.47s   PlaybackStatus = Playing                        posição 0.00s
6.37s   PlaybackStatus = Playing                        posição 0.10s  <- o som
```

**`PlaybackStatus` mente por ~6 segundos.** É o `CanGoNext` da Etapa 3 outra
vez: o sinal honesto é a **posição andando**. A confirmação agora espera isso, e
se a posição não anda ele diz que o som não saiu em vez de anunciar música.

**A identidade do player estava errada.** O código gravava
`_iniciado_por_nos = "org.mpris.MediaPlayer2.mpv"` fixo, mas só o primeiro mpv
de uma sessão ganha esse nome — os seguintes viram `mpv.instance{PID}`. Como a
comparação era `startswith`, "nosso" virava "qualquer mpv". O D-Bus responde
qual **PID** é dono de cada nome, e o PID é identidade de verdade.

**Substituir, não somar.** Pedir música com algo nosso tocando encerra o
anterior. **Só o que é nosso**, pelo PID — o Brave do Léo e qualquer mpv aberto
por ele ficam de fora por construção. Verificado com o Brave **tocando ao mesmo
tempo**, que é o cenário que expôs o desempate alfabético na Etapa 3: o núcleo
escolheu o nosso mpv, e o Brave continuou tocando, intocado.

**E o tempo melhorou, não piorou.** Resolvendo a URL de áudio nós mesmos, o mpv
não precisa rodar o `yt-dlp` por dentro: `tocar_audio` leva **2,8s e só fala
depois do som sair**, contra o desenho antigo que falava em ~1,8s e só produzia
som lá pelos 7,8s.

> ### O aquecimento estava atrapalhando em silêncio desde a Etapa 3
>
> Os 16 segundos do primeiro comando: **10,95s de carga fria do modelo**, mais
> 1,91s da primeira inferência com as 9 ferramentas, mais 1,76s de `yt-dlp`.
>
> Tentando melhorar, medi três aquecimentos, descarregando o modelo antes de
> cada um:
>
> | | aquecer | 1ª inferência | total |
> |---|---|---|---|
> | A — como era | 11,55s | 2,94s | 14,49s |
> | B — com tools, gerando | 17,24s | 1,06s | **18,29s** |
> | C — com tools, `num_predict=1` | 12,74s | **1,12s** | **13,86s** |
>
> **B é pior que não aquecer direito**, e o motivo é o que importa: **o Ollama
> serializa por modelo.** Um aquecimento que gera texto entra na frente do
> comando real e o atrasa. A otimização viraria o problema.
>
> A versão A carregava o modelo mas deixava o schema das ferramentas fora do
> cache — desde a Etapa 3, calada, custando ~1,9s em todo primeiro comando.
> **C é a escolha:** carrega o modelo e o schema sem gerar nada. Confirmado
> depois de implementar: a primeira inferência de verdade caiu para **0,98s**.
>
> **O padrão:** otimização em recurso serializado pode ficar na frente do que
> ela queria acelerar. Medir o total, nunca só a parte que se quis melhorar.

**O que eu não consegui provar, e não forcei.** Por que o som do primeiro mpv só
saiu perto de quando o segundo subiu. Medi o caminho do `ytdl_hook` com
`--ao=null`, que não abre dispositivo de áudio, e reproduzir a parte do áudio
exigiria pôr som para fora na máquina do Léo — o que ele pediu para não fazer na
Etapa 3. **O conserto não depende da causa:** verificando a posição andar,
qualquer travamento — ytdl, rede, dispositivo — vira "o som não saiu" em vez de
uma mentira.

### Os 15 segundos do primeiro comando, e duas lições de método

**Set/2026.** O primeiro comando depois de subir o programa custava de 10 a 50
segundos; do segundo em diante, ~6s. O Léo trouxe cinco fatos que estreitaram o
diagnóstico antes de eu medir qualquer coisa, e um deles foi decisivo:

> *"Eu espero o programa imprimir que está pronto antes de chamar. Antes disso
> ele não responde a nada, então o 'pronto' é verdade para o wake word e o STT
> — os dois respondem na hora. O que atrasa é alguma coisa que só o comando
> usa."*

**Era ler 5,23 GB de modelo do disco. Praticamente só isso.** Medido no mesmo
arquivo, esvaziando o cache de página com `posix_fadvise` entre as leituras:

| | |
|---|---|
| disco frio | **14,8s** (354 MB/s — o SSD) |
| em cache de página | **1,2s** (4311 MB/s — a RAM) |

E o custo que o Léo sentia, do wake word até a resposta:

| | cache quente | cache frio |
|---|---|---|
| antes | 6,1 – 6,3s | **18,0 – 19,4s** |
| carregando na subida | 6,2 – 6,3s | **6,2 – 6,3s** |

**O conserto foi mover a carga para a subida**, antes de imprimir "pronto". Não
cria espera nova: põe os 15 segundos dentro de uma espera que já existia e que o
Léo já respeitava. O `keep_alive` fica em 5 minutos — recarregar do cache custa
1,2s, e isso é aceitável. E o terminal diz o que está fazendo enquanto carrega:
ver 15 segundos parados sem explicação é diferente de ver o motivo.

Ficou de fora, com motivo: `keep_alive = -1` resolveria também, mas segura ~6 GB
de VRAM o dia todo, que é o que a §4 quer evitar por causa dos jogos.

**Aprovado no teste por voz do Léo: caiu para ~7s, sem a variação de antes.**

> **Fica registrado, e não é para atacar agora:** o primeiro comando ainda custa
> mais que o dobro dos seguintes — ~7s contra 1 a 3s. Sobra a primeira
> inferência com o schema das 9 ferramentas e o resto do caminho frio. Decisão
> do Léo: *"de 50 para 7 já é a diferença entre irritante e aceitável."*

> ### Lição 1 — medição em cache não é medição
>
> Na rodada anterior eu afirmei **13,86s** para este mesmo caminho. Estava
> medindo um modelo que eu já havia carregado dezenas de vezes na mesma sessão:
> **medi a RAM achando que media o disco.** O número honesto com cache frio é
> 18,7s de média — quase 40% maior — e foi essa contaminação que criou a
> contradição entre a minha medição e o que o Léo sentia.
>
> **Toda medição de carga de arquivo grande tem que dizer se o cache estava
> frio ou quente.** Sem isso o número não significa nada. E o jeito de esvaziar
> só o arquivo de interesse, sem sudo e sem mexer no resto do sistema, é
> `posix_fadvise(POSIX_FADV_DONTNEED)`.
>
> *(Duas notas de honestidade: o `mincore` que eu escrevi para reportar a fração
> em cache estava quebrado — dizia 100% antes e depois de esvaziar — e eu
> descartei o número em vez de publicá-lo. O que prova a eficácia do
> `fadvise` é a leitura de 14,8s contra 1,2s.)*

> ### Lição 2 — "pronto" tem que incluir tudo que o primeiro uso precisa
>
> O `conferir()` da subida chamava `/api/tags`, que confirma que o modelo está
> **listado** — não que está **carregado**. O wake word (16 MB) e o Whisper
> (1,1 GB) eram carregados na subida e ficavam residentes; o `qwen3:8b` não, e
> era justamente o único que só o comando usa.
>
> **"Pronto" mentia por omissão.** Não dizia nada falso: deixava de dizer que
> faltava a peça mais cara. A regra que fica: antes de anunciar que está
> pronto, carregue tudo que o primeiro uso vai pedir — ou diga o que ainda
> falta.

### Escolher o player por voz

Com o Brave e o mpv tocando, "pausa" sempre pegava o mpv. Pedir de novo pegava o
Brave — mas isso é a fila esvaziando, não escolha. E para voltar o Brave não
havia jeito nenhum.

| o Léo diz | age em |
|---|---|
| "do Brave", "da aba", "do YouTube" | o Brave |
| "do computador", "do PC", "do player", "a tua", "a que você pôs" | o mpv que o Jarvis iniciou |
| nada | a regra de sempre: o que o Jarvis iniciou ganha |

Mora no `midia.COMANDOS_CRUS`, em Python, **sem crescer o schema do modelo** —
"pausa a do Brave" é comando mais qualificador, as duas coisas mecânicas. E
quando o player pedido não existe, ele diz ("não tem nada tocando no Brave") em
vez de agir no outro: escolher errado calado é pior que dizer que não achou.

**"do navegador" foi proposto e o Léo cortou:** ele usa o Brave há mais de um ano
e não vai trocar, e sinônimo a mais é superfície a mais — a lição da rodada do
"para", aplicada por ele.

Verificado com o Brave no barramento e o nosso mpv tocando ao mesmo tempo, 12/12,
interceptando as chamadas de método para não mexer na sessão real dele — que é o
cenário que expôs o desempate alfabético na Etapa 3.

### Etapa 5.5 — Mover e copiar arquivo ⚠️
O resto da Etapa 5 original. Só começa depois que a 5 estiver rodada no uso
real — a confirmação falada tem que ter sido provada com o Léo errando de
verdade, não só em teste.
- `mover_arquivo(origem, destino)`
- `copiar_arquivo(origem, destino)` — não é destrutivo; é a saída para "na
  dúvida, não move"

**O que esta etapa traz de novo, e que a 5 não tem:** duas identificações numa
frase só (origem **e** destino, cada uma podendo ser ambígua), travessia de
sistema de arquivos, e a dependência do `plocate` desatualizado para achar
pasta recém-criada. Os três problemas foram adiados de propósito.

**Provavelmente é aqui que o desfazer precisa virar histórico em disco**, porque
mover para longe é o erro que se percebe horas depois, não na hora.

### Etapa 6 — Interface
Um app à parte, não um puxadinho. Provavelmente maior que o motor de voz.
- Esfera animada estilo átomo/eletrosfera representando o estado
  (dormindo / ouvindo / pensando / falando)
- Histórico de tudo que foi conversado e executado
- Anexar arquivos
- Roda em segundo plano, ícone na bandeja

### Etapa 7 — Ensinar ele a me entender
Arquivo de contexto que o Jarvis lê antes de cada comando: apelidos,
atalhos, jeito de falar do Léo. Quando ele erra, a correção entra ali e
ele não erra de novo.
**Isto não é treinar o modelo** — é contexto persistente. Dá o mesmo
resultado prático e roda em qualquer máquina.

### Etapa 8 — Web e resumo
- `pesquisar_web(pergunta)`
- `resumir_arquivo(caminho)`
- Resumir "o que tá aberto na minha tela" é mais difícil (depende de
  detectar a janela ativa) e pode virar sub-etapa.

### Etapa 9 — Conversa de verdade
Cérebro maior, memória de longo prazo, papo que não é comando. Aqui pode
fazer sentido plugar uma API — decisão adiada de propósito.

### Etapa 10 — Proatividade
Ele fala sem ser chamado. **Só com gatilho concreto:**
- lembrete venceu
- GPU passou de X graus
- disco quase cheio

**Não entra:** palpite sobre o estado do Léo ("tu tá cansado", "dá uma
pausa"). Ele não tem como saber isso, e errar nisso torna o assistente
insuportável.

### Futuro (fora do escopo atual)
- Ver a tela (print + modelo de visão) — ajuda com Minecraft, etc.
- Troca de persona para personagem feminina
- Integração com os outros projetos do Léo

---

## 6. O que ele NÃO vai fazer

- Executar comando arbitrário no sistema
- Apagar arquivo definitivamente
- Agir sem confirmação em coisa destrutiva
- Adivinhar o que o Léo quis dizer sem perguntar
- Comprar, pagar ou mexer em conta/senha
- Falar sozinho por palpite

---

## 7. Riscos conhecidos

| Risco | Gravidade | Como mitigar |
|---|---|---|
| Modelo local errando tool calling **em português** | Alta | Poucas funções por etapa; nomes de função em inglês, descrições em PT-BR; testar cedo (Etapa 1) |
| **Whisper alucinando em silêncio/ruído** (comando fantasma) | **Alta** | VAD obrigatório antes do STT; descartar transcrição sem fala detectada; nunca executar ação destrutiva sem confirmação falada |
| Latência do ciclo completo alta demais | ~~Alta~~ — **não se confirmou** | Medida na Etapa 0 (set/2026): STT em 0,30s para 2,72s de fala. Evidência na §5 |
| Briga por VRAM com jogos/outros projetos | Média | Carregar e descarregar sob demanda |
| Ryzen 5 3400G (4 núcleos) gargalando o TTS | Média | Piper é leve; se pesar, testar voz menor |
| Piper lendo mal texto que não é frase corrida (letra solta, número com vírgula, palavra rara) | Baixa | Observado na Etapa 0. Não bloqueia: quem escreve o texto falado é o sistema, sempre em frase corrida. Ver §5 |
| **Sem dados de falso positivo na faixa 0.10–0.50** do wake word — a escuta passiva de 10 min não produziu nada acima do piso | Baixa | Só importa se um dia quisermos baixar o limiar de 0.50. O teste seria rodar `experimento_wakeword.py --piso 0.02` por uma hora em silêncio. Enquanto o limiar for 0.50, é irrelevante |
| Ducking por aplicativo no PipeWire ser mais trabalhoso que no Windows | Baixa | Testar cedo, na Etapa 0; se complicar, adiar para depois da Etapa 3 |
| **Prompt de classificação sem o contexto que está sendo classificado** | **Alta** — confirmada na Etapa 4 | O classificador de sim/não não via a pergunta e mandava pedido novo para NAO: 60/80. Com a pergunta, 80/80. Todo prompt que classifica uma resposta tem que receber aquilo a que ela responde |
| **Medir com texto limpo em vez do que o Whisper entrega** | Média — confirmada na Etapa 4 | `'não'` acertava e `'Não'` errava, e o Whisper sempre capitaliza a primeira palavra: em produção erraria sempre. Frases de teste têm que vir com a capitalização e a pontuação que o STT produz |
| Escopo crescendo e o projeto morrendo | **Alta** | Este documento. Nada fora dele sem atualizar ele antes |

---

## 8. Pendências antes de escrever código

1. ~~Confirmar modelos e bibliotecas atuais~~ — feito (ago/2026), ver §4.
2. ~~Definir pasta do projeto e ferramenta~~ — `D:\Jarvis`, Claude Code
   no VSCode.
3. ~~Sistema operacional~~ — migrado para Linux Mint Cinnamon (ago/2026).
4. ~~Confirmar o processador~~ — feito (set/2026). É mesmo um **AMD Ryzen 5
   3400G** (4 núcleos, 8 threads), conferido via `lscpu` na máquina.
5. ~~Verificar o wake word~~ — feito (set/2026) na **Etapa 0.5**. O
   openWakeWord v0.6.0 com o modelo pronto `hey_jarvis` foi testado e
   aprovado; ver §4 e §5. **A stack não tem mais item não verificado.**
6. ~~Testar tool calling do qwen3:8b em português~~ — feito (set/2026) na
   **Etapa 1**: 15/15 na decisão, zero resoluções erradas. A arquitetura de
   lista fechada se sustenta; ver §5.

**Não há mais pendência aberta nesta seção.**

---

## 9. Método de trabalho

Igual ao que já funciona no Claude Tracker:

1. Léo descreve o que quer
2. Investigação
3. **PLAN MODE** — plano escrito, sem código
4. Léo aprova o plano
5. Só então implementar
6. Rodar/testar
7. **Léo testa manualmente** — é a fonte de verdade
8. Só depois: próxima etapa

Este documento fica na raiz da pasta do projeto e é atualizado quando uma
decisão muda. Ele é a memória do projeto — não a memória de quem estiver
ajudando.

Ao fim de cada etapa aprovada, commit e push:

```
git add .
git commit -m "Etapa N: <o que foi feito>"
git push
```
