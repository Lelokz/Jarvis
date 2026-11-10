import QtQuick

// Texto em markdown com os blocos de código separados: o texto o Qt desenha
// (negrito, listas, títulos, links), e cada bloco de código vira uma caixa
// própria, com a linguagem e o botão de copiar, como no app do Claude.
Column {
    id: raiz

    // O diff em HTML: cada linha com a cor dela (o texto escapado, os espaços mantidos).
    function diffColorido(texto) {
        var linhas = texto.split("\n"), saida = [];
        for (var i = 0; i < linhas.length; i++) {
            var l = linhas[i], cor = "#c9d1dd";
            if (l.charAt(0) === "+") cor = "#4ade80";
            else if (l.charAt(0) === "-") cor = "#f87171";
            else if (l.indexOf("@@") === 0 || l.indexOf("diff ") === 0) cor = "#a78bfa";
            var e = l.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/ /g, "&nbsp;");
            saida.push("<span style=\"color:" + cor + "\">" + (e || "&nbsp;") + "</span>");
        }
        return saida.join("<br>");
    }
    property var tema
    property string texto: ""
    property real tamanhoDaFonte: 15
    property color cor: tema ? tema.textoMedio : "#b9c1cf"
    signal copiar(string texto)

    spacing: 10

    // "texto ```js\ncódigo\n``` texto" -> [{codigo:false, ...}, {codigo:true, lingua, ...}, ...]
    function _partes(t) {
        var partes = [];
        var re = /```([\w+#.-]*)[^\n]*\n([\s\S]*?)(```|$)/g;
        var inicio = 0, m;
        while ((m = re.exec(t)) !== null) {
            var antes = t.slice(inicio, m.index).trim();
            if (antes)
                partes.push({ codigo: false, lingua: "", conteudo: antes });
            partes.push({ codigo: true, lingua: m[1] || "", conteudo: m[2].replace(/\s+$/, "") });
            inicio = re.lastIndex;
            if (m[3] === "")
                break;
        }
        var resto = t.slice(inicio).trim();
        if (resto)
            partes.push({ codigo: false, lingua: "", conteudo: resto });
        return partes;
    }

    Repeater {
        model: raiz._partes(raiz.texto)

        Loader {
            required property var modelData
            width: raiz.width
            sourceComponent: modelData.codigo ? caixaDeCodigo : paragrafo
            property var parte: modelData
        }
    }

    Component {
        id: paragrafo
        Text {
            width: parent ? parent.width : 0
            text: parent ? parent.parte.conteudo : ""
            textFormat: Text.MarkdownText
            wrapMode: Text.Wrap
            color: raiz.cor
            linkColor: raiz.tema.persona
            font.family: raiz.tema.familia
            font.pixelSize: raiz.tamanhoDaFonte
            lineHeight: 1.3
            onLinkActivated: function (link) { Qt.openUrlExternally(link) }
            HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.IBeamCursor }
        }
    }

    Component {
        id: caixaDeCodigo
        Rectangle {
            id: caixa
            width: parent ? parent.width : 0
            height: cabecalho.height + corpo.height + 28
            radius: 12
            color: raiz.tema.codigo
            border.width: 1
            border.color: raiz.tema.traco
            clip: true
            property var parte: parent ? parent.parte : ({ lingua: "", conteudo: "" })
            property bool copiado: false

            Rectangle {
                id: cabecalho
                width: parent.width
                height: 36
                color: raiz.tema.superficie
                radius: 12
                Rectangle { // os cantos de baixo do cabeçalho, retos
                    anchors.bottom: parent.bottom; width: parent.width; height: 12
                    color: parent.color
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 14
                    text: caixa.parte.lingua || "código"
                    color: raiz.tema.textoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 12
                }
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    spacing: 6
                    opacity: areaCopiar.containsMouse ? 1.0 : 0.8
                    Icone {
                        anchors.verticalCenter: parent.verticalCenter
                        caminho: caixa.copiado ? raiz.tema.icones.certo : raiz.tema.icones.copiar
                        cor: areaCopiar.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco
                        tamanho: 13
                    }
                    Text {
                        text: caixa.copiado ? "Copiado" : "Copiar"
                        color: areaCopiar.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco
                        font.family: raiz.tema.familia
                        font.pixelSize: 12
                    }
                }
                MouseArea {
                    id: areaCopiar
                    anchors.right: parent.right
                    width: 90; height: parent.height
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        raiz.copiar(caixa.parte.conteudo);
                        caixa.copiado = true;
                        voltaCopiar.restart();
                    }
                }
                Timer { id: voltaCopiar; interval: 1600; onTriggered: caixa.copiado = false }
            }

            TextEdit {
                id: corpo
                anchors.top: cabecalho.bottom
                anchors.topMargin: 14
                x: 16
                width: parent.width - 32
                // Diff (modo code, beta 0.18.0): verde entrou, vermelho saiu.
                readonly property bool ehDiff: caixa.parte.lingua === "diff"
                text: ehDiff ? raiz.diffColorido(caixa.parte.conteudo) : caixa.parte.conteudo
                textFormat: ehDiff ? TextEdit.RichText : TextEdit.PlainText
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.WrapAnywhere
                color: "#c9d1dd"
                selectionColor: raiz.tema.tracoForte
                font.family: raiz.tema.mono
                font.pixelSize: 13
            }
        }
    }
}
