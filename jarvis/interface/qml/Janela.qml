import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window

// A janela grande do Jarvis (22/10/2026, protótipo aprovado pelo Léo): como
// o app do Claude — barra lateral com as conversas, a conversa no meio, a
// barra de escrever embaixo com persona, cérebro e esforço. Num chat novo, o
// átomo grande no meio e a barra logo abaixo dele.
//
// **Opaca e sem efeito na janela inteira, de propósito.** A janela pequena
// era transparente (cantos redondos) e tinha uma sombra feita com efeito, que
// redesenhava a janela inteira a cada quadro do átomo; arrastar ficava aos
// trancos ("parece 10 fps", 21/10/2026). Aqui o fundo é liso e o que anima
// só anima quando aparece (o átomo grande no chat novo, o pequeno quando ele
// está acordado).
//
// Moldura própria (sem a barra do Cinnamon): arrastar e redimensionar usam
// `startSystemMove`/`startSystemResize`, quem move é o gerenciador de janelas.
Window {
    id: janela
    width: 1440; height: 900
    minimumWidth: 900; minimumHeight: 600
    visible: !comecarNaBandeja
    color: tema.fundo
    flags: Qt.Window | Qt.FramelessWindowHint
    title: "NOVA"

    property alias estado: interno.estado
    property alias conectado: interno.conectado
    property alias nivel: interno.nivel
    property bool jogoNaFrente: false
    property string jogo: ""   // o modo jogo (o Jarvis viu um jogo aberto): o nome dele
    property bool gravando: false   // o modo gravação: o OBS gravando, o Jarvis quieto
    property bool demonstracao: false
    // Ligado pelo Python só quando existe bandeja: sem ícone no painel, uma
    // janela que se esconde ao fechar viraria um programa sem porta de volta.
    property bool fecharEsconde: false

    onClosing: function (evento) {
        if (janela.fecharEsconde) {
            evento.accepted = false;
            janela.hide();
        }
    }

    // O sinal honesto de "o Léo está vendo isto" (ver visibilidade.py).
    readonly property bool sendoVista: visibility !== Window.Minimized
                                       && visibility !== Window.Hidden
                                       && !jogoNaFrente
    readonly property bool maximizada: visibility === Window.Maximized
    readonly property color corAtual: conectado ? tema.corDoEstado(estado) : tema.corDoEstado("")

    QtObject {
        id: interno
        property string estado: "dormindo"
        property bool conectado: false
        property real nivel: 0.0
    }

    Tema {
        id: tema
        // Cada persona tem a sua cor: a Friday a dela (rosa, do config), o
        // Jarvis o azul. (A "Cor de destaque" saiu na beta 0.10.0.)
        persona: janela.persona === "friday" && janela.corPersona !== "" ? janela.corPersona : "#4da3ff"
        claro: !!(janela.ajustes && janela.ajustes.tema === "claro")
    }

    // -- o estado da tela ---------------------------------------------------
    Falas { id: falasAtual; objectName: "falasAtual" }   // a conversa ao vivo
    Falas { id: falasVendo }   // uma antiga, aberta na barra lateral
    ListModel { id: conversas } // a barra lateral

    property string conversaAtual: ""    // o id da conversa do Jarvis agora
    property string vendo: ""            // "" = a de agora; senão, o id da antiga
    property string pagina: "chat"       // "chat" | "memoria"
    property bool ajustesAbertos: false  // o painel dos Ajustes, por cima de tudo (beta 0.17.0)
    property var listaDeConversas: []
    property string modelo: "auto"
    property bool localDisponivel: false
    property string localNome: ""
    property string esforco: "medium"
    property string persona: "jarvis"
    property string corPersona: ""
    property string textoPensando: "Pensando…"
    property real usoCinco: -1
    property real voltaCinco: 0
    property real usoSemana: -1
    property real voltaSemana: 0
    property var som: null           // o evento "som" (os Ajustes, beta 0.6.0)
    property var ajustes: null       // o evento "ajustes" (volume da voz, notificações; beta 0.6.5)
    // O modo code (beta 0.18.0): o projeto aberto, a lista pra escolher e as mudanças.
    property string codeNome: ""
    property string codeCaminho: ""
    property var projetos: []
    property var mudancas: null
    property bool seletorCode: false
    // O modo code refeito (etapa 3 do tchan, 11/11/2026): os painéis do lado
    // (os botões do topo abrem e fecham), o Plano, o Contexto e o Terminal.
    property bool verMudancas: true
    property bool verTerminal: false
    property bool verPlano: false
    property bool verContexto: false
    property var plano: []
    property var programando: []
    property var estatisticas: null   // Ajustes → Uso e Tempo e foco (etapa 4)
    property var agendados: null      // a tela Agendados (etapa 5)
    property var feitos: null         // a galeria Feitos (etapa 5)
    readonly property var titulosDasConversas: {
        var t = {};
        for (var i = 0; i < listaDeConversas.length; i++) t[listaDeConversas[i].id] = listaDeConversas[i].titulo;
        return t;
    }
    property var contexto: null
    readonly property bool ladoCodeAberto: verMudancas || verTerminal || verPlano || verContexto
    ListModel { id: terminalModelo }
    function noTerminal(d) {
        if (d.limpar) { terminalModelo.clear(); return; }
        if (d.cmd !== undefined) {
            terminalModelo.append({ id: d.id, cmd: d.cmd, saida: "", erro: false, pronto: false });
            while (terminalModelo.count > 60) terminalModelo.remove(0);
            return;
        }
        for (var i = terminalModelo.count - 1; i >= 0; i--)
            if (terminalModelo.get(i).id === d.id) {
                terminalModelo.setProperty(i, "saida", d.saida || "");
                terminalModelo.setProperty(i, "erro", !!d.erro);
                terminalModelo.setProperty(i, "pronto", true);
                return;
            }
    }
    // Escreveu numa conversa antiga: primeiro o Jarvis volta pra ela, depois
    // a mensagem vai (quando a "conversa_atual" chegar com este id).
    property string esperandoContinuar: ""
    property var pendente: null

    readonly property bool boasVindas: pagina === "chat" && vendo === "" && falasAtual.count === 0

    // A hora da saudação: muda sozinha (de minuto em minuto), sem reabrir a janela.
    property int horaAgora: new Date().getHours()
    Timer { interval: 60000; running: true; repeat: true; onTriggered: janela.horaAgora = new Date().getHours() }
    property string ultimaAtividade: ""
    // PROTÓTIPO (11/11/2026, ideia do Léo): o átomo grandão, meio transparente,
    // atrás de tudo na tela inicial. Desligado até ele aprovar.
    property bool atomoNoFundo: false   // o que ele está fazendo agora (vai pro campo, "Pensando… lendo X")

    // A saudação da tela inicial (beta 0.18.5): muda com a hora e com a
    // persona. O Jarvis chama pelo nome; a Friday, de "chefinho".
    function saudacao() {
        var h = horaAgora;
        var friday = persona === "friday";
        var nome = friday ? "chefinho" : (ajustes && ajustes.nome ? ajustes.nome : "");
        var n = nome ? "<b>" + nome + "</b>" : "";
        if (h < 5) return nome ? "Madrugada, hein, " + n + "?" : "Madrugada, hein?";
        if (h < 12) return friday ? "Bom dia, " + n + "!" : (nome ? "Bom dia, " + n + "." : "Bom dia.");
        if (h < 18) return friday ? "Boa tarde, " + n + "!" : (nome ? "Boa tarde, " + n + "." : "Boa tarde.");
        return friday ? "Boa noite, " + n + "!" : (nome ? "Boa noite, " + n + "." : "Boa noite.");
    }

    // "Continuar de onde parou": as 3 conversas mais recentes (com o resumo
    // do que ele disse por último).
    readonly property var recentes: {
        var l = listaDeConversas.slice().sort(function (a, b) { return (b.quando || 0) - (a.quando || 0) });
        return l.filter(function (c) { return c.id !== conversaAtual }).slice(0, 3);
    }
    function quandoFoi(seg) {
        var d = Date.now() / 1000 - seg;
        if (d < 3600) return "há " + Math.max(1, Math.round(d / 60)) + " min";
        if (d < 6 * 3600) return "há " + Math.round(d / 3600) + " h";
        var hoje = new Date(); hoje.setHours(0, 0, 0, 0);
        if (seg >= hoje.getTime() / 1000) return "hoje";
        if (seg >= hoje.getTime() / 1000 - 86400) return "ontem";
        var dt = new Date(seg * 1000);
        return dt.getDate() + "/" + (dt.getMonth() + 1);
    }

    function grupoDe(quando) {
        var hoje = new Date(); hoje.setHours(0, 0, 0, 0);
        var dia = 24 * 3600;
        var t = quando, h = hoje.getTime() / 1000;
        if (t >= h) return "Hoje";
        if (t >= h - dia) return "Ontem";
        if (t >= h - 6 * dia) return "Esta semana";
        if (t >= h - 30 * dia) return "Este mês";
        return "Mais antigas";
    }

    function montarLista() {
        conversas.clear();
        var temAtual = false;
        for (var i = 0; i < listaDeConversas.length; i++)
            if (listaDeConversas[i].id === conversaAtual) temAtual = true;
        if (conversaAtual && !temAtual)
            conversas.append({ sessao: conversaAtual, titulo: "Chat novo", origem: "nova",
                               quando: Date.now() / 1000, grupo: "Hoje", fixada: false });
        for (var j = 0; j < listaDeConversas.length; j++) {
            var c = listaDeConversas[j];
            conversas.append({ sessao: c.id, titulo: c.titulo || "Conversa", origem: c.origem || "",
                               quando: c.quando || 0, fixada: !!c.fixada,
                               grupo: c.fixada ? "Fixadas" : grupoDe(c.quando || 0) });
        }
    }

    function tituloDe(sessao) {
        for (var i = 0; i < conversas.count; i++)
            if (conversas.get(i).sessao === sessao) return conversas.get(i).titulo;
        return "Chat novo";
    }

    function abrir(sessao) {
        pagina = "chat";
        if (!sessao || sessao === conversaAtual) {
            vendo = "";
            conversa.irProFim();
            return;
        }
        vendo = sessao;
        falasVendo.clear();
        if (typeof ponte !== "undefined")
            ponte.abrirConversa(sessao);
    }

    function novoChat() {
        pagina = "chat";
        if (vendo === "" && falasAtual.count === 0) {   // já está num chat novo
            compositor.focar();
            return;
        }
        vendo = "";
        if (typeof ponte === "undefined" || !ponte.novaConversa())
            avisar("a NOVA não está do outro lado");
        compositor.focar();
    }

    function enviar(texto, arquivos) {
        if (typeof ponte === "undefined") return;
        if (vendo !== "") {
            // Conversa antiga: o Jarvis volta pra ela, e a mensagem vai depois.
            esperandoContinuar = vendo;
            pendente = { texto: texto, arquivos: arquivos };
            if (!ponte.continuarConversa(vendo)) {
                esperandoContinuar = ""; pendente = null;
                avisar("não consegui enviar — a NOVA não está do outro lado");
            }
            return;
        }
        var ok = arquivos && arquivos.length ? ponte.enviarComAnexos(texto, arquivos)
                                             : ponte.enviarTexto(texto);
        if (!ok)
            avisar("não consegui enviar — a NOVA não está do outro lado");
    }

    function avisar(texto) {
        textoDoAviso.text = texto;
        aviso.opacity = 1;
        relogioDoAviso.restart();
    }

    function alternarMaximizar() {
        if (maximizada) janela.showNormal(); else janela.showMaximized();
    }

    // Os pedaços do texto entram na conversa em lotes (~16 por segundo), e
    // não um por um: cada atualização redesenha a fala inteira.
    Timer {
        id: escrita
        interval: 60
        property var pendentes: ({})   // bloco -> texto ainda não mostrado
        property var ordem: []
        function guardar(bloco, delta) {
            if (pendentes[bloco] === undefined) { pendentes[bloco] = ""; ordem.push(bloco); }
            pendentes[bloco] += delta;
            if (!running) start();
        }
        function esvaziar() {
            stop();
            for (var i = 0; i < ordem.length; i++)
                falasAtual.escrever(ordem[i], pendentes[ordem[i]]);
            pendentes = ({}); ordem = [];
        }
        onTriggered: esvaziar()
    }

    // Modo code: depois que ele mexe em algo, o painel Mudanças se atualiza
    // (espera 1,5 s: uma rajada de edições vira um pedido só).
    function mudouAlgo() { if (janela.codeCaminho) relerMudancas.restart() }
    // O modo code na conversa de agora (numa antiga, a tela é a de sempre).
    readonly property bool emCodeAqui: codeCaminho !== "" && pagina === "chat" && vendo === ""
    function alternarPainel(p) {
        if (p === "mudancas") { verMudancas = !verMudancas; if (verMudancas) mudouAlgo(); }
        else if (p === "terminal") verTerminal = !verTerminal;
        else if (p === "plano") verPlano = !verPlano;
        else verContexto = !verContexto;
    }
    Timer {
        id: relerMudancas
        interval: 1500
        onTriggered: if (janela.codeCaminho && typeof ponte !== "undefined") ponte.pedirMudancas(janela.codeCaminho)
    }
    Timer { // a lista da barra lateral, sem pedir a cada fala
        id: atualizarLista
        interval: 1500
        onTriggered: if (typeof ponte !== "undefined") ponte.pedirConversas()
    }

    Connections {
        target: typeof ponte !== "undefined" ? ponte : null
        ignoreUnknownSignals: true
        function onEstadoMudou(estado) {
            interno.estado = estado;
            if (estado !== "pensando") { janela.textoPensando = "Pensando…"; janela.ultimaAtividade = ""; }
            if (estado !== "pensando" && janela.codeCaminho) { janela.mudouAlgo(); ponte.pedirProjetos(); }
            // Ela pode ter anotado um recado ou feito um arquivo: a lateral e as páginas se atualizam.
            if (estado !== "pensando") { ponte.pedirAgendados(); if (janela.pagina === "feitos") ponte.pedirFeitos(); }
        }
        function onNivelMudou(v) { interno.nivel = v }
        function onConexaoMudou(ligado) {
            interno.conectado = ligado;
            if (ligado) { ponte.pedirConversas(); ponte.pedirProjetos(); ponte.pedirAgendados(); }
        }
        function onVoceDisse(texto, origem) { falasAtual.acrescentar("voce", texto, { origem: origem }) }
        function onJarvisDisse(texto, acao, perguntando, opcoes) {
            escrita.esvaziar();
            falasAtual.acrescentar("jarvis", texto, { perguntando: perguntando, opcoes: opcoes });
            atualizarLista.restart();
        }
        function onHistoricoRecebido(falas) { falasAtual.preencher(falas) }
        function onMostrar(titulo, texto) { escrita.esvaziar(); falasAtual.mostrar(titulo, texto); janela.mudouAlgo() }
        function onAtividade(texto) {
            janela.mudouAlgo();
            janela.ultimaAtividade = texto.split(" — ").slice(1).join(" — ") || texto;
            falasAtual.atividade(texto);
            janela.textoPensando = texto.split(" — ")[0] === "Pensando com calma"
                ? "Pensando com calma…" : "Pensando…";
        }
        function onAnexoFalhou(texto) { janela.avisar(texto) }
        function onAvisoMudou(tipo, voltaEm) { faixa.tipo = tipo; faixa.voltaEm = voltaEm }
        function onMemoriaTexto(texto) { }
        function onMemoriasLista(lista) { memoria.lista = lista; memoria.carregando = false }
        function onMemoriaAberta(id, titulo, texto, versao) { memoria.abrir(id, titulo, texto, versao) }
        function onMemoriaSalva(id, ok, conflito, texto, versao) { memoria.salvou(id, ok, conflito, texto, versao) }
        function onLocalMudou(disponivel, nome) { janela.localDisponivel = disponivel; janela.localNome = nome }
        function onJogoMudou(nome) { janela.jogo = nome }
        function onGravandoMudou(sim) { janela.gravando = sim }
        function onCodeMudou(nome, caminho) {
            if (caminho !== janela.codeCaminho) { janela.mudancas = null; janela.contexto = null; }
            if (nome !== janela.codeNome) ponte.pedirProjetos();
            janela.codeNome = nome; janela.codeCaminho = caminho;
            if (caminho) ponte.pedirMudancas(caminho);
        }
        function onProjetosRecebidos(lista) { janela.projetos = lista }
        function onProgramandoRecebido(lista) { janela.programando = lista }
        function onEstatisticasRecebidas(d) { janela.estatisticas = d }
        function onAgendadosRecebidos(d) { janela.agendados = d }
        function onFeitosRecebidos(l) { janela.feitos = l }
        function onMudancasRecebidas(d) { if (d.caminho === janela.codeCaminho) janela.mudancas = d }
        function onAlteracoesRecebidas(d) { falasAtual.alteracoes(d, true); janela.mudouAlgo(); ponte.pedirProjetos() }
        function onDesfeitoRecebido(d) {
            if (d.id) { falasAtual.desfeito(d); falasVendo.desfeito(d); }
            janela.mudouAlgo();
            janela.avisar(d.voltaram.length === 1 ? "Desfeito: " + d.voltaram[0] + " voltou" : "Desfeito: " + d.voltaram.length + " arquivos voltaram");
        }
        function onTerminalRecebido(d) { janela.noTerminal(d) }
        function onPlanoRecebido(l) { janela.plano = l }
        function onContextoRecebido(d) { janela.contexto = d }
        function onCerebroMudou(modelo, esforco, persona, cor) {
            janela.modelo = modelo; janela.esforco = esforco; janela.persona = persona;
            if (cor !== "") janela.corPersona = cor;
        }
        function onConversaAtual(sessao, falas, veioComFalas) {
            janela.conversaAtual = sessao;
            if (veioComFalas) {
                falasAtual.preencher(falas);
                if (janela.vendo === sessao) janela.vendo = "";
                if (janela.esperandoContinuar === sessao && janela.pendente) {
                    var p = janela.pendente;
                    janela.esperandoContinuar = ""; janela.pendente = null;
                    janela.vendo = "";
                    janela.enviar(p.texto, p.arquivos);
                }
                conversa.irProFim();
            }
            janela.montarLista();
            atualizarLista.restart();
        }
        function onConversasRecebidas(lista) { janela.listaDeConversas = lista; janela.montarLista() }
        function onConversaRecebida(sessao, falas) {
            if (sessao === janela.vendo) {
                falasVendo.preencher(falas);
                conversa.irProFim();
            }
        }
        function onEscrevendo(bloco, delta, fim, descartar) {
            if (fim) {
                escrita.esvaziar();
                falasAtual.encerrarEscrita(descartar);
            } else {
                escrita.guardar(bloco, delta);
            }
        }
        function onSomMudou(dados) { janela.som = dados; }
        function onAjustesMudou(dados) { janela.ajustes = dados; }
        function onUsoMudou(cinco, voltaCinco, semana, voltaSemana) {
            janela.usoCinco = cinco; janela.voltaCinco = voltaCinco;
            janela.usoSemana = semana; janela.voltaSemana = voltaSemana;
        }
        function onErroRecebido(motivo) {
            janela.esperandoContinuar = ""; janela.pendente = null;
            janela.avisar(motivo);
        }
    }

    Shortcut { sequence: "Ctrl+N"; onActivated: janela.novoChat() }
    Shortcut { sequence: "Ctrl+K"; onActivated: lateral.focarBusca() }
    Shortcut { sequence: "Esc"; onActivated: if (janela.ajustesAbertos) janela.ajustesAbertos = false; else janela.abrir("") }

    // -- a barra lateral -------------------------------------------------------
    Lateral {
        id: lateral
        width: 280
        height: parent.height
        tema: tema
        conversas: conversas
        selecionada: janela.vendo || janela.conversaAtual
        atual: janela.conversaAtual
        pagina: janela.pagina
        estado: janela.estado
        conectado: janela.conectado
        jogo: janela.jogo
        gravando: janela.gravando
        corAtual: janela.corAtual
        nivel: janela.nivel
        sendoVista: janela.sendoVista
        programando: janela.programando
        qtosAgendados: janela.agendados && janela.agendados.recados ? janela.agendados.recados.length : 0
        codeCaminho: janela.codeCaminho
        onEntrarCode: function (c) { if (typeof ponte !== "undefined") ponte.entrarCode(c) }
        onEscolherProjeto: { janela.seletorCode = true; if (typeof ponte !== "undefined") ponte.pedirProjetos(); }
        onNovoChat: janela.novoChat()
        onAbrir: function (sessao) { janela.abrir(sessao) }
        onRenomear: function (sessao, titulo) {
            if (typeof ponte !== "undefined") ponte.renomearConversa(sessao, titulo);
        }
        onFixar: function (sessao, sim) {
            if (typeof ponte !== "undefined") ponte.fixarConversa(sessao, sim);
        }
        onApagar: function (sessao) {
            if (janela.vendo === sessao) janela.abrir("");
            if (typeof ponte !== "undefined") ponte.apagarConversa(sessao);
            janela.avisar("Conversa mandada pra lixeira");
        }
        onIrPara: function (p) {
            if (p === "ajustes") {
                // A lista de som e o estado das conexões vêm de novo: um fone
                // plugado ou o celular que conectou agora aparecem.
                janela.ajustesAbertos = true;
                if (typeof ponte !== "undefined") { ponte.pedirSom(); ponte.pedirAjustes(); }
                return;
            }
            janela.pagina = p;
            if (p === "agendados" && typeof ponte !== "undefined") ponte.pedirAgendados();
            if (p === "feitos" && typeof ponte !== "undefined") ponte.pedirFeitos();
            if (p === "memoria") {
                memoria.voltarParaLista();
                memoria.carregando = memoria.lista.length === 0;
                if (typeof ponte === "undefined" || !ponte.pedirMemorias())
                    memoria.carregando = false;
            }
        }
        onArrastar: janela.startSystemMove()
        onAlternarMaximizar: janela.alternarMaximizar()
    }

    // -- a área principal --------------------------------------------------------
    Item {
        id: principal
        anchors { left: lateral.right; right: parent.right; top: parent.top; bottom: parent.bottom }

        // A barra de cima: o título, o que está valendo e os botões da janela.
        Item {
            id: topo
            width: parent.width
            height: 56
            DragHandler { target: null; onActiveChanged: if (active) janela.startSystemMove() }
            TapHandler { onDoubleTapped: janela.alternarMaximizar() }

            // No modo code (etapa 3): "</> Loft ⌄" (abre a lista dos projetos)
            // e o ramo, no lugar do título da conversa.
            Row {
                id: tituloCode
                visible: janela.emCodeAqui
                anchors.verticalCenter: parent.verticalCenter
                x: 22
                spacing: 10
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    height: 32; radius: 8; width: linhaTitCode.width + 16
                    color: areaTitCode.containsMouse || janela.seletorCode ? tema.superficie2 : "transparent"
                    Row {
                        id: linhaTitCode
                        anchors.centerIn: parent; spacing: 8
                        Icone { anchors.verticalCenter: parent.verticalCenter; caminho: tema.icones.codigo
                                cor: tema.persona; tamanho: 17; espessura: 1.9 }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: janela.codeNome.replace(/^Projeto /, "")
                               color: tema.texto; font.family: tema.familia; font.pixelSize: 15; font.weight: Font.DemiBold }
                        Icone { anchors.verticalCenter: parent.verticalCenter; caminho: tema.icones.seta
                                cor: tema.textoFraco; tamanho: 13 }
                    }
                    MouseArea {
                        id: areaTitCode
                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            janela.seletorCode = !janela.seletorCode;
                            if (janela.seletorCode && typeof ponte !== "undefined") ponte.pedirProjetos();
                        }
                    }
                }
                Rectangle {
                    visible: !!janela.mudancas && janela.mudancas.git
                    anchors.verticalCenter: parent.verticalCenter
                    height: 24; radius: 6; width: linhaRamo.width + 16
                    color: "transparent"; border.width: 1; border.color: tema.tracoForte
                    Row {
                        id: linhaRamo
                        anchors.centerIn: parent; spacing: 6
                        Icone { anchors.verticalCenter: parent.verticalCenter; caminho: tema.icones.ramo
                                cor: tema.textoFraco; tamanho: 12; espessura: 1.7 }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: !janela.mudancas ? "" : (janela.mudancas.ramo || "?")
                                  + (janela.mudancas.a_frente > 0 ? " · " + janela.mudancas.a_frente + " commit"
                                     + (janela.mudancas.a_frente === 1 ? "" : "s") + " esperando push" : "")
                            color: tema.textoFraco; font.family: tema.mono; font.pixelSize: 12
                        }
                    }
                }
            }

            Row {
                visible: !janela.emCodeAqui
                anchors.verticalCenter: parent.verticalCenter
                x: 28
                spacing: 12
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, topo.width - 420)
                    elide: Text.ElideRight
                    text: janela.pagina === "memoria" ? "Memórias"
                        : janela.pagina === "agendados" ? "Agendados"
                        : janela.pagina === "feitos" ? "Feitos"
                        : janela.pagina === "ajustes" ? "Ajustes"
                        : janela.tituloDe(janela.vendo || janela.conversaAtual)
                    color: janela.boasVindas ? tema.textoFraco : tema.texto
                    font.family: tema.familia
                    font.pixelSize: 15
                    font.weight: Font.Medium
                }
                // Só o aviso "Conversa antiga": o cérebro e o esforço já estão
                // embaixo do campo (pedido do Léo, 11/11/2026).
                Rectangle {
                    visible: janela.pagina === "chat" && janela.vendo !== ""
                    anchors.verticalCenter: parent.verticalCenter
                    height: 22
                    width: textoPilula.implicitWidth + 18
                    radius: 11
                    color: janela.vendo ? "#2a2114" : tema.superficie
                    border.width: 1
                    border.color: janela.vendo ? "#5c4422" : tema.traco
                    Text {
                        id: textoPilula
                        anchors.centerIn: parent
                        text: janela.vendo ? "Conversa antiga"
                            : compositor.nomeDoModelo() + " · esforço " + compositor.nomeDoEsforco().toLowerCase()
                        color: janela.vendo ? "#ffcf8a" : tema.textoFraco
                        font.family: tema.familia
                        font.pixelSize: 12
                    }
                }
            }

            // Os botões dos painéis do modo code (etapa 3): abrem e fecham cada um.
            Row {
                id: botoesPaineis
                visible: janela.emCodeAqui
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: botoesJanela.left
                anchors.rightMargin: 18
                spacing: 4
                Repeater {
                    model: [
                        { id: "mudancas", nome: "Mudanças", icone: tema.icones.mudancas,
                          conta: janela.mudancas && janela.mudancas.arquivos ? String(janela.mudancas.arquivos.length || "") : "" },
                        { id: "terminal", nome: "Terminal", icone: tema.icones.terminal, conta: "" },
                        { id: "plano", nome: "Plano", icone: tema.icones.plano,
                          conta: janela.plano.length ? janela.plano.filter(function (p) { return p.estado === "completed" }).length + "/" + janela.plano.length : "" },
                        { id: "contexto", nome: "Contexto", icone: tema.icones.contexto, conta: "" },
                    ]
                    Rectangle {
                        required property var modelData
                        readonly property bool aberto: modelData.id === "mudancas" ? janela.verMudancas
                                                     : modelData.id === "terminal" ? janela.verTerminal
                                                     : modelData.id === "plano" ? janela.verPlano : janela.verContexto
                        height: 32; radius: 8; width: linhaPainel.width + 20
                        color: aberto ? tema.realce : areaPainel.containsMouse ? tema.superficie2 : "transparent"
                        border.width: aberto ? 1 : 0; border.color: tema.tracoForte
                        Row {
                            id: linhaPainel
                            anchors.centerIn: parent; spacing: 6
                            Icone { anchors.verticalCenter: parent.verticalCenter; caminho: modelData.icone; tamanho: 14
                                    espessura: 1.8; cor: parent.parent.aberto ? tema.texto : tema.textoFraco }
                            Text { anchors.verticalCenter: parent.verticalCenter; text: modelData.nome
                                   color: parent.parent.aberto ? tema.texto : tema.textoFraco
                                   font.family: tema.familia; font.pixelSize: 13 }
                            Rectangle {
                                visible: modelData.conta !== ""
                                anchors.verticalCenter: parent.verticalCenter
                                height: 18; radius: 5; width: tConta.implicitWidth + 10
                                color: tema.superficie2; border.width: 1; border.color: tema.tracoForte
                                Text { id: tConta; anchors.centerIn: parent; text: modelData.conta; color: tema.textoMedio
                                       font.family: tema.familia; font.pixelSize: 11 }
                            }
                        }
                        MouseArea {
                            id: areaPainel
                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: janela.alternarPainel(modelData.id)
                        }
                    }
                }
            }

            Rectangle {
                id: botaoCode
                visible: !janela.emCodeAqui
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: botoesJanela.left
                anchors.rightMargin: 10
                height: 30; radius: 15
                width: textoCode.implicitWidth + 30
                color: janela.codeNome ? Qt.rgba(tema.persona.r, tema.persona.g, tema.persona.b, 0.18)
                     : areaCode.containsMouse ? tema.superficie2 : "transparent"
                border.width: 1
                border.color: janela.codeNome ? tema.persona : tema.traco
                Text {
                    id: textoCode
                    anchors.centerIn: parent
                    text: janela.codeNome ? "</>  Code · " + janela.codeNome.replace(/^Projeto /, "") : "</>  Code"
                    color: janela.codeNome ? tema.texto : tema.textoMedio
                    font.family: tema.familia; font.pixelSize: 13; font.weight: Font.Medium
                }
                MouseArea {
                    id: areaCode
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        janela.seletorCode = !janela.seletorCode;
                        if (janela.seletorCode && typeof ponte !== "undefined") ponte.pedirProjetos();
                    }
                }
            }

            Row {
                id: botoesJanela
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                anchors.rightMargin: 10
                spacing: 4
                Repeater {
                    model: [
                        { icone: "minimizar", acao: "min" },
                        { icone: janela.maximizada ? "restaurar" : "maximizar", acao: "max" },
                        { icone: "fechar", acao: "fechar" },
                    ]
                    Rectangle {
                        required property var modelData
                        width: 40; height: 32; radius: 8
                        color: areaBotao.containsMouse
                               ? (modelData.acao === "fechar" ? "#c4423f" : tema.superficie2) : "transparent"
                        Behavior on color { ColorAnimation { duration: tema.rapido } }
                        Icone {
                            anchors.centerIn: parent
                            caminho: tema.icones[modelData.icone]
                            cor: areaBotao.containsMouse ? tema.texto : tema.textoFraco
                            tamanho: 16
                            espessura: 1.6
                        }
                        MouseArea {
                            id: areaBotao
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                if (modelData.acao === "min") janela.showMinimized();
                                else if (modelData.acao === "max") janela.alternarMaximizar();
                                else janela.close();
                            }
                        }
                    }
                }
            }
            Rectangle {
                anchors.bottom: parent.bottom; width: parent.width; height: 1
                color: tema.traco
                opacity: janela.boasVindas ? 0 : 1
            }
        }

        // -- o chat ----------------------------------------------------------------
        CodeLado {
            id: painelCode
            anchors { top: topo.bottom; right: parent.right; bottom: parent.bottom }
            width: visible ? Math.min(580, Math.max(360, principal.width * 0.34)) : 0
            visible: janela.emCodeAqui && janela.ladoCodeAberto
            tema: tema
            caminho: janela.codeCaminho
            mudancas: janela.mudancas
            plano: janela.plano
            contexto: janela.contexto
            terminal: terminalModelo
            ocupado: janela.estado === "pensando"
            verMudancas: janela.verMudancas
            verTerminal: janela.verTerminal
            verPlano: janela.verPlano
            verContexto: janela.verContexto
            onFechar: function (p) { janela.alternarPainel(p) }
            onCommit: if (typeof ponte !== "undefined") ponte.git("commit")
            onPush: if (typeof ponte !== "undefined") ponte.git("push")
            onDesfazerArquivo: function (arq) { if (typeof ponte !== "undefined") ponte.desfazerGit(janela.codeCaminho, arq) }
        }

        Item {
            id: areaDoChat
            anchors { top: topo.bottom; left: parent.left; right: painelCode.visible ? painelCode.left : parent.right; bottom: parent.bottom }
            visible: janela.pagina === "chat"
            readonly property real largura: Math.min(780, width - 64)

            Conversa {
                id: conversa
                anchors { top: parent.top; left: parent.left; right: parent.right; bottom: faixa.top }
                anchors.bottomMargin: 8
                visible: !janela.boasVindas
                tema: tema
                falas: janela.vendo !== "" ? falasVendo : falasAtual
                pensando: janela.vendo === "" && janela.conectado && janela.estado === "pensando"
                textoPensando: janela.textoPensando
                corPensando: tema.corDoEstado("pensando")
                onCopiar: function (t) { if (typeof ponte !== "undefined") ponte.copiar(t) }
                onResponder: function (t) { janela.enviar(t, []) }
                onOuvir: function (t) {
                    if (typeof ponte === "undefined" || !ponte.repetir(t)) janela.avisar("a NOVA não está do outro lado");
                }
                onAvaliar: function (t, nota) {
                    if (typeof ponte !== "undefined" && ponte.avaliar(t, nota))
                        janela.avisar(nota === "boa" ? "Anotado: tu gostou dessa" : "Anotado: essa não ficou boa");
                }
                onDesfazer: function (id, arq) {
                    if (typeof ponte === "undefined" || !ponte.desfazer(id, arq)) janela.avisar("a NOVA não está do outro lado");
                }
                onVerArquivo: function (arq) {
                    if (!janela.codeCaminho) { janela.avisar("Abre o modo code nesse projeto pra ver as mudanças"); return; }
                    janela.verMudancas = true; janela.mudouAlgo(); painelCode.escolher(arq);
                }
            }

            // O átomo no fundo (protótipo): desenhado em 460 px e esticado,
            // atrás de tudo, meio transparente. Só na tela inicial.
            Item {
                id: fundoAtomo
                anchors.fill: parent
                visible: janela.atomoNoFundo && opacity > 0
                opacity: janela.boasVindas ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: tema.lento } }
                clip: true
                Esfera {
                    id: esferaFundo
                    objectName: "esferaFundo"
                    // O núcleo logo acima da caixa de escrever, e o átomo inteiro
                    // na tela (sem cortar em cima): o tamanho é o que cabe.
                    readonly property real centroY: compositor.y - 30
                    readonly property real ladoFundo: Math.min(Math.max(fundoAtomo.width, fundoAtomo.height) * 0.5,
                                                          2 * (centroY - 16))
                    width: 460; height: 460
                    x: (parent.width - width) / 2
                    y: centroY - height / 2
                    transform: Scale { origin.x: 230; origin.y: 230
                                       xScale: Math.max(0.3, esferaFundo.ladoFundo / 460); yScale: xScale }
                    opacity: tema.claro ? 0.30 : 0.22
                    readonly property bool vivo: janela.conectado
                    corDeFundo: tema.fundo
                    parada: !vivo
                    sendoVista: janela.sendoVista && janela.boasVindas && janela.atomoNoFundo
                    nivel: janela.nivel
                    cor: janela.corAtual
                    velocidade: !vivo ? 0.0 : janela.estado === "pensando" ? 1.6 : janela.estado === "dormindo" ? 0.3 : 0.8
                    brilho: !vivo ? 0.3 : 0.9
                }
                // Escurece as bordas: o átomo some no fundo, sem cortar seco.
                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        orientation: Gradient.Vertical
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.80; color: "transparent" }
                        GradientStop { position: 1.0; color: tema.fundo }
                    }
                }
            }

            // O chat novo: o átomo grande, a saudação e (logo abaixo) a barra.
            Column {
                id: boasVindas
                anchors.horizontalCenter: parent.horizontalCenter
                y: Math.max(16, (parent.height - (height + 30 + compositor.height + (cartoes.visible ? 190 : 20))) / 2 - 10)
                visible: opacity > 0
                opacity: janela.boasVindas ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: tema.normal } }
                spacing: 0

                Esfera {
                    id: esfera
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: !janela.atomoNoFundo
                    // Em tela grande ele cresce (11/11/2026: 230 px ficava miúdo no 1080p do Léo).
                    width: Math.min(370, areaDoChat.height * 0.36)
                    height: janela.atomoNoFundo ? 0 : width
                    readonly property bool vivo: janela.conectado
                    corDeFundo: tema.fundo
                    parada: !vivo
                    pulsando: vivo && janela.estado === "dormindo"
                    sendoVista: janela.sendoVista && janela.boasVindas
                    nivel: janela.nivel
                    cor: janela.corAtual
                    escala: !vivo ? 0.80
                          : janela.estado === "escutando" ? 1.14
                          : janela.estado === "falando" ? 1.06
                          : janela.estado === "pensando" ? 1.02
                          : janela.estado === "dormindo" ? 0.88 : 1.0
                    velocidade: !vivo ? 0.0
                              : janela.estado === "pensando" ? 2.2
                              : janela.estado === "falando" ? 1.25
                              : janela.estado === "escutando" ? 1.15
                              : janela.estado === "dormindo" ? 0.35 : 1.0
                    turbulencia: !vivo ? 0.0
                               : janela.estado === "pensando" ? 1.0
                               : janela.estado === "escutando" ? 0.35
                               : janela.estado === "falando" ? 0.25 : 0.0
                    brilho: !vivo ? 0.28
                          : janela.estado === "dormindo" ? 0.7
                          : janela.estado === "pensando" ? 1.2 : 1.0
                }
                Item { width: 1; height: 18 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: janela.saudacao()
                    textFormat: Text.StyledText
                    color: tema.texto
                    font.family: tema.familia
                    font.pixelSize: 36
                    font.weight: Font.Light
                    font.letterSpacing: -0.5
                }
                Item { width: 1; height: 8 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: janela.conectado ? "Fala \u201cHey " + (janela.persona === "friday" ? "Friday" : "Jarvis") + "\u201d ou escreve aqui embaixo"
                                           : "Esperando a NOVA subir…"
                    color: tema.textoFraco
                    font.family: tema.familia
                    font.pixelSize: 15
                }
            }

            // Continuar de onde parou (beta 0.18.5): as 3 conversas mais
            // recentes, com o que ele disse por último. Clicar abre.
            Column {
                id: cartoes
                anchors.horizontalCenter: parent.horizontalCenter
                y: compositor.y + compositor.height + 34
                width: areaDoChat.largura
                spacing: 14
                visible: opacity > 0 && janela.recentes.length > 0
                opacity: janela.boasVindas && janela.conectado ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: tema.normal } }
                Item {
                    width: parent.width; height: 18
                    Text { text: "Continuar de onde parou"; color: tema.textoFraco; font.family: tema.familia; font.pixelSize: 13 }
                    Text {
                        anchors.right: parent.right
                        text: "Ver todas"
                        color: areaVerTodas.containsMouse ? tema.texto : tema.textoFraco
                        font.family: tema.familia; font.pixelSize: 13
                        MouseArea { id: areaVerTodas; anchors.fill: parent; hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor; onClicked: lateral.focarBusca() }
                    }
                }
                Row {
                    spacing: 14
                    Repeater {
                        model: janela.recentes
                        Rectangle {
                            id: cartao
                            required property var modelData
                            required property int index
                            width: (cartoes.width - 28) / 3
                            height: 116
                            radius: 14
                            color: areaCartao.containsMouse ? tema.superficie2 : tema.superficie
                            border.width: 1
                            border.color: areaCartao.containsMouse ? tema.tracoForte : tema.traco
                            Behavior on color { ColorAnimation { duration: tema.rapido } }
                            // Entram um depois do outro.
                            opacity: 0
                            y: 8
                            Component.onCompleted: entrada.start()
                            ParallelAnimation {
                                id: entrada
                                SequentialAnimation {
                                    PauseAnimation { duration: 80 * cartao.index }
                                    NumberAnimation { target: cartao; property: "opacity"; to: 1; duration: 320; easing.type: Easing.OutCubic }
                                }
                                SequentialAnimation {
                                    PauseAnimation { duration: 80 * cartao.index }
                                    NumberAnimation { target: cartao; property: "y"; to: 0; duration: 320; easing.type: Easing.OutCubic }
                                }
                            }
                            Column {
                                x: 15; y: 14
                                width: parent.width - 30
                                spacing: 6
                                Text {
                                    width: parent.width
                                    elide: Text.ElideRight
                                    text: cartao.modelData.titulo || "Conversa"
                                    color: tema.texto
                                    font.family: tema.familia; font.pixelSize: 14; font.weight: Font.Medium
                                }
                                Text {
                                    width: parent.width
                                    height: 36
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                    text: cartao.modelData.ultima || "Sem resumo ainda."
                                    color: tema.textoFraco
                                    font.family: tema.familia; font.pixelSize: 13
                                    lineHeight: 1.1
                                }
                            }
                            Row {
                                x: 15
                                anchors.bottom: parent.bottom; anchors.bottomMargin: 12
                                spacing: 6
                                Icone {
                                    anchors.verticalCenter: parent.verticalCenter
                                    caminho: cartao.modelData.origem === "voz" ? tema.icones.voz
                                           : cartao.modelData.origem === "celular" ? tema.icones.celular
                                           : cartao.modelData.origem === "relogio" ? tema.icones.relogio : tema.icones.teclado
                                    cor: tema.muitoFraco
                                    tamanho: 12
                                }
                                Text {
                                    text: ({ voz: "voz", celular: "celular", relogio: "relógio" }[cartao.modelData.origem] || "texto")
                                          + " · " + janela.quandoFoi(cartao.modelData.quando || 0)
                                    color: tema.muitoFraco
                                    font.family: tema.familia; font.pixelSize: 12
                                }
                            }
                            MouseArea {
                                id: areaCartao
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: janela.abrir(cartao.modelData.id)
                            }
                        }
                    }
                }
            }

            // Lendo uma conversa antiga: o que for escrito continua ela.
            Rectangle {
                id: avisoAntiga
                visible: janela.vendo !== ""
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: compositor.top
                anchors.bottomMargin: 8
                width: linhaAntiga.width + 24
                height: 30
                radius: 15
                color: tema.superficie
                border.width: 1
                border.color: tema.traco
                Row {
                    id: linhaAntiga
                    anchors.centerIn: parent
                    spacing: 10
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "O que tu escrever aqui continua esta conversa"
                        color: tema.textoFraco
                        font.family: tema.familia
                        font.pixelSize: 12
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Voltar pra de agora"
                        color: tema.persona
                        font.family: tema.familia
                        font.pixelSize: 12
                        font.weight: Font.Medium
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: janela.abrir("")
                        }
                    }
                }
            }

            // O aviso do cérebro de nuvem: limite acabou / sem internet.
            Rectangle {
                id: faixa
                property string tipo: "ok"
                property real voltaEm: 0
                property real agora: Date.now() / 1000
                readonly property bool ativa: (tipo === "limite" && (voltaEm === 0 || voltaEm > agora))
                                              || tipo === "offline"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: janela.vendo !== "" ? avisoAntiga.top : compositor.top
                anchors.bottomMargin: ativa ? 8 : 0
                width: areaDoChat.largura
                height: ativa ? textoDaFaixa.implicitHeight + 18 : 0
                visible: ativa
                radius: 10
                color: tipo === "offline" ? "#2a1618" : "#2a2114"
                border.width: 1
                border.color: tipo === "offline" ? "#ff6b6b" : "#ffb454"

                function hora(seg) {
                    var d = new Date(seg * 1000);
                    return d.getHours() + ":" + ("0" + d.getMinutes()).slice(-2);
                }
                function falta(seg) {
                    var min = Math.max(1, Math.round((seg - agora) / 60));
                    var h = Math.floor(min / 60), m = min % 60;
                    return (h ? h + "h" : "") + (h && m ? ("0" + m).slice(-2) : (m + " min"));
                }
                Text {
                    id: textoDaFaixa
                    anchors.centerIn: parent
                    width: parent.width - 24
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    color: faixa.tipo === "offline" ? "#ff9c9c" : "#ffcf8a"
                    font.family: tema.familia
                    font.pixelSize: 13
                    text: faixa.tipo === "offline"
                          ? "Sem internet · só abrir, fechar e mexer nas janelas até ela voltar"
                          : faixa.voltaEm > 0
                            ? "Limite do Claude acabou · volta às " + faixa.hora(faixa.voltaEm)
                              + " (falta " + faixa.falta(faixa.voltaEm) + ")"
                            : "Limite do Claude acabou"
                }
                Timer {
                    running: faixa.tipo === "limite"
                    interval: 30000
                    repeat: true
                    onTriggered: faixa.agora = Date.now() / 1000
                }
            }

            Compositor {
                id: compositor
                width: areaDoChat.largura
                anchors.horizontalCenter: parent.horizontalCenter
                y: janela.boasVindas ? boasVindas.y + boasVindas.height + 30
                                     : parent.height - height - 16
                Behavior on y { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
                tema: tema
                conectado: janela.conectado
                estado: janela.estado
                nivel: janela.nivel
                fazendo: janela.ultimaAtividade
                mostrarDica: !janela.boasVindas
                modelo: janela.modelo
                localDisponivel: janela.localDisponivel
                localNome: janela.localNome
                esforco: janela.esforco
                persona: janela.persona
                menusParaCima: !janela.boasVindas
                emCode: janela.codeCaminho !== ""
                permissao: janela.ajustes && janela.ajustes.code_permissao ? janela.ajustes.code_permissao : "auto"
                onEscolherPermissao: function (v) { if (typeof ponte !== "undefined") ponte.mudarAjusteCode("code_permissao", v) }
                // Pensando OU falando: o Parar cala a voz no meio da frase (26/10/2026).
                trabalhando: janela.vendo === "" && janela.conectado
                             && (janela.estado === "pensando" || janela.estado === "falando")
                onParar: if (typeof ponte !== "undefined") ponte.parar()
                onEnviar: function (texto) { janela.enviar(texto, []) }
                onEnviarComAnexos: function (texto, arquivos) { janela.enviar(texto, arquivos) }
                onAvisar: function (texto) { janela.avisar(texto) }
                onEscolherModelo: function (v) {
                    janela.modelo = v;
                    if (typeof ponte !== "undefined") ponte.definirCerebro(v, "");
                }
                onEscolherEsforco: function (v) {
                    janela.esforco = v;
                    if (typeof ponte !== "undefined") ponte.definirCerebro("", v);
                }
                onEscolherPersona: function (v) {
                    janela.persona = v;
                    if (typeof ponte !== "undefined") ponte.definirPersona(v);
                }

                function nomeDoModelo() {
                    for (var i = 0; i < opcoesModelo.length; i++)
                        if (opcoesModelo[i].valor === janela.modelo) return opcoesModelo[i].nome;
                    return janela.modelo;
                }
                function nomeDoEsforco() {
                    for (var i = 0; i < opcoesEsforco.length; i++)
                        if (opcoesEsforco[i].valor === janela.esforco) return opcoesEsforco[i].nome;
                    return janela.esforco;
                }
            }
        }

        PaginaAgendados {
            anchors { top: topo.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
            visible: janela.pagina === "agendados"
            tema: tema
            dados: janela.agendados
            conectado: janela.conectado
            onApagar: function (id) { if (typeof ponte !== "undefined") ponte.apagarRecado(id) }
            onCriar: function (texto) {
                if (typeof ponte !== "undefined" && ponte.novoAgendado(texto)) janela.avisar("Pedido mandado: ela anota e te confirma");
            }
        }
        PaginaFeitos {
            anchors { top: topo.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
            visible: janela.pagina === "feitos"
            tema: tema
            lista: janela.feitos
            titulos: janela.titulosDasConversas
            onAbrirConversa: function (sessao) { janela.abrir(sessao) }
        }

        PaginaMemoria {
            id: memoria
            anchors { top: topo.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
            visible: janela.pagina === "memoria"
            tema: tema
            onCopiar: function (t) { if (typeof ponte !== "undefined") ponte.copiar(t) }
            onPedirLista: if (typeof ponte !== "undefined") ponte.pedirMemorias()
            onPedirAbrir: function (id) { if (typeof ponte !== "undefined") ponte.lerMemoria(id) }
            onPedirSalvar: function (id, texto, versao) {
                if (typeof ponte === "undefined" || !ponte.salvarMemoria(id, texto, versao))
                    janela.avisar("Sem conexão com a NOVA: não deu pra salvar")
            }
            onAvisar: function (t) { janela.avisar(t) }
        }

        // -- avisos rápidos ----------------------------------------------------------
        Rectangle {
            id: aviso
            anchors.horizontalCenter: parent.horizontalCenter
            y: areaDoChat.y + compositor.y - height - 14
            width: Math.min(textoDoAviso.implicitWidth + 32, parent.width - 40)
            height: 36
            radius: 18
            color: tema.superficie2
            border.width: 1
            border.color: tema.tracoForte
            opacity: 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: tema.normal } }
            Text {
                id: textoDoAviso
                anchors.centerIn: parent
                color: tema.textoMedio
                font.family: tema.familia
                font.pixelSize: 13
            }
            Timer { id: relogioDoAviso; interval: 3200; onTriggered: aviso.opacity = 0 }
        }
    }

    // Arrastar um arquivo para a janela = anexar (o clipe, sem abrir nada).
    DropArea {
        anchors.fill: parent
        onDropped: function (drop) {
            janela.pagina = "chat";
            for (var i = 0; i < drop.urls.length; i++)
                compositor.adicionar(drop.urls[i]);
            compositor.focar();
        }
    }

    // Só para os retratos: a conversa com alguma coisa dentro. Reativo, e não
    // no onCompleted: quem liga a demonstração é o Python, depois de carregar.
    onDemonstracaoChanged: {
        if (!demonstracao) return;
        janela.conversaAtual = "demo";
        janela.listaDeConversas = [
            { id: "demo", titulo: "Organizar os prints da área de trabalho", origem: "voz", quando: Date.now() / 1000 },
            { id: "b", titulo: "Previsão do tempo pra amanhã", origem: "relogio", quando: Date.now() / 1000 - 3600 },
            { id: "c", titulo: "Mandar o link do app no WhatsApp", origem: "celular", quando: Date.now() / 1000 - 90000 },
        ];
        janela.montarLista();
        falasAtual.acrescentar("voce", "junta todos os prints soltos na área de trabalho numa pasta só, separados por mês", { origem: "voz" });
        falasAtual.atividade("Bash — listando os prints");
        falasAtual.atividade("Bash — criando as pastas por mês");
        falasAtual.mostrar("", "Pronto. Achei **47 prints** e coloquei em **Imagens/Prints**:\n\n- **Agosto** — 9\n- **Setembro** — 21\n- **Outubro** — 17\n\nPra fazer de novo:\n\n```bash\nfor f in ~/Área\\ de\\ trabalho/Captura*.png; do\n  mes=$(date -r \"$f\" +%Y-%m)\n  mkdir -p ~/Imagens/Prints/$mes && mv \"$f\" ~/Imagens/Prints/$mes/\ndone\n```");
        falasAtual.acrescentar("jarvis", "Pronto. Achei quarenta e sete prints.", {});
        falasAtual.acrescentar("voce", "valeu. abre o vídeo novo do canal", { origem: "texto" });
        falasAtual.acrescentar("jarvis", "Abri no navegador, já tá tocando.", {});
        falasAtual.acrescentar("voce", "apaga os prints de setembro", { origem: "voz" });
        falasAtual.acrescentar("jarvis", "Tem 21 prints de setembro. Mando pra lixeira ou deixo?",
                               { perguntando: true, opcoes: ["Mandar pra lixeira", "Deixar"] });
    }

    // -- redimensionar pelas bordas ----------------------------------------
    Item {
        anchors.fill: parent
        visible: !janela.maximizada
        Repeater {
            model: [
                { e: Qt.LeftEdge,                  cur: Qt.SizeHorCursor },
                { e: Qt.RightEdge,                 cur: Qt.SizeHorCursor },
                { e: Qt.TopEdge,                   cur: Qt.SizeVerCursor },
                { e: Qt.BottomEdge,                cur: Qt.SizeVerCursor },
                { e: Qt.LeftEdge | Qt.TopEdge,     cur: Qt.SizeFDiagCursor },
                { e: Qt.RightEdge | Qt.BottomEdge, cur: Qt.SizeFDiagCursor },
                { e: Qt.RightEdge | Qt.TopEdge,    cur: Qt.SizeBDiagCursor },
                { e: Qt.LeftEdge | Qt.BottomEdge,  cur: Qt.SizeBDiagCursor },
            ]
            MouseArea {
                id: aresta
                required property var modelData
                readonly property int borda: modelData.e
                readonly property int faixa: 6
                readonly property bool horizontal: (borda & Qt.LeftEdge) || (borda & Qt.RightEdge)
                readonly property bool vertical: (borda & Qt.TopEdge) || (borda & Qt.BottomEdge)
                width: horizontal ? faixa : parent.width
                height: vertical ? faixa : parent.height
                x: (borda & Qt.RightEdge) ? parent.width - faixa : 0
                y: (borda & Qt.BottomEdge) ? parent.height - faixa : 0
                cursorShape: modelData.cur
                onPressed: janela.startSystemResize(aresta.borda)
            }
        }
    }

    // Os Ajustes: um painel por cima da janela inteira (lateral junto).
    // -- o modo code: escolher o projeto -------------------------------------------
    MouseArea {
        anchors.fill: parent
        visible: janela.seletorCode
        z: 40
        onClicked: janela.seletorCode = false
        Rectangle {
            id: listaCode
            x: principal.x + principal.width - width - 60
            y: 50
            width: 300
            height: Math.min(colProjetos.height + 24, janela.height - 80)
            radius: 12
            color: tema.superficie
            border.width: 1; border.color: tema.tracoForte
            MouseArea { anchors.fill: parent }   // clique dentro não fecha
            Flickable {
                anchors { fill: parent; margins: 12 }
                contentHeight: colProjetos.height; clip: true; boundsBehavior: Flickable.StopAtBounds
                Column {
                    id: colProjetos
                    width: parent.width; spacing: 2
                    Text { text: "Programar pela voz em…"; color: tema.textoFraco; font.family: tema.familia; font.pixelSize: 12
                           bottomPadding: 6; leftPadding: 6 }
                    // Projeto novo (10/11/2026): o nome vira a pasta em Projetos, no HD, e abre um chat novo nele.
                    Rectangle {
                        id: linhaNovo
                        objectName: "linhaNovo"
                        property bool escrevendo: false
                        width: colProjetos.width; height: escrevendo ? 84 : 36; radius: 8
                        color: escrevendo ? tema.superficie2 : maNovo.containsMouse ? tema.superficie2 : "transparent"
                        Text { visible: !linhaNovo.escrevendo; x: 10; anchors.verticalCenter: parent.verticalCenter
                               text: "+  Novo projeto"; color: tema.persona; font.family: tema.familia; font.pixelSize: 14; font.weight: Font.Medium }
                        MouseArea { id: maNovo; anchors.fill: parent; visible: !linhaNovo.escrevendo; hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor; onClicked: { linhaNovo.escrevendo = true; campoNovo.forceActiveFocus() } }
                        Column {
                            visible: linhaNovo.escrevendo
                            x: 8; y: 8; width: parent.width - 16; spacing: 8
                            TextField {
                                id: campoNovo
                                width: parent.width; height: 34
                                placeholderText: "Nome do projeto"; placeholderTextColor: tema.muitoFraco
                                color: tema.texto; font.family: tema.familia; font.pixelSize: 14; leftPadding: 10
                                background: Rectangle { radius: 8; color: tema.fundo; border.width: 1
                                                        border.color: campoNovo.activeFocus ? tema.persona : tema.traco }
                                onAccepted: criarNovo.criar()
                                Keys.onEscapePressed: linhaNovo.escrevendo = false
                            }
                            Row {
                                spacing: 8
                                Rectangle {
                                    id: criarNovo
                                    function criar() {
                                        if (!campoNovo.text.trim()) return;
                                        if (typeof ponte !== "undefined") ponte.novoProjeto(campoNovo.text.trim());
                                        campoNovo.text = ""; linhaNovo.escrevendo = false; janela.seletorCode = false;
                                    }
                                    height: 28; width: tcn.implicitWidth + 24; radius: 7
                                    color: campoNovo.text.trim() ? tema.persona : tema.tracoForte
                                    Text { id: tcn; anchors.centerIn: parent; text: "Criar e abrir"; color: "#0a0c10"
                                           font.family: tema.familia; font.pixelSize: 12; font.weight: Font.DemiBold }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: criarNovo.criar() }
                                }
                                Text { anchors.verticalCenter: parent.verticalCenter; text: "na pasta Projetos do HD"
                                       color: tema.muitoFraco; font.family: tema.familia; font.pixelSize: 11 }
                            }
                        }
                    }
                    Rectangle { width: colProjetos.width; height: 1; color: tema.traco }
                    Text { visible: janela.projetos.length === 0; text: "Procurando os projetos…"; color: tema.muitoFraco
                           font.family: tema.familia; font.pixelSize: 13; leftPadding: 6 }
                    Repeater {
                        model: janela.projetos
                        Rectangle {
                            required property var modelData
                            readonly property bool atual: modelData.caminho === janela.codeCaminho
                            width: colProjetos.width; height: 36; radius: 8
                            color: atual ? tema.realce : maProj.containsMouse ? tema.superficie2 : "transparent"
                            Text { x: 10; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 40; elide: Text.ElideRight
                                   text: modelData.nome.replace(/^Projeto /, ""); color: tema.texto; font.family: tema.familia; font.pixelSize: 14 }
                            Text { anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                                   visible: parent.atual; text: "aberto"; color: tema.persona; font.family: tema.familia; font.pixelSize: 11 }
                            MouseArea {
                                id: maProj; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: { janela.seletorCode = false; if (!parent.atual && typeof ponte !== "undefined") ponte.entrarCode(modelData.caminho) }
                            }
                        }
                    }
                    Rectangle { visible: janela.codeNome !== ""; width: colProjetos.width; height: 1; color: tema.traco }
                    Rectangle {
                        visible: janela.codeNome !== ""
                        width: colProjetos.width; height: 36; radius: 8
                        color: maSair.containsMouse ? tema.superficie2 : "transparent"
                        Text { x: 10; anchors.verticalCenter: parent.verticalCenter; text: "Sair do modo code"
                               color: tema.textoMedio; font.family: tema.familia; font.pixelSize: 14 }
                        MouseArea { id: maSair; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: { janela.seletorCode = false; if (typeof ponte !== "undefined") ponte.entrarCode("") } }
                    }
                    Text { width: colProjetos.width; wrapMode: Text.WordWrap; topPadding: 8; leftPadding: 6; rightPadding: 6
                           text: "Pela voz: \"modo code no Loft\", \"troca pro Terror\", \"cria um projeto novo chamado…\", \"sai do modo code\"."
                           color: tema.muitoFraco; font.family: tema.familia; font.pixelSize: 12 }
                }
            }
        }
    }

    PaginaAjustes {
        id: paginaAjustes
        anchors.fill: parent
        z: 50
        aberto: janela.ajustesAbertos
        onFechar: janela.ajustesAbertos = false
        tema: tema
        conectado: janela.conectado
        conversa: janela.conversaAtual
        modelo: janela.modelo
        esforco: janela.esforco
        persona: janela.persona
        corFriday: janela.corPersona
        usoCinco: janela.usoCinco
        voltaCinco: janela.voltaCinco
        usoSemana: janela.usoSemana
        voltaSemana: janela.voltaSemana
        som: janela.som
        ajustes: janela.ajustes
        estatisticas: janela.estatisticas
        onPedirEstatisticas: if (typeof ponte !== "undefined") ponte.pedirEstatisticas()
        onMudarFoco: (minutos) => { if (typeof ponte !== "undefined") ponte.mudarFoco(minutos) }
        onMudarVolume: (volume) => { if (typeof ponte !== "undefined") ponte.mudarVolumeVoz(volume) }
        onMudarNome: (nome) => { if (typeof ponte !== "undefined") ponte.mudarNome(nome) }
        onMudarCode: (chave, valor) => { if (typeof ponte !== "undefined") ponte.mudarAjusteCode(chave, valor) }
        onMudarGrupo: (ligado) => { if (typeof ponte !== "undefined") ponte.mudarGrupo(ligado) }
        onEscolherSom: (tipo, aparelho) => { if (typeof ponte !== "undefined") ponte.escolherSom(tipo, aparelho) }
        onPedirConexao: (id, acao, valor) => { if (typeof ponte !== "undefined") ponte.conexao(id, acao, valor) }
        onPedirAjustes: { if (typeof ponte !== "undefined") ponte.pedirAjustes() }
        Connections {
            target: typeof ponte !== "undefined" ? ponte : null
            function onConexaoMudou(dados) { paginaAjustes.conexao = dados }
        }
    }
}
