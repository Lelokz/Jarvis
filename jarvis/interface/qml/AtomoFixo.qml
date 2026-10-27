import QtQuick
import QtQuick.Window

// O átomo parado: o avatar das respostas e a marca da barra lateral. É o
// desenho dos ícones (icone_atomo.py, pelo ProvedorDoAtomo do interface.py):
// as argolas abertas, uma bolinha em cada, feito para ser lido pequeno.
// Transparente, então serve em cima de qualquer fundo.
Image {
    id: raiz
    property color cor: "#4da3ff"
    property color corDeFundo: "#0a0c10"   // não usa mais (quem passa, pode continuar)
    property real tamanho: 30

    width: tamanho
    height: tamanho
    readonly property int _lado: Math.ceil(tamanho * Screen.devicePixelRatio)
    sourceSize: Qt.size(_lado, _lado)
    source: "image://atomo/" + cor.toString().slice(1)   // sem o "#": na URL ele cortaria o resto
    smooth: true
    cache: true
}
