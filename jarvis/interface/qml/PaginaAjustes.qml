import QtQuick

// Ajustes: os limites da assinatura no topo, o som (o primeiro ajuste de
// verdade, beta 0.6.0) e, sempre por último, o que está valendo e os atalhos. O que se troca toda hora (cérebro, esforço,
// persona) fica na barra de escrever, à mão.
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
    // O evento "som" da ponte (jarvis/som.py): aparelhos, padrão e escolha.
    property var som: null
    signal escolherSom(string tipo, string aparelho)

    // "Padrão do sistema" primeiro (com o aparelho que ele é agora), depois
    // todos os aparelhos que o Linux enxerga.
    function opcoesDeSom(aparelhos, padrao) {
        var lista = [{ valor: "", nome: "Padrão" + (padrao ? " (" + padrao + ")" : ""),
                       descricao: "Acompanha o padrão das configurações de som do Linux" }];
        for (var i = 0; i < (aparelhos || []).length; i++)
            lista.push({ valor: aparelhos[i].id, nome: aparelhos[i].nome, descricao: "" });
        return lista;
    }

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

    Flickable {
        anchors.fill: parent
        contentHeight: coluna.height + 80
        clip: true
        boundsBehavior: Flickable.StopAtBounds

    Column {
        id: coluna
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

        // -- o som --------------------------------------------------------------
        Text {
            bottomPadding: 10
            text: "SOM"
            color: raiz.tema.muitoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 11
            font.weight: Font.DemiBold
            font.letterSpacing: 0.8
        }
        Rectangle {
            width: parent.width
            height: raiz.som ? 2 * 56 : 56
            radius: 14
            color: raiz.tema.lateral
            border.width: 1
            border.color: raiz.tema.traco
            Text {
                visible: !raiz.som
                anchors.verticalCenter: parent.verticalCenter
                x: 18
                text: raiz.conectado ? "Procurando os aparelhos de som…" : "Aparece quando o Jarvis subir."
                color: raiz.tema.textoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 14
            }
            Column {
                visible: !!raiz.som
                width: parent.width
                Repeater {
                    model: [
                        { tipo: "saida", nome: "Saída (alto-falante)", lista: "saidas", padrao: "padrao_saida" },
                        { tipo: "entrada", nome: "Entrada (microfone)", lista: "entradas", padrao: "padrao_entrada" },
                    ]
                    Item {
                        required property var modelData
                        required property int index
                        width: parent.width
                        height: 56
                        z: 2 - index  // o menu de cima abre por cima da linha de baixo
                        Rectangle {
                            visible: index > 0
                            x: 18; width: parent.width - 36; height: 1
                            color: raiz.tema.traco
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            x: 18
                            text: modelData.nome
                            color: raiz.tema.textoMedio
                            font.family: raiz.tema.familia
                            font.pixelSize: 14
                        }
                        Seletor {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            tema: raiz.tema
                            paraCima: false
                            alinharDireita: true
                            rotulo: modelData.nome
                            opcoes: raiz.som ? raiz.opcoesDeSom(raiz.som[modelData.lista], raiz.som[modelData.padrao]) : []
                            valor: raiz.som ? (raiz.som[modelData.tipo] || "") : ""
                            onEscolhido: (valor) => raiz.escolherSom(modelData.tipo, valor)
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
                    ["Versão da janela", "beta 0.6.0"],
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
}
