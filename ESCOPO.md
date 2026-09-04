# JARVIS — Documento de Escopo

> Este arquivo é a fonte de verdade do projeto. Qualquer agente de IA que
> for mexer no código deve ler este documento **inteiro** antes de escrever
> qualquer linha. Se algo aqui conflitar com um pedido, pergunte antes de
> implementar.

Versão: 2.4. Sistema: **Linux Mint Cinnamon**.
Pasta: `~/Projetos/Jarvis`. Repositório Git privado no GitHub.
Etapas 0 a 2 aprovadas (set/2026). Da Etapa 3 em diante, nada feito.

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
- `mídia(pausar | próxima | anterior | volume)`
- `tocar_musica(termo)` — YouTube
- `status_pc()` — temperatura de GPU/CPU, uso, espaço em disco

### Etapa 4 — Anotar e lembrar
Só cria coisa nova. Não toca em nada existente.
- `criar_nota(texto)`
- `criar_lembrete(texto, quando)`

### Etapa 5 — Mexer em arquivo ⚠️
A etapa perigosa. Só depois que a busca (Etapa 2) estiver sólida.
- `criar_pasta(nome, dentro_de)`
- `mover_arquivo(origem, destino)`
- `renomear(caminho, novo_nome)`
- **Confirmação falada obrigatória em todas.**

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
