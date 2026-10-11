# JARVIS — o que existe hoje

> O estado ATUAL do projeto, curto de propósito. A história de cada decisão
> (por que, o que foi medido, o que deu errado) está no
> [`HISTORIA.md`](HISTORIA.md), que era o ESCOPO até out/2026. As medições
> brutas estão em `medicoes/`.
>
> **O que o Léo fala vale mais que este arquivo.** Quando conflitar, pergunte
> citando os dois e atualize aqui.

Pasta: `~/Projetos/Jarvis`. Repositório privado no GitHub. Linux Mint Cinnamon,
RTX 3060 12GB, Ryzen 5 3400G, 16GB RAM.

---

## 1. O que é

Assistente pessoal por voz que roda no PC do Léo e **faz coisas** dentro do
computador: abre, busca, toca, marca, move, lembra. Referência: o Jarvis do
Homem de Ferro. A visão é **conversar** com ele, não decorar comando: ele
entende a intenção, faz, e sugere jeitos melhores.

---

## 2. Regras

1. **Comando gerado pelo modelo só com aprovação na tela.** O caminho
   principal são ferramentas escritas à mão. Para o que nenhuma cobre, o
   modelo pode escrever um comando, mas o Jarvis mostra na janela e pergunta
   antes; só comando de leitura roda direto. **Nunca** roda comando que veio
   de e-mail, página web ou outro texto de fora. *(Hoje ainda não existe
   comando gerado: é tudo ferramenta fechada. A regra vale para quando entrar
   a API do Claude.)*
2. **Chutar pode, em coisa inofensiva.** Abrir, tocar, responder: ele pega o
   mais provável e diz o que fez. **Em coisa destrutiva, pergunta** quando
   houver dúvida.
3. **Ação destrutiva exige confirmação falada.** A pergunta, obrigatória em
   toda função nova: *esta ação pode machucar ou destruir alguma coisa?* Se
   sim, confirma. Inclui volume acima de 70 (foi a 100 uma vez e machucou o
   ouvido do Léo).
4. **Nunca apagar arquivo de vez.** Mandar para a lixeira pode, com
   confirmação falada. *(Ainda não implementado.)*
5. **Toda ação executada vai pro log** (`logs/`).
6. **O que ele não faz:** comprar, pagar, mexer em conta ou senha.
7. **Proatividade só com gatilho concreto** (lembrete venceu, GPU quente,
   disco cheio). Palpite sobre o estado do Léo ("tá cansado") fica de fora
   por enquanto; pode entrar no futuro.
8. **O STT nunca roda sem VAD na frente** (o Whisper inventa texto no
   silêncio).
9. **Latência baixa é prioridade.** Funcionar bem > arquitetura elegante.
10. **Nada pessoal no git.** O Jarvis tem que poder ir para outra pessoa sem
    levar as coisas do Léo (memória fica fora; atalhos tendem a virar memória).

---

## 3. Persona

Nome **Jarvis**, voz masculina (Piper, `pt_BR-faber-medium`). Fala como pessoa
normal: nem formal, nem cheio de gíria. Respostas curtas: é voz.

Tudo no `config.toml` (`[persona]`), nada chumbado no código. **No futuro vira
uma personagem feminina**, e é aí que a voz troca (Kokoro ou outra).

---

## 4. Como funciona

```
microfone ─► wake word "hey Jarvis" (CPU) ─► "Pois não?" ─► 30 s ouvindo
          ─► VAD (Silero) ─► Whisper (GPU) ─► NÚCLEO ─► resposta ─► Piper (fala)
```

- **Dormindo → acordado (30 s) → dormindo.** A janela de 30 s reinicia quando
  ele termina de responder. "Dorme aí" faz dormir na hora.
- **Núcleo e clientes.** O núcleo (`jarvis/nucleo/`) recebe texto, decide,
  executa e devolve texto; não sabe o que é microfone nem tela. O cliente de
  voz (`assistente.py`) e a janela (`interface.py`) são clientes. **É o que
  permite o cliente de celular depois. Mantenha.**
