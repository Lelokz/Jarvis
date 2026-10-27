import QtQuick
import "atomo.js" as Atomo

// O átomo parado: o avatar das respostas e a marca da barra lateral. O mesmo
// átomo da Esfera (atomo.js), num quadro só, com o traço mais grosso para ler
// em tamanho pequeno. Desenhado uma vez (e de novo só se a cor ou o tamanho
// mudar): não custa nada depois. O ícone da bandeja (atomo_icone.py) é a foto
// do mesmo átomo.
Canvas {
    id: raiz
    property color cor: "#4da3ff"
    property color corDeFundo: "#0a0c10"
    property real tamanho: 30

    width: tamanho
    height: tamanho

    // Um estado só para todos (as faces acesas do núcleo saem sempre iguais).
    readonly property var _estado: Atomo.novo()
    function _rgb(c) { return [c.r * 255, c.g * 255, c.b * 255] }

    onPaint: Atomo.desenhar(getContext("2d"), width, height, 5.2, _rgb(cor), {
        estado: _estado, fundo: _rgb(corDeFundo), traco: tamanho < 64 ? 3 : 1.5
    })
    onCorChanged: requestPaint()
    onCorDeFundoChanged: requestPaint()
    onTamanhoChanged: requestPaint()
}
