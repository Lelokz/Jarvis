import QtQuick

// Uma fala na conversa, no estilo do app do Claude (janela grande, 22/10/2026):
//
//   voce       balão à direita, com a origem (voz, digitado, celular) e a hora;
//   jarvis     sem balão, com o átomo ao lado e o texto em markdown;
//   painel     o que ele mandou para a janela: sem título, é a resposta
//              formatada (fica igual a uma fala dele); com título, um cartão;
//   atividade  o que ele fez: uma pílula ("3 passos · Bash — ..."), que abre
//              a lista de passos ao clicar.
//
// A coluna da conversa tem largura fixa no meio da área (`largura`), e o
// delegado ocupa a lista inteira, para a rolagem pegar em qualquer lugar.
Item {
    id: raiz

    property var tema
    property string quem: "voce"
    property string texto: ""
    property string origem: ""
    property string titulo: ""
    property real quando: 0
    property bool perguntando: false
    property string passos: ""
    property bool animar: true
    property real largura: 780
    property color corPersona: tema ? tema.persona : "#4da3ff"
    signal copiar(string texto)

    readonly property bool minha: quem === "voce"
    readonly property bool atividade: quem === "atividade"
    readonly property bool cartao: quem === "painel" && titulo !== ""
    readonly property real x0: Math.max(0, (width - largura) / 2)

    width: ListView.view ? ListView.view.width : 800
    height: corpo.height + (atividade ? 14 : 26)

    function hora(seg) {
        if (!seg)
            return "";
        var d = new Date(seg * 1000);
        return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
    }

    function nomeDaOrigem(o) {
        return { voz: "voz", texto: "digitado", digitado: "digitado", celular: "celular",
                 relogio: "relógio" }[o] || o;
    }

    function iconeDaOrigem(o) {
        return { voz: tema.icones.voz, texto: tema.icones.teclado, digitado: tema.icones.teclado,
                 celular: tema.icones.celular, relogio: tema.icones.relogio }[o] || tema.icones.teclado;
    }

    Item {
        id: corpo
        x: raiz.x0
        width: raiz.largura
        height: raiz.minha ? balao.height + meta.height + 6
              : raiz.atividade ? pilula.height + (pilula.aberta ? listaPassos.height + 8 : 0)
              : resposta.height
        // A entrada anima ESTE y, e não o do delegado: no ListView quem manda
        // no y do delegado é a lista.
        y: raiz.animar ? 10 : 0
        opacity: raiz.animar ? 0 : 1
        Component.onCompleted: { y = 0; opacity = 1; }
        Behavior on y { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

        // -- a minha fala -----------------------------------------------------
        Rectangle {
            id: balao
            visible: raiz.minha
            anchors.right: parent.right
            width: Math.min(textoMeu.implicitWidth, raiz.largura * 0.72) + 34
            height: textoMeu.height + 24
            radius: 18
            bottomRightRadius: 6
            color: raiz.tema.superficie2
            border.width: 1
            border.color: raiz.tema.traco

            TextEdit {
                id: textoMeu
                x: 17; y: 12
                width: Math.min(implicitWidth, raiz.largura * 0.72)
                text: raiz.minha ? raiz.texto : ""
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                color: raiz.tema.texto
                selectionColor: raiz.tema.tracoForte
                font.family: raiz.tema.familia
                font.pixelSize: 15
            }
        }
        Row {
            id: meta
            visible: raiz.minha
            anchors.right: parent.right
            anchors.top: balao.bottom
            anchors.topMargin: 6
            spacing: 5
            Icone {
                anchors.verticalCenter: parent.verticalCenter
                caminho: raiz.iconeDaOrigem(raiz.origem)
                cor: raiz.tema.muitoFraco
                tamanho: 12
            }
            Text {
                text: raiz.nomeDaOrigem(raiz.origem || "texto") + " · " + raiz.hora(raiz.quando)
                color: raiz.tema.muitoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 12
            }
        }

        // -- o que ele fez ------------------------------------------------------
        Rectangle {
            id: pilula
            visible: raiz.atividade
            property bool aberta: false
            readonly property var lista: raiz.passos ? raiz.passos.split("\n") : []
            x: 46
            width: Math.min(linhaPilula.width + 28, raiz.largura - 46)
            height: 32
            radius: 16
            color: areaPilula.containsMouse ? raiz.tema.superficie : raiz.tema.lateral
            border.width: 1
            border.color: raiz.tema.traco
            Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
            Row {
                id: linhaPilula
                anchors.verticalCenter: parent.verticalCenter
                x: 12
                spacing: 8
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 7; height: 7; radius: 3.5
                    color: "#38d39f"
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, raiz.largura - 140)
                    elide: Text.ElideRight
                    text: (pilula.lista.length > 1 ? pilula.lista.length + " passos · " : "") + raiz.texto
                    color: raiz.tema.textoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 13
                }
                Icone {
                    anchors.verticalCenter: parent.verticalCenter
                    caminho: pilula.aberta ? raiz.tema.icones.seta : raiz.tema.icones.direita
                    cor: raiz.tema.muitoFraco
                    tamanho: 13
                }
            }
            MouseArea {
                id: areaPilula
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: pilula.aberta = !pilula.aberta
            }
        }
        Column {
            id: listaPassos
            visible: raiz.atividade && pilula.aberta
            anchors.top: pilula.bottom
            anchors.topMargin: 8
            x: 60
            width: raiz.largura - 60
            spacing: 4
            Repeater {
                model: listaPassos.visible ? pilula.lista : []
                Text {
                    required property var modelData
                    width: listaPassos.width
                    elide: Text.ElideRight
                    text: "·  " + modelData
                    color: raiz.tema.textoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 13
                }
            }
        }

        // -- a fala dele (e o painel) -------------------------------------------
        Item {
            id: resposta
            visible: !raiz.minha && !raiz.atividade
            width: parent.width
            height: Math.max(30, colunaResposta.height)

            AtomoFixo {
                y: 2
                tamanho: 30
                cor: raiz.corPersona
                corDeFundo: raiz.tema.fundo
            }

            Column {
                id: colunaResposta
                x: 46
                width: parent.width - 46
                spacing: 8

                // A pergunta que ainda espera resposta.
                Row {
                    visible: raiz.perguntando
                    spacing: 6
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 7; height: 7; radius: 3.5
                        color: raiz.tema.pergunta
                    }
                    Text {
                        text: "Esperando tua resposta"
                        color: raiz.tema.pergunta
                        font.family: raiz.tema.familia
                        font.pixelSize: 12
                    }
                }

                Rectangle {
                    // Com título: um cartão (pedido de permissão, aviso...).
                    width: parent.width
                    height: raiz.cartao ? colunaCartao.height + 28 : textoDele.height
                    color: raiz.cartao ? raiz.tema.superficie : "transparent"
                    border.width: raiz.cartao ? 1 : 0
                    border.color: raiz.perguntando ? raiz.tema.pergunta : raiz.tema.traco
                    radius: 12

                    Column {
                        id: colunaCartao
                        x: raiz.cartao ? 16 : 0
                        y: raiz.cartao ? 14 : 0
                        width: parent.width - 2 * x
                        spacing: 8
                        Text {
                            visible: raiz.cartao
                            width: parent.width
                            text: raiz.titulo
                            elide: Text.ElideRight
                            color: raiz.tema.texto
                            font.family: raiz.tema.familia
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        BlocoMarkdown {
                            id: textoDele
                            tema: raiz.tema
                            width: parent.width
                            texto: raiz.minha || raiz.atividade ? "" : raiz.texto
                            onCopiar: function (t) { raiz.copiar(t) }
                        }
                    }
                }

                // Copiar e a hora: aparecem com o mouse em cima.
                Row {
                    spacing: 14
                    opacity: areaResposta.hovered ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: raiz.tema.rapido } }
                    Item {
                        width: linhaCopiar.width
                        height: linhaCopiar.height
                        Row {
                            id: linhaCopiar
                            spacing: 5
                            Icone {
                                anchors.verticalCenter: parent.verticalCenter
                                caminho: raiz.tema.icones.copiar
                                cor: areaCopiarTudo.containsMouse ? raiz.tema.texto : raiz.tema.muitoFraco
                                tamanho: 13
                            }
                            Text {
                                text: "Copiar"
                                color: areaCopiarTudo.containsMouse ? raiz.tema.texto : raiz.tema.muitoFraco
                                font.family: raiz.tema.familia
                                font.pixelSize: 12
                            }
                        }
                        MouseArea {
                            id: areaCopiarTudo
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: raiz.copiar(raiz.texto)
                        }
                    }
                    Text {
                        text: raiz.hora(raiz.quando)
                        color: raiz.tema.muitoFraco
                        font.family: raiz.tema.familia
                        font.pixelSize: 12
                    }
                }
            }
            HoverHandler { id: areaResposta }
        }
    }
}
