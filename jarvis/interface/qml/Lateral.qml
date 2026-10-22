import QtQuick
import QtQuick.Controls.Basic

// A barra lateral: a marca, o "Novo chat", a busca, as conversas por data e,
// embaixo, o estado do Jarvis (o átomo pequeno), a memória e os ajustes.
//
// O átomo daqui só anima quando ele está fazendo alguma coisa: dormindo (o
// dia inteiro) ele fica parado, e a janela não redesenha nada à toa.
Rectangle {
    id: raiz
    property var tema
    property var conversas            // ListModel: sessao, titulo, quando, origem, grupo
    property string selecionada: ""   // o id que está na tela
    property string pagina: "chat"
    property string estado: "dormindo"
    property bool conectado: false
    property color corAtual: "#7387a8"
    property real nivel: 0
    property bool sendoVista: true
    property alias filtro: busca.text
    signal novoChat()
    signal abrir(string id)
    signal irPara(string pagina)
    signal arrastar()
    signal alternarMaximizar()

    function focarBusca() { busca.forceActiveFocus(); }

    color: tema.lateral
    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: raiz.tema.traco }

    function iconeDaOrigem(o) {
        return { voz: tema.icones.voz, texto: tema.icones.teclado, digitado: tema.icones.teclado,
                 celular: tema.icones.celular, relogio: tema.icones.relogio, nova: tema.icones.mais }[o]
               || tema.icones.teclado;
    }

    // -- a marca (arrasta a janela, como a barra de título) -------------------
    Item {
        id: marca
        width: parent.width
        height: 56
        Row {
            anchors.verticalCenter: parent.verticalCenter
            x: 20
            spacing: 10
            AtomoFixo { tamanho: 22; cor: raiz.tema.persona; corDeFundo: raiz.tema.lateral }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "JARVIS"
                color: raiz.tema.textoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 13
                font.weight: Font.DemiBold
                font.letterSpacing: 3
            }
        }
        DragHandler { target: null; onActiveChanged: if (active) raiz.arrastar() }
        TapHandler { onDoubleTapped: raiz.alternarMaximizar() }
    }

    // -- novo chat -------------------------------------------------------------
    Rectangle {
        id: novo
        anchors.top: marca.bottom
        anchors.topMargin: 6
        x: 14
        width: parent.width - 28
        height: 40
        radius: 10
        color: areaNovo.containsMouse ? raiz.tema.superficie2 : raiz.tema.superficie
        border.width: 1
        border.color: raiz.tema.traco
        Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
        Row {
            anchors.verticalCenter: parent.verticalCenter
            x: 12
            spacing: 10
            Rectangle {
                width: 20; height: 20; radius: 6
                color: raiz.tema.persona
                Icone { anchors.centerIn: parent; caminho: raiz.tema.icones.mais; cor: "#06101d"; tamanho: 14; espessura: 2.6 }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Novo chat"
                color: raiz.tema.texto
                font.family: raiz.tema.familia
                font.pixelSize: 14
                font.weight: Font.Medium
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            anchors.rightMargin: 12
            text: "Ctrl N"
            color: raiz.tema.muitoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 12
        }
        MouseArea {
            id: areaNovo
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: raiz.novoChat()
        }
    }

    // -- busca -------------------------------------------------------------------
    Item {
        id: caixaBusca
        anchors.top: novo.bottom
        anchors.topMargin: 8
        x: 14
        width: parent.width - 28
        height: 34
        Icone {
            anchors.verticalCenter: parent.verticalCenter
            x: 12
            caminho: raiz.tema.icones.lupa
            cor: busca.activeFocus ? raiz.tema.textoMedio : raiz.tema.muitoFraco
            tamanho: 16
            espessura: 2
        }
        TextInput {
            id: busca
            anchors.verticalCenter: parent.verticalCenter
            x: 38
            width: parent.width - 46
            color: raiz.tema.texto
            selectionColor: raiz.tema.tracoForte
            font.family: raiz.tema.familia
            font.pixelSize: 13
            clip: true
            Keys.onEscapePressed: { text = ""; focus = false; }
            Text {
                visible: !busca.text && !busca.activeFocus
                text: "Procurar conversa"
                color: raiz.tema.muitoFraco
                font: busca.font
            }
        }
    }

    // -- as conversas ------------------------------------------------------------
    ListView {
        id: lista
        anchors.top: caixaBusca.bottom
        anchors.topMargin: 4
        anchors.bottom: rodape.top
        x: 8
        width: parent.width - 16
        clip: true
        model: raiz.conversas
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {
            contentItem: Rectangle {
                implicitWidth: 4; radius: 2
                color: raiz.tema.tracoForte
                opacity: parent.active ? 0.9 : 0.0
                Behavior on opacity { NumberAnimation { duration: raiz.tema.normal } }
            }
        }

        section.property: "grupo"
        section.delegate: Item {
            required property string section
            width: lista.width
            height: 34
            Text {
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 6
                x: 12
                text: section.toUpperCase()
                color: raiz.tema.muitoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 11
                font.weight: Font.DemiBold
                font.letterSpacing: 0.8
            }
        }

        delegate: Rectangle {
            id: item
            required property string sessao
            required property string titulo
            required property string origem
            readonly property bool combina: raiz.filtro === ""
                || titulo.toLowerCase().indexOf(raiz.filtro.toLowerCase()) >= 0
            readonly property bool escolhida: sessao === raiz.selecionada && raiz.pagina === "chat"
            width: lista.width
            height: combina ? 36 : 0
            visible: combina
            radius: 8
            color: escolhida ? raiz.tema.superficie2
                 : areaItem.containsMouse ? raiz.tema.superficie : "transparent"
            Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
            Icone {
                anchors.verticalCenter: parent.verticalCenter
                x: 12
                caminho: raiz.iconeDaOrigem(item.origem)
                cor: item.escolhida ? raiz.tema.persona : raiz.tema.muitoFraco
                tamanho: 14
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                x: 36
                width: parent.width - 46
                elide: Text.ElideRight
                text: item.titulo
                color: item.escolhida ? raiz.tema.texto : raiz.tema.textoMedio
                font.family: raiz.tema.familia
                font.pixelSize: 14
            }
            MouseArea {
                id: areaItem
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: raiz.abrir(item.sessao)
            }
        }
    }

    // -- embaixo: o estado, a memória e os ajustes --------------------------------
    Column {
        id: rodape
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        width: parent.width
        Rectangle { width: parent.width; height: 1; color: raiz.tema.traco }
        Item {
            width: parent.width
            height: 64
            Item {
                id: atomoDoEstado
                anchors.verticalCenter: parent.verticalCenter
                x: 18
                width: 42; height: 42
                readonly property bool ativo: raiz.conectado && raiz.estado !== "dormindo"
                Esfera {
                    anchors.fill: parent
                    visible: atomoDoEstado.ativo
                    sendoVista: raiz.sendoVista && atomoDoEstado.ativo
                    corDeFundo: raiz.tema.lateral
                    cor: raiz.corAtual
                    nivel: raiz.nivel
                    velocidade: raiz.estado === "pensando" ? 2.2 : 1.2
                    turbulencia: raiz.estado === "pensando" ? 1.0 : 0.3
                }
                AtomoFixo {
                    anchors.centerIn: parent
                    visible: !atomoDoEstado.ativo
                    tamanho: 36
                    cor: raiz.corAtual
                    corDeFundo: raiz.tema.lateral
                    opacity: raiz.conectado ? 0.9 : 0.5
                }
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: atomoDoEstado.right
                anchors.leftMargin: 12
                spacing: 2
                Text {
                    text: raiz.tema.rotuloDoEstado(raiz.conectado ? raiz.estado : "")
                    color: raiz.corAtual
                    font.family: raiz.tema.familia
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.6
                    Behavior on color { ColorAnimation { duration: raiz.tema.normal } }
                }
                Text {
                    text: raiz.tema.dicaDoEstado(raiz.conectado ? raiz.estado : "")
                    color: raiz.tema.textoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 12
                }
            }
        }
        Repeater {
            model: [
                { pagina: "memoria", nome: "Memória", icone: "memoria" },
                { pagina: "ajustes", nome: "Ajustes", icone: "ajustes" },
            ]
            Rectangle {
                required property var modelData
                readonly property bool aqui: raiz.pagina === modelData.pagina
                x: 8
                width: raiz.width - 16
                height: 36
                radius: 8
                color: aqui ? raiz.tema.superficie2 : areaLink.containsMouse ? raiz.tema.superficie : "transparent"
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 12
                    spacing: 12
                    Icone {
                        anchors.verticalCenter: parent.verticalCenter
                        caminho: raiz.tema.icones[modelData.icone]
                        cor: aqui ? raiz.tema.texto : raiz.tema.textoFraco
                        tamanho: 18
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.nome
                        color: aqui ? raiz.tema.texto : raiz.tema.textoMedio
                        font.family: raiz.tema.familia
                        font.pixelSize: 14
                    }
                }
                MouseArea {
                    id: areaLink
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: raiz.irPara(aqui ? "chat" : modelData.pagina)
                }
            }
        }
    }
}
