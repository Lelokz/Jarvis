import QtQuick
import QtQuick.Controls.Basic

// Agendados (etapa 5 do tchan, 11/11/2026): o que a NOVA faz sozinha na hora
// marcada. Os recados dela (uma vez ou repetindo), com a lixeira; um campo pra
// criar escrevendo (vira um pedido, e ela anota do jeito dela); e as rotinas
// que rodam pelo sistema (painel do canal, faxina, backup).
Item {
    id: raiz
    property var tema
    property var dados: null            // o evento "agendados": {recados, rotinas}
    property bool conectado: false
    signal atualizar()
    signal apagar(string id)
    signal criar(string texto)

    readonly property var recados: dados && dados.recados ? dados.recados : []
    readonly property var rotinas: dados && dados.rotinas ? dados.rotinas : []

    function hora(seg) { var d = new Date(seg * 1000); return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2) }
    function dia(seg) {
        var d = new Date(seg * 1000), hoje = new Date();
        var a = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate()), b = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        var n = Math.round((b - a) / 86400000);
        if (n === 0) return "hoje";
        if (n === 1) return "amanhã";
        return ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"][d.getDay()] + " " + d.getDate() + "/" + (d.getMonth() + 1);
    }
    readonly property var icones: ({
        yt: "M3 8a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3zM10 9l5 3-5 3z",
        vassoura: "M14 4l-4 8M6 13h8l2 7H4zM9 16v4M12 16v4",
        nuvem: "M7 18a4 4 0 0 1-.5-8A6 6 0 0 1 18 9a4.5 4.5 0 0 1-.5 9zM12 11v5M9.5 13.5L12 11l2.5 2.5",
        lixo: "M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13M10 11v6M14 11v6"
    })

    Flickable {
        anchors.fill: parent
        contentHeight: coluna.height + 60
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
            id: coluna
            width: Math.min(860, raiz.width - 64)
            x: (raiz.width - width) / 2
            y: 36
            spacing: 0

            Text { text: "Agendados"; color: raiz.tema.texto; font.family: raiz.tema.familia; font.pixelSize: 26; font.weight: Font.DemiBold }
            Text {
                width: parent.width; topPadding: 6; wrapMode: Text.WordWrap
                text: "O que ela faz sozinha na hora marcada. Pede escrevendo aqui ou falando: “me lembra amanhã às 8 de…”, “todo dia às 7 me fala a agenda”."
                color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 14; lineHeight: 1.15
            }
            Item { width: 1; height: 22 }
            Rectangle {
                width: parent.width; height: 52; radius: 14
                color: raiz.tema.superficie
                border.width: 1; border.color: campo.activeFocus ? raiz.tema.persona : raiz.tema.tracoForte
                Icone { x: 16; anchors.verticalCenter: parent.verticalCenter; caminho: raiz.tema.icones.mais; cor: raiz.tema.textoFraco; tamanho: 18 }
                TextInput {
                    id: campo
                    x: 46; width: parent.width - 46 - 60
                    anchors.verticalCenter: parent.verticalCenter
                    color: raiz.tema.texto; selectionColor: raiz.tema.tracoForte
                    font.family: raiz.tema.familia; font.pixelSize: 15
                    clip: true
                    enabled: raiz.conectado
                    function mandar() { if (text.trim()) { raiz.criar(text.trim()); text = "" } }
                    Keys.onReturnPressed: mandar()
                    Text { visible: !campo.text; text: "Novo: o quê e quando… (“toda sexta às 18h me lembra do lixo”)"
                           color: raiz.tema.muitoFraco; font: campo.font }
                }
                Rectangle {
                    anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                    width: 36; height: 36; radius: 10
                    color: raiz.tema.persona
                    opacity: campo.text.trim() ? 1 : 0.4
                    Icone { anchors.centerIn: parent; caminho: raiz.tema.icones.enviar; cor: "#06101d"; tamanho: 18; espessura: 2.2 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: campo.mandar() }
                }
            }

            component Titulo: Text {
                topPadding: 30; bottomPadding: 10
                color: raiz.tema.muitoFraco; font.family: raiz.tema.familia; font.pixelSize: 11; font.weight: Font.DemiBold
                font.letterSpacing: 1.2
            }
            component Etiqueta: Rectangle {
                property string texto
                property color cor: raiz.tema.textoMedio
                property bool colorida: false
                width: tEt.implicitWidth + 18; height: 22; radius: 7
                color: colorida ? Qt.rgba(cor.r, cor.g, cor.b, 0.09) : "transparent"
                border.width: 1; border.color: colorida ? Qt.rgba(cor.r, cor.g, cor.b, 0.45) : raiz.tema.tracoForte
                Text { id: tEt; anchors.centerIn: parent; text: parent.texto; color: parent.colorida ? parent.cor : raiz.tema.textoMedio
                       font.family: raiz.tema.familia; font.pixelSize: 11 }
            }

            Titulo { text: "PRÓXIMOS" }
            Rectangle {
                width: parent.width
                height: raiz.recados.length ? listaRec.height : 64
                radius: 14; color: raiz.tema.superficie; border.width: 1; border.color: raiz.tema.traco
                clip: true
                Text {
                    visible: raiz.recados.length === 0
                    anchors.centerIn: parent
                    text: raiz.dados ? "Nada marcado. Pede: “me lembra amanhã às 8 de…”" : "Carregando…"
                    color: raiz.tema.muitoFraco; font.family: raiz.tema.familia; font.pixelSize: 13
                }
                Column {
                    id: listaRec
                    width: parent.width
                    Repeater {
                        model: raiz.recados
                        Rectangle {
                            required property var modelData
                            required property int index
                            width: listaRec.width; height: Math.max(64, tRec.implicitHeight + 28)
                            color: areaRec.containsMouse ? raiz.tema.superficie2 : "transparent"
                            Rectangle { visible: index > 0; width: parent.width; height: 1; color: raiz.tema.traco }
                            MouseArea { id: areaRec; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
                            Column {
                                x: 18; anchors.verticalCenter: parent.verticalCenter; width: 112
                                Text { text: raiz.hora(modelData.quando); color: raiz.tema.texto; font.family: raiz.tema.familia; font.pixelSize: 15; font.weight: Font.DemiBold }
                                Text { text: raiz.dia(modelData.quando); color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 12 }
                            }
                            Text {
                                id: tRec
                                x: 146; width: parent.width - 146 - etRec.width - 70
                                anchors.verticalCenter: parent.verticalCenter
                                wrapMode: Text.WordWrap
                                text: modelData.texto
                                color: raiz.tema.texto; font.family: raiz.tema.familia; font.pixelSize: 14
                            }
                            Etiqueta {
                                id: etRec
                                anchors { right: lixo.left; rightMargin: 12; verticalCenter: parent.verticalCenter }
                                texto: modelData.repete || "uma vez"
                                colorida: !!modelData.repete
                                cor: "#9ccbff"
                            }
                            Rectangle {
                                id: lixo
                                anchors { right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
                                width: 30; height: 30; radius: 8
                                color: areaLixo.containsMouse ? raiz.tema.realce : "transparent"
                                Icone { anchors.centerIn: parent; caminho: raiz.icones.lixo; tamanho: 16
                                        cor: areaLixo.containsMouse ? "#f87171" : raiz.tema.textoFraco }
                                MouseArea { id: areaLixo; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            enabled: raiz.conectado; onClicked: raiz.apagar(modelData.id) }
                                ToolTipSimples { tema: raiz.tema; visivel: areaLixo.containsMouse; texto: "Apagar" }
                            }
                        }
                    }
                }
            }

            Titulo { text: "ROTINAS DA NOVA" }
            Rectangle {
                width: parent.width
                height: raiz.rotinas.length ? listaRot.height : 64
                radius: 14; color: raiz.tema.superficie; border.width: 1; border.color: raiz.tema.traco
                clip: true
                Text { visible: raiz.rotinas.length === 0; anchors.centerIn: parent; text: raiz.dados ? "Nenhuma rotina ligada." : "Carregando…"
                       color: raiz.tema.muitoFraco; font.family: raiz.tema.familia; font.pixelSize: 13 }
                Column {
                    id: listaRot
                    width: parent.width
                    Repeater {
                        model: raiz.rotinas
                        Item {
                            required property var modelData
                            required property int index
                            width: listaRot.width; height: 68
                            Rectangle { visible: index > 0; width: parent.width; height: 1; color: raiz.tema.traco }
                            Rectangle {
                                x: 18; anchors.verticalCenter: parent.verticalCenter
                                width: 36; height: 36; radius: 10; color: raiz.tema.superficie2
                                Icone { anchors.centerIn: parent; caminho: raiz.icones[modelData.icone] || ""; cor: raiz.tema.textoMedio; tamanho: 16 }
                            }
                            Column {
                                x: 70; anchors.verticalCenter: parent.verticalCenter; spacing: 3
                                width: parent.width - 70 - ladoRot.width - 30
                                Text { text: modelData.nome; color: raiz.tema.texto; font.family: raiz.tema.familia; font.pixelSize: 15 }
                                Text { width: parent.width; elide: Text.ElideRight; text: modelData.descricao; color: raiz.tema.textoFraco
                                       font.family: raiz.tema.familia; font.pixelSize: 12 }
                            }
                            Row {
                                id: ladoRot
                                anchors { right: parent.right; rightMargin: 18; verticalCenter: parent.verticalCenter }
                                spacing: 14
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.quando + (modelData.proxima && modelData.icone === "yt" ? " · próxima " + raiz.hora(modelData.proxima) : "")
                                    color: raiz.tema.textoMedio; font.family: raiz.tema.familia; font.pixelSize: 13
                                }
                                Etiqueta {
                                    anchors.verticalCenter: parent.verticalCenter
                                    texto: modelData.estado === "falta configurar" ? "falta tu configurar" : modelData.estado
                                    colorida: true
                                    cor: modelData.estado === "ligado" ? "#38d39f" : modelData.estado === "falta configurar" ? "#ffb454" : "#7e879b"
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
