import QtQuick
import QtQuick.Controls.Basic

// A memória do Jarvis: o CLAUDE.md da casa, inteiro, em markdown. É o que
// ele sabe do Léo; muda quando o Léo pede "lembra que…" ou "esquece…".
Item {
    id: raiz
    property var tema
    property string texto: ""
    property bool carregando: false
    signal copiar(string texto)

    Flickable {
        id: rolagem
        anchors.fill: parent
        contentHeight: coluna.height + 80
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {
            contentItem: Rectangle {
                implicitWidth: 6; radius: 3
                color: raiz.tema.tracoForte
                opacity: parent.active ? 0.9 : 0.0
            }
        }

        Column {
            id: coluna
            x: Math.max(32, (parent.width - width) / 2)
            y: 40
            width: Math.min(780, raiz.width - 64)
            spacing: 6

            Text {
                text: "Memória"
                color: raiz.tema.texto
                font.family: raiz.tema.familia
                font.pixelSize: 28
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "O que o Jarvis sabe de ti. Pra mudar, é só falar: \"lembra que…\" ou \"esquece…\"."
                color: raiz.tema.textoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 14
            }
            Item { width: 1; height: 22 }
            Rectangle {
                width: parent.width
                height: corpo.height + 48
                radius: 14
                color: raiz.tema.lateral
                border.width: 1
                border.color: raiz.tema.traco
                BlocoMarkdown {
                    id: corpo
                    x: 24; y: 24
                    width: parent.width - 48
                    tema: raiz.tema
                    tamanhoDaFonte: 15
                    texto: raiz.carregando ? "Carregando…"
                         : raiz.texto || "Nada ainda. Fala \"lembra que…\" pra ele anotar."
                    onCopiar: function (t) { raiz.copiar(t) }
                }
            }
        }
    }
}
