import QtQuick

// Um ícone de traço, de um caminho SVG numa caixa de 24×24 (os caminhos
// moram no Tema). Vira uma imagem SVG, e não um Shape: o Shape com o
// CurveRenderer ignorava o corte da lista (clip) e os ícones de mensagens
// que já tinham rolado para cima apareciam por cima da barra do topo.
Image {
    id: raiz
    property string caminho: ""
    property color cor: "#7e879b"
    property real tamanho: 18
    property real espessura: 1.8
    property bool cheio: false

    width: tamanho
    height: tamanho
    sourceSize: Qt.size(Math.ceil(tamanho * 2), Math.ceil(tamanho * 2))
    smooth: true
    asynchronous: false

    readonly property string _rgb: "rgb(" + Math.round(cor.r * 255) + "," + Math.round(cor.g * 255)
                                   + "," + Math.round(cor.b * 255) + ")"
    source: caminho === "" ? "" : "data:image/svg+xml;base64," + Qt.btoa(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        + '<path d="' + caminho + '" fill="' + (cheio ? _rgb : "none") + '" fill-opacity="' + cor.a
        + '" stroke="' + (cheio ? "none" : _rgb) + '" stroke-opacity="' + cor.a
        + '" stroke-width="' + espessura + '" stroke-linecap="round" stroke-linejoin="round"/></svg>')
}
