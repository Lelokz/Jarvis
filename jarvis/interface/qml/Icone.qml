import QtQuick
import QtQuick.Shapes

// Um ícone de traço, desenhado de um caminho SVG numa caixa de 24×24 (os
// caminhos moram no Tema). Desenho fixo: o Qt monta a forma uma vez só.
Item {
    id: raiz
    property string caminho: ""
    property color cor: "#7e879b"
    property real tamanho: 18
    property real espessura: 1.8
    property bool cheio: false

    width: tamanho
    height: tamanho

    Shape {
        width: 24
        height: 24
        preferredRendererType: Shape.CurveRenderer
        transform: Scale { xScale: raiz.tamanho / 24; yScale: raiz.tamanho / 24 }
        ShapePath {
            strokeColor: raiz.cheio ? "transparent" : raiz.cor
            fillColor: raiz.cheio ? raiz.cor : "transparent"
            strokeWidth: raiz.espessura
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: raiz.caminho }
        }
    }
}
