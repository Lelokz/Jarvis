import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import QtQuick.Dialogs

// O Painel do Canal (09/11/2026): o canal Lelokz no estilo da NOVA, em roxo
// (a cor do Léo). Etapa 2: Início, Vídeos e a ficha de cada vídeo. As outras
// abas aparecem apagadas, com a etapa em que chegam.
Window {
    id: janela
    width: 1280; height: 800
    minimumWidth: 1100; minimumHeight: 700
    visible: true
    color: fundo
    title: "Painel do Canal"

    readonly property string familia: "Inter Variable"
    readonly property color fundo: "#0b0a10"
    readonly property color superficie: "#15131d"
    readonly property color superficie2: "#1b1826"
    readonly property color traco: "#262037"
    readonly property color trilho: "#221d30"
    readonly property color texto: "#ece9f5"
    readonly property color textoMedio: "#bdb6d0"
    readonly property color textoFraco: "#857d9c"
    readonly property color roxo: "#a78bfa"
    readonly property color roxoForte: "#8b5cf6"
    readonly property color verde: "#4ade80"
    readonly property color vermelho: "#f87171"
    readonly property color amarelo: "#fbbf24"

    readonly property var d: painel.dados
    readonly property bool temDados: d.temDados === true
    readonly property var canal: d.canal || ({ titulo: "", inscritos: 0, views: 0, videos: 0, meta: 100 })
    readonly property var numeros: d.numeros || ({})
    readonly property var videos: d.videos || []
    property string aba: abaInicial || "inicio"
    property var ficha: null
    property string avisoTexto: ""
    property bool avisoOk: true
    property bool ocupado: false

    // ---- ajudantes ----
    function mil(n) { return Math.round(n || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".") }
    function dataDe(iso) {
        if (!iso) return null
        return new Date(iso)
    }
    function dataCurta(iso) {
        var x = dataDe(iso); if (!x) return ""
        return ("0" + x.getDate()).slice(-2) + "/" + ("0" + (x.getMonth() + 1)).slice(-2) + "/" + x.getFullYear()
    }
    function haQuanto(iso) {
        var x = dataDe(iso); if (!x) return ""
        var dias = Math.floor((Date.now() - x.getTime()) / 86400000)
        return dias <= 0 ? "hoje" : dias === 1 ? "ontem" : dias < 30 ? "há " + dias + " dias"
             : dias < 365 ? "há " + Math.floor(dias / 30) + (dias < 60 ? " mês" : " meses") : "há " + Math.floor(dias / 365) + (dias < 730 ? " ano" : " anos")
    }
    function agendadoPara(iso) {
        var x = dataDe(iso); if (!x) return ""
        var sem = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"][x.getDay()]
        return sem + ", " + ("0" + x.getDate()).slice(-2) + "/" + ("0" + (x.getMonth() + 1)).slice(-2) + " às " + ("0" + x.getHours()).slice(-2) + ":" + ("0" + x.getMinutes()).slice(-2)
    }
    function duracao(s) {
        var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), ss = s % 60
        return (h ? h + ":" + ("0" + m).slice(-2) : m) + ":" + ("0" + ss).slice(-2)
    }
    function atualizadoHa(seg) {
        var m = Math.floor((Date.now() / 1000 - seg) / 60)
        return m < 1 ? "Atualizado agora" : m < 60 ? "Atualizado há " + m + " min" : m < 1440 ? "Atualizado há " + Math.floor(m / 60) + " h"
             : "Atualizado " + haQuanto(new Date(seg * 1000).toISOString())
    }
    function nomeVis(v) { return v === "public" ? "Público" : v === "unlisted" ? "Não listado" : "Privado" }
    function corVar(v) { return v === null || v === undefined ? textoFraco : v >= 0 ? verde : vermelho }
    function textoVar(v) { return v === null || v === undefined ? "sem comparação" : (v >= 0 ? "+" : "") + v + "% contra os 28 dias antes" }
    function ultimoPublico() { for (var i = 0; i < videos.length; i++) if (videos[i].visibilidade === "public" && !videos[i].agendado) return videos[i]; return null }
    function agendados() { return videos.filter(function (v) { return v.agendado }).reverse() }
    function abrirFicha(v) { ficha = v; avisoTexto = "" }

    Connections {
        target: painel
        function onAviso(t, ok) { avisoTexto = t; avisoOk = ok; if (ok && ficha) {
            for (var i = 0; i < videos.length; i++) if (videos[i].id === ficha.id) { ficha = videos[i]; break } } }
        function onTrabalhando(b) { ocupado = b }
    }
    Component.onCompleted: if (fichaInicial) for (var i = 0; i < videos.length; i++) if (videos[i].id === fichaInicial) abrirFicha(videos[i])

    // ---- peças ----
    component Cartao: Rectangle {
        property string titulo
        radius: 16; color: superficie; border.color: traco
        Text { x: 20; y: 16; text: parent.titulo; color: textoFraco; visible: parent.titulo !== ""
               font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium; capitalization: Font.AllUppercase } }
    }

    component Numero: Cartao {
        id: num
        property string valor
        property string detalhe
        property color corDetalhe: textoFraco
        Text { x: 20; y: 38; text: num.valor; color: texto; font { family: familia; pixelSize: 34; weight: Font.DemiBold } }
        Text { x: 20; y: 86; width: num.width - 40; elide: Text.ElideRight; text: num.detalhe; color: num.corDetalhe
               font { family: familia; pixelSize: 12 } }
    }

    component Thumb: Rectangle {
        id: th
        property string fonte
        property string rotulo
        radius: 10; clip: true
        gradient: Gradient { orientation: Gradient.Horizontal
            GradientStop { position: 0; color: "#2a1f47" } GradientStop { position: 1; color: "#1a1428" } }
        Image { anchors.fill: parent; source: th.fonte; fillMode: Image.PreserveAspectCrop; asynchronous: true
                visible: status === Image.Ready; smooth: true; mipmap: true }
        Text { anchors.centerIn: parent; width: parent.width - 24; visible: th.fonte === ""; text: th.rotulo
               horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
               color: textoMedio; font { family: familia; pixelSize: 13; weight: Font.Medium } }
    }

    component Etiqueta: Rectangle {
        property alias texto: rot.text
        property color cor: roxo
        height: 22; radius: 6; width: rot.implicitWidth + 14
        color: Qt.rgba(cor.r, cor.g, cor.b, 0.18)
        Text { id: rot; anchors.centerIn: parent; color: parent.cor; font { family: familia; pixelSize: 11; weight: Font.DemiBold } }
    }

    component Botao: Rectangle {
        id: bt
        property string rotulo
        property bool principal: false
        property bool ativo: true
        signal clicado()
        height: 38; radius: 10; width: rb.implicitWidth + 32
        opacity: ativo ? 1 : 0.45
        color: principal ? (ma.containsMouse ? "#9a7af7" : roxoForte) : (ma.containsMouse ? "#2a2440" : superficie2)
        border.color: principal ? "transparent" : traco
        Text { id: rb; anchors.centerIn: parent; text: bt.rotulo; color: principal ? "white" : texto
               font { family: familia; pixelSize: 13; weight: Font.DemiBold } }
        MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; enabled: bt.ativo; cursorShape: Qt.PointingHandCursor
                    onClicked: bt.clicado() }
    }

    component Grafico: Canvas {
        id: gr
        property var valores: []
        property var rotulos: []
        onValoresChanged: requestPaint()
        onWidthChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            var n = valores.length; if (n < 2) return
            var maxV = Math.max.apply(null, valores) || 1
            var e = 8, t = 10, b = 26, w = width - e * 2, h = height - t - b
            function px(i) { return e + w * i / (n - 1) }
            function py(v) { return t + h - h * v / maxV }
            c.strokeStyle = trilho; c.lineWidth = 1
            for (var k = 0; k <= 3; k++) { var y = t + h * k / 3; c.beginPath(); c.moveTo(e, y); c.lineTo(e + w, y); c.stroke() }
            var g = c.createLinearGradient(0, t, 0, t + h)
            g.addColorStop(0, Qt.rgba(0.65, 0.55, 0.98, 0.35)); g.addColorStop(1, Qt.rgba(0.65, 0.55, 0.98, 0.0))
            c.beginPath(); c.moveTo(px(0), py(valores[0]))
            for (var i = 1; i < n; i++) c.lineTo(px(i), py(valores[i]))
            c.lineTo(px(n - 1), t + h); c.lineTo(px(0), t + h); c.closePath(); c.fillStyle = g; c.fill()
            c.beginPath(); c.moveTo(px(0), py(valores[0]))
            for (var j = 1; j < n; j++) c.lineTo(px(j), py(valores[j]))
            c.strokeStyle = roxo; c.lineWidth = 2.2; c.lineJoin = "round"; c.stroke()
            c.fillStyle = textoFraco; c.font = "11px '" + familia + "'"
            var passos = Math.min(5, n)
            for (var q = 0; q < passos; q++) {
                var idx = Math.round(q * (n - 1) / (passos - 1))
                var r = rotulos[idx] || ""
                c.textAlign = q === 0 ? "left" : q === passos - 1 ? "right" : "center"
                c.fillText(r, px(idx), height - 6)
            }
        }
    }

    // ---- barra da esquerda ----
    Rectangle {
        id: lado
        width: 232; height: parent.height
        color: "#0f0d16"
        Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: traco }
        Image { x: 22; y: 24; width: 30; height: 30; source: "image://atomo/a78bfa"; sourceSize: Qt.size(60, 60); smooth: true }
        Text { x: 62; y: 22; text: "Painel do Canal"; color: texto; font { family: familia; pixelSize: 17; weight: Font.DemiBold } }
        Text { x: 62; y: 44; text: temDados ? canal.titulo : "sem canal"; color: textoFraco; font { family: familia; pixelSize: 12 } }

        Column {
            y: 92; width: parent.width; spacing: 4
            Repeater {
                model: [ { id: "inicio", nome: "Início", etapa: 0 }, { id: "calendario", nome: "Calendário", etapa: 3 },
                         { id: "producao", nome: "Produção", etapa: 3 }, { id: "videos", nome: "Vídeos", etapa: 0 },
                         { id: "comentarios", nome: "Comentários", etapa: 4 }, { id: "comunidade", nome: "Comunidade", etapa: 5 },
                         { id: "analises", nome: "Análises", etapa: 4 } ]
                Rectangle {
                    x: 12; width: lado.width - 24; height: 40; radius: 10
                    readonly property bool atual: aba === modelData.id
                    readonly property bool pronta: modelData.etapa === 0
                    color: atual ? Qt.rgba(0.65, 0.55, 0.98, 0.16) : maNav.containsMouse && pronta ? superficie2 : "transparent"
                    Rectangle { x: 0; anchors.verticalCenter: parent.verticalCenter; width: 3; height: 18; radius: 2; color: roxo; visible: parent.atual }
                    Text { x: 16; anchors.verticalCenter: parent.verticalCenter; text: modelData.nome
                           color: parent.atual ? texto : parent.pronta ? textoMedio : "#5a536d"
                           font { family: familia; pixelSize: 14; weight: parent.atual ? Font.DemiBold : Font.Normal } }
                    Text { anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
                           visible: !parent.pronta; text: "etapa " + modelData.etapa; color: "#4d4760"; font { family: familia; pixelSize: 11 } }
                    MouseArea { id: maNav; anchors.fill: parent; hoverEnabled: true; enabled: parent.pronta
                                cursorShape: Qt.PointingHandCursor; onClicked: { aba = modelData.id; ficha = null } }
                }
            }
        }

        Column {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 20 }
            spacing: 10
            Text { width: parent.width; wrapMode: Text.WordWrap; color: textoFraco; font { family: familia; pixelSize: 12 }
                   text: !temDados ? "" : ocupado ? "Atualizando…" : atualizadoHa(d.atualizado) }
            Botao { rotulo: "Atualizar agora"; ativo: d.conectado === true && !ocupado; onClicado: painel.sincronizar() }
        }
    }

    // ---- sem dados ----
    Column {
        visible: !temDados
        anchors.centerIn: conteudo
        spacing: 12
        width: 460
        Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: d.conectado ? "Buscando os dados do canal…" : "Falta conectar o YouTube"
               color: texto; font { family: familia; pixelSize: 22; weight: Font.DemiBold } }
        Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; color: textoFraco
               font { family: familia; pixelSize: 14 }
               text: d.conectado ? "Leva um minutinho na primeira vez." : "É uma vez só, uns 10 minutos: siga o guia em docs/PAINEL - CONECTAR O YOUTUBE.md, no projeto do Jarvis." }
    }

    Item {
        id: conteudo
        anchors { left: lado.right; right: parent.right; top: parent.top; bottom: parent.bottom; margins: 28 }
        visible: temDados

        // ================= INÍCIO =================
        Item {
            anchors.fill: parent
            visible: aba === "inicio"
            Text { text: "Início"; color: texto; font { family: familia; pixelSize: 26; weight: Font.DemiBold } }
            Text { y: 36; text: "Os últimos 28 dias do canal"; color: textoFraco; font { family: familia; pixelSize: 13 } }

            Row {
                id: linhaNumeros
                y: 76; width: parent.width; height: 120; spacing: 16
                readonly property real larg: (width - spacing * 3) / 4
                Numero { width: linhaNumeros.larg; height: parent.height; titulo: "Inscritos"; valor: mil(canal.inscritos)
                         detalhe: (numeros.inscritos28 >= 0 ? "+" : "") + mil(numeros.inscritos28) + " nos últimos 28 dias"
                         corDetalhe: numeros.inscritos28 >= 0 ? verde : vermelho }
                Numero { width: linhaNumeros.larg; height: parent.height; titulo: "Views"; valor: mil(numeros.views28)
                         detalhe: textoVar(numeros.views28_var); corDetalhe: corVar(numeros.views28_var) }
                Numero { width: linhaNumeros.larg; height: parent.height; titulo: "Horas assistidas"; valor: mil(numeros.horas28)
                         detalhe: textoVar(numeros.horas28_var); corDetalhe: corVar(numeros.horas28_var) }
                Cartao {
                    width: linhaNumeros.larg; height: parent.height; titulo: "Próxima meta"
                    Text { x: 20; y: 38; text: mil(canal.meta); color: texto; font { family: familia; pixelSize: 34; weight: Font.DemiBold } }
                    Text { anchors { right: parent.right; rightMargin: 20; baseline: parent.top; baselineOffset: 72 }
                           text: "faltam " + mil(canal.meta - canal.inscritos); color: roxo; font { family: familia; pixelSize: 13; weight: Font.Medium } }
                    Rectangle { x: 20; y: 90; width: parent.width - 40; height: 8; radius: 4; color: trilho
                        Rectangle { width: parent.width * Math.min(1, canal.inscritos / canal.meta); height: 8; radius: 4; color: roxo } }
                }
            }

            Cartao {
                id: cGrafico
                y: linhaNumeros.y + linhaNumeros.height + 16
                width: parent.width - colDireita.width - 16; height: parent.height - y
                titulo: "Views por dia · últimos 90 dias"
                Grafico {
                    anchors { fill: parent; topMargin: 44; leftMargin: 12; rightMargin: 12; bottomMargin: 10 }
                    valores: (d.dias || []).map(function (x) { return x.views })
                    rotulos: (d.dias || []).map(function (x) { return x.dia.slice(8, 10) + "/" + x.dia.slice(5, 7) })
                }
            }

            Column {
                id: colDireita
                x: parent.width - width; y: cGrafico.y
                width: 380; spacing: 16
                Cartao {
                    id: cUltimo
                    width: parent.width; height: 330; titulo: "Último vídeo"
                    readonly property var v: ultimoPublico()
                    visible: v !== null
                    Thumb { id: thU; x: 20; y: 40; width: parent.width - 40; height: width * 9 / 16
                            fonte: cUltimo.v ? cUltimo.v.thumb : ""; rotulo: cUltimo.v ? cUltimo.v.titulo : "" }
                    Text { x: 20; y: thU.y + thU.height + 12; width: parent.width - 40; text: cUltimo.v ? cUltimo.v.titulo : ""
                           elide: Text.ElideRight; color: texto; font { family: familia; pixelSize: 15; weight: Font.DemiBold } }
                    Text { x: 20; y: thU.y + thU.height + 36; width: parent.width - 40; elide: Text.ElideRight; color: textoMedio
                           font { family: familia; pixelSize: 12 }
                           text: cUltimo.v ? haQuanto(cUltimo.v.publicado) + " · " + mil(cUltimo.v.views) + " views · " + mil(cUltimo.v.likes) + " likes · " + mil(cUltimo.v.comentarios) + " comentários" : "" }
                    Text { x: 20; y: thU.y + thU.height + 56; width: parent.width - 40; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                           font { family: familia; pixelSize: 12; weight: Font.Medium }
                           color: !cUltimo.v ? textoFraco : cUltimo.v.comparacao.indexOf("acima") >= 0 ? verde : cUltimo.v.comparacao.indexOf("abaixo") >= 0 ? amarelo : textoMedio
                           text: cUltimo.v && cUltimo.v.comparacao ? cUltimo.v.comparacao.charAt(0).toUpperCase() + cUltimo.v.comparacao.slice(1) : "" }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { aba = "videos"; abrirFicha(cUltimo.v) } }
                }
                Cartao {
                    width: parent.width; height: cGrafico.height - cUltimo.height - 16; titulo: "Agendados"
                    readonly property var lista: agendados()
                    Text { x: 20; y: 46; visible: parent.lista.length === 0; text: "Nenhum vídeo agendado."; color: textoFraco; font { family: familia; pixelSize: 13 } }
                    Column {
                        x: 20; y: 44; width: parent.width - 40; spacing: 10
                        Repeater {
                            model: parent.parent.lista.slice(0, 3)
                            Row {
                                spacing: 12
                                Thumb { width: 72; height: 40.5; radius: 6; fonte: modelData.thumb; rotulo: "" }
                                Column {
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text { width: 236; elide: Text.ElideRight; text: modelData.titulo; color: texto; font { family: familia; pixelSize: 13; weight: Font.Medium } }
                                    Text { text: agendadoPara(modelData.agendado); color: roxo; font { family: familia; pixelSize: 12 } }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ================= VÍDEOS =================
        Item {
            id: abaVideos
            anchors.fill: parent
            visible: aba === "videos"
            property string filtro: "todos"
            property string ordem: "novos"
            property string busca: ""
            readonly property var lista: {
                var b = busca.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
                var r = videos.filter(function (v) {
                    if (filtro === "agendados" && !v.agendado) return false
                    if (filtro === "public" && (v.visibilidade !== "public" || v.agendado)) return false
                    if ((filtro === "unlisted" || filtro === "private") && (v.visibilidade !== filtro || v.agendado)) return false
                    return !b || v.titulo.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").indexOf(b) >= 0
                })
                if (ordem === "vistos") r = r.slice().sort(function (a, c) { return c.views - a.views })
                return r
            }

            Text { text: "Vídeos"; color: texto; font { family: familia; pixelSize: 26; weight: Font.DemiBold } }
            Text { y: 36; text: mil(abaVideos.lista.length) + (abaVideos.lista.length === 1 ? " vídeo" : " vídeos"); color: textoFraco; font { family: familia; pixelSize: 13 } }

            Row {
                id: filtros
                y: 72; spacing: 8
                TextField {
                    width: 280; height: 38
                    placeholderText: "Procurar pelo título…"
                    placeholderTextColor: textoFraco; color: texto
                    font { family: familia; pixelSize: 13 }
                    leftPadding: 14
                    background: Rectangle { radius: 10; color: superficie; border.color: parent.activeFocus ? roxo : traco }
                    onTextChanged: abaVideos.busca = text
                }
                Item { width: 8; height: 1 }
                Repeater {
                    model: [ { id: "todos", t: "Todos" }, { id: "public", t: "Públicos" }, { id: "agendados", t: "Agendados" },
                             { id: "unlisted", t: "Não listados" }, { id: "private", t: "Privados" } ]
                    Rectangle {
                        height: 38; radius: 19; width: tf.implicitWidth + 28
                        readonly property bool sel: abaVideos.filtro === modelData.id
                        color: sel ? Qt.rgba(0.65, 0.55, 0.98, 0.18) : superficie
                        border.color: sel ? roxo : traco
                        Text { id: tf; anchors.centerIn: parent; text: modelData.t; color: parent.sel ? texto : textoMedio
                               font { family: familia; pixelSize: 13; weight: parent.sel ? Font.DemiBold : Font.Normal } }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: abaVideos.filtro = modelData.id }
                    }
                }
            }
            Rectangle {
                anchors { right: parent.right; top: filtros.top }
                height: 38; radius: 10; width: to.implicitWidth + 28; color: superficie; border.color: traco
                Text { id: to; anchors.centerIn: parent; text: abaVideos.ordem === "novos" ? "Mais novos primeiro" : "Mais vistos primeiro"
                       color: textoMedio; font { family: familia; pixelSize: 13 } }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: abaVideos.ordem = abaVideos.ordem === "novos" ? "vistos" : "novos" }
            }

            GridView {
                id: grade
                y: 128; width: parent.width; height: parent.height - y
                clip: true
                readonly property int colunas: Math.max(2, Math.floor(width / 290))
                cellWidth: width / colunas; cellHeight: cellWidth * 9 / 16 + 86
                model: abaVideos.lista
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Item {
                    width: grade.cellWidth; height: grade.cellHeight
                    Rectangle {
                        anchors { fill: parent; margins: 8 }
                        radius: 14; color: maV.containsMouse ? superficie2 : "transparent"
                        Thumb { id: thV; x: 0; y: 0; width: parent.width; height: width * 9 / 16; fonte: modelData.thumb; rotulo: modelData.titulo }
                        Rectangle { anchors { right: thV.right; bottom: thV.bottom; margins: 8 } visible: modelData.duracao > 0
                                    height: 20; radius: 5; width: td.implicitWidth + 10; color: Qt.rgba(0, 0, 0, 0.75)
                                    Text { id: td; anchors.centerIn: parent; text: duracao(modelData.duracao); color: "white"; font { family: familia; pixelSize: 11; weight: Font.DemiBold } } }
                        Etiqueta { anchors { left: thV.left; top: thV.top; margins: 8 }
                                   visible: modelData.agendado || modelData.visibilidade !== "public"
                                   texto: modelData.agendado ? "Agendado" : nomeVis(modelData.visibilidade)
                                   cor: modelData.agendado ? roxo : amarelo }
                        Text { x: 4; y: thV.height + 10; width: parent.width - 8; text: modelData.titulo; wrapMode: Text.WordWrap
                               maximumLineCount: 2; elide: Text.ElideRight; color: texto; font { family: familia; pixelSize: 14; weight: Font.Medium } }
                        Text { x: 4; y: thV.height + 52; color: textoFraco; font { family: familia; pixelSize: 12 }
                               text: modelData.agendado ? "Sai " + agendadoPara(modelData.agendado) : dataCurta(modelData.publicado) + " · " + mil(modelData.views) + " views" }
                        MouseArea { id: maV; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: abrirFicha(modelData) }
                    }
                }
            }
        }
    }

    // ================= A FICHA DO VÍDEO =================
    Rectangle {
        anchors.fill: parent
        visible: ficha !== null
        color: Qt.rgba(0.02, 0.01, 0.05, 0.72)
        MouseArea { anchors.fill: parent; onClicked: ficha = null }

        Rectangle {
            id: cFicha
            anchors.centerIn: parent
            width: Math.min(parent.width - 80, 1100); height: Math.min(parent.height - 60, 700)
            radius: 18; color: superficie; border.color: traco
            MouseArea { anchors.fill: parent }   // clique dentro não fecha

            property var dias: ficha ? painel.diasDoVideo(ficha.id) : []
            onVisibleChanged: if (visible && ficha) carregar()
            function carregar() {
                campoTitulo.text = ficha.titulo; campoDesc.text = ficha.descricao
                campoTags.text = (ficha.tags || []).join(", "); escolhaVis.valor = ficha.visibilidade
            }
            Connections { target: janela; function onFichaChanged() { if (ficha) cFicha.carregar() } }

            // esquerda: a thumb e os números
            Column {
                id: colFichaEsq
                x: 28; y: 28; width: 430; spacing: 14
                Thumb { width: parent.width; height: width * 9 / 16; fonte: ficha ? ficha.thumb : ""; rotulo: ficha ? ficha.titulo : "" }
                Row {
                    spacing: 10
                    Botao { rotulo: "Trocar a thumb"; ativo: !ocupado; onClicado: escolherThumb.open() }
                    Botao { rotulo: "Abrir no YouTube"; onClicado: painel.abrirLink("https://youtu.be/" + ficha.id) }
                }
                Row {
                    spacing: 10
                    Repeater {
                        model: ficha ? [ { t: "views", v: ficha.views }, { t: "likes", v: ficha.likes }, { t: "comentários", v: ficha.comentarios } ] : []
                        Rectangle {
                            width: 136; height: 66; radius: 12; color: superficie2; border.color: traco
                            Text { x: 14; y: 10; text: mil(modelData.v); color: texto; font { family: familia; pixelSize: 22; weight: Font.DemiBold } }
                            Text { x: 14; y: 40; text: modelData.t; color: textoFraco; font { family: familia; pixelSize: 12 } }
                        }
                    }
                }
                Text { width: parent.width; wrapMode: Text.WordWrap; color: textoMedio; font { family: familia; pixelSize: 12 }
                       text: !ficha ? "" : ficha.agendado ? "Agendado: sai " + agendadoPara(ficha.agendado) + "." :
                             "Publicado em " + dataCurta(ficha.publicado) + " (" + haQuanto(ficha.publicado) + ")" + (ficha.duracao ? " · " + duracao(ficha.duracao) : "") +
                             (ficha.comparacao ? ". " + ficha.comparacao.charAt(0).toUpperCase() + ficha.comparacao.slice(1) + "." : ".") }
                Rectangle {
                    width: parent.width; height: Math.max(120, cFicha.height - y - 56); radius: 12; color: superficie2; border.color: traco
                    visible: cFicha.dias.length > 1
                    Text { x: 14; y: 10; text: "VIEWS POR DIA DESDE QUE SAIU"; color: textoFraco; font { family: familia; pixelSize: 10; letterSpacing: 1.1; weight: Font.Medium } }
                    Grafico { anchors { fill: parent; topMargin: 30; margins: 8 }
                              valores: cFicha.dias.map(function (x) { return x.views })
                              rotulos: cFicha.dias.map(function (x) { return x.dia.slice(8, 10) + "/" + x.dia.slice(5, 7) }) }
                }
            }

            // direita: o que dá pra mudar
            Column {
                x: colFichaEsq.x + colFichaEsq.width + 32; y: 28
                width: cFicha.width - x - 28; spacing: 8

                Row {
                    width: parent.width
                    Text { width: parent.width - contTit.width; text: "TÍTULO"; color: textoFraco; font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                    Text { id: contTit; text: campoTitulo.length + "/100"; color: campoTitulo.length > 100 ? vermelho : textoFraco; font { family: familia; pixelSize: 11 } }
                }
                TextField {
                    id: campoTitulo
                    width: parent.width; height: 44
                    color: texto; font { family: familia; pixelSize: 15; weight: Font.Medium }
                    leftPadding: 14; selectByMouse: true
                    background: Rectangle { radius: 10; color: superficie2; border.color: campoTitulo.activeFocus ? roxo : traco }
                }
                Item { width: 1; height: 6 }
                Text { text: "DESCRIÇÃO"; color: textoFraco; font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                ScrollView {
                    width: parent.width; height: Math.max(140, cFicha.height - 372)
                    background: Rectangle { radius: 10; color: superficie2; border.color: campoDesc.activeFocus ? roxo : traco }
                    TextArea {
                        id: campoDesc
                        color: texto; font { family: familia; pixelSize: 13 }
                        wrapMode: TextArea.Wrap; selectByMouse: true
                        padding: 14
                        background: null
                    }
                }
                Item { width: 1; height: 6 }
                Text { text: "TAGS (separadas por vírgula)"; color: textoFraco; font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                TextField {
                    id: campoTags
                    width: parent.width; height: 40
                    color: texto; font { family: familia; pixelSize: 13 }
                    leftPadding: 14; selectByMouse: true
                    background: Rectangle { radius: 10; color: superficie2; border.color: campoTags.activeFocus ? roxo : traco }
                }
                Item { width: 1; height: 6 }
                Text { text: "VISIBILIDADE"; color: textoFraco; font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                Row {
                    id: escolhaVis
                    property string valor: "public"
                    spacing: 8
                    Repeater {
                        model: [ "public", "unlisted", "private" ]
                        Rectangle {
                            height: 38; radius: 10; width: tv.implicitWidth + 30
                            readonly property bool sel: escolhaVis.valor === modelData
                            color: sel ? Qt.rgba(0.65, 0.55, 0.98, 0.18) : superficie2
                            border.color: sel ? roxo : traco
                            Text { id: tv; anchors.centerIn: parent; text: nomeVis(modelData); color: parent.sel ? texto : textoMedio
                                   font { family: familia; pixelSize: 13; weight: parent.sel ? Font.DemiBold : Font.Normal } }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: escolhaVis.valor = modelData }
                        }
                    }
                }
                Text { visible: ficha && ficha.agendado && escolhaVis.valor !== "private"; width: parent.width; wrapMode: Text.WordWrap
                       color: amarelo; font { family: familia; pixelSize: 12 }
                       text: "Mudando pra " + nomeVis(escolhaVis.valor) + ", ele sai AGORA e deixa de estar agendado." }
            }

            // embaixo: salvar
            Row {
                anchors { right: parent.right; bottom: parent.bottom; margins: 24 }
                spacing: 10
                Botao { rotulo: "Fechar"; onClicado: ficha = null }
                Botao { rotulo: ocupado ? "Salvando…" : "Salvar no YouTube"; principal: true; ativo: !ocupado && campoTitulo.length > 0 && campoTitulo.length <= 100
                        onClicado: painel.salvar(ficha.id, campoTitulo.text, campoDesc.text, campoTags.text, escolhaVis.valor) }
            }
            Text {
                anchors { left: parent.left; bottom: parent.bottom; margins: 28; bottomMargin: 34 }
                width: parent.width * 0.5; elide: Text.ElideRight
                text: avisoTexto; color: avisoOk ? verde : vermelho; font { family: familia; pixelSize: 13; weight: Font.Medium }
            }
        }
    }

    FileDialog {
        id: escolherThumb
        title: "Escolha a nova thumb (JPG ou PNG, até 2 MB)"
        nameFilters: ["Imagens (*.jpg *.jpeg *.png)"]
        onAccepted: painel.trocarThumb(ficha.id, selectedFile.toString())
    }
}
