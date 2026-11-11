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
    property string opcoes: ""            // as da pergunta, uma por linha
    property string passos: ""
    property bool escrevendo: false       // o texto ainda está chegando
    property bool animar: true
    property int puff: -1                 // conversa antiga abrindo: o atraso do sopro (ms)

    // -- digitando (11/11/2026, pedido do Léo) --------------------------------
    // A resposta ao vivo aparece letra por letra, um pouco mais rápido que a
    // voz, em vez de a frase inteira "teleportar". Atrasou (frase longa,
    // painel grande)? Acelera e alcança. O histórico entra inteiro.
    readonly property bool digitar: animar && !minha && !atividade
    property real mostrados: digitar ? 0 : 1e9
    readonly property bool digitando: digitar && mostrados < texto.length
    readonly property string textoParcial: parcial(texto)
    Timer {
        interval: 16
        repeat: true
        running: raiz.digitando
        onTriggered: {
            var falta = raiz.texto.length - raiz.mostrados;
            raiz.mostrados = Math.min(raiz.texto.length, raiz.mostrados + Math.max(1.1, (falta - 120) / 25));
        }
    }
    // O pedaço já digitado, sem deixar o markdown pela metade: "**" aberto
    // fecha, bloco de código aberto fecha, e não corta no meio de um "*".
    function parcial(t) {
        if (!digitando) return t;
        var p = t.substring(0, Math.floor(mostrados));
        while (p.length && (p[p.length - 1] === "*" || p[p.length - 1] === "`" || p[p.length - 1] === "["))
            p = p.substring(0, p.length - 1);
        if ((p.split("```").length - 1) % 2) p += "\n```";
        else if ((p.split("`").length - 1) % 2) p += "`";
        if ((p.split("**").length - 1) % 2) p += "**";
        var link = p.lastIndexOf("[");
        if (link > p.lastIndexOf(")")) p = p.substring(0, link) + p.substring(link + 1).replace(/\]\(.*$/, "");
        return p;
    }
    property real largura: 780
    property color corPersona: tema ? tema.persona : "#4da3ff"
    property bool ultima: false           // a última resposta: os botões ficam sempre à vista
    signal copiar(string texto)
    signal responder(string texto)
    // Os botões embaixo da resposta (beta 0.18.5).
    signal ouvir(string texto)
    signal refazer()
    signal avaliar(string texto, string nota)
    property string nota: ""              // "boa" | "ruim" (o que ele já marcou aqui)
    // O cartão "Alterou N arquivos" do modo code (JSON; "" = sem cartão).
    property string dados: ""
    signal desfazer(string id, string arquivo)
    signal verArquivo(string arquivo)

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
        y: raiz.animar || raiz.puff >= 0 ? 10 : 0
        opacity: raiz.animar || raiz.puff >= 0 ? 0 : 1
        scale: raiz.puff >= 0 ? 0.985 : 1
        Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
        // Ao vivo entra na hora; a conversa antiga abre em sopros, uma fala depois da outra.
        Timer { id: soprar; interval: Math.max(1, raiz.puff); onTriggered: { corpo.y = 0; corpo.opacity = 1; corpo.scale = 1; } }
        Component.onCompleted: { if (raiz.puff >= 0 && !raiz.animar) soprar.start(); else { y = 0; opacity = 1; } }
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
                            // Enquanto chega, um cursor no fim.
                            texto: raiz.minha || raiz.atividade ? ""
                                 : raiz.escrevendo || raiz.digitando ? raiz.parcial(raiz.texto) + " ▍" : raiz.texto
                            onCopiar: function (t) { raiz.copiar(t) }
                        }
                    }
                }

                // A pergunta com opções: um botão para cada (ou responder falando).
                Flow {
                    visible: raiz.perguntando && raiz.opcoes !== ""
                    width: parent.width
                    spacing: 8
                    Repeater {
                        model: raiz.perguntando && raiz.opcoes ? raiz.opcoes.split("\n") : []
                        Rectangle {
                            required property string modelData
                            width: textoOpcao.implicitWidth + 30
                            height: 36
                            radius: 10
                            color: areaOpcao.containsMouse ? "#3a2c16" : "#2a2114"
                            border.width: 1
                            border.color: areaOpcao.containsMouse ? raiz.tema.pergunta : "#5c4422"
                            Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
                            Text {
                                id: textoOpcao
                                anchors.centerIn: parent
                                text: modelData
                                color: "#ffcf8a"
                                font.family: raiz.tema.familia
                                font.pixelSize: 14
                                font.weight: Font.Medium
                            }
                            MouseArea {
                                id: areaOpcao
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: raiz.responder(modelData)
                            }
                        }
                    }
                }

                Loader {
                    active: raiz.dados !== ""
                    visible: active
                    width: parent.width
                    sourceComponent: CartaoAlteracoes {
                        width: parent ? parent.width : 600
                        tema: raiz.tema
                        dados: raiz.dados !== "" ? JSON.parse(raiz.dados) : ({})
                        onDesfazer: function (id, arq) { raiz.desfazer(id, arq) }
                        onVerArquivo: function (arq) { raiz.verArquivo(arq) }
                    }
                }

                // Copiar, ouvir de novo, refazer, gostei/não gostei e a hora
                // (beta 0.18.5). Na última resposta ficam sempre à vista; nas
                // outras, com o mouse em cima.
                Row {
                    spacing: 2
                    visible: !raiz.escrevendo && !raiz.digitando
                    opacity: raiz.ultima || areaResposta.hovered ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: raiz.tema.rapido } }
                    Repeater {
                        model: [
                            { id: "copiar", icone: raiz.tema.icones.copiar, dica: "Copiar" },
                            { id: "ouvir", icone: raiz.tema.icones.som, dica: "Ouvir de novo" },
                            { id: "refazer", icone: raiz.tema.icones.refazer, dica: "Pedir de novo" },
                            { id: "boa", icone: raiz.tema.icones.gostei, dica: "Gostei" },
                            { id: "ruim", icone: raiz.tema.icones.naoGostei, dica: "Não gostei" },
                        ]
                        Rectangle {
                            id: botaoAcao
                            required property var modelData
                            readonly property bool marcado: raiz.nota === modelData.id
                            property bool feito: false
                            width: 30; height: 30; radius: 8
                            color: areaAcao.containsMouse || marcado ? raiz.tema.superficie2 : "transparent"
                            Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
                            Icone {
                                anchors.centerIn: parent
                                caminho: botaoAcao.feito ? raiz.tema.icones.certo : botaoAcao.modelData.icone
                                cor: botaoAcao.marcado ? raiz.corPersona
                                   : areaAcao.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco
                                tamanho: 15
                                espessura: 1.7
                            }
                            MouseArea {
                                id: areaAcao
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var id = botaoAcao.modelData.id;
                                    if (id === "copiar") { raiz.copiar(raiz.texto); botaoAcao.feito = true; voltaCerto.restart(); }
                                    else if (id === "ouvir") raiz.ouvir(raiz.texto);
                                    else if (id === "refazer") raiz.refazer();
                                    else if (raiz.nota !== id) { raiz.nota = id; raiz.avaliar(raiz.texto, id); }
                                }
                            }
                            Timer { id: voltaCerto; interval: 1400; onTriggered: botaoAcao.feito = false }
                            ToolTipSimples {
                                tema: raiz.tema
                                anchors.bottom: undefined
                                anchors.top: parent.bottom
                                anchors.topMargin: 6
                                visivel: areaAcao.containsMouse
                                texto: botaoAcao.modelData.dica
                                z: 5
                            }
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        leftPadding: 8
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
