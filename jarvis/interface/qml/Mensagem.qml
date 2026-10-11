import QtQuick

// Uma fala na conversa. A sua vem numa bolha cheia, a dele numa bolha só de
// contorno — a diferença é de peso, não de cor, para a cor continuar sendo o
// que diz o ESTADO.
//
// A largura segue a regra que não cria laço: o texto pede `min(implicitWidth,
// máximo)`, e a bolha se ajusta ao texto. Pedir a largura do pai e o pai pedir
// a do filho degenerava a bolha num fiapo.
Item {
    id: raiz

    property var tema
    property string quem: "voce"          // "voce" | "jarvis"
    property string texto: ""
    property string acao: ""
    property bool perguntando: false
    property bool animar: true
    property color corDoEstado: "#4da3ff"

    readonly property bool minha: quem === "voce"
    readonly property real maxLargura: width * 0.86 - 28

    width: ListView.view ? ListView.view.width : 320
    height: bolha.height + 8

    Rectangle {
        id: bolha
        anchors.right: raiz.minha ? parent.right : undefined
        anchors.left: raiz.minha ? undefined : parent.left
        // A entrada anima ESTE y, e não o do delegado: num ListView quem manda
        // no y do delegado é a lista, e as duas coisas brigando empilhavam
        // todas as falas na mesma linha.
        //
        // Sem animar, os valores já nascem no destino e os Behaviors não têm o
        // que fazer — é assim que o histórico entra inteiro, parado.
        y: raiz.animar ? 8 : 0
        opacity: raiz.animar ? 0 : 1
        Component.onCompleted: { y = 0; opacity = 1; }
        Behavior on y { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
        width: conteudo.width + 28
        height: conteudo.height + 22
        radius: 14
        color: raiz.minha ? raiz.tema.superficie : "transparent"
        border.width: raiz.minha ? 0 : 1
        border.color: raiz.perguntando ? raiz.corDoEstado : raiz.tema.traco
        Behavior on border.color { ColorAnimation { duration: raiz.tema.normal } }

        Column {
            id: conteudo
            anchors.centerIn: parent
            spacing: 5

            Text {
                id: corpoDaFala
                width: Math.min(implicitWidth, raiz.maxLargura)
                text: raiz.texto
                color: raiz.tema.texto
                font.family: raiz.tema.familia
                font.pixelSize: 14
                renderType: Text.NativeRendering
                wrapMode: Text.WordWrap
            }

            // O que ele FEZ, e não só o que disse. É a §2.5 aparecendo na tela.
            Text {
                visible: raiz.acao !== ""
                width: Math.min(implicitWidth, raiz.maxLargura)
                text: raiz.acao
                color: raiz.tema.textoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 10
                font.letterSpacing: 0.5
                renderType: Text.NativeRendering
                elide: Text.ElideRight
            }
        }
    }

}
