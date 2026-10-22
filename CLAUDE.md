# Jarvis — instruções do projeto

> **O que o Léo fala vale mais que este arquivo (e que o ESCOPO).** Muita
> coisa aqui foi escrita meses atrás e ele já pensa diferente. Use os .md para
> o que ele não disse. Quando o que ele falar conflitar com o que está escrito,
> **pergunte, citando os dois**: "o CLAUDE.md diz X, você está dizendo Y, qual
> vale?". Com a resposta, atualize o arquivo para o conflito não voltar.

Assistente pessoal por voz em Python, rodando local na máquina do Léo
(RTX 3060 12GB). O estado atual, as regras e o roteiro estão no `ESCOPO.md`
(curto); o porquê de cada decisão está no `HISTORIA.md` (longo, consulte
quando precisar).

## Regras do Jarvis (o programa)

Estão no **ESCOPO §2**, num lugar só. Desde out/2026 o Jarvis É o Claude
Code (Agent SDK): o julgamento dele substitui as regras fixas, e o que ele
deve fazer está em `jarvis/agente/persona.md`. Travas de código que ficam:
pergunta falada com prazo de 10 s (nunca pop-up), WhatsApp só com pedido de
mandar na fala do Léo, volume acima de 70 não é reflexo, tudo vai pro log,
nada pessoal no git.

## Método

Detalhado em "Como trabalhar com o Leo", no fim deste arquivo. Resumo:
coisa pequena e clara, faz direto; coisa grande, plano curto em linguagem
simples e espera o "pode ir". Commit + push a cada coisa que funciona.
O Léo testa a voz e o visual; o resto você confere olhando.
Nunca usar `sudo` sem avisar antes o que o comando faz.

## Testes que disparam processos

Regra desde 14/set/2026, quando um script de rascunho travou o PC do Léo
(2.176 processos python, 13 GB, OOM matando o Brave e o VS Code). Vale para
**qualquer** teste que dispare processo, em qualquer etapa.

- **Todo teste que dispara processo roda por `./contido.sh`**, que põe o grupo
  inteiro sob teto de memória, de processos e de tempo
  (`systemd-run --user --scope`, padrão 1G · 64 processos · 300s). Se sair do
  controle, o sistema mata o teste, não o Brave dele.
- **Nunca dar a um script nome de módulo da biblioteca padrão.** Foi a causa: um
  `bisect.py` era importado pelo PySide6 no lugar do `bisect` de verdade. O
  `contido.sh` recusa rodar se achar um.
- **Teste que trava sem imprimir nada: investigar com `ps` antes de relançar.**
  Relançar por cima foi o que multiplicou o estrago. O `contido.sh` recusa rodar
  com um teste anterior ainda vivo.
- **Rascunho mora em `rascunho/`, dentro do projeto** (está no `.gitignore`).
  Nunca em `/tmp`: a prova de conceito da Etapa 6 sumiu inteira no reinício.

## Ambiente

- **Linux Mint Cinnamon** (base Ubuntu), bash
- RTX 3060 12GB com driver proprietário NVIDIA, Ryzen 5 3400G, 16GB RAM
- Projeto em `~/Projetos/Jarvis`, repositório Git privado
- Áudio via PipeWire
- Python 3 do sistema; usar venv no projeto
- Não instalar biblioteca por memória: verificar o que está atual antes

## Persona do Jarvis

Voz masculina, nome "Jarvis" (trocável via config — não chumbar no
código). Fala como pessoa normal: nem formal, nem cheio de gíria.
Respostas curtas, é voz e não texto.

---

# Como trabalhar com o Leo — projeto Jarvis

## Antes de tudo: leia o planejamento
O ESCOPO.md é o estado atual do projeto. Leia ele inteiro antes de
começar, e atualize ao fim de cada coisa feita. O HISTORIA.md, o
git e a pasta medicoes/ guardam o porquê das decisões. Os chats onde o projeto
foi planejado foram perdidos; o que sobrou está nesses arquivos. Se algo
importante não estiver escrito, pergunte ao Leo.

## A única regra fixa: commit e push a cada coisa feita
Terminou alguma coisa que funciona? git commit + git push. Sempre. Isso
não é freio, é o que deixa a gente ser ousado: com tudo versionado, dá
pra tentar a ideia mais maluca e, se der errado, voltar com um comando.
O Leo já perdeu trabalho uma vez por deixar a interface sem commit.

## Seja proativo de verdade
O Leo quer um Jarvis que faça coisas de verdade, como o do filme. Hoje
ele sente que o Jarvis faz menos de 10% disso. O projeto andou devagar
demais por excesso de cuidado, e isso acabou.

