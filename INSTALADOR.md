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
   - Falta: o script que monta o pacote, o Léo subir no Drive, e o download no
     instalador (conferindo o convite).
4. Instalador Linux (agora 8 telas: a 7ª é "Conexões", o mesmo passo a passo dos
   Ajustes, tudo opcional), com a escolha da pasta.
5. Teste limpo (usuário novo, sem nada deste PC).
6. Windows.
