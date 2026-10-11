import QtQuick

// Botão da barra de título. Existe separado porque é o primeiro lugar onde o
// "bastante resposta visual" aparece: cresce, acende e troca de cor ao passar
// o mouse, e tudo isso com Behavior — nada muda num piscar seco.
Item {
    id: raiz
    property var tema
    property string simbolo: ""
    property color corDeFundoAtiva: raiz.tema ? raiz.tema.traco : "#1c2431"
    signal clicado()

    width: 26
    height: 26

    Rectangle {
        id: fundo
        anchors.fill: parent
        radius: raiz.tema ? raiz.tema.raioBotao : 8
        color: area.containsMouse ? raiz.corDeFundoAtiva : "transparent"
        opacity: area.containsMouse ? (area.containsPress ? 1.0 : 0.85) : 0.0
        scale: area.containsPress ? 0.92 : 1.0
        Behavior on color   { ColorAnimation  { duration: 160 } }
        Behavior on opacity { NumberAnimation { duration: 160 } }
        Behavior on scale   { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
    }

    Text {
        anchors.centerIn: parent
        text: raiz.simbolo
        font.family: raiz.tema ? raiz.tema.familia : "Noto Sans"
        renderType: Text.NativeRendering
        color: area.containsMouse ? (raiz.tema ? raiz.tema.texto : "#e6ebf2")
                                  : (raiz.tema ? raiz.tema.textoFraco : "#7e879b")
        font.pixelSize: 14
        Behavior on color { ColorAnimation { duration: 160 } }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        onClicked: raiz.clicado()
    }
}