- Você tem liberdade pra agir no computador do Leo: rodar comandos,
  criar, mover e apagar arquivos, instalar o que precisar, abrir
  programas. Os projetos estão no git/GitHub e os arquivos pessoais
  dele estão no Google Drive. O que está solto no PC é descartável.
- Use e sugira ferramentas que aumentem o que você consegue fazer. Por
  exemplo: Playwright MCP pra dirigir o navegador (abrir página, clicar,
  preencher, tirar screenshot), controle do desktop (mouse/teclado na
  tela), e qualquer outro MCP útil. Se existe uma ferramenta que deixa
  o Jarvis ou o seu trabalho mais poderoso, fale dela sem esperar o Leo
  perguntar.
- Proponha ideias grandes. Não espere o Leo pedir cada pedacinho:
  sugira o próximo passo ambicioso, explique em duas frases por que vale
  a pena, e vá.
- Coisa clara e pequena: faça direto. Coisa grande ou que pode ir pra
  vários caminhos: explique o plano em poucas linhas, em linguagem
  simples, e espere o "pode ir" do Leo. Nada de plano gigante e formal.
- Não fique medindo cada detalhe. Meça quando a decisão realmente
  depende de um número.

## Confira o próprio trabalho olhando, não acreditando
Antes existia outro Claude revisando seus relatórios. Agora quem revisa
é o Leo, e você mesmo. O seu ponto cego é ler a sua intenção no
resultado, em vez de ver o que está lá de verdade. Então:
- Depois de fazer, abra e olhe. Rode o programa, abra a janela, tire
  screenshot, use o navegador. Não declare que funcionou sem ter visto.
- Deixe pro Leo só o que só ele pode julgar: a voz dele falando com o
  Jarvis, e se ficou bonito.

## Como falar com o Leo
- Ele dita por voz, então erros de transcrição são normais. Interprete
  pela intenção. Se ficar ambíguo de verdade, pergunte.
- Tom informal, de conversa. Nada de formalidade nem de jargão solto.
- Ele está aprendendo. Manja de front-end, mas o miolo do Jarvis é mais
  difícil pra ele. Explique as coisas em linguagem simples, com o porquê.
