import QtQuick
import "atomo.js" as Atomo

// A esfera: o átomo da NOVA, animado (o definitivo, 27/10/2026 — o mesmo do
// site). O desenho mora em atomo.js: núcleo geodésico, três argolas de
// formatos diferentes girando como moeda e oito bolinhas com rastro.
//
// O estado continua sem trocar de imagem: vira número, e todo número atravessa
// um Behavior. `escala` aumenta e diminui o átomo, `velocidade` acelera o
// tempo dele, `nivel` (a voz) e `brilho` acendem o brilho, `parada` congela
// e apaga, `pulsando` respira devagar.
Item {
    id: raiz

    property real escala: 1.0
    property real turbulencia: 0.0      // do átomo antigo; o novo não usa (quem passa, pode continuar)
    property real velocidade: 1.0       // quão rápido o tempo do átomo anda
    property real brilho: 1.0
    property real nivel: 0.0
    property color cor: "#4da3ff"
    property color corDeFundo: "#0a0c10"
    property bool sendoVista: true
    property bool parada: false         // sem conexão: o átomo congela
    property bool pulsando: false       // dormindo: respira devagar

    Behavior on escala      { NumberAnimation { duration: 520; easing.type: Easing.OutBack; easing.overshoot: 1.05 } }
    Behavior on velocidade  { NumberAnimation { duration: 900; easing.type: Easing.InOutCubic } }
    Behavior on brilho      { NumberAnimation { duration: 420; easing.type: Easing.InOutQuad } }
    Behavior on cor         { ColorAnimation  { duration: 640; easing.type: Easing.InOutQuad } }

    readonly property real lado: Math.min(width, height)
    readonly property bool animando: sendoVista && !parada

    property real _nivelSuave: 0.0
    Behavior on _nivelSuave { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
    onNivelChanged: _nivelSuave = nivel

    property real _respiro: 1.0
    SequentialAnimation on _respiro {
        running: raiz.animando && raiz.pulsando
        loops: Animation.Infinite
        NumberAnimation { to: 0.94; duration: 2200; easing.type: Easing.InOutSine }
        NumberAnimation { to: 1.0; duration: 2200; easing.type: Easing.InOutSine }
        onRunningChanged: if (!running) raiz._respiro = 1.0
    }

    // O tempo do átomo é SOMADO a cada quadro (e não uma animação de 0 a N):
    // assim trocar a velocidade vale no quadro seguinte, sem pulo. Desenha a
    // 30 quadros por segundo: o átomo anda devagar, e o desenho custa ~5 ms.
    property real tempo: 3
    property real _desdeODesenho: 0
    property var _estado: Atomo.novo()
    FrameAnimation {
        running: raiz.animando
        onTriggered: {
            var dt = Math.min(frameTime, 0.1)
            raiz.tempo += dt * raiz.velocidade
            raiz._desdeODesenho += dt
            if (raiz._desdeODesenho >= 1 / 31) {
                raiz._desdeODesenho = 0
                tela.requestPaint()
            }
        }
    }

    function _rgb(c) { return [c.r * 255, c.g * 255, c.b * 255] }

    Canvas {
        id: tela
        anchors.centerIn: parent
        width: raiz.lado
        height: raiz.lado
        opacity: raiz.parada ? 0.55 : 1.0
        Behavior on opacity { NumberAnimation { duration: 600 } }
        transform: Scale {
            origin.x: tela.width / 2; origin.y: tela.height / 2
            xScale: raiz.escala * raiz._respiro; yScale: xScale
        }
        onPaint: Atomo.desenhar(getContext("2d"), width, height, raiz.tempo, raiz._rgb(raiz.cor), {
            estado: raiz._estado, fundo: raiz._rgb(raiz.corDeFundo),
            brilho: raiz.brilho * (1 + raiz._nivelSuave * 0.6)
        })
        // Parada, a cor ainda pode mudar (o estado mudou): redesenha uma vez.
        Connections {
            target: raiz
            function onCorChanged() { tela.requestPaint() }
            function onCorDeFundoChanged() { tela.requestPaint() }
        }
        onWidthChanged: requestPaint()
    }
}
