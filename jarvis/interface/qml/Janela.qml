import QtQuick
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
    // Escreveu numa conversa antiga: primeiro o Jarvis volta pra ela, depois
    // a mensagem vai (quando a "conversa_atual" chegar com este id).
    property string esperandoContinuar: ""
    property var pendente: null

    readonly property bool boasVindas: pagina === "chat" && vendo === "" && falasAtual.count === 0

    function saudacao() {
        var h = new Date().getHours();
        // O nome de quem usa (Ajustes, "Seu nome"); sem nome, só o cumprimento.
        var nome = ajustes && ajustes.nome ? ", " + ajustes.nome : "";
        return (h < 5 ? "Boa noite" : h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite") + nome + ".";
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
            if (estado !== "pensando") janela.textoPensando = "Pensando…";
        }
        function onNivelMudou(v) { interno.nivel = v }
        function onConexaoMudou(ligado) {
            interno.conectado = ligado;
            if (ligado) ponte.pedirConversas();
        }
        function onVoceDisse(texto, origem) { falasAtual.acrescentar("voce", texto, { origem: origem }) }
        function onJarvisDisse(texto, acao, perguntando, opcoes) {
            escrita.esvaziar();
            falasAtual.acrescentar("jarvis", texto, { perguntando: perguntando, opcoes: opcoes });
            atualizarLista.restart();
        }
        function onHistoricoRecebido(falas) { falasAtual.preencher(falas) }
        function onMostrar(titulo, texto) { escrita.esvaziar(); falasAtual.mostrar(titulo, texto) }
        function onAtividade(texto) {
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
        corAtual: janela.corAtual
        nivel: janela.nivel
        sendoVista: janela.sendoVista
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

            Row {
                anchors.verticalCenter: parent.verticalCenter
                x: 28
                spacing: 12
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, topo.width - 420)
                    elide: Text.ElideRight
                    text: janela.pagina === "memoria" ? "Memórias"
                        : janela.pagina === "ajustes" ? "Ajustes"
                        : janela.tituloDe(janela.vendo || janela.conversaAtual)
                    color: janela.boasVindas ? tema.textoFraco : tema.texto
                    font.family: tema.familia
                    font.pixelSize: 15
                    font.weight: Font.Medium
                }
                Rectangle {
                    visible: janela.pagina === "chat" && !janela.boasVindas
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

            Row {
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
        Item {
            id: areaDoChat
            anchors { top: topo.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
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
            }

            // O chat novo: o átomo grande, a saudação e (logo abaixo) a barra.
            Column {
                id: boasVindas
                anchors.horizontalCenter: parent.horizontalCenter
                y: Math.max(20, (parent.height - (height + 30 + compositor.height + 70)) / 2 - 20)
                visible: opacity > 0
                opacity: janela.boasVindas ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: tema.normal } }
                spacing: 0

                Esfera {
                    id: esfera
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(230, areaDoChat.height * 0.28)
                    height: width
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
                    color: tema.texto
                    font.family: tema.familia
                    font.pixelSize: 34
                    font.weight: Font.Medium
                    font.letterSpacing: -0.3
                }
                Item { width: 1; height: 8 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: janela.conectado ? "Fala \"Hey Jarvis\" ou \"Hey Friday\", ou escreve aqui embaixo."
                                           : "Esperando a NOVA subir…"
                    color: tema.textoFraco
                    font.family: tema.familia
                    font.pixelSize: 15
                }
            }

            // Ideias de pedido, embaixo da barra no chat novo.
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                y: compositor.y + compositor.height + 6
                spacing: 10
                visible: opacity > 0
                opacity: janela.boasVindas && janela.conectado ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: tema.normal } }
                Repeater {
                    model: ["Como tá o tempo amanhã?", "O que eu tenho essa semana?",
                            "Toca alguma coisa pra focar"]
                    Rectangle {
                        required property string modelData
                        width: textoIdeia.implicitWidth + 28
                        height: 36
                        radius: 18
                        color: areaIdeia.containsMouse ? tema.superficie : tema.lateral
                        border.width: 1
                        border.color: tema.traco
                        Text {
                            id: textoIdeia
                            anchors.centerIn: parent
                            text: modelData
                            color: tema.textoMedio
                            font.family: tema.familia
                            font.pixelSize: 13
                        }
                        MouseArea {
                            id: areaIdeia
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: janela.enviar(modelData, [])
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
                modelo: janela.modelo
                esforco: janela.esforco
                persona: janela.persona
                menusParaCima: !janela.boasVindas
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
        onEscolherPersona: (v) => {
            janela.persona = v;
            if (typeof ponte !== "undefined") ponte.definirPersona(v);
        }
        onMudarVolume: (volume) => { if (typeof ponte !== "undefined") ponte.mudarVolumeVoz(volume) }
        onMudarNome: (nome) => { if (typeof ponte !== "undefined") ponte.mudarNome(nome) }
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
