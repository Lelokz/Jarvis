import QtQuick
import QtQuick.Controls.Basic

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
    // O evento "ajustes" (beta 0.6.5): volume da voz no PC e notificações da escola.
    property var ajustes: null
    signal mudarVolume(int volume)
    signal mudarNotificar(bool ligado)
    signal mudarNome(string nome)
    signal mudarGrupo(bool ligado)

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
        auto: "Automático (Sonnet + Opus)", haiku: "Haiku", sonnet: "Sonnet", opus: "Opus",
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

        // -- voz e avisos (beta 0.6.5) -----------------------------------------
        Text {
            bottomPadding: 10
            text: "VOZ E AVISOS"
            color: raiz.tema.muitoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 11
            font.weight: Font.DemiBold
            font.letterSpacing: 0.8
        }
        Rectangle {
            readonly property bool temEscola: !!raiz.ajustes && !!raiz.ajustes.tem_escola
            readonly property bool temGrupo: !!raiz.ajustes && !!raiz.ajustes.grupo_jid
            width: parent.width
            height: (1 + (temEscola ? 1 : 0) + (temGrupo ? 1 : 0)) * 56
            radius: 14
            color: raiz.tema.lateral
            border.width: 1
            border.color: raiz.tema.traco
            enabled: !!raiz.ajustes
            opacity: enabled ? 1 : 0.5
            // O volume da voz do Jarvis no PC. 100% é o de sempre e é o teto:
            // daqui só se abaixa (o volume já machucou o ouvido do Léo).
            Item {
                width: parent.width
                height: 56
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 18
                    text: "Volume da voz do Jarvis"
                    color: raiz.tema.textoMedio
                    font.family: raiz.tema.familia
                    font.pixelSize: 14
                }
                Text {
                    id: rotuloVolume
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: 18
                    width: 44
                    horizontalAlignment: Text.AlignRight
                    text: Math.round(deslizador.value) + "%"
                    color: raiz.tema.texto
                    font.family: raiz.tema.familia
                    font.pixelSize: 14
                }
                Slider {
                    id: deslizador
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: rotuloVolume.left
                    anchors.rightMargin: 12
                    width: Math.min(260, parent.width * 0.4)
                    from: 0; to: 100; stepSize: 5
                    value: raiz.ajustes ? raiz.ajustes.volume_voz : 100
                    // Manda só quando solta: arrastando não vira uma enxurrada de pedidos.
                    onPressedChanged: if (!pressed) raiz.mudarVolume(Math.round(value))
                    background: Rectangle {
                        x: deslizador.leftPadding
                        y: deslizador.topPadding + deslizador.availableHeight / 2 - height / 2
                        width: deslizador.availableWidth
                        height: 6
                        radius: 3
                        color: raiz.tema.superficie2
                        Rectangle {
                            width: deslizador.visualPosition * parent.width
                            height: parent.height
                            radius: 3
                            color: raiz.tema.persona
                        }
                    }
                    handle: Rectangle {
                        x: deslizador.leftPadding + deslizador.visualPosition * (deslizador.availableWidth - width)
                        y: deslizador.topPadding + deslizador.availableHeight / 2 - height / 2
                        width: 16; height: 16; radius: 8
                        color: deslizador.pressed ? raiz.tema.texto : raiz.tema.textoMedio
                    }
                }
            }
            Item {
                visible: parent.temEscola
                y: 56
                width: parent.width
                height: 56
                Rectangle { x: 18; width: parent.width - 36; height: 1; color: raiz.tema.traco }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 18
                    spacing: 2
                    Text {
                        text: "Notificações da escola"
                        color: raiz.tema.textoMedio
                        font.family: raiz.tema.familia
                        font.pixelSize: 14
                    }
                    Text {
                        text: "Avisa quando aparecer algo novo"
                        color: raiz.tema.textoFraco
                        font.family: raiz.tema.familia
                        font.pixelSize: 12
                    }
                }
                // O interruptor.
                Rectangle {
                    id: interruptor
                    readonly property bool ligado: raiz.ajustes ? raiz.ajustes.notificar_escola : true
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: 18
                    width: 40; height: 22; radius: 11
                    color: ligado ? raiz.tema.persona : raiz.tema.superficie2
                    Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
                    Rectangle {
                        y: 3; width: 16; height: 16; radius: 8
                        x: interruptor.ligado ? interruptor.width - width - 3 : 3
                        color: raiz.tema.texto
                        Behavior on x { NumberAnimation { duration: raiz.tema.rapido; easing.type: Easing.OutCubic } }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: raiz.mudarNotificar(!interruptor.ligado)
                    }
                }
            }
            // O Jarvis no grupo da família do WhatsApp (só onde o grupo foi configurado).
            Item {
                visible: parent.temGrupo
                y: 56 * (parent.temEscola ? 2 : 1)
                width: parent.width
                height: 56
                Rectangle { x: 18; width: parent.width - 36; height: 1; color: raiz.tema.traco }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 18
                    spacing: 2
                    Text {
                        text: "Jarvis no grupo da família"
                        color: raiz.tema.textoMedio
                        font.family: raiz.tema.familia
                        font.pixelSize: 14
                    }
                    Text {
                        text: "Responde no WhatsApp quando chamam o Jarvis"
                        color: raiz.tema.textoFraco
                        font.family: raiz.tema.familia
                        font.pixelSize: 12
                    }
                }
                Rectangle {
                    id: interruptorGrupo
                    readonly property bool ligado: raiz.ajustes ? !!raiz.ajustes.grupo_ligado : false
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: 18
                    width: 40; height: 22; radius: 11
                    color: ligado ? raiz.tema.persona : raiz.tema.superficie2
                    Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
                    Rectangle {
                        y: 3; width: 16; height: 16; radius: 8
                        x: interruptorGrupo.ligado ? interruptorGrupo.width - width - 3 : 3
                        color: raiz.tema.texto
                        Behavior on x { NumberAnimation { duration: raiz.tema.rapido; easing.type: Easing.OutCubic } }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: raiz.mudarGrupo(!interruptorGrupo.ligado)
                    }
                }
            }
        }
        Item { width: 1; height: 24 }

        // -- aparência (beta 0.7.0) --------------------------------------------
        Text {
            bottomPadding: 10
            text: "APARÊNCIA"
            color: raiz.tema.muitoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 11
            font.weight: Font.DemiBold
            font.letterSpacing: 0.8
        }
        Rectangle {
            width: parent.width
            height: 56
            radius: 14
            color: raiz.tema.lateral
            border.width: 1
            border.color: raiz.tema.traco
            enabled: !!raiz.ajustes
            // Como o Jarvis chama quem usa (a saudação, as falas, a persona).
            Item {
                width: parent.width
                height: 56
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 18
                    text: "Seu nome"
                    color: raiz.tema.textoMedio
                    font.family: raiz.tema.familia
                    font.pixelSize: 14
                }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    width: 220; height: 34; radius: 9
                    color: raiz.tema.superficie
                    border.width: 1
                    border.color: campoNome.activeFocus ? raiz.tema.persona : raiz.tema.traco
                    TextInput {
                        id: campoNome
                        anchors.fill: parent
                        anchors.leftMargin: 12; anchors.rightMargin: 12
                        verticalAlignment: TextInput.AlignVCenter
                        maximumLength: 30
                        clip: true
                        color: raiz.tema.texto
                        selectionColor: raiz.tema.persona
                        font.family: raiz.tema.familia
                        font.pixelSize: 14
                        text: raiz.ajustes ? (raiz.ajustes.nome || "") : ""
                        // Salva quando sai do campo ou dá Enter.
                        onEditingFinished: if (raiz.ajustes && text.trim() !== (raiz.ajustes.nome || "")) raiz.mudarNome(text.trim())
                        Text {
                            visible: !campoNome.text && !campoNome.activeFocus
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Como o Jarvis te chama"
                            color: raiz.tema.muitoFraco
                            font.family: raiz.tema.familia
                            font.pixelSize: 14
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
                    ["Versão da janela", "beta 0.16.5"],
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
