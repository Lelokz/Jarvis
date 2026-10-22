import QtQuick

// Ajustes: o que está valendo agora e os atalhos. Pequena de propósito: o
// que se troca toda hora (cérebro, esforço, persona) fica na barra de
// escrever, à mão.
Item {
    id: raiz
    property var tema
    property bool conectado: false
    property string conversa: ""
    property string modelo: ""
    property string esforco: ""

    readonly property var nomes: ({
        auto: "Automático (Haiku + Opus)", haiku: "Haiku", sonnet: "Sonnet", opus: "Opus",
        low: "Baixo", medium: "Médio", high: "Alto", xhigh: "Muito alto", max: "Máximo"
    })

    Column {
        x: Math.max(32, (parent.width - width) / 2)
        y: 40
        width: Math.min(780, raiz.width - 64)
        spacing: 6

        Text {
            text: "Ajustes"
            color: raiz.tema.texto
            font.family: raiz.tema.familia
            font.pixelSize: 28
            font.weight: Font.DemiBold
        }
        Item { width: 1; height: 22 }

        Repeater {
            model: [
                { titulo: "Agora", linhas: [
                    ["Conexão", raiz.conectado ? "Ligado" : "Esperando o Jarvis subir"],
                    ["Cérebro", raiz.nomes[raiz.modelo] || raiz.modelo || "—"],
                    ["Esforço", raiz.nomes[raiz.esforco] || raiz.esforco || "—"],
                    ["Conversa", raiz.conversa ? raiz.conversa.slice(0, 8) : "—"],
                    ["Versão da janela", "beta 0.3"],
                ] },
                { titulo: "Atalhos", linhas: [
                    ["Ctrl + N", "Novo chat"],
                    ["Ctrl + K", "Procurar conversa"],
                    ["Esc", "Voltar pra conversa de agora"],
                    ["Enter / Shift + Enter", "Enviar / quebrar a linha"],
                ] },
            ]
            Column {
                required property var modelData
                width: parent.width
                spacing: 0
                bottomPadding: 24
                Text {
                    bottomPadding: 10
                    text: modelData.titulo.toUpperCase()
                    color: raiz.tema.muitoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                }
                Rectangle {
                    width: parent.width
                    height: linhas.height
                    radius: 14
                    color: raiz.tema.lateral
                    border.width: 1
                    border.color: raiz.tema.traco
                    Column {
                        id: linhas
                        width: parent.width
                        Repeater {
                            model: modelData.linhas
                            Item {
                                required property var modelData
                                required property int index
                                width: linhas.width
                                height: 48
                                Rectangle {
                                    visible: index > 0
                                    x: 18; width: parent.width - 36; height: 1
                                    color: raiz.tema.traco
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: 18
                                    text: modelData[0]
                                    color: raiz.tema.textoMedio
                                    font.family: raiz.tema.familia
                                    font.pixelSize: 14
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.right: parent.right
                                    anchors.rightMargin: 18
                                    text: modelData[1]
                                    color: raiz.tema.texto
                                    font.family: raiz.tema.familia
                                    font.pixelSize: 14
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
