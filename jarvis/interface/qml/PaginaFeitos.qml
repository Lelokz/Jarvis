import QtQuick
import QtQuick.Controls.Basic

// Feitos (etapa 5 do tchan, 11/11/2026): o que a NOVA criou ou te mandou,
// com miniatura, filtro por tipo e a conversa de onde veio. Clicar abre o
// arquivo; passando o mouse, "Abrir" e "Mostrar na pasta". Começou a contar
// em 11/11/2026.
Item {
    id: raiz
    property var tema
    property var lista: null             // o evento "feitos": [{id, caminho, nome, pasta, tipo, quando, sessao, miniatura, previa, duracao}]
    property var titulos: ({})           // sessão -> título da conversa
    property string filtro: ""           // "" | imagem | video | documento | codigo
    signal abrirConversa(string sessao)

    readonly property var todos: lista || []
    readonly property var vistos: filtro ? todos.filter(function (f) { return f.tipo === filtro }) : todos
    function conta(t) { return todos.filter(function (f) { return f.tipo === t }).length }

    function grupoDe(seg) {
        var d = new Date(seg * 1000), hoje = new Date();
        var n = Math.round((new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate())
                            - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);
        return n <= 0 ? "HOJE" : n === 1 ? "ONTEM" : n < 7 ? "ESTA SEMANA" : n < 31 ? "ESTE MÊS" : "ANTES";
    }
    function quando(seg) {
        var d = new Date(seg * 1000);
        if (grupoDe(seg) === "HOJE") return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
        if (grupoDe(seg) === "ONTEM") return "ontem";
        return ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"][d.getDay()] + " " + d.getDate() + "/" + (d.getMonth() + 1);
    }
    // Os feitos agrupados por quando: [{grupo, itens}]
    readonly property var grupos: {
        var saida = [], atual = null;
        for (var i = 0; i < vistos.length; i++) {
            var g = grupoDe(vistos[i].quando);
            if (!atual || atual.grupo !== g) { atual = { grupo: g, itens: [] }; saida.push(atual); }
            atual.itens.push(vistos[i]);
        }
        return saida;
    }
    function urlDe(caminho) { return "file://" + encodeURI(caminho).replace(/#/g, "%23").replace(/\?/g, "%3F") }
    readonly property string iconeDoc: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h4"

    Flickable {
        anchors.fill: parent
        contentHeight: coluna.height + 60
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
            id: coluna
            width: Math.min(1300, raiz.width - 64)
            x: (raiz.width - width) / 2
            y: 32

            Text { text: "Feitos"; color: raiz.tema.texto; font.family: raiz.tema.familia; font.pixelSize: 26; font.weight: Font.DemiBold }
            Text {
                width: parent.width; topPadding: 6; wrapMode: Text.WordWrap
                text: "O que ela criou ou te mandou: imagens, vídeos, documentos e códigos. Clica pra abrir; cada um lembra de qual conversa veio."
                color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 14
            }
            Item { width: 1; height: 22 }
            Flow {
                width: parent.width; spacing: 8
                Repeater {
                    model: [ { t: "", n: "Tudo" }, { t: "imagem", n: "Imagens" }, { t: "video", n: "Vídeos" },
                             { t: "documento", n: "Documentos" }, { t: "codigo", n: "Código" } ]
                    Rectangle {
                        required property var modelData
                        readonly property bool sel: raiz.filtro === modelData.t
                        width: linhaChip.width + 28; height: 36; radius: 10
                        color: sel ? Qt.rgba(raiz.tema.persona.r, raiz.tema.persona.g, raiz.tema.persona.b, 0.12)
                             : areaChip.containsMouse ? raiz.tema.superficie2 : raiz.tema.superficie
                        border.width: 1; border.color: sel ? raiz.tema.persona : raiz.tema.tracoForte
                        Row {
                            id: linhaChip
                            anchors.centerIn: parent; spacing: 5
                            Text { text: modelData.n; color: parent.parent.sel ? raiz.tema.texto : raiz.tema.textoMedio
                                   font.family: raiz.tema.familia; font.pixelSize: 13 }
                            Text { text: modelData.t ? raiz.conta(modelData.t) : raiz.todos.length; color: raiz.tema.textoFraco
                                   font.family: raiz.tema.familia; font.pixelSize: 13 }
                        }
                        MouseArea { id: areaChip; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: raiz.filtro = modelData.t }
                    }
                }
            }
            Text {
                visible: raiz.vistos.length === 0
                topPadding: 40
                width: parent.width; wrapMode: Text.WordWrap
                text: raiz.lista === null ? "Carregando…"
                    : raiz.todos.length === 0 ? "Nada ainda. O que ela criar ou te mandar daqui pra frente (imagem, vídeo, documento, código) aparece aqui."
                    : "Nada desse tipo ainda."
                color: raiz.tema.muitoFraco; font.family: raiz.tema.familia; font.pixelSize: 14
            }

            Repeater {
                model: raiz.grupos
                Column {
                    required property var modelData
                    width: coluna.width
                    Text { topPadding: 28; bottomPadding: 10; text: modelData.grupo; color: raiz.tema.muitoFraco
                           font.family: raiz.tema.familia; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1.2 }
                    Grid {
                        id: grade
                        columns: Math.max(2, Math.floor((coluna.width + 16) / 300))
                        spacing: 16
                        readonly property real lado: (coluna.width - spacing * (columns - 1)) / columns
                        Repeater {
                            model: modelData.itens
                            Rectangle {
                                id: cartao
                                required property var modelData
                                width: grade.lado; height: miniatura.height + metaCartao.height
                                radius: 14; color: raiz.tema.superficie; clip: true
                                border.width: 1; border.color: sobreCartao.hovered ? raiz.tema.tracoForte : raiz.tema.traco
                                HoverHandler { id: sobreCartao }
                                Rectangle {
                                    id: miniatura
                                    width: parent.width; height: Math.round(width * 0.54)
                                    color: modelData.tipo === "codigo" ? raiz.tema.codigo : raiz.tema.claro ? "#e9edf3" : "#10141c"
                                    radius: 14
                                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 14; color: parent.color }
                                    Image {
                                        anchors.fill: parent
                                        visible: !!modelData.miniatura
                                        source: modelData.miniatura ? raiz.urlDe(modelData.miniatura) : ""
                                        sourceSize.width: 480
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        cache: true
                                    }
                                    Rectangle {
                                        visible: modelData.tipo === "video" && !!modelData.miniatura
                                        anchors.centerIn: parent; width: 46; height: 46; radius: 23; color: Qt.rgba(0, 0, 0, 0.55)
                                        Icone { anchors.centerIn: parent; anchors.horizontalCenterOffset: 2; caminho: "M8 5l11 7-11 7z"
                                                cheio: true; cor: "white"; tamanho: 20 }
                                    }
                                    Rectangle {
                                        visible: !!modelData.duracao
                                        anchors { right: parent.right; bottom: parent.bottom; margins: 8 }
                                        width: tDur.implicitWidth + 12; height: 20; radius: 5; color: Qt.rgba(0, 0, 0, 0.7)
                                        Text { id: tDur; anchors.centerIn: parent; text: modelData.duracao; color: "white"
                                               font.family: raiz.tema.familia; font.pixelSize: 11 }
                                    }
                                    Column {
                                        visible: !modelData.miniatura && modelData.tipo !== "codigo"
                                        anchors.centerIn: parent; spacing: 6
                                        readonly property string ext: modelData.nome.split(".").pop().toUpperCase()
                                        readonly property color cor: ext === "PDF" ? "#ff8f8f" : ext.indexOf("DOC") === 0 || ext === "ODT" ? "#7fb8ff"
                                                                   : ext.indexOf("XLS") === 0 || ext === "CSV" || ext === "ODS" ? "#6fdc9f"
                                                                   : modelData.tipo === "video" ? "#c4a5ff" : raiz.tema.textoMedio
                                        Icone { anchors.horizontalCenter: parent.horizontalCenter; caminho: raiz.iconeDoc; cor: parent.cor; tamanho: 46; espessura: 1.4 }
                                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: parent.ext; color: parent.cor
                                               font.family: raiz.tema.familia; font.pixelSize: 12; font.weight: Font.DemiBold; font.letterSpacing: 1 }
                                    }
                                    Text {
                                        visible: modelData.tipo === "codigo"
                                        x: 16; y: 14; width: parent.width - 32; height: parent.height - 22
                                        clip: true
                                        text: modelData.previa
                                        textFormat: Text.PlainText
                                        color: raiz.tema.textoMedio; font.family: raiz.tema.mono; font.pixelSize: 11
                                        lineHeight: 1.2
                                    }
                                }
                                Column {
                                    id: metaCartao
                                    anchors.top: miniatura.bottom
                                    x: 14; width: parent.width - 28
                                    topPadding: 11; bottomPadding: 13; spacing: 2
                                    Text { width: parent.width; elide: Text.ElideMiddle; text: modelData.nome; color: raiz.tema.texto
                                           font.family: raiz.tema.familia; font.pixelSize: 14; font.weight: Font.Medium }
                                    Text {
                                        width: parent.width; elide: Text.ElideRight
                                        text: raiz.quando(modelData.quando) + " · " + (modelData.como === "mandou" ? "enviado no WhatsApp"
                                              : (raiz.titulos[modelData.sessao] || modelData.pasta.replace(/^\/home\/[^\/]+/, "~")))
                                        color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 12
                                    }
                                }
                                MouseArea {
                                    id: areaCartao
                                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: Qt.openUrlExternally(raiz.urlDe(modelData.caminho))
                                }
                                Row {
                                    visible: sobreCartao.hovered
                                    anchors { top: parent.top; right: parent.right; margins: 10 }
                                    spacing: 6
                                    component Acao: Rectangle {
                                        property string rotulo
                                        signal clicado()
                                        width: tAc.implicitWidth + 20; height: 28; radius: 8
                                        color: ma.containsMouse ? raiz.tema.realce : Qt.rgba(0.05, 0.06, 0.09, 0.88)
                                        border.width: 1; border.color: raiz.tema.tracoForte
                                        Text { id: tAc; anchors.centerIn: parent; text: parent.rotulo; color: "#e6ebf2"
                                               font.family: raiz.tema.familia; font.pixelSize: 12 }
                                        MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                    onClicked: parent.clicado() }
                                    }
                                    Acao { rotulo: "Abrir"; onClicado: Qt.openUrlExternally(raiz.urlDe(cartao.modelData.caminho)) }
                                    Acao { rotulo: "Mostrar na pasta"; onClicado: Qt.openUrlExternally(raiz.urlDe(cartao.modelData.pasta)) }
                                    Acao { visible: !!cartao.modelData.sessao && !!raiz.titulos[cartao.modelData.sessao]; rotulo: "Conversa"
                                           onClicado: raiz.abrirConversa(cartao.modelData.sessao) }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