- **Assistente e janela são dois processos**, ligados por um socket
  (`jarvis/ponte/`). Um não depende do outro.
- **Dentro do núcleo, a ordem é:** pendências (confirmação, busca aberta)
  → listas fechadas em Python (mídia, tela, hora, memória) → modelo
  (`qwen3:8b` via Ollama, escolhe entre 11 ferramentas) → se nenhuma pegou,
  o modelo responde com a memória → senão "Isso eu ainda não sei fazer."

**Stack:** openWakeWord `hey_jarvis` (limiar 0.50, pronúncia inglesa ou
brasileira) · pysilero-vad · faster-whisper `large-v3-turbo` int8 na GPU ·
`qwen3:8b` no Ollama (`keep_alive` 5 min, carrega na subida) · Piper · janela
em PySide6/QML.

**VRAM:** ~7 GB com Whisper + qwen; cai para ~1,5 GB quando o Ollama solta o
qwen (5 min parado). Importa por causa dos jogos.

### Dependências de sistema (não vêm com o pip)

| peça | precisa de | sem ela |
|---|---|---|
| janela | pacote `libxcb-cursor0` | morre na subida, com erro |
| ícone na bandeja | **applet de ícones no painel do Cinnamon** | **some em silêncio**, sem erro |
| bloquear a tela | `cinnamon-screensaver` | avisa "não consigo bloquear" |
| openWakeWord | instalar com `--no-deps` (ver `requirements-wakeword.txt`) | `pip` falha no Python 3.12 |

Se a bandeja sumir noutra máquina, olhe o painel, não o gerenciador de
pacotes (**não** instalar `xapp-sn-watcher`: conflita com o Mint).

---

## 5. O que ele sabe fazer

| você diz | o que acontece |
|---|---|
| "abre o Discord", "abre o Kabum", "abre o projeto Loft" | abre **qualquer programa instalado, favorito do Brave ou projeto do VS Code**, sem cadastro (ver abaixo) |
| "fecha o Discord", "fecha a pasta Downloads", "fecha essa janela" | fecha como o × (o programa pergunta se quiser salvar); **várias janelas ou uma aba do navegador → pergunta antes** |
| "põe o Discord na frente", "vai pro terminal", "minimiza o Brave", "maximiza essa janela", "restaura o terminal" | mexe na janela, sem perguntar (inofensivo) |
| "minimiza tudo" / "mostra a área de trabalho", e "volta as janelas" | esconde tudo e traz de volta |
| "abre gravações", "abre o loft" | o que está no `atalhos.toml` ganha de tudo |
| "abre o relatório" | nada com esse nome: **busca** no disco e pergunta qual se achar vários |
| "toca X", "toca X no YouTube" | toca no mpv (só áudio) ou no Brave; só diz "tocando" depois do som sair |
| "pausa", "continua", "próxima", "aumenta o volume" | controle de mídia; "do Brave"/"do computador" escolhe o player |
| "volume 80" | **pergunta antes** (acima de 70) |
| "qual a temperatura da GPU" | status da GPU |
| "marca dentista amanhã às 15h", "o que tenho hoje" | Google Agenda: cria e lista |
| "renomeia X pra Y", "move X pra Y", "copia X pra Y" | **pergunta antes**; só em pastas liberadas no `config.toml` |
| "cria a pasta X em Y" | cria |
| "desfaz" | desfaz a última renomeação/movimento (esquece quando ele dorme) |
| "bloqueia o PC" | fala "Bloqueando." e trava a tela |
| "que horas são", "que dia é hoje" | responde na hora |
| "lembra que…", "esquece que…" | memória em `memoria.txt` (fora do git); esquecer **pergunta antes** |
| "qual o nome da minha namorada?" | responde pela memória; sem resposta, diz que não sabe |
| "esquece", "cancela", "deixa pra lá" | larga o que estiver pendente e diz o que largou |
| "dorme aí", "tchau" | "Tá bom." e dorme |

**De onde vem o que ele sabe abrir** (`catalogo.py`, lido do PC na hora, a
cada 5 min, e nunca para o git):

