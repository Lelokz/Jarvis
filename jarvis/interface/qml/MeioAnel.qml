import QtQuick
import QtQuick.Shapes

// Metade de um anel — a de trás ou a da frente.
//
// O anel é uma elipse cujo raio vertical acompanha o cosseno do ângulo: ele
// abre, fecha até virar uma linha, e abre de novo. É um aro girando em torno
// do eixo horizontal, visto de frente.
//
// Quando o cosseno troca de sinal, o aro passou de perfil: a metade que estava
// atrás agora está na frente. Por isso `metadeDeCima` depende do sinal — e a
// troca é invisível, porque acontece quando as duas metades coincidem.
Shape {
    id: raiz

    property var anel                 // { vel, fase, raio, inclinacao }
    property bool atras: false
    property real corpoLado: 100
    property real giro: 0
    property color cor: "#4da3ff"
    property real brilho: 1.0

    readonly property real angulo: (giro * anel.vel + anel.fase) * Math.PI / 180
    readonly property real coseno: Math.cos(angulo)
    readonly property real raioX: corpoLado * anel.raio
    // Nunca zera de todo: um aro exatamente de perfil some, e some feio.
    readonly property real raioY: Math.max(corpoLado * 0.012, raioX * Math.abs(coseno))
    // Qual metade fica atrás depende do lado para onde o aro está inclinado.
    readonly property bool metadeDeCima: atras === (coseno >= 0)

    anchors.fill: parent
    preferredRendererType: Shape.CurveRenderer

    transform: Rotation {
        origin.x: raiz.corpoLado / 2
        origin.y: raiz.corpoLado / 2
        axis { x: 0; y: 0; z: 1 }
        angle: raiz.anel.inclinacao
    }

    ShapePath {
        fillColor: "transparent"
        // A metade de trás é mais apagada: é o que o olho usa para saber que
        // ela está mais longe, junto com o corpo opaco cobrindo o meio dela.
        strokeColor: Qt.rgba(raiz.cor.r, raiz.cor.g, raiz.cor.b,
                             (raiz.atras ? 0.26 : 0.52) * raiz.brilho)
        strokeWidth: raiz.atras ? 1.0 : 1.3
        capStyle: ShapePath.RoundCap
        PathAngleArc {
            centerX: raiz.corpoLado / 2
            centerY: raiz.corpoLado / 2
            radiusX: raiz.raioX
            radiusY: raiz.raioY
            startAngle: raiz.metadeDeCima ? 180 : 0
            sweepAngle: 180
        }
    }
}
