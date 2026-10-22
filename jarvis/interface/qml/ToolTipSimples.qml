import QtQuick

// Uma dica curta em cima de um botão ("Parar"), sem depender do estilo do Qt.
Rectangle {
    id: raiz
    property var tema
    property bool visivel: false
    property string texto: ""

    anchors.bottom: parent.top
    anchors.bottomMargin: 8
    anchors.horizontalCenter: parent.horizontalCenter
    width: rotulo.implicitWidth + 16
    height: 26
    radius: 7
    color: tema.superficie2
    border.width: 1
    border.color: tema.tracoForte
    opacity: visivel ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 120 } }
    Text {
        id: rotulo
        anchors.centerIn: parent
        text: raiz.texto
        color: raiz.tema.texto
        font.family: raiz.tema.familia
        font.pixelSize: 12
    }
}
