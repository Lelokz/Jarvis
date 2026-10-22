import QtQuick
import QtQuick.Controls.Basic

// A conversa: uma coluna no meio da área (como no app do Claude), rolando
// por baixo. O modelo vem de fora (Falas): a janela tem um para a conversa
// ao vivo e outro para a antiga que o Léo abriu na barra lateral.
Item {
    id: raiz
    property var tema
    property var falas
    property bool pensando: false
    property string textoPensando: "Pensando…"
    property color corPensando: "#9b7bff"
    property color corPersona: tema ? tema.persona : "#4da3ff"
    property real largura: Math.min(780, width - 64)
    signal copiar(string texto)
    signal responder(string texto)

    // "Estou acompanhando o fim da conversa." Só muda quando o Léo rola a
    // lista — e não a cada fala nova (decidir por `atYEnd` na hora da fala
    // falhava logo depois do histórico, com as falas ainda sem altura).
    property bool seguindo: true

    function irProFim() {
        raiz.seguindo = true;
        Qt.callLater(lista.positionViewAtEnd);
    }

    ListView {
        id: lista
        anchors.fill: parent
        clip: true
        model: raiz.falas
        topMargin: 28
        bottomMargin: 24
        boundsBehavior: Flickable.StopAtBounds
        onCountChanged: if (raiz.seguindo) Qt.callLater(positionViewAtEnd)
        onMovementEnded: raiz.seguindo = atYEnd
        onContentHeightChanged: if (raiz.seguindo && !moving) Qt.callLater(positionViewAtEnd)

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            contentItem: Rectangle {
                implicitWidth: 6
                radius: 3
                color: raiz.tema.tracoForte
                opacity: parent.active ? 0.9 : 0.0
                Behavior on opacity { NumberAnimation { duration: raiz.tema.normal } }
            }
        }

        delegate: Mensagem {
            tema: raiz.tema
            largura: raiz.largura
            corPersona: raiz.corPersona
            quem: model.quem
            texto: model.texto
            origem: model.origem
            titulo: model.titulo
            quando: model.quando
            perguntando: model.perguntando
            opcoes: model.opcoes
            passos: model.passos
            animar: model.animar
            onCopiar: function (t) { raiz.copiar(t) }
            onResponder: function (t) { raiz.responder(t) }
        }

        // Enquanto ele trabalha: o átomo roxo e o que está fazendo.
        footer: Item {
            width: lista.width
            height: raiz.pensando ? 46 : 0
            Behavior on height { NumberAnimation { duration: raiz.tema.normal; easing.type: Easing.OutCubic } }
            Row {
                x: Math.max(0, (parent.width - raiz.largura) / 2)
                y: 8
                spacing: 16
                opacity: raiz.pensando ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: raiz.tema.normal } }
                AtomoFixo {
                    tamanho: 30
                    cor: raiz.corPensando
                    corDeFundo: raiz.tema.fundo
                    SequentialAnimation on opacity {
                        running: raiz.pensando
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.45; duration: 900; easing.type: Easing.InOutSine }
                        NumberAnimation { from: 0.45; to: 1.0; duration: 900; easing.type: Easing.InOutSine }
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: raiz.textoPensando
                    color: raiz.tema.textoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 14
                }
            }
        }
    }

    // A conversa some por baixo da barra de escrever, em vez de cortar seco.
    Rectangle {
        anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
        height: 28
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 1.0; color: raiz.tema.fundo }
        }
    }

    // Voltar pro fim, quando ele rolou para cima e chegou coisa nova.
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        width: 36; height: 36; radius: 18
        color: raiz.tema.superficie2
        border.width: 1
        border.color: raiz.tema.tracoForte
        visible: opacity > 0
        opacity: !raiz.seguindo && !lista.atYEnd ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: raiz.tema.rapido } }
        Icone {
            anchors.centerIn: parent
            caminho: raiz.tema.icones.seta
            cor: raiz.tema.texto
            tamanho: 18
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: raiz.irProFim()
        }
    }
}
