import QtQuick

// Uma fala na conversa. A sua vem numa bolha cheia, a dele numa bolha só de
// contorno — a diferença é de peso, não de cor. A única cor é a borda da
// pergunta que ainda espera resposta.
//
// Mais dois tipos, desde que o cérebro virou o Claude Code (out/2026):
//   painel     o que ele mandou para a janela (código, lista, passos): cartão
//              largo, markdown, texto selecionável para copiar;
//   atividade  o que ele está fazendo agora: uma linha fraca, sem bolha.
//
// A largura segue a regra que não cria laço: o texto pede `min(implicitWidth,
// máximo)`, e a bolha se ajusta ao texto. Pedir a largura do pai e o pai pedir
// a do filho degenerava a bolha num fiapo.
Item {
    id: raiz

    property var tema
    property string quem: "voce"          // "voce" | "jarvis" | "painel" | "atividade"
    property string texto: ""
    property string acao: ""
    property string titulo: ""
    property bool perguntando: false
    property bool animar: true

    readonly property bool minha: quem === "voce"
    readonly property bool painel: quem === "painel"
    readonly property bool atividade: quem === "atividade"
    readonly property real maxLargura: width * 0.86 - 28

    width: ListView.view ? ListView.view.width : 320
    height: atividade ? linhaDeAtividade.height + 6 : bolha.height + 8

    Text {
        id: linhaDeAtividade
        visible: raiz.atividade
        x: 4
        y: 3
        width: raiz.width - 8
        text: "▸ " + raiz.texto
        color: raiz.tema.textoFraco
        opacity: 0.8
        font.family: raiz.tema.familia
        font.pixelSize: 11
        font.letterSpacing: 0.3
        renderType: Text.NativeRendering
        elide: Text.ElideRight
    }

    Rectangle {
        id: bolha
        visible: !raiz.atividade
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
        width: raiz.painel ? raiz.width : conteudo.width + 28
        height: conteudo.height + 22
        radius: raiz.painel ? 10 : 14
        color: raiz.minha || raiz.painel ? raiz.tema.superficie : "transparent"
        border.width: raiz.minha ? 0 : 1
        border.color: raiz.perguntando ? raiz.tema.pergunta : raiz.tema.traco
        Behavior on border.color { ColorAnimation { duration: raiz.tema.normal } }

        Column {
            id: conteudo
            anchors.centerIn: parent
            spacing: 5

            Text {
                visible: raiz.painel && raiz.titulo !== ""
                width: raiz.width - 28
                text: raiz.titulo.toUpperCase()
                color: raiz.tema.textoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 10
                font.letterSpacing: 1.2
                font.bold: true
                renderType: Text.NativeRendering
                elide: Text.ElideRight
            }

            // O cartão do painel: markdown, e dá para selecionar e copiar.
            TextEdit {
                visible: raiz.painel
                width: raiz.width - 28
                text: raiz.painel ? raiz.texto : ""
                textFormat: TextEdit.MarkdownText
                readOnly: true
                selectByMouse: true
                selectionColor: raiz.tema.traco
                color: raiz.tema.texto
                font.family: raiz.tema.familia
                font.pixelSize: 13
                renderType: Text.NativeRendering
                wrapMode: TextEdit.Wrap
            }

            Text {
                id: corpoDaFala
                visible: !raiz.painel
                width: Math.min(implicitWidth, raiz.maxLargura)
                text: raiz.painel ? "" : raiz.texto
                color: raiz.tema.texto
                font.family: raiz.tema.familia
                font.pixelSize: 14
                renderType: Text.NativeRendering
                wrapMode: Text.WordWrap
            }

            // O que ele FEZ, e não só o que disse. É a §2.5 aparecendo na tela.
            Text {
                visible: raiz.acao !== "" && !raiz.painel
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
