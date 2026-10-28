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
    width: 1040
    height: 680
    minimumWidth: 900
    minimumHeight: 620
    visible: true
    title: "Instalador da NOVA"
    flags: Qt.Window | Qt.FramelessWindowHint
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

    Connections {
        target: instalador
        function onChecou(dados) {
            janela.pc = dados;
            janela.vozes = dados.dubladas ? "dubladas" : "leves";
        }
    }
    onTelaChanged: if (tela === 2 && !pc) instalador.checar()

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
            Image { source: "img/atomo.png"; width: 32; height: 32; sourceSize.width: 64; smooth: true; mipmap: true }
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

        Loader {
            id: telaAtual
            x: 46; y: 54
            width: area.width - 92
            height: area.height - 54 - 96
            sourceComponent: [tela1, tela2, tela3, emConstrucao, emConstrucao, emConstrucao, emConstrucao, emConstrucao][janela.tela - 1]
        }

        // Os botões de baixo.
        Row {
            anchors.right: parent.right; anchors.rightMargin: 46
            anchors.bottom: parent.bottom; anchors.bottomMargin: 30
            spacing: 18
            Botao {
                visible: janela.tela > 1 && janela.tela !== 4
                texto: "← Voltar"
                vazio: true
                onClicado: janela.tela--
            }
            Botao {
                texto: janela.tela === 1 ? "Começar →" : janela.tela === 3 ? "Instalar →" : "Continuar →"
                ativo: janela.tela !== 2 || (!!janela.pc && janela.pc.pode)
                visible: janela.tela < 4
                onClicado: {
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
            Image {
                source: "img/atomo.png"
                width: Math.min(parent.width * 0.4, 330); height: width
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                sourceSize.width: 512; smooth: true; mipmap: true
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
                    var p = instalador.caminhoDe(selectedFolder.toString());
                    // Uma pasta própria dentro da escolhida, para não espalhar arquivos.
                    janela.pasta = p.endsWith("/NOVA") ? p : p + "/NOVA";
                }
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