- **programas:** os ícones do menu (`.desktop`), Flatpak incluído. Também pelo
  nome em inglês e por apelidos comuns ("vs code", "navegador", "zap");
- **projetos do VS Code:** toda pasta já aberta nele, falada como
  "projeto <nome>";
- **favoritos do Brave:** o nome sai do endereço (`kabum.com.br` → "kabum",
  `music.youtube.com` → "youtube music"). Favorito novo vale em até 5 min,
  sem reiniciar;
- **sites mais visitados no Brave** (histórico, a partir de 3 visitas): é o que
  faz "abre o GitHub" funcionar sem favorito. Favorito ganha do histórico.

**Programa que sobe só na bandeja** (o ZapZap): se depois de abrir aparece o
ícone na bandeja mas nenhuma janela, ele abre de novo e a janela vem. Vale para
qualquer programa, sem lista; quem já abre com janela não é afetado. Precisa
de `wmctrl` e `xwininfo` (vêm no Mint).

Casou bem e sem concorrente, **ele abre e diz o nome** do que abriu, mesmo sem
certeza total (abrir é inofensivo). Dois parecidos ("whatsapp": ZapZap ou
WhatsApp Web?) → pergunta. Exceção: **programa ganha de site** ("whatsapp" é
o ZapZap, "minecraft" é o launcher); "whatsapp web" dito inteiro abre o site.

