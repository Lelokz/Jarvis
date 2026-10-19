import QtQuick
import QtQuick.Window
import QtQuick.Effects

// A janela, com moldura própria: cantos arredondados, sombra e os botões
// desenhados por nós. Decisão do Léo — com a barra do Cinnamon em cima, a
// janela pareceria um programa genérico com um conteúdo bonito dentro.
//
// Arrastar e redimensionar usam `startSystemMove` e `startSystemResize`: quem
// move a janela é o gerenciador de janelas, e não aritmética de mouse nossa.
//
// A ligação com o assistente é por sinal, e não por costura no Python: o QML
// escuta a ponte direto.
Window {
    id: janela
    width: 460; height: 760
    minimumWidth: 380; minimumHeight: 520
    visible: !comecarNaBandeja
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint
    title: "Jarvis"

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

    readonly property color corAtual: conectado ? tema.corDoEstado(estado)
                                                : tema.corDoEstado("")

    QtObject {
        id: interno
        property string estado: "dormindo"
        property bool conectado: false
        property real nivel: 0.0
    }

    Tema { id: tema }

    Connections {
        target: typeof ponte !== "undefined" ? ponte : null
        ignoreUnknownSignals: true
        function onEstadoMudou(estado) { interno.estado = estado }
        function onNivelMudou(v) { interno.nivel = v }
        function onConexaoMudou(ligado) { interno.conectado = ligado }
        function onVoceDisse(texto, origem) { conversa.acrescentar("voce", texto, "", false) }
        function onJarvisDisse(texto, acao, perguntando) {
            conversa.acrescentar("jarvis", texto, acao, perguntando)
        }
        function onHistoricoRecebido(falas) { conversa.preencher(falas) }
        function onMostrar(titulo, texto) { conversa.mostrar(titulo, texto) }
        function onAtividade(texto) { conversa.atividade(texto) }
        function onAvisoMudou(tipo, voltaEm) { faixa.tipo = tipo; faixa.voltaEm = voltaEm }
        function onMemoriaRecebida(fatos, conversas) {
            painelMemoria.fatos = fatos; painelMemoria.conversas = conversas;
            painelMemoria.carregando = false;
        }
    }

    readonly property int margemSombra: 18

    MultiEffect {
        source: moldura
        anchors.fill: moldura
        visible: janela.sendoVista
        shadowEnabled: janela.sendoVista
        shadowBlur: 1.0
        shadowOpacity: 0.55
        shadowVerticalOffset: 6
        shadowColor: "#000000"
    }

    Rectangle {
        id: moldura
        // Escondida, a janela some INTEIRA da cena, e não só as animações.
        //
        // Medido: com a esfera travada mas a janela minimizada, o nível e o
        // estado chegando pela ponte ainda sujavam a cena e forçavam 27 quadros
        // por segundo. Travar a animação não basta quando a propriedade muda de
        // fora. Sem nada visível, não há o que desenhar — e aí vale para o
        // nível, para o estado e para mensagem nova chegando.
        visible: janela.sendoVista
        anchors.fill: parent
        anchors.margins: janela.margemSombra
        radius: tema.raioJanela
        color: tema.fundo
        border.width: 1
        border.color: tema.traco

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.045) }
                GradientStop { position: 0.35; color: "transparent" }
            }
        }

        // -- barra de título própria ---------------------------------------
        Item {
            id: barra
            height: 44
            anchors { top: parent.top; left: parent.left; right: parent.right }

            DragHandler {
                target: null
                onActiveChanged: if (active) janela.startSystemMove()
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 18
                text: "JARVIS"
                color: tema.textoFraco
                font.family: tema.familia
                font.pixelSize: 11
                font.letterSpacing: 2.5
                font.weight: Font.DemiBold
                renderType: Text.NativeRendering
            }

            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                anchors.rightMargin: 14
                spacing: 6

                // "memória": o que o Jarvis sabe e do que a gente conversou.
                Rectangle {
                    width: textoMemoria.implicitWidth + 16
                    height: 26
                    radius: tema.raioBotao
                    color: areaMemoria.containsMouse || painelMemoria.aberto ? tema.traco : "transparent"
                    Behavior on color { ColorAnimation { duration: tema.rapido } }
                    Text {
                        id: textoMemoria
                        anchors.centerIn: parent
                        text: "memória"
                        color: areaMemoria.containsMouse || painelMemoria.aberto ? tema.texto : tema.textoFraco
                        font.family: tema.familia
                        font.pixelSize: 11
                        font.letterSpacing: 1
                        renderType: Text.NativeRendering
                    }
                    MouseArea {
                        id: areaMemoria
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: painelMemoria.alternar()
                    }
                }
                BotaoDaBarra { tema: tema; simbolo: "–"; onClicado: janela.showMinimized() }
                BotaoDaBarra {
                    tema: tema
                    simbolo: "×"
                    corDeFundoAtiva: tema.perigo
                    onClicado: janela.close()
                }
            }
        }

        // -- a esfera e o rótulo do estado ----------------------------------
        Item {
            id: areaEsfera
            anchors { top: barra.bottom; left: parent.left; right: parent.right }
            height: Math.max(190, Math.min(330, moldura.height * 0.42))

            Esfera {
                id: esfera
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                width: Math.min(parent.width - 60, parent.height - 54)
                height: width

                readonly property bool vivo: janela.conectado
                corDeFundo: tema.fundo
                // Sem conexão é o ÚNICO estado parado. Dormindo continua girando,
                // devagar, porque ele está vivo esperando ser chamado.
                parada: !vivo
                pulsando: vivo && janela.estado === "dormindo"
                sendoVista: janela.sendoVista
                nivel: janela.nivel
                cor: janela.corAtual
                escala: !vivo ? 0.80
                      : janela.estado === "escutando" ? 1.14
                      : janela.estado === "falando" ? 1.06
                      : janela.estado === "pensando" ? 1.02
                      : janela.estado === "dormindo" ? 0.84 : 1.0
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
                      : janela.estado === "dormindo" ? 0.62
                      : janela.estado === "pensando" ? 1.2 : 1.0
            }

            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                spacing: 8

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: tema.rotuloDoEstado(janela.conectado ? janela.estado : "")
                    color: janela.corAtual
                    font.family: tema.familia
                    font.pixelSize: 13
                    font.letterSpacing: 3
                    font.weight: Font.Medium
                    renderType: Text.NativeRendering
                    Behavior on color { ColorAnimation { duration: tema.normal } }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: janela.conectado ? "" : "esperando o Jarvis subir"
                    color: tema.textoFraco
                    font.family: tema.familia
                    font.pixelSize: 12
                    renderType: Text.NativeRendering
                    opacity: text ? 0.85 : 0.0
                    Behavior on opacity { NumberAnimation { duration: tema.normal } }
                }
            }
        }

        // -- a conversa ------------------------------------------------------
        Conversa {
            id: conversa
            tema: tema
            dica: janela.conectado ? "diga \"hey Jarvis\", ou escreva aqui embaixo" : ""
            anchors {
                top: areaEsfera.bottom
                left: parent.left
                right: parent.right
                bottom: faixa.top
            }
        }

        // -- o painel de memória ----------------------------------------------
        // Por cima da esfera e da conversa. Pede a memória ao assistente toda
        // vez que abre: o diário muda quando ele dorme.
        Rectangle {
            id: painelMemoria
            objectName: "painelMemoria"
            property bool aberto: false
            property bool carregando: false
            property var fatos: []
            property var conversas: []
            function alternar() {
                aberto = !aberto;
                if (aberto) {
                    carregando = true;
                    if (typeof ponte === "undefined" || !ponte.pedirMemoria()) {
                        carregando = false;
                        janela.avisar("o Jarvis não está do outro lado");
                    }
                }
            }
            z: 5
            anchors { top: barra.bottom; left: parent.left; right: parent.right; bottom: barraDeTexto.top }
            color: tema.fundo
            visible: opacity > 0
            opacity: aberto ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: tema.rapido } }

            Flickable {
                anchors.fill: parent
                anchors.leftMargin: 22
                anchors.rightMargin: 22
                contentHeight: colunaMemoria.height + 24
                clip: true

                Column {
                    id: colunaMemoria
                    width: parent.width
                    spacing: 10
                    topPadding: 8

                    Text {
                        text: "O QUE EU SEI DE VOCÊ"
                        color: tema.textoFraco
                        font.family: tema.familia
                        font.pixelSize: 11
                        font.letterSpacing: 2
                        renderType: Text.NativeRendering
                    }
                    Text {
                        visible: painelMemoria.fatos.length === 0
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: painelMemoria.carregando ? "carregando…" : "Nada ainda. Diga \"lembra que…\"."
                        color: tema.textoFraco
                        font.family: tema.familia
                        font.pixelSize: 13
                        renderType: Text.NativeRendering
                    }
                    Repeater {
                        model: painelMemoria.fatos
                        Text {
                            required property var modelData
                            width: colunaMemoria.width
                            wrapMode: Text.WordWrap
                            text: "•  " + modelData
                            color: tema.texto
                            font.family: tema.familia
                            font.pixelSize: 13
                            renderType: Text.NativeRendering
                        }
                    }

                    Item { width: 1; height: 8 }
                    Text {
                        text: "CONVERSAS"
                        color: tema.textoFraco
                        font.family: tema.familia
                        font.pixelSize: 11
                        font.letterSpacing: 2
                        renderType: Text.NativeRendering
                    }
                    Text {
                        visible: painelMemoria.conversas.length === 0
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: painelMemoria.carregando ? "carregando…"
                              : "Nenhuma ainda. Cada conversa entra aqui quando o Jarvis dorme."
                        color: tema.textoFraco
                        font.family: tema.familia
                        font.pixelSize: 13
                        renderType: Text.NativeRendering
                    }
                    Repeater {
                        model: painelMemoria.conversas
                        Rectangle {
                            required property var modelData
                            width: colunaMemoria.width
                            height: blocoConversa.height + 18
                            radius: 12
                            color: tema.superficie
                            Column {
                                id: blocoConversa
                                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                spacing: 4
                                Text {
                                    width: parent.width
                                    wrapMode: Text.WordWrap
                                    text: modelData.tema
                                    color: tema.texto
                                    font.family: tema.familia
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    renderType: Text.NativeRendering
                                }
                                Text {
                                    text: modelData.quando
                                    color: "#9b7bff"
                                    font.family: tema.familia
                                    font.pixelSize: 11
                                    renderType: Text.NativeRendering
                                }
                                Text {
                                    width: parent.width
                                    wrapMode: Text.WordWrap
                                    text: modelData.resumo
                                    color: tema.textoFraco
                                    font.family: tema.familia
                                    font.pixelSize: 12
                                    renderType: Text.NativeRendering
                                }
                            }
                        }
                    }
                }
            }
        }

        // -- o aviso do cérebro de nuvem: limite acabou / sem internet --------
        // Fica até a situação mudar. No limite, conta quanto falta e some
        // sozinho quando dá a hora.
        Rectangle {
            id: faixa
            property string tipo: "ok"
            property real voltaEm: 0
            property real agora: Date.now() / 1000
            readonly property bool ativa: (tipo === "limite" && (voltaEm === 0 || voltaEm > agora))
                                          || tipo === "offline"
            anchors { left: parent.left; right: parent.right; bottom: barraDeTexto.top }
            anchors.leftMargin: 20
            anchors.rightMargin: 20
            anchors.bottomMargin: ativa ? 6 : 0
            height: ativa ? textoDaFaixa.implicitHeight + 16 : 0
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
                font.pixelSize: 12
                renderType: Text.NativeRendering
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

        // -- a barra de escrita ----------------------------------------------
        BarraDeTexto {
            id: barraDeTexto
            tema: tema
            estado: janela.estado
            conectado: janela.conectado
            corDoEstado: janela.corAtual
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            anchors.bottomMargin: 6
            onEnviar: function (texto) {
                if (typeof ponte === "undefined" || !ponte.enviarTexto(texto))
                    janela.avisar("não consegui enviar — o Jarvis não está do outro lado");
            }
            onAvisar: function (texto) { janela.avisar(texto) }
        }

        // -- avisos rápidos ---------------------------------------------------
        Rectangle {
            id: aviso
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: barraDeTexto.top
            anchors.bottomMargin: 10
            width: Math.min(textoDoAviso.implicitWidth + 28, parent.width - 40)
            height: 34
            radius: 17
            color: tema.superficie
            border.width: 1
            border.color: tema.traco
            opacity: 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: tema.normal } }

            Text {
                id: textoDoAviso
                anchors.centerIn: parent
                color: tema.textoFraco
                font.family: tema.familia
                font.pixelSize: 12
                renderType: Text.NativeRendering
            }

            Timer {
                id: relogioDoAviso
                interval: 2600
                onTriggered: aviso.opacity = 0
            }
        }
    }

    function avisar(texto) {
        textoDoAviso.text = texto;
        aviso.opacity = 1;
        relogioDoAviso.restart();
    }

    // Só para os retratos: mostra a conversa com alguma coisa dentro.
    //
    // Reativo, e não no Component.onCompleted: quem liga a demonstração é o
    // Python, DEPOIS de a janela já ter carregado — no onCompleted a conversa
    // saía vazia nos retratos.
    onDemonstracaoChanged: {
        if (demonstracao) {
            conversa.acrescentar("voce", "abre o loft", "", false);
            conversa.acrescentar("jarvis", "Abri o Loft.", "abrir:loft", false);
            conversa.acrescentar("voce", "renomeia o relatório para proposta", "", false);
            conversa.acrescentar("jarvis", "Renomeio relatório para proposta. Pode?", "", true);
            conversa.acrescentar("voce", "como eu listo os maiores arquivos de uma pasta?", "", false);
            conversa.atividade("Bash — olhando o tamanho das pastas");
            conversa.mostrar("Maiores arquivos", "Os dez maiores, do maior para o menor:\n\n```\ndu -ah ~/Downloads | sort -rh | head -n 10\n```\n\n- `du -ah` mede tudo\n- `sort -rh` ordena do maior");
            conversa.acrescentar("jarvis", "Deixei o comando na janela.", "", false);
        }
    }

    // -- redimensionar pelas bordas ----------------------------------------
    Item {
        anchors.fill: moldura

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
                readonly property int faixa: 8
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
}
