import QtQuick
import QtQuick.Shapes

// O átomo parado: o avatar das respostas e a marca da barra lateral. Os
// mesmos três anéis da Esfera (raio e inclinação), sem animação: desenhado
// uma vez, não custa nada depois.
Item {
    id: raiz
    property color cor: "#4da3ff"
    property color corDeFundo: "#0a0c10"
    property real tamanho: 30

    width: tamanho
    height: tamanho

    readonly property real meio: tamanho / 2
    readonly property var aneis: [
        { rx: 0.46, ry: 0.15, angulo: 0 },
        { rx: 0.39, ry: 0.22, angulo: 62 },
        { rx: 0.32, ry: 0.12, angulo: 121 },
    ]

    // O brilho do núcleo, e o disco escuro que faz os anéis passarem "atrás".
    Rectangle {
        anchors.centerIn: parent
        width: raiz.tamanho * 0.6; height: width; radius: width / 2
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: Qt.rgba(raiz.cor.r, raiz.cor.g, raiz.cor.b, 0.10) }
            GradientStop { position: 1.0; color: Qt.rgba(raiz.cor.r, raiz.cor.g, raiz.cor.b, 0.04) }
        }
    }
    Rectangle {
        anchors.centerIn: parent
        width: raiz.tamanho * 0.34; height: width; radius: width / 2
        color: Qt.rgba(raiz.cor.r, raiz.cor.g, raiz.cor.b, 0.55)
    }

    Repeater {
        model: raiz.aneis
        Shape {
            required property var modelData
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            transform: Rotation {
                origin.x: raiz.meio; origin.y: raiz.meio
                angle: modelData.angulo
            }
            ShapePath {
                fillColor: "transparent"
                strokeColor: raiz.cor
                strokeWidth: Math.max(1.0, raiz.tamanho / 22)
                PathAngleArc {
                    centerX: raiz.meio; centerY: raiz.meio
                    radiusX: raiz.tamanho * modelData.rx
                    radiusY: raiz.tamanho * modelData.ry
                    startAngle: 0; sweepAngle: 360
                }
            }
        }
    }
}
