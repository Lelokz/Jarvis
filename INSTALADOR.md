# Instalador da NOVA — etapa 1: o que o Jarvis usa deste PC

Levantamento de 27/10/2026. O protótipo das 7 telas (site/prototipo-instalador.html)
foi aprovado pelo Léo em 26/10. Ordem: Linux primeiro, depois Windows.

## Pacotes Python

- requirements.txt cobre quase tudo. Faltam três que a .venv tem:
  `pyside6-essentials` (6.11.2, a janela), `kokoro-onnx` (0.6.1, a voz reserva)
  e `httpx` (0.28.1).
- Os pacotes CUDA (`nvidia-*`, `onnxruntime-gpu`) só servem com placa NVIDIA.
  Sem ela, o instalador põe o `onnxruntime` normal e o Whisper roda no processador.
- A .venv daqui tem 4,6 GB, quase tudo CUDA.

## Programas do sistema

| Programa | Para quê | No PC dos testers |
|---|---|---|
| python3 3.12 + venv | tudo | o instalador confere |
| mpv + mpv-mpris | tocar música | instalar (apt) ou pular a mídia |
| notify-send | avisos | quase sempre já vem |
| pactl | volume | vem com o PipeWire/Pulse |
| loginctl, cinnamon-screensaver-command, xprop | bloqueio de tela e janelas | só Linux Mint/Cinnamon: precisa de reserva |
| nvidia-smi | ver a placa | só com NVIDIA |
| claude (Claude Code) | o cérebro | instalar e entrar com a conta DELE |
| tailscale | celular de fora de casa | opcional |

## Caminhos fixos deste PC

- jarvis.sh: `APPLIO` aponta para o HD do Léo (voz RVC). Nos testers não existe.
- atalhos.toml: a pasta "gravações" aponta para o HD. Os atalhos são do Léo:
  o instalador começa com uma lista vazia ou genérica.

## O que é do Léo e não pode ir junto

- ~/.local/share/jarvis: escola (gov.br), venice.env, memórias, WhatsApp, voz-leo
  (a impressão de voz dele), casa/CLAUDE.md, aprovações, recebidos.
- Na raiz do projeto: credenciais_google.json, token_google.json, memoria.txt,
  conversas.jsonl, agenda_ical.txt, logs, medicoes.
- No código, o "dono" é o Léo por nome: persona.md (`voz do Léo`), quem_fala.py,
  travas.py, whatsapp.py (o número dele), grupo/familia.py, escola/. Na etapa 2
  isso vira "o dono", com o nome que a pessoa digita no instalador.

## Vozes (pacote separado, etapa 3)

- Dubladas: voz-jarvis (8,8 GB) e voz-friday (2,6 GB). O instalador confere a placa
  e só baixa se ela aguentar. Senão, a Kokoro (reserva).
- Piper (vozes/, 518 MB) e wakeword (9 MB) vão sempre.

## Etapa 2 feita (28/10/2026): a NOVA num PC sem nada

Testado com `testes/testar_pc_novo.py` (pasta de usuário vazia, sem microfone):
- O nome do dono já vinha dos Ajustes ("Seu nome", ajustes.json); sem nome é
  "usuário". O instalador grava o nome que a pessoa digitar. Saíram o "Léo" do
  persona.md e a família dele do exemplo do grupo.
- Conexões começam desligadas: o WhatsApp só conta com a ponte instalada (antes
  bastava a porta 8080 aberta), celular e relógio só ficam "Pronto" com o
  Tailscale de pé, e a escola não tenta ler sem o escola.env (antes avisava
  "saiu da sua conta" para quem nunca entrou). Pediram algo de uma conexão
  desligada: ele diz para ligar em Ajustes → Conexões.
- Claude Code instalado sem conta: fala o `sem_conta` da persona, não o
  "Not logged in" em inglês. Sem o `claude`, o assistente para com a
  instrução de instalar (o instalador cuida disso).
