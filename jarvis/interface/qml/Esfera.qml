import QtQuick
import QtQuick.Shapes
import QtQuick.Particles
import QtQuick.Effects

// A esfera: um átomo com profundidade de verdade.
//
// **Por que a primeira versão parecia chapada.** Ela girava os anéis em torno
// do eixo da TELA. Isso roda o desenho no próprio plano e nunca muda quem está
// na frente de quem: os anéis eram desenhados depois do núcleo, então ficavam
// por cima o tempo todo. O Léo leu isso nos retratos parados — "nenhum anel
// passa atrás do núcleo".
//
// **Como funciona agora.** Cada anel é desenhado em DUAS METADES: uma antes do
// núcleo e outra depois. O que anima é o achatamento da elipse (`ry`), como um
// aro girando em torno do eixo horizontal. Quando ele passa de perfil, a
// metade de trás troca com a da frente — e a troca é invisível porque acontece
// no instante em que as duas coincidem numa linha.
//
// O disco opaco no meio é o que torna o "atrás" visível: o núcleo é um
// gradiente translúcido e, sozinho, não esconderia nada.
//
// O estado continua sem trocar de imagem: vira número, e todo número atravessa
// um Behavior.
Item {
    id: raiz

    property real escala: 1.0
    property real turbulencia: 0.0      // energia das partículas
    property real velocidade: 1.0       // quão rápido os anéis giram
    property real brilho: 1.0
    property real nivel: 0.0
    property color cor: "#4da3ff"
    property color corDeFundo: "#0a0c10"
    property bool sendoVista: true
    property bool parada: false         // sem conexão: o átomo congela
    property bool pulsando: false       // dormindo: respira devagar

    Behavior on escala      { NumberAnimation { duration: 520; easing.type: Easing.OutBack; easing.overshoot: 1.05 } }
    Behavior on turbulencia { NumberAnimation { duration: 700; easing.type: Easing.InOutCubic } }
    Behavior on velocidade  { NumberAnimation { duration: 900; easing.type: Easing.InOutCubic } }
    Behavior on brilho      { NumberAnimation { duration: 420; easing.type: Easing.InOutQuad } }
    Behavior on cor         { ColorAnimation  { duration: 640; easing.type: Easing.InOutQuad } }

    readonly property real lado: Math.min(width, height)
    readonly property bool animando: sendoVista && !parada

    // Um ângulo só para todos os anéis: cada um aplica o próprio multiplicador
    // e a própria fase. Assim as duas metades de um anel nunca saem de sincronia.
    //
    // O giro é SOMADO a cada quadro, e não uma animação de 0 a 360. A versão
    // antiga tinha dois defeitos: ao voltar de 360 para 0, os anéis de 0.73 e
    // 1.31 davam um pulo (262,8° e 471,6° não fecham volta); e a duração só era
    // lida quando a animação começava, então trocar de estado não mudava a
    // velocidade. Somando, a velocidade vale no quadro seguinte.
    //
    // A volta em 36000 é sem pulo: 36000 × 0.73 e 36000 × 1.31 são voltas
    // inteiras (73 e 131). Um multiplicador novo precisa manter isso.
    property real giro: 0
    FrameAnimation {
        running: raiz.animando
        // 40°/s é uma volta em 9 s na velocidade 1.
        onTriggered: raiz.giro = (raiz.giro + frameTime * 40 * raiz.velocidade) % 36000
    }

    // Três anéis, cada um com velocidade, fase, raio e inclinação próprios.
    readonly property var aneis: [
        { vel: 1.00, fase:   0, raio: 0.46, inclinacao:   0 },
        { vel: 0.73, fase:  90, raio: 0.39, inclinacao:  62 },
        { vel: 1.31, fase: 210, raio: 0.32, inclinacao: 121 },
    ]

    property real _nivelSuave: 0.0
    Behavior on _nivelSuave { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
    onNivelChanged: _nivelSuave = nivel

    property real _respiro: 1.0
    SequentialAnimation on _respiro {
        running: raiz.animando && raiz.pulsando
        loops: Animation.Infinite
        NumberAnimation { from: 1.0; to: 1.055; duration: 2600; easing.type: Easing.InOutSine }
        NumberAnimation { from: 1.055; to: 1.0; duration: 2600; easing.type: Easing.InOutSine }
    }
    onPulsandoChanged: if (!pulsando) _respiro = 1.0

    MultiEffect {
        source: corpo
        anchors.fill: corpo
        blurEnabled: raiz.sendoVista
        blur: 0.85
        blurMax: 32
        brightness: 0.22 * raiz.brilho
        saturation: 0.15
        // Mais baixo do que parece necessário: o passe borra TUDO, inclusive o
        // corpo opaco, e o escuro espalhado virava um halo sujo em volta.
        opacity: 0.6
        visible: raiz.sendoVista
    }

    Item {
        id: corpo
        anchors.centerIn: parent
        width: raiz.lado
        height: raiz.lado
        scale: raiz.escala * raiz._respiro * (1.0 + raiz._nivelSuave * 0.08)
        Behavior on scale { NumberAnimation { duration: 90 } }

        readonly property real meio: width / 2

        // -- metades de trás ------------------------------------------------
        Repeater {
            model: raiz.aneis
            MeioAnel {
                required property var modelData
                anel: modelData
                atras: true
                corpoLado: corpo.width
                giro: raiz.giro
                cor: raiz.cor
                brilho: raiz.brilho
            }
        }

        // -- partículas de trás ---------------------------------------------
        ParticleSystem { id: sistemaTras; anchors.fill: parent; running: raiz.animando }
        Emitter {
            system: sistemaTras; anchors.fill: parent; enabled: raiz.animando
            emitRate: 7 + raiz.turbulencia * 26 + raiz._nivelSuave * 16
            lifeSpan: 2800; size: 3; endSize: 0
            shape: EllipseShape { fill: false }
            velocity: AngleDirection {
                angle: 0; angleVariation: 360
                magnitude: 4 + raiz.turbulencia * 26 + raiz._nivelSuave * 10
                magnitudeVariation: 8
            }
        }
        ImageParticle { system: sistemaTras; color: raiz.cor; alpha: 0.0; colorVariation: 0.3
                        opacity: 0.55; entryEffect: ImageParticle.Scale }

        // -- o corpo opaco: é ele que faz o "atrás" existir -------------------
        Rectangle {
            anchors.centerIn: parent
            width: corpo.width * 0.50
            height: width
            radius: width / 2
            color: raiz.corDeFundo
        }

        // -- o núcleo que brilha ---------------------------------------------
        Shape {
            anchors.fill: parent
            ShapePath {
                fillGradient: RadialGradient {
                    centerX: corpo.meio; centerY: corpo.meio
                    centerRadius: corpo.width * (0.27 + raiz._nivelSuave * 0.04)
                    focalX: centerX; focalY: centerY
                    GradientStop { position: 0.0; color: Qt.rgba(raiz.cor.r, raiz.cor.g, raiz.cor.b, 0.62 * raiz.brilho) }
                    GradientStop { position: 0.6; color: Qt.rgba(raiz.cor.r, raiz.cor.g, raiz.cor.b, 0.14 * raiz.brilho) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                strokeWidth: -1
                PathAngleArc {
                    centerX: corpo.meio; centerY: corpo.meio
                    radiusX: corpo.width * 0.30; radiusY: corpo.width * 0.30
                    startAngle: 0; sweepAngle: 360
                }
            }
        }

        // -- partículas da frente ---------------------------------------------
        ParticleSystem { id: sistemaFrente; anchors.fill: parent; running: raiz.animando }
        Emitter {
            system: sistemaFrente; anchors.fill: parent; enabled: raiz.animando
            emitRate: 7 + raiz.turbulencia * 26 + raiz._nivelSuave * 16
            lifeSpan: 2800; size: 3; endSize: 0
            shape: EllipseShape { fill: false }
            velocity: AngleDirection {
                angle: 0; angleVariation: 360
                magnitude: 4 + raiz.turbulencia * 26 + raiz._nivelSuave * 10
                magnitudeVariation: 8
            }
        }
        ImageParticle { system: sistemaFrente; color: raiz.cor; alpha: 0.0; colorVariation: 0.3
                        entryEffect: ImageParticle.Scale }

        // -- metades da frente ------------------------------------------------
        Repeater {
            model: raiz.aneis
            MeioAnel {
                required property var modelData
                anel: modelData
                atras: false
                corpoLado: corpo.width
                giro: raiz.giro
                cor: raiz.cor
                brilho: raiz.brilho
            }
        }
    }
}
