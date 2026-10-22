import QtQuick

// O átomo parado: o avatar das respostas e a marca da barra lateral. Os
// mesmos três anéis da Esfera (raio e inclinação), sem animação. É uma imagem
// SVG (e não Shapes): respeita o corte da lista e não custa nada depois de
// desenhada. O ícone da bandeja (atomo_icone.py) é o mesmo desenho.
Image {
    id: raiz
    property color cor: "#4da3ff"
    property color corDeFundo: "#0a0c10"
    property real tamanho: 30

    width: tamanho
    height: tamanho
    sourceSize: Qt.size(Math.ceil(tamanho * 2), Math.ceil(tamanho * 2))
    smooth: true

    readonly property string _rgb: "rgb(" + Math.round(cor.r * 255) + "," + Math.round(cor.g * 255)
                                   + "," + Math.round(cor.b * 255) + ")"
    // O traço em unidades da caixa de 100: ~1/22 do lado, como antes.
    readonly property real _traco: Math.max(100 / tamanho, 100 / 22)

    function _anel(rx, ry, angulo) {
        return '<ellipse rx="' + rx + '" ry="' + ry + '" transform="rotate(' + angulo + ')" fill="none" stroke="'
               + _rgb + '" stroke-width="' + _traco + '"/>';
    }

    source: "data:image/svg+xml;base64," + Qt.btoa(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-50 -50 100 100">'
        + '<circle r="30" fill="' + _rgb + '" fill-opacity="0.08"/>'
        + '<circle r="17" fill="' + _rgb + '" fill-opacity="0.55"/>'
        + _anel(46, 15, 0) + _anel(39, 22, 62) + _anel(32, 12, 121)
        + '</svg>')
}