**Fechar** (`janelas.py`, via `wmctrl`): o nome casa primeiro com um programa
do catálogo (todas as janelas dele) e depois com o título das janelas ("pasta
Downloads" → a janela do Nemo chamada Downloads). Nunca fecha a área de
trabalho (`nemo-desktop`) nem a janela do Jarvis. Programa de bandeja (ZapZap)
só esconde a janela e continua rodando, igual ao ×.

**Mexer em janela** usa a mesma busca do fechar. Minimizar vale para todas as
janelas do programa; trazer, maximizar e restaurar, para a mais recente.
Minimizar não dá pelo `wmctrl` no Cinnamon (medido): usa `python-xlib` com o
pedido padrão de minimizar (ICCCM `WM_CHANGE_STATE`).

Arquivos editáveis à mão: `atalhos.toml` (o que ele abre), `config.toml`
(frases, pastas liberadas e vetadas, limites), `memoria.txt` (o que ele sabe
do Léo).

---

## 6. Como ligar

**Ele liga sozinho quando o Léo entra no PC**, com a janela escondida: só o
ícone na bandeja. Clicar no ícone (bandeja ou menu "Jarvis") abre a janela.

- **Desligar:** menu → **"Desligar Jarvis"**.
- **O × da janela só esconde a janela.** O assistente continua ouvindo.
- O terminal do assistente vai para `logs/assistente-terminal.log`.
- Parar de ligar sozinho: apagar `~/.config/autostart/jarvis.desktop`.

Por baixo:

```
~/Projetos/Jarvis/jarvis.sh               # liga e abre a janela
~/Projetos/Jarvis/jarvis.sh --na-bandeja  # liga com a janela escondida
~/Projetos/Jarvis/jarvis.sh --desligar    # desliga tudo
```

Para depurar no terminal (dois terminais, o `cd` faz parte):

```
cd ~/Projetos/Jarvis && .venv/bin/python assistente.py
cd ~/Projetos/Jarvis && .venv/bin/python interface.py
```

---

## 7. Testes

Todo teste que dispara processo roda por `./contido.sh` (teto de memória,
processos e tempo; ver CLAUDE.md).

```
.venv/bin/python regressao.py --rapido    # roteamento: rodar antes de cada commit
.venv/bin/python regressao.py             # completo (mais lento)
python3 verificar_linha.py                # o núcleo não conhece áudio
.venv/bin/python etapa0.py --autoteste    # TTS -> VAD -> STT
.venv/bin/python assistente.py --teste-ciclo
.venv/bin/python testes/terminal_identico.py
.venv/bin/python testes/testar_ponte.py
.venv/bin/python testes/testar_ciclo_eventos.py
```

Medir só quando a decisão depende de um número. A voz do Léo falando com o
Jarvis é o teste que vale; o resto se confere olhando.

---

## 8. Problemas conhecidos

- **"Para a música" abre a pasta Músicas** em vez de pausar, e "para o vídeo"
  nunca funcionou. Use "pausa". Conserto proposto: as duas frases na lista
  fechada de mídia.
- **"Procura o relatório e renomeia pra proposta"** às vezes vai para abrir:
  frase no limite entre duas funções. Temperatura 0 não resolve (ver
  HISTORIA).
- **A agenda expira a cada 7 dias** (app do Google em modo "Testing"); quando
  expira, rodar `autorizar_google.py`. Saída: duas páginas no GitHub Pages
  e publicar o app.
- Data com nome de mês ("31 de dezembro") não é entendida; a confirmação
  denuncia antes de marcar.
- A busca não acha arquivo com acento quando se fala sem acento.
- Pergunta sem resposta na memória ouve "Isso eu ainda não sei fazer".
- "Abre o monitor do sistema" não chega a chamar o abrir (o modelo não
  reconhece como pedido de abrir); "abre o System Monitor" funciona.
- O vocabulário do Whisper só conhece os nomes do `atalhos.toml`; nome de
  programa difícil (Kdenlive, Crunchyroll) pode sair errado na transcrição.
- O Piper lê mal letra solta e número com vírgula.
- Minimizar falhou **uma vez** em ~10 (a calculadora, por nome), dizendo
  "Minimizei" sem minimizar. Não reproduziu de novo; causa desconhecida.
- Música às vezes vem a versão errada (é o 1º resultado do YouTube).

---

## 9. Lições que valem para qualquer mudança

- **As camadas mentem.** O mpv diz que tem próxima faixa e não tem; o player
  diz "tocando" 6 s antes do som. Confira observando.
- **Comando curto e fixo vai numa lista fechada, antes do modelo:** 0 ms e
  sem erro de roteamento.
- **Instrução de reivindicação funciona; de renúncia, não.** Escreva na
  ferramenta que deve GANHAR a frase ("use isto quando…"), não na que deve
  perder.
- **Toda função nova é concorrência nova.** O que nenhuma descrição
  reivindica por escrito é o que cai primeiro.
- **Frase de teste tem que vir como o Whisper entrega** (maiúscula,
  pontuação). `'não'` acertava e `'Não'` errava.
- **Classificador precisa ver o que está classificando** (a pergunta junto da
  resposta).
- **Mensagem descreve o que o Léo pediu, não o estado interno.** "Não existe"
  e "não posso" são coisas diferentes.
- **Busca que acha o arquivo errado é pior que não achar nada.**
- **Antes de publicar um número, diga que pergunta ele responde.** Três
  medições já responderam a pergunta errada (cache, instrumento quebrado,
  camada errada).

---

## 10. Roteiro

Sem ordem rígida: faz, o Léo testa o que é de voz, segue.

1. **Briefing da manhã:** "bom dia" → agenda + clima + e-mails importantes
   num resumo falado. E-mail é priorizar, não ler tudo, e cuidado com o que
   sai em voz alta (tem gente na casa).
2. **API do Claude, híbrido:** local (qwen) para o rápido e privado, Claude
   para conversa e raciocínio. Decisão do Léo pesando privacidade e custo.
3. **Jarvis no celular:** PC como servidor, Tailscale (por causa do CGNAT),
   página web na tela inicial antes de qualquer APK.
4. **Proatividade** com gatilho concreto.
5. **Revisão de upgrades, sempre:** para cada coisa que ele já faz, perguntar
   se há jeito mais esperto, mais simples ou com resposta melhor, e trocar.
6. Depois: ver a tela (print + modelo de visão), personagem feminina,
   integração com os outros projetos do Léo, resumir arquivo e página.

Inspiração visual: HUD futurista com cards na tela enquanto ele fala (clima,
agenda, e-mail). A cor do Léo é roxo.
