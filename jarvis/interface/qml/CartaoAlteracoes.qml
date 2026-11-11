import QtQuick

// O cartão "Alterou 3 arquivos" embaixo da resposta que mexeu no projeto
// (etapa 3 do tchan, 11/11/2026): cada arquivo com o +/−, "Ver tudo" (abre o
// painel Mudanças) e o Desfazer, que pergunta antes ("ou fala 'desfaz isso'").
// Os arquivos voltam como estavam antes DESTA resposta; o resto do projeto
// não muda.
Rectangle {
    id: raiz
    objectName: "cartaoAlteracoes"
    property var tema
    property var dados: ({})          // {id, arquivos: [{arquivo, estado, mais, menos}], mais, menos, desfeito}
    property bool confirmando: false
    signal desfazer(string id, string arquivo)
    signal verArquivo(string arquivo)  // "" = ver tudo

    readonly property var arquivos: dados && dados.arquivos ? dados.arquivos : []
    readonly property var desfeitos: dados && dados.desfeito ? dados.desfeito : []
    readonly property bool tudoDesfeito: arquivos.length > 0 && desfeitos.length >= arquivos.length
    readonly property string vermelho: tema.claro ? "#c93a3a" : "#e5484d"

    width: parent ? parent.width : 600
    height: coluna.height
    radius: 10
    color: tema.superficie
    border.width: 1
    border.color: confirmando ? Qt.rgba(0.9, 0.28, 0.3, 0.75) : tema.tracoForte
    Behavior on border.color { ColorAnimation { duration: tema.rapido } }

    function plural(n) { return n === 1 ? "1 arquivo" : n + " arquivos" }

    Column {
        id: coluna
        width: parent.width

        // -- o cabeçalho ------------------------------------------------------
        Item {
            width: parent.width; height: 40
            Text {
                x: 16; anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 32 - botaoDesfazer.width
                elide: Text.ElideRight
                text: raiz.confirmando ? "Desfazer as mudanças desta resposta?"
                    : raiz.tudoDesfeito ? "Desfeito: " + (raiz.arquivos.length === 1 ? "o arquivo voltou" : "os " + raiz.arquivos.length + " arquivos voltaram")
                    : "Alterou " + raiz.plural(raiz.arquivos.length)
                color: raiz.tudoDesfeito && !raiz.confirmando ? raiz.tema.textoFraco : raiz.tema.texto
                font.family: raiz.tema.familia; font.pixelSize: 14; font.weight: Font.Medium
            }
            Rectangle {
                id: botaoDesfazer
                visible: !raiz.confirmando && !raiz.tudoDesfeito
                anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                height: 28; radius: 7; width: linhaDesfazer.width + 18
                color: areaDesfazer.containsMouse ? raiz.tema.superficie2 : "transparent"
                Row {
                    id: linhaDesfazer
                    anchors.centerIn: parent; spacing: 5
                    Icone { anchors.verticalCenter: parent.verticalCenter; caminho: raiz.tema.icones.desfazer
                            cor: areaDesfazer.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco; tamanho: 13; espessura: 1.7 }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: "Desfazer"
                           color: areaDesfazer.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco
                           font.family: raiz.tema.familia; font.pixelSize: 13 }
                }
                MouseArea { id: areaDesfazer; anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor; onClicked: raiz.confirmando = true }
            }
        }
        Rectangle { width: parent.width; height: 1; color: raiz.tema.traco }

        // -- a confirmação ----------------------------------------------------
        Item {
            visible: raiz.confirmando
            width: parent.width
            height: visible ? confirmacao.height + 24 : 0
            Column {
                id: confirmacao
                x: 16; y: 12; width: parent.width - 32; spacing: 12
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    text: (raiz.arquivos.length - raiz.desfeitos.length === 1 ? "O arquivo volta"
                           : "Os " + (raiz.arquivos.length - raiz.desfeitos.length) + " arquivos voltam")
                          + " a ficar como estavam antes dela (o resto do projeto não muda)."
                    color: raiz.tema.textoMedio; font.family: raiz.tema.familia; font.pixelSize: 13
                }
                Item {
                    width: parent.width; height: 34
                    Row {
                        spacing: 8
                        Rectangle {
                            height: 34; radius: 8; width: tSim.implicitWidth + 30
                            color: areaSim.containsMouse ? Qt.rgba(0.9, 0.28, 0.3, 0.3) : Qt.rgba(0.9, 0.28, 0.3, 0.16)
                            border.width: 1; border.color: Qt.rgba(0.9, 0.28, 0.3, 0.6)
                            Text { id: tSim; anchors.centerIn: parent; text: "Desfazer"; color: raiz.tema.claro ? "#a52a2a" : "#ff8f8f"
                                   font.family: raiz.tema.familia; font.pixelSize: 13; font.weight: Font.DemiBold }
                            MouseArea { id: areaSim; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: { raiz.confirmando = false; raiz.desfazer(raiz.dados.id, "") } }
                        }
                        Rectangle {
                            height: 34; radius: 8; width: tNao.implicitWidth + 30
                            color: areaNao.containsMouse ? raiz.tema.realce : raiz.tema.superficie2
                            border.width: 1; border.color: raiz.tema.traco
                            Text { id: tNao; anchors.centerIn: parent; text: "Cancelar"; color: raiz.tema.texto
                                   font.family: raiz.tema.familia; font.pixelSize: 13; font.weight: Font.DemiBold }
                            MouseArea { id: areaNao; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: raiz.confirmando = false }
                        }
                    }
                    Text {
                        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                        text: "ou fala “desfaz isso”"
                        color: raiz.tema.muitoFraco; font.family: raiz.tema.familia; font.pixelSize: 12
                    }
                }
            }
        }

        // -- os arquivos ------------------------------------------------------
        Column {
            visible: !raiz.confirmando
            width: parent.width
            topPadding: 4
            bottomPadding: 4
            Repeater {
                model: raiz.arquivos.slice(0, 8)
                Rectangle {
                    required property var modelData
                    readonly property bool voltou: raiz.desfeitos.indexOf(modelData.arquivo) >= 0
                    width: coluna.width; height: 32
                    color: areaArq.containsMouse ? raiz.tema.superficie2 : "transparent"
                    Icone { x: 16; anchors.verticalCenter: parent.verticalCenter; caminho: raiz.tema.icones.arquivo
                            cor: raiz.tema.textoFraco; tamanho: 13; espessura: 1.5 }
                    Text {
                        x: 38; anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 38 - contas.width - 28
                        elide: Text.ElideMiddle
                        text: modelData.arquivo
                        font.strikeout: parent.voltou
                        color: parent.voltou ? raiz.tema.muitoFraco : raiz.tema.textoMedio
                        font.family: raiz.tema.mono; font.pixelSize: 13
                    }
                    Row {
                        id: contas
                        anchors { right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
                        spacing: 6
                        opacity: parent.voltou ? 0.4 : 1
                        Text { text: "+" + modelData.mais; color: "#4ade80"; font.family: raiz.tema.mono; font.pixelSize: 12 }
                        Text { visible: modelData.menos > 0 || modelData.estado !== "novo"; text: "−" + modelData.menos
                               color: "#f87171"; font.family: raiz.tema.mono; font.pixelSize: 12 }
                    }
                    MouseArea { id: areaArq; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: raiz.verArquivo(modelData.arquivo) }
                }
            }
            Rectangle {
                width: coluna.width; height: 34
                color: areaTudo.containsMouse ? raiz.tema.superficie2 : "transparent"
                Text { x: 16; anchors.verticalCenter: parent.verticalCenter
                       text: raiz.arquivos.length > 8 ? "Ver tudo (mais " + (raiz.arquivos.length - 8) + ")" : "Ver tudo"
                       color: raiz.tema.texto; font.family: raiz.tema.familia; font.pixelSize: 13 }
                Row {
                    anchors { right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
                    spacing: 6
                    Text { text: "+" + (raiz.dados.mais || 0); color: "#4ade80"; font.family: raiz.tema.mono; font.pixelSize: 12 }
                    Text { text: "−" + (raiz.dados.menos || 0); color: "#f87171"; font.family: raiz.tema.mono; font.pixelSize: 12 }
                }
                MouseArea { id: areaTudo; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: raiz.verArquivo("") }
            }
        }
    }
}
