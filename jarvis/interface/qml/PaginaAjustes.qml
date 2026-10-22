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
    // O uso da assinatura (0 a 1; -1 = ainda não sei) e quando cada um renova.
    property real usoCinco: -1
    property real voltaCinco: 0
    property real usoSemana: -1
    property real voltaSemana: 0

    function quandoRenova(seg, comDia) {
        if (!seg) return "";
        var d = new Date(seg * 1000);
        var hora = ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
        if (!comDia) return "renova às " + hora;
        var dias = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
        return "renova " + dias[d.getDay()] + " " + d.getDate() + "/" + (d.getMonth() + 1) + ", " + hora;
    }

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

        // -- o uso da assinatura ----------------------------------------------
        Text {
            bottomPadding: 10
            text: "USO DA ASSINATURA"
            color: raiz.tema.muitoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 11
            font.weight: Font.DemiBold
            font.letterSpacing: 0.8
        }
        Rectangle {
            width: parent.width
            height: colunaUso.height + 36
            radius: 14
            color: raiz.tema.lateral
            border.width: 1
            border.color: raiz.tema.traco
            Column {
                id: colunaUso
                x: 18; y: 18
                width: parent.width - 36
                spacing: 18
                Text {
                    visible: raiz.usoCinco < 0 && raiz.usoSemana < 0
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Aparece depois do primeiro pedido ao Claude."
                    color: raiz.tema.textoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 14
                }
                Repeater {
                    model: [
                        { nome: "Últimas 5 horas", uso: raiz.usoCinco, volta: raiz.voltaCinco, dia: false },
                        { nome: "Esta semana", uso: raiz.usoSemana, volta: raiz.voltaSemana, dia: true },
                    ]
                    Column {
                        required property var modelData
                        visible: modelData.uso >= 0
                        width: colunaUso.width
                        spacing: 8
                        readonly property color corDaBarra: modelData.uso >= 0.9 ? "#ff6b6b"
                                                          : modelData.uso >= 0.7 ? "#ffb454" : raiz.tema.persona
                        Item {
                            width: parent.width
                            height: 20
                            Text {
                                text: modelData.nome
                                color: raiz.tema.textoMedio
                                font.family: raiz.tema.familia
                                font.pixelSize: 14
                            }
                            Text {
                                anchors.right: parent.right
                                text: Math.round(modelData.uso * 100) + "%  ·  " + raiz.quandoRenova(modelData.volta, modelData.dia)
                                color: raiz.tema.texto
                                font.family: raiz.tema.familia
                                font.pixelSize: 14
                            }
                        }
                        Rectangle {
                            width: parent.width
                            height: 8
                            radius: 4
                            color: raiz.tema.superficie2
                            Rectangle {
                                width: Math.max(8, parent.width * Math.min(1, modelData.uso))
                                height: parent.height
                                radius: 4
                                color: parent.parent.corDaBarra
                                Behavior on width { NumberAnimation { duration: raiz.tema.lento; easing.type: Easing.OutCubic } }
                            }
                        }
                    }
                }
            }
        }
        Item { width: 1; height: 24 }

        Repeater {
            model: [
                { titulo: "Agora", linhas: [
                    ["Conexão", raiz.conectado ? "Ligado" : "Esperando o Jarvis subir"],
                    ["Cérebro", raiz.nomes[raiz.modelo] || raiz.modelo || "—"],
                    ["Esforço", raiz.nomes[raiz.esforco] || raiz.esforco || "—"],
                    ["Conversa", raiz.conversa ? raiz.conversa.slice(0, 8) : "—"],
                    ["Versão da janela", "beta 0.4"],
                ] },
                { titulo: "Atalhos", linhas: [
                    ["Ctrl + N", "Novo chat"],
                    ["Ctrl + K", "Procurar conversa"],
                    ["Esc", "Voltar pra conversa de agora"],
                    ["Enter / Shift + Enter", "Enviar / quebrar a linha"],
                    ["Ctrl + V", "Colar texto, ou anexar imagem e arquivo copiados"],
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
