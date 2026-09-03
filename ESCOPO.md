# JARVIS — Documento de Escopo

> Este arquivo é a fonte de verdade do projeto. Qualquer agente de IA que
> for mexer no código deve ler este documento **inteiro** antes de escrever
> qualquer linha. Se algo aqui conflitar com um pedido, pergunte antes de
> implementar.

Versão: 2.2. Sistema: **Linux Mint Cinnamon**.
Pasta: `~/Projetos/Jarvis`. Repositório Git privado no GitHub.
Etapas 0 e 0.5 aprovadas (set/2026). Da Etapa 1 em diante, nada feito.

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
  wake word ("Jarvis")          ← leve, roda na CPU, sempre ativo
        ↓
  carrega Whisper + LLM na GPU  ← só agora ocupa VRAM
        ↓
  fala → texto (Whisper)
        ↓
  LLM local decide qual função chamar (tool calling)
        ↓
  executa a função (código Python nosso, lista fechada)
        ↓
  resposta → fala (Piper)
        ↓
  janela de 30s aguardando novo comando
        ↓
  sem fala → descarrega modelos → volta a dormir
```

**Ciclo de vida:** dormindo (só o wake word) → acordado (30s, renovável a
cada fala) → dormindo. Isso evita segurar VRAM enquanto o Léo joga.

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

### Etapa 0.5 — Wake word
Só depois da Etapa 0 aprovada. Verificar o openWakeWord (§8.5) e colocá-lo na
frente da cadeia: rodando na CPU, sempre ativo, disparando o resto só quando
ouvir o nome. Aqui entra o ciclo de vida dormindo → acordado → dormindo
descrito na §4.
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

**Pendência técnica, registrada e não corrigida:** o
`experimento_wakeword.py` só grava `.wav` quando há disparo, o que torna
impossível auditar os quase-acertos — justamente os frames mais
interessantes quando se investiga por que algo *não* disparou. Corrigir
quando o wake word virar integração de verdade.

**Atenção ao ler esta etapa:** a aprovação cobre a **escolha da peça** —
modelo, pronúncia e limiar, medidos em experimento isolado. A integração
descrita no parágrafo acima **não foi construída**: o wake word ainda não
está na frente da cadeia, e o ciclo dormindo → acordado → dormindo da §4
continua sem existir. Isso fica para quando for integrar.

### Etapa 1 — Abrir coisas
Primeiras funções com tool calling. Risco baixo: se errar, abre a coisa
errada e pronto.
- `abrir_programa(nome)`
- `abrir_pasta(caminho)`
- `abrir_site(url_ou_nome, navegador="Brave")`

### Etapa 2 — Buscar
O Jarvis não precisa saber onde as coisas ficam. Ele precisa saber procurar.
- `buscar_arquivo(nome)` → lista de caminhos
- `buscar_pasta(nome)` → lista de caminhos
- **Desambiguação obrigatória:** achou mais de um, pergunta qual.

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
6. **Testar tool calling do qwen3:8b em português** antes de construir
   qualquer coisa em cima. Se falhar feio, a arquitetura muda.

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