- Sem o perfil de voz: o reconhecimento desliga, toda voz vale como o dono, e
  Ajustes → Voz e som mostra "Reconhecer a tua voz: Desligado" (janela e app).
- O microfone se escolhe em Ajustes → Voz e som; a tela 6 do instalador também.
- requirements.txt ganhou pyside6-essentials e httpx (kokoro-onnx vai com --no-deps).

## Próximas etapas

2. ~~Primeira vez: nome do dono, conta do Claude dele, microfone; WhatsApp, escola e
   Tailscale opcionais (desligados de saída).~~ Feita. (A escola saiu em 28/10.)
   - Conexões com Conectar e passo a passo, na janela e no app (28/10): WhatsApp por
     QR (janela) ou código de 8 letras (app, testado pelo Léo religando o dele),
     grupo, Tailscale, celular por QR (nova://ligar), música, relógio, atalhos e os
     conectores da conta do Claude. A ponte do WhatsApp é a do upstream +
     `instalador/ponte-whatsapp.patch`.
3. Pacote de vozes separado (Drive do Léo, só para convidados; 28/10).
   - Só os modelos vão no pacote (~1,4 GB): o timbre do Jarvis (rvc/, 97 MB) e a
     Friday (modelo F5 1,3 GB, vocab, ref). Os programas das vozes (PyTorch, F5,
     Applio; 7–12 GB) o instalador instala da internet, e só se a placa aguentar.
   - ~~Achar as vozes em qualquer pasta~~ Feito: `jarvis/vozes.py`. O instalador
     anota a pasta (ajustes.json → "pasta_vozes"); a etiqueta `nova-vozes.json`
     dentro do pacote deixa a NOVA se achar se a pasta for movida (busca na pasta
     pessoal e nos discos, ~1 s); sem achar, voz reserva e Ajustes → Voz e som
     mostra "Procurar pasta" (janela; o app mostra o estado). O jarvis.sh pergunta
     a pasta com `python -m jarvis.vozes --shell`.
   - ~~O script que monta o pacote~~ Feito: `instalador/empacotar_vozes.py` →
     HD/Arquivo/NOVA - Pacote de vozes/nova-vozes-1.zip (1,45 GB, sha256
     d64bafe1df9dfb29404c122e48ca823d89ed1267224b90118a683aa9dbcba5bd).
   - Falta: o Léo subir no Drive, e o download no instalador (conferindo o convite).
4. Instalador Linux (agora 8 telas: a 7ª é "Conexões", o mesmo passo a passo dos
   Ajustes, tudo opcional), com a escolha da pasta.
5. Teste limpo (usuário novo, sem nada deste PC).
6. Windows.

## Etapa 4: como o instalador funciona (28/10/2026)

- **Quem recebe:** só convidado. O site (login do Google + `convites/<email>`) é a
  barreira; o `link` do convite aponta para o `instalar-nova.sh` (um script
  pequeno, fora do site público). Esse script é o ÚNICO lugar com o endereço do
  pacote de vozes no Drive (`VOZES_DRIVE`): o GitHub é público, então o modelo
  em `instalador/instalar-nova.sh` vai com o campo vazio e a cópia preenchida
  nunca entra no git.
- **Sem sudo e sem Python do sistema:** o script baixa o `uv` (Astral, oficial)
  numa pasta temporária, baixa o código da NOVA do GitHub (zip do `main`) e abre
  a janela do instalador com `uv run --python 3.12 --with pyside6-essentials`.
- **A janela:** PySide6 + QML, com o tema, as fontes e o átomo da janela da
  NOVA; as 8 telas do protótipo aprovado. Código em `instalador/nova_instalador/`.
- **Tela 2 (Seu PC):** sistema, placa (`nvidia-smi`), memória, microfone
  (`pactl`), internet. Vozes dubladas: NVIDIA com 8 GB ou mais (a NOVA usa ~5,8
  GB da placa do Léo: ouvido 2,8 + Friday 2,0 + Jarvis 1,0). Abaixo: vozes leves.
- **Tela 4 (Instalação):** cada parte é um passo que recomeça de onde parou:
  código, venv (`uv`, CUDA só com NVIDIA), ouvido (Whisper), "Hey Jarvis/Friday",
  voz leve (Kokoro), Claude Code, e se for o caso as vozes dubladas (Drive +
  programas delas). No fim: atalho, ícone perto do relógio, ligar com o PC.
- **Tela 5:** o login do Claude Code da conta da PESSOA.
- **Tela 6:** o teste do microfone com o "Hey Jarvis" / "Hey Friday" de verdade.
- **Tela 7:** as Conexões, com o mesmo `jarvis/conectar.py` dos Ajustes.

### Feito em 28/10/2026 (as 8 telas)

- Telas 1–8 na janela do instalador, do tamanho do monitor (desenho em 1040 × 680
  numa escala só: ~52% da largura e 60% da altura, grande ou pequeno; arrasta,
  mas não estica nem maximiza). Logo da lateral = o ícone desenhado da janela.
- Tela 4, testada de verdade num usuário falso no HD (CPU e com dubladas): código,
  bibliotecas, Whisper, Hey Jarvis/Friday, Kokoro, Claude Code, ponte do WhatsApp,
  vozes do Drive (1,45 GB, sha ok) e os programas das vozes; a NOVA instalada ouve,
  fala, acorda, e as duas vozes dubladas tocam pelos caminhos que o instalador montou.
- Programas das vozes num ambiente só (`instalador/requisitos-vozes.txt`, 7,9 GB em
  vez de 15): PyTorch 2.11 + CUDA 12.8, a Friday (F5) e a parte de tocar do Applio
  (só `rvc/`, commit da17444, + rmvpe e contentvec do Hugging Face do Applio). O
  torchcodec vai do PyPI (a versão de placa pede bibliotecas que não vêm).
- Ponte do WhatsApp: `instalador/ponte-whatsapp/` (os 3 arquivos do upstream MIT com
  as mudanças da NOVA e o SQLite em Go puro) compilada com o Go oficial, sem gcc;
  compila também para Windows (`GOOS=windows`). O Go e o cache são apagados no fim.
- `jarvis/vozes.py --shell` diz ao jarvis.sh onde estão os programas das vozes
  (`programas_vozes` nos ajustes) e o Whisper (a Friday usa o mesmo, `--whisper`).
- Tela 5: `claude auth login` (o site mostra um código, cola na tela) + `auth status`.
- Tela 6: `jarvis/teste_microfone.py` (volume, ruído e o Hey Jarvis/Friday de verdade).
- Tela 7: `python -m jarvis.conectar` (o mesmo dos Ajustes): WhatsApp por QR,
  Tailscale, música; o Celular fica para os Ajustes, com a NOVA ligada.
- Falta: o teste limpo de ponta a ponta pela janela (com o Léo, 28/10 à noite).

## Windows (começado em 28/10/2026)

O instalador já sabe instalar no Windows (10 de 1809 ou mais novo, sem administrador).
Nada disso foi rodado num Windows de verdade ainda: daqui só deu para conferir que
todas as bibliotecas existem para Windows (`uv pip compile --python-platform
x86_64-pc-windows-msvc`), que a ponte compila para lá e que o Linux segue igual.

- **Entrada:** `instalador/instalar-nova.cmd` (o irmão do `.sh`; só ASCII, CRLF). Usa o
  curl e o tar que vêm no Windows, baixa o uv pelo `install.ps1` oficial, monta um
  Python só para a janela e abre com `pythonw` (sem terminal). Mesmo esquema do
  convite: no git com `VOZES_DRIVE` vazio.
- **Tela 2:** placa pelo `nvidia-smi` (vem com o driver) ou pelo PowerShell
  (`Win32_VideoController`); memória pela API do Windows; microfones pelo registro
  (`MMDevices\Audio\Capture`, só os ativos).
- **Tela 4:** `Scripts\python.exe` nos ambientes; sem `python-xlib`/`pulsectl`; Go
  oficial `.zip` e a ponte vira `whatsapp-bridge.exe`; Claude Code pelo `install.ps1`
  (fica em `~\.local\bin\claude.exe`; o Git é opcional); nas vozes, sem os pacotes
  `nvidia-*`/`cuda-*`/`triton` (o torch de placa do Windows já traz o CUDA) e com o
  FFmpeg 8.1.2 do gyan.dev (versão fixa, sha conferido) em `programas\ffmpeg`.
- **Atalhos:** `.lnk` no Menu Iniciar ("NOVA", "Desligar NOVA") e na pasta Inicializar
  (liga com o PC), pelo PowerShell, com o ícone desenhado em `.ico`.
- **`jarvis/ligar.py`:** o `jarvis.sh` do Windows (liga ponte, vozes, assistente,
  porta e janela; `--desligar`; `--na-bandeja`), anotando cada parte em `logs/*.pid`.
- **Nos dois sistemas:** o Python que o uv baixa para a NOVA fica em
  `<pasta>\programas\python` (antes ficava no cache do instalador: apagar o cache
  quebraria a NOVA).

### A NOVA em si no Windows (28/10/2026, com o OK do Léo)

Feito (o Linux segue igual: os 92 + 81 + 9 testes passam):
- `jarvis/canal.py`: as partes conversam por socket Unix no Linux (como antes) e por
  TCP em 127.0.0.1 no Windows, com a porta anotada no mesmo arquivo do canal. Usado
  pela ponte, pela porta do celular e pelos três servidores de voz; testado no modo
  Windows aqui (conecta, recusa servidor duplicado, apaga sobra de canal morto).
- Cadeado da janela: "named pipe" com o nome do usuário no Windows.
- `jarvis/ligar.py --desligar` no Windows: deixa `logs/desligar.pedido`, e o
  assistente sai como no ctrl+c (fecha o microfone, grava o resumo); 20 s e à força.
- Travas da voz e do grupo da família também para a ferramenta **PowerShell** do
  Claude Code (no Windows ela roda os comandos): apagar, mover, criar arquivo,
  instalar (winget, msiexec, irm | iex), desligar e fechar programa (Stop-Computer,
  Stop-Process, taskkill), bloquear a tela (LockWorkStation). No grupo, pelo
  PowerShell nunca mexe em arquivo, e `$env:`, `%VAR%` e `C:\` contam como coisa do dono.
- Tela: bloquear (`LockWorkStation`) e saber se está bloqueada; desbloquear pelo
  celular não existe no Windows (lá só com a senha).
- Volume e mudo pelo pycaw; pausar, continuar, próxima, anterior e "o que está
  tocando" pelo controle de mídia do Windows (pywinrt 3.2.1); vídeo no navegador
  padrão. Bibliotecas só para Windows no `requirements.txt` (marcador `win32`).
- Conexões: a ponte `.exe` (sem `preexec_fn`/`pkill`), o Tailscale do Windows; o
  aviso do grupo sem `notify-send`.

- Escolher microfone e saída nos Ajustes também no Windows (`jarvis/som.py`: a lista do
  DirectSound, a escolha pelo nome, o índice achado na hora de abrir cada fluxo).
- Música no Windows: o instalador põe o mpv oficial (v0.41.0) em `programas\mpv`; a
  NOVA sabe que o som saiu pela ligação de controle do mpv (named pipe), e os
  controles de mídia do Windows já pegam o mpv.
- A ponte do WhatsApp já compilada (19 MB) em vez de compilar no PC da pessoa — falta o
  Léo subir os dois arquivos (HD, "NOVA - Pacote de vozes/ponte-build") para o Drive e
  pôr os ids em `PONTE_PRONTA` (passos.py). Até lá, compila como antes.
- A janela preta do `instalar-nova.cmd` com barra de carregamento.

Falta:
- **Rodar tudo num Windows de verdade** (o PC do Chris ou uma máquina virtual):
  nada da parte do Windows foi executado num Windows ainda.
