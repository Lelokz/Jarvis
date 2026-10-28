import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import "../../../jarvis/interface/qml"

// O instalador da NOVA: as telas do protótipo aprovado (site/prototipo-instalador.html,
// 26/10/2026) mais a de Conexões (28/10). Lateral com os passos, a tela da vez à
// direita e os botões embaixo. Sem barra do sistema: arrasta pelo fundo.
Window {
    id: janela
    // Do tamanho do monitor (pedido do Léo, 28/10/2026): uns 55–60% dele, grande ou
    // pequeno, no meio da tela; arrasta para onde quiser, mas não estica nem maximiza.
    // O desenho é feito em 1040 × 680 e a janela inteira cresce ou encolhe junto.
    readonly property real proporcao: 680 / 1040
    readonly property int largura: Math.round(Math.min(Screen.desktopAvailableWidth * 0.55,
                                                       Screen.desktopAvailableHeight * 0.6 / proporcao))
    readonly property int altura: Math.round(largura * proporcao)
    width: largura
    height: altura
    minimumWidth: largura
    maximumWidth: largura
    minimumHeight: altura
    maximumHeight: altura
    x: Screen.virtualX + (Screen.desktopAvailableWidth - largura) / 2
    y: Screen.virtualY + (Screen.desktopAvailableHeight - altura) / 2
    visible: true
    title: "Instalador da NOVA"
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
    color: cor.fundo

    Tema { id: tema }

    // As cores do protótipo (um tom mais escuras que as da janela da NOVA).
    QtObject {
        id: cor
        readonly property color fundo: "#05070b"
        readonly property color lateral: "#080b11"
        readonly property color vidro: "#0e131c"
        readonly property color traco: Qt.rgba(120 / 255, 150 / 255, 200 / 255, 0.14)
        readonly property color tracoForte: Qt.rgba(120 / 255, 150 / 255, 200 / 255, 0.28)
        readonly property color ok: "#38d39f"
        readonly property color aviso: "#ffb454"
        readonly property color azul: "#4da3ff"
        readonly property string mono: "DejaVu Sans Mono"
    }

    property int tela: 1
    readonly property var passos: ["Boas-vindas", "Seu PC", "Escolhas", "Instalação", "Conta do Claude",
                                   "Microfone", "Conexões", "Pronto"]
    // O que a tela 2 achou e o que a pessoa escolheu na 3.
    property var pc: null
    property string nome: instalador.nomePadrao
    property string persona: "jarvis"
    property string vozes: "leves"
    property string pasta: instalador.pastaPadrao
    property bool comOPc: true
    property bool atalho: true
    property bool bandeja: true

    // A tela 4: o que o motor da instalação (passos.py) manda.
    property var prog: null
    // Tela 5: a conta do Claude. Tela 6: o microfone. Tela 7: a conexão aberta.
    property var conta: null
    property var mic: ({ nivel: -90, ruido: -90 })
    property real picoMic: -90
    property int ouviuJarvis: 0
    property int ouviuFriday: 0
    property string conexaoAberta: ""
    property var conexoes: ({})
    Connections {
        target: instalador
        function onProgresso(dados) { janela.prog = dados }
        function onClaude(dados) {
            janela.conta = dados;
            if (dados.url && !janela.conta.abriu) { Qt.openUrlExternally(dados.url); janela.conta.abriu = true }
        }
        function onMicrofone(dados) {
            if (dados.ouviu === "jarvis") janela.ouviuJarvis++;
            else if (dados.ouviu === "friday") janela.ouviuFriday++;
            else if (dados.nivel !== undefined) { janela.mic = dados; janela.picoMic = Math.max(janela.picoMic - 0.4, dados.nivel) }
            else if (dados.erro) janela.mic = dados;
        }
        function onConexao(dados) {
            var c = Object.assign({}, janela.conexoes); c[dados.id] = dados; janela.conexoes = c;
        }
        function onChecou(dados) {
            janela.pc = dados;
            janela.vozes = dados.dubladas ? "dubladas" : "leves";
        }
    }
    onTelaChanged: {
        if (tela === 2 && !pc) instalador.checar();
        if (tela === 4 && !(prog && prog.fim)) instalador.instalar();
        if (tela === 5 && !conta) instalador.claudeConferir();
        if (tela === 6) { ouviuJarvis = 0; ouviuFriday = 0; instalador.microfoneTestar("") } else instalador.microfoneParar();
        if (tela === 7) for (var id of ["whatsapp", "fora", "musica"]) instalador.conectar(id, "estado", "");
    }
    // A conexão aberta na tela 7 se confere sozinha de 2 em 2 s (o QR troca, o celular aparece).
    Timer {
        interval: 2000; repeat: true
        running: janela.tela === 7 && janela.conexaoAberta !== ""
        onTriggered: instalador.conectar(janela.conexaoAberta, janela.conexaoAberta === "fora" ? "conectar" : "estado", "")
    }

    // O palco: tudo desenhado em 1040 × 680, na escala da janela.
    Item {
    id: palco
    width: 1040
    height: 680
    scale: janela.width / 1040
    transformOrigin: Item.TopLeft

    // Arrastar a janela pelo fundo (não há barra do sistema).
    MouseArea {
        anchors.fill: parent
        onPressed: janela.startSystemMove()
    }

    // ---------------------------------------------------------------- lateral
    Rectangle {
        id: lateral
        width: 250
        height: parent.height
        color: cor.lateral
        Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: cor.traco }

        Row {
            x: 22; y: 26
            spacing: 10
            AtomoFixo { tamanho: 32; cor: "#4da3ff" }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                Text { text: "NOVA"; color: tema.texto; font.family: tema.familia; font.pixelSize: 14; font.weight: Font.ExtraBold; font.letterSpacing: 2.8 }
                Text { text: "INSTALADOR · BETA 0.1"; color: tema.textoFraco; font.family: cor.mono; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1.5 }
            }
        }

        Column {
            x: 22; y: 100
            spacing: 0
            Repeater {
                model: janela.passos
                Item {
                    required property int index
                    required property string modelData
                    readonly property int n: index + 1
                    width: 210; height: 45
                    // A linha que liga as bolinhas.
                    Rectangle {
                        visible: n < janela.passos.length
                        x: 13; y: 27; width: 1; height: 45 - 27 + 0
                        color: cor.tracoForte
                    }
                    Rectangle {
                        width: 27; height: 27; radius: 14
                        color: n === janela.tela ? cor.azul : n < janela.tela ? Qt.rgba(77 / 255, 163 / 255, 1, 0.15) : cor.lateral
                        border.width: 1
                        border.color: n <= janela.tela ? cor.azul : cor.tracoForte
                        Text {
                            anchors.centerIn: parent
                            text: n < janela.tela ? "✓" : n
                            color: n === janela.tela ? "#050a12" : n < janela.tela ? cor.azul : tema.textoFraco
                            font.family: cor.mono; font.pixelSize: 11; font.weight: Font.Bold
                        }
                    }
                    Text {
                        x: 40; y: 4
                        text: modelData
                        color: n === janela.tela ? tema.texto : n < janela.tela ? tema.textoMedio : tema.textoFraco
                        font.family: tema.familia; font.pixelSize: 14
                        font.weight: n === janela.tela ? Font.DemiBold : Font.Normal
                    }
                }
            }
        }

        Text {
            x: 22; anchors.bottom: parent.bottom; anchors.bottomMargin: 22
            text: "// beta fechado\n// só convidados"
            color: tema.muitoFraco; font.family: cor.mono; font.pixelSize: 11; lineHeight: 1.3
        }
    }

    // ------------------------------------------------------------- conteúdo
    Item {
        id: area
        anchors.left: lateral.right
        anchors.right: parent.right
        height: parent.height

        // O quadriculado bem fraco do fundo.
        Canvas {
            anchors.fill: parent
            onPaint: {
                var c = getContext("2d");
                c.strokeStyle = "rgba(77,163,255,0.035)";
                c.lineWidth = 1;
                for (var x = 0.5; x < width; x += 40) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, height); c.stroke(); }
                for (var y = 0.5; y < height; y += 40) { c.beginPath(); c.moveTo(0, y); c.lineTo(width, y); c.stroke(); }
            }
        }

        // Minimizar e fechar.
        Row {
            anchors.right: parent.right; anchors.rightMargin: 14; y: 10
            spacing: 4
            Repeater {
                model: [["—", function () { janela.showMinimized(); }], ["✕", function () { Qt.quit(); }]]
                Rectangle {
                    required property var modelData
                    width: 34; height: 30; radius: 8
                    color: areaControle.containsMouse ? cor.vidro : "transparent"
                    Text { anchors.centerIn: parent; text: modelData[0]; color: tema.textoMedio; font.pixelSize: 14 }
                    MouseArea { id: areaControle; anchors.fill: parent; hoverEnabled: true; onClicked: modelData[1]() }
                }
            }
        }

        // A tela da vez rola quando passa da altura (a 7 com o WhatsApp aberto).
        Flickable {
            id: rolagem
            x: 46; y: 54
            width: area.width - 92
            height: area.height - 54 - 96
            contentHeight: Math.max(height, telaAtual.item ? telaAtual.item.implicitHeight : 0)
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: rolagem.contentHeight > rolagem.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }
        Loader {
            id: telaAtual
            width: rolagem.width
            height: rolagem.contentHeight
            sourceComponent: [tela1, tela2, tela3, tela4, tela5, tela6, tela7, tela8][janela.tela - 1]
            onLoaded: rolagem.contentY = 0
        }
        }

        // Os botões de baixo.
        Row {
            anchors.right: parent.right; anchors.rightMargin: 46
            anchors.bottom: parent.bottom; anchors.bottomMargin: 30
            spacing: 18
            Botao {
                visible: janela.tela > 1 && janela.tela < 4
                texto: "← Voltar"
                vazio: true
                onClicado: janela.tela--
            }
            Botao {
                visible: janela.tela === 6 || janela.tela === 7
                texto: "Pular"
                vazio: true
                onClicado: { janela.conexaoAberta = ""; janela.tela++ }
            }
            Botao {
                visible: janela.tela === 8
                texto: "Concluir"
                vazio: true
                onClicado: Qt.quit()
            }
            Botao {
                visible: janela.tela === 8
                texto: "Abrir a NOVA"
                onClicado: { instalador.abrirNova(); Qt.quit() }
            }
            Botao {
                texto: janela.tela === 1 ? "Começar →" : janela.tela === 3 ? "Instalar →" : "Continuar →"
                ativo: (janela.tela !== 2 || (!!janela.pc && janela.pc.pode))
                       && (janela.tela !== 5 || (!!janela.conta && janela.conta.logado))
                       && (janela.tela !== 6 || janela.ouviuJarvis > 0 || janela.ouviuFriday > 0)
                // Na instalação, só quando ela terminar.
                visible: janela.tela < 4 || (janela.tela === 4 && !!janela.prog && !!janela.prog.fim)
                         || (janela.tela > 4 && janela.tela < 8)
                onClicado: {
                    janela.conexaoAberta = "";
                    if (janela.tela === 3)
                        instalador.guardarEscolhas({ nome: janela.nome, persona: janela.persona, vozes: janela.vozes,
                                                     pasta: janela.pasta, comOPc: janela.comOPc, atalho: janela.atalho,
                                                     bandeja: janela.bandeja });
                    janela.tela++;
                }
            }
        }
        Text {
            visible: janela.tela === 1
            x: 46; anchors.bottom: parent.bottom; anchors.bottomMargin: 44
            text: "// núcleo operacional de vozes autônomas"
            color: tema.muitoFraco; font.family: cor.mono; font.pixelSize: 12
        }
    }

    }

    // ------------------------------------------------------------ componentes
    component Botao: Rectangle {
        id: botao
        property string texto: ""
        property bool vazio: false
        property bool ativo: true
        signal clicado()
        width: rotuloBotao.implicitWidth + (vazio ? 20 : 52)
        height: 46
        radius: 12
        opacity: ativo ? 1 : 0.4
        color: vazio ? "transparent" : (areaBotao.containsMouse && ativo ? Qt.lighter(cor.azul, 1.08) : cor.azul)
        Text {
            id: rotuloBotao
            anchors.centerIn: parent
            text: botao.texto
            color: botao.vazio ? tema.textoMedio : "#06101d"
            font.family: tema.familia; font.pixelSize: 15; font.weight: Font.Bold
        }
        MouseArea { id: areaBotao; anchors.fill: parent; hoverEnabled: true; enabled: botao.ativo; onClicked: botao.clicado() }
    }

    // "—— PASSO 2 · SEU PC", o título grande com a parte azul e o subtítulo.
    component Cabeca: Column {
        property string rotulo: ""
        property string titulo: ""
        property string destaque: ""
        property string sub: ""
        width: parent ? parent.width : 0
        spacing: 10
        Row {
            spacing: 10
            Rectangle { width: 22; height: 1; color: cor.azul; anchors.verticalCenter: parent.verticalCenter }
            Text { text: rotulo; color: cor.azul; font.family: cor.mono; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 2.4 }
        }
        Text {
            width: parent.width
            wrapMode: Text.WordWrap
            textFormat: Text.StyledText
            text: titulo + (destaque ? " <font color='#4da3ff'>" + destaque + "</font>" : "")
            color: tema.texto; font.family: tema.familia; font.pixelSize: 38; font.weight: Font.ExtraBold; font.letterSpacing: -1.2
            lineHeight: 0.95
        }
        Text {
            visible: !!sub
            width: parent.width; wrapMode: Text.WordWrap
            text: sub; color: tema.textoMedio; font.family: tema.familia; font.pixelSize: 15; lineHeight: 1.35
        }
    }

    component Caixa: Rectangle {
        default property alias conteudo: dentro.data
        property int folga: 18
        width: parent ? parent.width : 0
        height: dentro.implicitHeight + folga * 2
        radius: 14
        color: cor.vidro
        border.width: 1
        border.color: cor.traco
        Column { id: dentro; x: folga; y: folga; width: parent.width - folga * 2; spacing: 0 }
    }

    component Rotulo: Text {
        color: tema.textoFraco; font.family: cor.mono; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.8
    }

    component Opcao: Rectangle {
        id: opcao
        property string titulo: ""
        property string sub: ""
        property string etiqueta: ""
        property bool escolhida: false
        property bool ativa: true
        signal escolher()
        height: 64
        radius: 12
        opacity: ativa ? 1 : 0.45
        color: escolhida ? Qt.rgba(77 / 255, 163 / 255, 1, 0.08) : cor.vidro
        border.width: 1
        border.color: escolhida ? cor.azul : cor.traco
        Column {
            x: 16; anchors.verticalCenter: parent.verticalCenter
            spacing: 3
            Text { text: opcao.titulo; color: tema.texto; font.family: tema.familia; font.pixelSize: 14; font.weight: Font.DemiBold }
            Text { text: opcao.sub; color: tema.textoFraco; font.family: tema.familia; font.pixelSize: 12 }
        }
        Text {
            visible: !!opcao.etiqueta
            anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
            text: opcao.etiqueta; color: cor.ok; font.family: cor.mono; font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: 1
        }
        MouseArea { anchors.fill: parent; enabled: opcao.ativa; onClicked: opcao.escolher() }
    }

    component Marca: Row {
        id: marca
        property string texto: ""
        property bool ligado: true
        signal trocar()
        spacing: 9
        Rectangle {
            width: 18; height: 18; radius: 5
            color: marca.ligado ? cor.azul : "transparent"
            border.width: 1; border.color: marca.ligado ? cor.azul : cor.tracoForte
            Text { anchors.centerIn: parent; visible: marca.ligado; text: "✓"; color: "#06101d"; font.pixelSize: 12; font.weight: Font.Bold }
            MouseArea { anchors.fill: parent; onClicked: marca.trocar() }
        }
        Text { text: marca.texto; color: tema.textoMedio; font.family: tema.familia; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
    }

    // ------------------------------------------------------------------ telas
    Component {
        id: tela1
        Item {
            Column {
                width: parent.width * 0.58
                anchors.verticalCenter: parent.verticalCenter
                spacing: 22
                Cabeca {
                    rotulo: "BEM-VINDO"
                    titulo: "Vamos ligar a<br>sua"
                    destaque: "NOVA."
                    sub: "Em uns 15 minutos o Jarvis e a Friday estão morando no seu PC. O instalador faz o trabalho pesado:"
                }
                Column {
                    spacing: 12
                    Repeater {
                        model: ["Confere se o seu PC aguenta tudo", "Baixa só o que falta, das fontes oficiais",
                                "Liga na sua conta do Claude", "Testa o microfone com você"]
                        Row {
                            required property int index
                            required property string modelData
                            spacing: 14
                            Rectangle {
                                width: 30; height: 26; radius: 7; color: Qt.rgba(77 / 255, 163 / 255, 1, 0.1)
                                Text { anchors.centerIn: parent; text: "0" + (index + 1); color: cor.azul; font.family: cor.mono; font.pixelSize: 12; font.weight: Font.Bold }
                            }
                            Text { text: modelData; color: tema.textoMedio; font.family: tema.familia; font.pixelSize: 15; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                }
            }
            Esfera {
                width: Math.min(parent.width * 0.4, 330); height: width
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                cor: "#4da3ff"; corDeFundo: janela.color   // (aqui dentro, "cor" é a da Esfera)
            }
        }
    }

    Component {
        id: tela2
        Column {
            spacing: 22
            Cabeca {
                rotulo: "PASSO 2 · SEU PC"
                titulo: !janela.pc ? "Conferindo o" : janela.pc.pode ? "Seu PC" : "Falta uma"
                destaque: !janela.pc ? "seu PC…" : janela.pc.pode ? "aguenta tudo." : "coisa."
                sub: !janela.pc ? "Olhando as peças que a NOVA usa. Nada é instalado agora."
                     : "Conferi as peças que a NOVA usa. Nada foi instalado ainda."
            }
            Caixa {
                folga: 6
                Repeater {
                    model: janela.pc ? janela.pc.itens : []
                    Item {
                        required property var modelData
                        required property int index
                        width: parent.width; height: 50
                        Rectangle {
                            visible: index > 0
                            x: 14; width: parent.width - 28; height: 1; color: cor.traco
                        }
                        Rectangle {
                            x: 14; anchors.verticalCenter: parent.verticalCenter
                            width: 24; height: 24; radius: 12
                            color: modelData.ok ? Qt.rgba(56 / 255, 211 / 255, 159 / 255, 0.14) : Qt.rgba(1, 180 / 255, 84 / 255, 0.14)
                            Text { anchors.centerIn: parent; text: modelData.ok ? "✓" : "!"; color: modelData.ok ? cor.ok : cor.aviso; font.pixelSize: 12; font.weight: Font.Bold }
                        }
                        Rotulo { x: 52; anchors.verticalCenter: parent.verticalCenter; text: modelData.rotulo.toUpperCase() }
                        Text {
                            x: parent.width * 0.32; anchors.verticalCenter: parent.verticalCenter
                            width: parent.width * 0.45; elide: Text.ElideRight
                            text: modelData.valor; color: tema.texto; font.family: tema.familia; font.pixelSize: 14
                        }
                        Text {
                            anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                            text: modelData.nota; color: modelData.ok ? cor.ok : cor.aviso; font.family: cor.mono; font.pixelSize: 11
                        }
                    }
                }
                Row {
                    visible: !janela.pc
                    height: 60; spacing: 10; x: 14
                    BusyIndicator { width: 22; height: 22; anchors.verticalCenter: parent.verticalCenter; running: true }
                    Text { text: "conferindo…"; color: tema.textoFraco; font.family: cor.mono; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                }
            }
            Rectangle {
                visible: !!janela.pc
                width: parent.width; height: textoVozes.implicitHeight + 30; radius: 14
                color: Qt.rgba(56 / 255, 211 / 255, 159 / 255, 0.05)
                border.width: 1; border.color: Qt.rgba(56 / 255, 211 / 255, 159 / 255, 0.3)
                Text { x: 16; anchors.verticalCenter: parent.verticalCenter; text: "⚡"; color: cor.aviso; font.pixelSize: 16 }
                Text {
                    id: textoVozes
                    x: 44; width: parent.width - 60; anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WordWrap; textFormat: Text.StyledText
                    color: tema.textoMedio; font.family: tema.familia; font.pixelSize: 14
                    text: janela.pc && janela.pc.dubladas
                          ? "Com essa placa, o Jarvis e a Friday falam com as <b>vozes dubladas</b>. Sem placa NVIDIA, a NOVA usa vozes leves, que rodam em qualquer PC."
                          : "Sem uma placa NVIDIA de 8 GB, o Jarvis e a Friday falam com as <b>vozes leves</b>, que rodam em qualquer PC. O resto funciona igual."
                }
            }
        }
    }

    Component {
        id: tela3
        Column {
            spacing: 20
            Cabeca { rotulo: "PASSO 3 · ESCOLHAS"; titulo: "Do"; destaque: "seu jeito." }
            Row {
                width: parent.width
                spacing: 20
                Column {
                    width: (parent.width - 20) / 2
                    spacing: 8
                    Rotulo { text: "COMO ELES TE CHAMAM" }
                    Rectangle {
                        width: parent.width; height: 44; radius: 10; color: cor.vidro
                        border.width: 1; border.color: campoNome.activeFocus ? cor.azul : cor.traco
                        TextInput {
                            id: campoNome
                            x: 14; width: parent.width - 28; anchors.verticalCenter: parent.verticalCenter
                            text: janela.nome; maximumLength: 30
                            color: tema.texto; font.family: tema.familia; font.pixelSize: 15; selectByMouse: true
                            onTextEdited: janela.nome = text
                        }
                    }
                }
                Column {
                    width: (parent.width - 20) / 2
                    spacing: 8
                    Rotulo { text: "QUEM ATENDE PRIMEIRO" }
                    Row {
                        spacing: 10
                        Repeater {
                            model: [["jarvis", "Jarvis"], ["friday", "Friday"]]
                            Opcao {
                                required property var modelData
                                width: 140; height: 44
                                titulo: modelData[1]
                                escolhida: janela.persona === modelData[0]
                                onEscolher: janela.persona = modelData[0]
                            }
                        }
                    }
                }
            }
            Column {
                width: parent.width
                spacing: 8
                Rotulo { text: "VOZES" }
                Row {
                    width: parent.width
                    spacing: 12
                    Opcao {
                        width: (parent.width - 12) / 2
                        titulo: "Dubladas"
                        sub: "As vozes do Jarvis e da Friday · ~9 GB"
                        etiqueta: janela.pc && janela.pc.dubladas ? "SEU PC AGUENTA" : ""
                        ativa: !!janela.pc && janela.pc.dubladas
                        escolhida: janela.vozes === "dubladas"
                        onEscolher: janela.vozes = "dubladas"
                    }
                    Opcao {
                        width: (parent.width - 12) / 2
                        titulo: "Leves"
                        sub: "Rodam em qualquer PC · 350 MB"
                        escolhida: janela.vozes === "leves"
                        onEscolher: janela.vozes = "leves"
                    }
                }
            }
            Column {
                width: parent.width
                spacing: 8
                Rotulo { text: "ONDE INSTALAR" }
                Row {
                    width: parent.width
                    spacing: 10
                    Rectangle {
                        width: parent.width - botaoPasta.width - 10; height: 44; radius: 10; color: cor.vidro
                        border.width: 1; border.color: cor.traco
                        Text {
                            x: 14; width: parent.width - 28; anchors.verticalCenter: parent.verticalCenter
                            text: janela.pasta; elide: Text.ElideMiddle
                            color: tema.texto; font.family: cor.mono; font.pixelSize: 13
                        }
                    }
                    Botao { id: botaoPasta; texto: "Procurar…"; vazio: true; height: 44; onClicado: seletorPasta.open() }
                }
                Text {
                    // ~ o que fica no disco: programa e ouvido (com placa NVIDIA, a parte CUDA), mais as vozes.
                    readonly property int usa: (janela.pc && janela.pc.nvidia ? 7 : 4) + (janela.vozes === "dubladas" ? 9 : 0)
                    readonly property int livre: instalador.discoLivre(janela.pasta)
                    text: livre + " GB livres nesse disco · a NOVA usa ~ " + usa + " GB"
                          + (livre < usa + 2 ? " · pouco espaço: escolhe outro disco" : "")
                    color: livre < usa + 2 ? cor.aviso : tema.textoFraco; font.family: cor.mono; font.pixelSize: 11
                }
            }
            Row {
                spacing: 26
                Marca { texto: "Ligar junto com o PC"; ligado: janela.comOPc; onTrocar: janela.comOPc = !janela.comOPc }
                Marca { texto: "Atalho no menu"; ligado: janela.atalho; onTrocar: janela.atalho = !janela.atalho }
                Marca { texto: "Ícone perto do relógio"; ligado: janela.bandeja; onTrocar: janela.bandeja = !janela.bandeja }
            }
            FolderDialog {
                id: seletorPasta
                title: "Onde instalar a NOVA?"
                onAccepted: {
                    janela.pasta = instalador.caminhoDe(selectedFolder.toString());
                }
            }
        }
    }

    Component {
        id: tela4
        Column {
            spacing: 18
            readonly property var p: janela.prog || ({ passos: [], fracao: 0, texto: "Começando…" })
            Cabeca {
                rotulo: "PASSO 4 · INSTALAÇÃO"
                titulo: p.fim ? "Núcleo" : "Montando o"
                destaque: p.fim ? "montado." : "núcleo."
                sub: p.erro ? "Parou num passo. O que já foi feito fica: tentar de novo continua daqui."
                     : "Pode deixar rodando. Se a internet cair, ele continua de onde parou."
            }
            Row {
                width: parent.width
                spacing: 16
                Text {
                    text: Math.round(p.fracao * 100) + "%"
                    color: tema.texto; font.family: tema.familia; font.pixelSize: 34; font.weight: Font.ExtraBold
                    anchors.verticalCenter: parent.verticalCenter
                }
                Rectangle {
                    width: parent.width - 110; height: 8; radius: 4; color: cor.vidro
                    anchors.verticalCenter: parent.verticalCenter
                    Rectangle {
                        width: parent.width * Math.max(0.02, p.fracao); height: parent.height; radius: 4
                        color: p.erro ? cor.aviso : cor.azul
                        Behavior on width { NumberAnimation { duration: 300 } }
                    }
                }
            }
            Caixa {
                folga: 6
                Repeater {
                    model: p.passos
                    Item {
                        required property var modelData
                        required property int index
                        width: parent.width; height: 38
                        Rectangle { visible: index > 0; x: 14; width: parent.width - 28; height: 1; color: cor.traco }
                        Rectangle {
                            x: 14; anchors.verticalCenter: parent.verticalCenter
                            width: 20; height: 20; radius: 10
                            color: modelData.estado === "feito" ? Qt.rgba(56 / 255, 211 / 255, 159 / 255, 0.14)
                                 : modelData.estado === "agora" ? Qt.rgba(77 / 255, 163 / 255, 1, 0.16)
                                 : modelData.estado === "erro" ? Qt.rgba(1, 180 / 255, 84 / 255, 0.16) : "transparent"
                            border.width: modelData.estado === "esperando" ? 1 : 0
                            border.color: cor.tracoForte
                            Text {
                                anchors.centerIn: parent
                                text: modelData.estado === "feito" ? "✓" : modelData.estado === "erro" ? "!" : ""
                                color: modelData.estado === "feito" ? cor.ok : cor.aviso; font.pixelSize: 11; font.weight: Font.Bold
                            }
                            BusyIndicator { anchors.centerIn: parent; width: 18; height: 18; running: modelData.estado === "agora"; visible: running }
                        }
                        Text {
                            x: 48; anchors.verticalCenter: parent.verticalCenter
                            text: modelData.nome
                            color: modelData.estado === "esperando" ? tema.textoFraco : tema.texto
                            font.family: tema.familia; font.pixelSize: 14
                        }
                        Text {
                            anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                            text: modelData.tamanho; color: tema.textoFraco; font.family: cor.mono; font.pixelSize: 11
                        }
                    }
                }
            }
            Text {
                width: parent.width; elide: Text.ElideRight
                text: "// " + p.texto
                color: tema.muitoFraco; font.family: cor.mono; font.pixelSize: 11
            }
            Rectangle {
                visible: !!p.erro
                width: parent.width; height: colErro.implicitHeight + 28; radius: 12
                color: Qt.rgba(1, 180 / 255, 84 / 255, 0.06)
                border.width: 1; border.color: Qt.rgba(1, 180 / 255, 84 / 255, 0.35)
                Column {
                    id: colErro
                    x: 16; y: 14; width: parent.width - 32; spacing: 10
                    Text {
                        width: parent.width; wrapMode: Text.WrapAnywhere; maximumLineCount: 4; elide: Text.ElideRight
                        text: p.erro || ""; color: tema.textoMedio; font.family: cor.mono; font.pixelSize: 11
                    }
                    Botao { texto: "Tentar de novo"; height: 36; onClicado: instalador.instalar() }
                }
            }
        }
    }


    component Espera: Row {
        property string texto: ""
        spacing: 9
        BusyIndicator { width: 18; height: 18; running: true; anchors.verticalCenter: parent.verticalCenter }
        Text { text: parent.texto; color: tema.textoFraco; font.family: cor.mono; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
    }

    // Uma linha de comando para copiar (o que precisa da senha do PC a pessoa roda).
    component Comando: Rectangle {
        id: comando
        property string texto: ""
        property bool copiado: false
        width: parent ? parent.width : 0; height: 40; radius: 9
        color: "#03050a"; border.width: 1; border.color: cor.traco
        Text {
            x: 12; width: parent.width - 110; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
            text: comando.texto; color: tema.texto; font.family: cor.mono; font.pixelSize: 12
        }
        TextEdit { id: copiar; visible: false; text: comando.texto }
        Botao {
            anchors.right: parent.right; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter
            height: 32; vazio: true; texto: comando.copiado ? "Copiado ✓" : "Copiar"
            onClicado: { copiar.selectAll(); copiar.copy(); comando.copiado = true }
        }
    }

    Component {
        id: tela5
        Column {
            spacing: 20
            readonly property var c: janela.conta || ({})
            Cabeca {
                rotulo: "PASSO 5 · CONTA DO CLAUDE"
                titulo: "O cérebro é"; destaque: "o seu Claude."
                sub: "O Jarvis e a Friday pensam com o Claude, na sua própria conta. Nada passa por servidor nosso."
            }
            Caixa {
                folga: 20
                Column {
                    width: parent.width; spacing: 14
                    // Já entrou (ou acabou de entrar).
                    Row {
                        visible: !!c.logado
                        spacing: 12
                        Rectangle {
                            width: 28; height: 28; radius: 14; color: Qt.rgba(56 / 255, 211 / 255, 159 / 255, 0.14)
                            Text { anchors.centerIn: parent; text: "✓"; color: cor.ok; font.weight: Font.Bold }
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            Text { text: "Conta ligada: " + (c.email || ""); color: tema.texto; font.family: tema.familia; font.pixelSize: 15; font.weight: Font.DemiBold }
                            Text {
                                text: c.plano ? "Plano " + c.plano + "." : "Confere se a conta tem o plano Pro ou Max."
                                color: tema.textoFraco; font.family: tema.familia; font.pixelSize: 13
                            }
                        }
                    }
                    Column {
                        visible: !c.logado
                        width: parent.width; spacing: 14
                        Text { text: "Entrar no Claude"; color: tema.texto; font.family: tema.familia; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text {
                            width: parent.width; wrapMode: Text.WordWrap; textFormat: Text.StyledText
                            text: "Abre o navegador, você entra com a sua conta do Claude e o site mostra um <b>código</b>. Cola ele aqui embaixo. Precisa do plano <b>Pro</b> ou <b>Max</b>."
                            color: tema.textoMedio; font.family: tema.familia; font.pixelSize: 14; lineHeight: 1.3
                        }
                        Botao { texto: c.url ? "Abrir o login de novo" : "Abrir o login do Claude"; height: 42; onClicado: {
                            if (c.url) Qt.openUrlExternally(c.url); else instalador.claudeEntrar() } }
                        Row {
                            visible: !!c.url
                            width: parent.width; spacing: 10
                            Rectangle {
                                width: parent.width - botaoCodigo.width - 10; height: 42; radius: 10; color: "#03050a"
                                border.width: 1; border.color: campoCodigo.activeFocus ? cor.azul : cor.traco
                                Text { visible: !campoCodigo.text; x: 14; anchors.verticalCenter: parent.verticalCenter; text: "Cola o código aqui"; color: tema.muitoFraco; font.family: tema.familia; font.pixelSize: 14 }
                                TextInput {
                                    id: campoCodigo
                                    x: 14; width: parent.width - 28; anchors.verticalCenter: parent.verticalCenter
                                    color: tema.texto; font.family: cor.mono; font.pixelSize: 13; selectByMouse: true; clip: true
                                    onAccepted: if (text) instalador.claudeCodigo(text)
                                }
                            }
                            Botao { id: botaoCodigo; texto: "Entrar"; height: 42; ativo: !!campoCodigo.text; onClicado: instalador.claudeCodigo(campoCodigo.text) }
                        }
                        Espera { visible: !!c.url; texto: "esperando você entrar no navegador…" }
                        Text {
                            visible: !!c.erro; width: parent.width; wrapMode: Text.WordWrap
                            text: c.erro || ""; color: cor.aviso; font.family: tema.familia; font.pixelSize: 13
                        }
                    }
                }
            }
            Text {
                text: "Não tem conta? Dá pra criar no mesmo lugar."
                color: tema.textoFraco; font.family: tema.familia; font.pixelSize: 13
            }
        }
    }

    Component {
        id: tela6
        Column {
            spacing: 18
            readonly property bool volumeBom: janela.picoMic > -40
            readonly property bool ruidoBaixo: janela.mic.ruido < -50
            Cabeca {
                rotulo: "PASSO 6 · MICROFONE"
                titulo: "Agora"; destaque: "fala com ele."
                sub: "Diga \"Hey Jarvis\" e depois \"Hey Friday\", do jeito que você vai chamar no dia a dia."
            }
            Row {
                width: parent.width; spacing: 22
                // A onda: o volume de agora.
                Rectangle {
                    width: 240; height: 150; radius: 14; color: cor.vidro; border.width: 1; border.color: cor.traco
                    Row {
                        anchors.centerIn: parent; spacing: 5
                        Repeater {
                            model: 22
                            Rectangle {
                                required property int index
                                readonly property real forca: Math.max(0.06, Math.min(1, (janela.mic.nivel + 70) / 50))
                                width: 5; radius: 3; anchors.verticalCenter: parent.verticalCenter
                                height: 8 + 100 * forca * (0.45 + 0.55 * Math.abs(Math.sin(index * 1.7 + janela.mic.nivel)))
                                color: janela.ouviuJarvis + janela.ouviuFriday > 0 ? cor.ok : cor.azul
                                Behavior on height { NumberAnimation { duration: 90 } }
                            }
                        }
                    }
                }
                Column {
                    width: parent.width - 262; spacing: 10
                    Rotulo { text: "MICROFONE" }
                    ComboBox {
                        id: escolhaMic
                        width: parent.width
                        height: 40
                        // No tema escuro do instalador (o padrão do Qt é claro).
                        background: Rectangle { radius: 10; color: cor.vidro; border.width: 1; border.color: escolhaMic.popup.visible ? cor.azul : cor.traco }
                        contentItem: Text {
                            leftPadding: 12; rightPadding: 30; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                            text: escolhaMic.displayText; color: tema.texto; font.family: tema.familia; font.pixelSize: 14
                        }
                        indicator: Text { x: escolhaMic.width - 24; anchors.verticalCenter: parent.verticalCenter; text: "▾"; color: tema.textoFraco; font.pixelSize: 13 }
                        delegate: ItemDelegate {
                            required property var modelData
                            required property int index
                            width: escolhaMic.width; height: 36
                            highlighted: escolhaMic.highlightedIndex === index
                            background: Rectangle { color: parent.highlighted ? cor.tracoForte : cor.vidro }
                            contentItem: Text { text: modelData.nome; color: tema.texto; font.family: tema.familia; font.pixelSize: 14; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
                        }
                        popup.background: Rectangle { radius: 10; color: cor.vidro; border.width: 1; border.color: cor.tracoForte }
                        model: instalador.entradas()
                        textRole: "nome"; valueRole: "id"
                        onActivated: { janela.ouviuJarvis = 0; janela.ouviuFriday = 0; instalador.microfoneTestar(currentValue) }
                    }
                    Repeater {
                        model: [
                            ["Volume", volumeBom ? "bom ✓" : "muito baixo: chega mais perto ou aumenta", volumeBom],
                            ["Ruído do ambiente", ruidoBaixo ? "baixo ✓" : "alto: o \"Hey\" pode falhar", ruidoBaixo],
                            ["\"Hey Jarvis\"", janela.ouviuJarvis ? "ouvido " + janela.ouviuJarvis + "× ✓" : "falta testar", janela.ouviuJarvis > 0],
                            ["\"Hey Friday\"", janela.ouviuFriday ? "ouvido " + janela.ouviuFriday + "× ✓" : "falta testar", janela.ouviuFriday > 0]
                        ]
                        Item {
                            required property var modelData
                            width: parent.width; height: 26
                            Text { text: modelData[0]; color: tema.textoMedio; font.family: tema.familia; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                text: modelData[1]; color: modelData[2] ? cor.ok : tema.textoFraco; font.family: cor.mono; font.pixelSize: 12
                            }
                        }
                    }
                    Text { visible: !!janela.mic.erro; width: parent.width; wrapMode: Text.WordWrap; text: janela.mic.erro || ""; color: cor.aviso; font.pixelSize: 13 }
                }
            }
        }
    }

    Component {
        id: tela7
        Column {
            spacing: 14
            Cabeca {
                rotulo: "PASSO 7 · CONEXÕES"
                titulo: "Ligar as"; destaque: "suas coisas."
                sub: "Tudo opcional. O que você pular fica em Ajustes → Conexões, na janela e no app."
            }
            Repeater {
                model: [
                    ["whatsapp", "WhatsApp", "Ler, mandar e avisar quem te escreveu"],
                    ["fora", "Fora de casa", "O celular fala com o PC de qualquer lugar (Tailscale)"],
                    ["celular", "Celular", "O app NOVA: depois do Fora de casa, em Ajustes → Conexões, com a NOVA ligada"],
                    ["musica", "Música", "Tocar YouTube pelo PC"]
                ]
                Rectangle {
                    id: cartao
                    required property var modelData
                    readonly property string cid: modelData[0]
                    readonly property var e: janela.conexoes[cid] || ({})
                    readonly property bool aberto: janela.conexaoAberta === cid
                    width: parent.width; radius: 12; color: cor.vidro; border.width: 1
                    border.color: aberto ? cor.azul : cor.traco
                    height: linhaCartao.height + (aberto ? passoCartao.height + 14 : 0) + 24
                    Item {
                        id: linhaCartao
                        x: 16; y: 12; width: parent.width - 32; height: 40
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            Text { text: modelData[1]; color: tema.texto; font.family: tema.familia; font.pixelSize: 15; font.weight: Font.DemiBold }
                            Text { text: modelData[2]; color: tema.textoFraco; font.family: tema.familia; font.pixelSize: 13 }
                        }
                        Text {
                            visible: e.estado === "conectado"
                            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                            text: "✓ " + (cid === "musica" ? "pronto" : "conectado"); color: cor.ok; font.family: cor.mono; font.pixelSize: 12
                        }
                        Botao {
                            visible: cid !== "celular" && e.estado !== "conectado"
                            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; height: 36
                            texto: aberto ? "Fechar" : "Conectar"; vazio: aberto
                            onClicado: {
                                if (aberto) { if (cid === "whatsapp" && e.estado === "esperando") instalador.conectar("whatsapp", "cancelar", ""); janela.conexaoAberta = "" }
                                else { janela.conexaoAberta = cid; instalador.conectar(cid, cid === "musica" ? "estado" : "conectar", "") }
                            }
                        }
                    }
                    Column {
                        id: passoCartao
                        visible: aberto
                        x: 16; anchors.top: linhaCartao.bottom; anchors.topMargin: 14; width: parent.width - 32; spacing: 10
                        // WhatsApp: o QR da ponte.
                        Row {
                            visible: cid === "whatsapp"
                            spacing: 18
                            Rectangle {
                                width: 150; height: 150; radius: 10; color: "white"
                                Image { anchors.fill: parent; anchors.margins: 4; source: e.qr || ""; smooth: false; visible: !!e.qr }
                                Espera { anchors.centerIn: parent; visible: !e.qr; texto: "" }
                            }
                            Column {
                                width: passoCartao.width - 168; spacing: 8; anchors.verticalCenter: parent.verticalCenter
                                Text { width: parent.width; wrapMode: Text.WordWrap; textFormat: Text.StyledText; color: tema.textoMedio; font.family: tema.familia; font.pixelSize: 14; lineHeight: 1.35
                                    text: "1. No celular, abre o WhatsApp<br>2. <b>Aparelhos conectados</b> → <b>Conectar um aparelho</b><br>3. Aponta a câmera para o código" }
                                Text { text: e.estado === "expirou" ? "O código expirou: fecha e abre de novo." : "O código troca a cada 20 segundos."; color: tema.textoFraco; font.family: tema.familia; font.pixelSize: 12 }
                            }
                        }
                        // Fora de casa: os passos do Tailscale.
                        Column {
                            visible: cid === "fora"
                            width: parent.width; spacing: 8
                            Text { text: (e.instalado ? "✓ " : "1. ") + "Instalar o Tailscale neste PC"; color: e.instalado ? cor.ok : tema.texto; font.family: tema.familia; font.pixelSize: 14 }
                            Comando { visible: !e.instalado; texto: e.comando_instalar || "" }
                            Text { text: (e.conta ? "✓ Entrou como " + e.conta : "2. Entrar com a sua conta"); color: e.conta ? cor.ok : tema.texto; font.family: tema.familia; font.pixelSize: 14 }
                            Comando { visible: !!e.instalado && !e.conta; texto: e.comando_entrar || "" }
                            Text { text: (e.celular ? "✓ Achei: " + e.celular : "3. No celular, instala o Tailscale e entra com a mesma conta"); color: e.celular ? cor.ok : tema.texto; font.family: tema.familia; font.pixelSize: 14 }
                            Text { visible: !!e.detalhe; width: parent.width; wrapMode: Text.WordWrap; text: e.detalhe || ""; color: cor.aviso; font.family: tema.familia; font.pixelSize: 13 }
                        }
                        // Música: o comando do mpv.
                        Column {
                            visible: cid === "musica"
                            width: parent.width; spacing: 8
                            Text { text: "Falta o programa que toca o som (o mpv). Copia e roda no terminal (pede a senha do PC):"; width: parent.width; wrapMode: Text.WordWrap; color: tema.textoMedio; font.family: tema.familia; font.pixelSize: 14 }
                            Comando { texto: e.comando || "sudo apt install mpv mpv-mpris" }
                        }
                    }
                }
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap; textFormat: Text.StyledText
                text: "✦ Gmail, Agenda e Drive vêm da sua conta do Claude: ligue em <b>claude.ai → Configurações → Conectores</b>, e o Jarvis e a Friday já usam."
                color: tema.textoFraco; font.family: tema.familia; font.pixelSize: 13
            }
        }
    }

    Component {
        id: tela8
        Item {
            Column {
                width: parent.width * 0.6
                anchors.verticalCenter: parent.verticalCenter
                spacing: 24
                Cabeca { rotulo: "TUDO PRONTO"; titulo: "A NOVA está"; destaque: "ligada." }
                Column {
                    id: dicas
                    width: parent.width
                    spacing: 14
                    Repeater {
                        model: [["🎙", "Diga <b>\"Hey Jarvis\"</b> ou <b>\"Hey Friday\"</b> de qualquer canto do quarto."],
                                ["◎", "A janela fica no <b>ícone perto do relógio</b>."],
                                ["📱", "Quer no celular? Pede: <b>\"Jarvis, me ajuda a ligar o app.\"</b>"]]
                        Row {
                            required property var modelData
                            spacing: 14
                            Text { text: modelData[0]; font.pixelSize: 18; color: cor.azul; width: 24 }
                            Text { text: modelData[1]; textFormat: Text.StyledText; color: tema.textoMedio; font.family: tema.familia; font.pixelSize: 15; anchors.verticalCenter: parent.verticalCenter
                                   width: dicas.width - 38; wrapMode: Text.WordWrap; lineHeight: 1.3 }
                        }
                    }
                }
            }
            Esfera {
                width: Math.min(parent.width * 0.36, 300); height: width
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                cor: "#4da3ff"; corDeFundo: janela.color   // (aqui dentro, "cor" é a da Esfera)
            }
        }
    }

    Component {
        id: emConstrucao
        Column {
            spacing: 18
            Cabeca {
                rotulo: "PASSO " + janela.tela + " · " + janela.passos[janela.tela - 1].toUpperCase()
                titulo: "Em"
                destaque: "construção."
                sub: "Esta tela vem nos próximos passos do instalador."
            }
        }
    }
}