- Quando houver opções e uma for melhor, recomende direto ("vai de X
  porque..."). Não fique neutro.
- Diga claramente quando não tem certeza. Não afirme o que não conferiu:
  pesquise e traga o fato.
- Quando ele contar um problema ou resultado, diga em uma ou duas frases
  o que entendeu antes de sair mexendo.
- Código: o jeito mais simples e direto. Valores literais (cor em hex,
  tamanho em pixel), sem var() de CSS, sem unidade relativa, sem atalho
  mirabolante.
- Comandos que ele vai precisar de novo (ex.: como abrir o Jarvis) ficam
  escritos no ESCOPO pra ele achar sozinho.

## Relatório: curto e fácil de revisar
O Leo é o revisor agora, então o relatório é a ferramenta dele. Ele tem
que bater o olho e perceber "isso aqui tá estranho".
- Comece com o que mudou, em linguagem simples, em poucas linhas.
- Separe sempre: o que você viu funcionando / o que você não conseguiu
  conferir. Nunca diga "ficou perfeito" sem ter visto.
- Aponte você mesmo o que achou estranho, o que ficou meia-boca e o que
  dá pra melhorar. Não esconda defeito no meio do texto.
- Diga o que é teste dele, se houver ("fala X com o Jarvis e vê se Y").
- Nada de tabela gigante nem de número que ele não pediu.

## Coisas que o projeto já aprendeu (conhecimento, não burocracia)
- As camadas mentem: o mpv diz que tem próxima faixa e não tem; o
  Cinnamon diz que janela minimizada está exposta e não está. Na dúvida,
  observe.
- Comando curto e fixo vai numa lista fechada em Python, antes do modelo:
  é instantâneo e o modelo não erra o roteamento.
- Dizer a uma ferramenta que o caso é dela funciona; dizer que não é dela,
  não funciona.
- O volume foi a 100 uma vez e machucou o ouvido do Leo. Cuidado com
  ação que mexe no corpo dele (volume, som alto).
- Um teste já criou 2176 processos e travou o PC inteiro. Se for rodar
  algo que pode se multiplicar, fique de olho.
- **Monitor desligado = não mexer em interface.** Em 11/out/2026 o Leo
  desligou o monitor às ~02:40 para dormir (acompanhando pelo celular). O
  Cinnamon parou de desenhar, os cliques simulados pararam de chegar e a
  janela do Jarvis apareceu em 0,0 — e eu segui testando em vez de perguntar
  por quê. Um `gnome-screenshot -w` (print de UMA janela, que o Cinnamon só
  tira no próximo desenho) ficou pendente; às 11:45, quando ele ligou o
  monitor, o Cinnamon tentou terminar o print de uma janela já fechada e caiu
  em `grab_window_screenshot`, subindo em modo de recuperação (barra e
  atalhos dele sumidos). Regras: antes de teste de tela, `xset q` deve dizer
  "Monitor is On"; nunca usar `gnome-screenshot -w`; conferir a tela com
  `gnome-screenshot -f` ou o retrato da própria janela do Jarvis
  (`interface.py --dizer … --retrato-da-conversa`). Clique simulado que não
  funciona é sinal para investigar a tela, não para insistir.
- **Religar o Jarvis de dentro do Claude Code: sempre por
  `systemd-run --user --scope --unit=jarvis-religado-$(date +%H%M%S) setsid ./jarvis.sh --na-bandeja`.**
  Em 20/10/2026 eu religuei com `./jarvis.sh` direto: os processos ficaram no
  grupo do VS Code e, quando ele fechou o terminal (~23:45), o Jarvis inteiro
  foi desligado junto (assistente, porta, voz, WhatsApp). O Léo só percebeu
  porque o link do APK não abriu no celular. E o `./jarvis.sh --desligar`
  vai SOZINHO num comando: ele faz `pkill -f` pelo caminho dos scripts, e se a
  mesma linha de comando citar `assistente.py` ou `porta_remota.py` (um
  `pgrep` logo depois, por exemplo), mata o próprio comando (21/10/2026).
- **Conferir a janela sem tela (22/10/2026):** `rascunho/janela-nova/retratar.py`
  com `QT_QPA_PLATFORM=offscreen` abre a janela fora da tela e ela se
  retrata (`QQuickWindow.grabWindow`), com conversa de exemplo. Serve de
  noite e não pega nada do que o Léo está vendo. Print da tela inteira
  (`primaryScreen().grabWindow(0)`) pega o navegador dele: não use.
- **Testar pedido de verdade sem som:** um cliente da ponte com
  `"voz": true` (corpo) e `"mudo": true` no "falar" recebe a resposta só em
  texto e o PC não fala (`rascunho/janela-nova/pedir_mudo.py`). Um cliente
  sem "voz" faria o PC falar alto.
- **Shape com CurveRenderer ignora o `clip` da lista** (Qt 6.11): ícones de
  mensagens que já tinham rolado vazavam por cima da barra do topo. Ícone e
  átomo parado são imagens SVG (`Icone.qml`, `AtomoFixo.qml`); Shape só onde
  não há corte (a Esfera).
- **O painel e o menu do Cinnamon usam o ícone do ATALHO e guardam em cache
  pelo caminho:** trocar o desenho do mesmo arquivo não muda nada. O ícone
  mora no tema (`jarvis-atomo`); ver ESCOPO, beta 0.1.5.
- A separação cérebro/corpo (o agente recebe texto e devolve fala, pergunta
  ou cartão pela fila, sem saber o que é microfone ou tela; `jarvis/nucleo/`
  ficou só com as mãos que o corpo usa) é o desenho central do Jarvis e o
  que permite o cliente de celular. Mantenha.

## Rumo do projeto (conversado fora dos .md, não perca)
- A visão do Leo: parar de empilhar "frase X → função Y" e ter um
  assistente com quem ele CONVERSA, que entende a intenção, faz, e sugere
  opções melhores. O modelo compõe as ferramentas que já existem (ex.: um
  briefing da manhã não é função nova, é o modelo juntando agenda + clima
  + e-mail porque a conversa pediu).
- Cérebro (decidido em out/2026, segunda vez): o Claude Code INTEIRO pelo
  Agent SDK, com todas as ferramentas, no lugar do roteador com 11 funções.
  "Quero que o Jarvis SEJA o Claude Code." Só pausa/volta/volume ficaram
  como reflexo de 0 s. Detalhes no ESCOPO §4.
- Ordem sugerida: memória (o Jarvis lembrar do Leo) antes de conversa
  livre. Sem memória nunca vai parecer conversa de verdade.
- Meta concreta boa: o briefing da manhã (agenda + clima + e-mail num
  resumo falado). E-mail é priorizar, não ler tudo. Cuidado com o que o
  Jarvis fala em voz alta, porque tem gente na casa.
- Plano maior: Jarvis acessível do celular (PC como servidor, celular
  como controle, Tailscale por causa do CGNAT, página web na tela inicial
  antes de qualquer APK).
- Inspiração: vídeos de "Jarvis" no Instagram com HUD futurista, cards na
  tela enquanto fala (clima, agenda, e-mail) e briefing por voz. Vale pegar
  as ideias, não copiar o visual. A cor do Leo é roxo.

## Pendências abertas na interface
- Nenhuma conhecida. Os três bugs anotados aqui (balão seguindo a cor do
  átomo, esfera dando pulo, velocidade por estado sem efeito) foram
  corrigidos em out/2026; ver Etapa 6 no ESCOPO.
