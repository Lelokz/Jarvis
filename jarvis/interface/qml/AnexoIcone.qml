import QtQuick
import QtQuick.Shapes

// Ícone de anexo, desenhado em vetor (24x24). **Só o visual nesta etapa**:
// anexo de verdade é coisa de mais para frente, e o botão diz isso ao ser
// tocado em vez de fingir que funciona.
Item {
    id: raiz
    property var tema
    property string traco: ""      // o caminho SVG
    property string aviso: ""
    signal tocado()

    width: 34
    height: 34

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: area.containsMouse ? raiz.tema.superficie : "transparent"
        opacity: area.containsMouse ? 1.0 : 0.0
        scale: area.containsPress ? 0.92 : 1.0
        Behavior on opacity { NumberAnimation { duration: 160 } }
        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
    }

    Shape {
        anchors.centerIn: parent
        width: 24; height: 24
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: "transparent"
            strokeColor: area.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco
            strokeWidth: 1.4
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: raiz.traco }
        }
        Behavior on opacity { NumberAnimation { duration: 160 } }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        onClicked: raiz.tocado()
    }
}
