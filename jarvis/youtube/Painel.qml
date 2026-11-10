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
    readonly property var cards: d.cards || []
    readonly property var comentarios: d.comentarios || []
    readonly property var analises: d.analises || ({})
    property var cardAberto: null          // o card no editor ({} = novo)
    property var confirmar: null           // { texto, sim: function }
    property var arrasto: null             // { tipo: "agendado"|"card", id, titulo }
    property point arrastoPos: Qt.point(0, 0)
    property date mesVisto: new Date(new Date().getFullYear(), new Date().getMonth(), 1)
    readonly property var colunas: [ { id: "ideia", t: "Ideia" }, { id: "gravando", t: "Gravando" }, { id: "editando", t: "Editando" },
                                     { id: "pronto", t: "Pronto" }, { id: "agendado", t: "Agendado" }, { id: "postado", t: "Postado" } ]
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
    function isoDia(x) { return x.getFullYear() + "-" + ("0" + (x.getMonth() + 1)).slice(-2) + "-" + ("0" + x.getDate()).slice(-2) }
    function diaDe(iso) { var x = dataDe(iso); return x ? isoDia(x) : "" }
    function brParaIso(s) { var m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(s.trim()); return m ? m[3] + "-" + ("0" + m[2]).slice(-2) + "-" + ("0" + m[1]).slice(-2) : "" }
    function isoParaBr(s) { return s ? s.slice(8, 10) + "/" + s.slice(5, 7) + "/" + s.slice(0, 4) : "" }
    function nomeMes(x) { return ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"][x.getMonth()] }
    function videoDe(id) { for (var i = 0; i < videos.length; i++) if (videos[i].id === id) return videos[i]; return null }
    function nomeColuna(id) { for (var i = 0; i < colunas.length; i++) if (colunas[i].id === id) return colunas[i].t; return id }
    function diasSemVideo() { var u = ultimoPublico(); return u ? Math.floor((Date.now() - dataDe(u.publicado).getTime()) / 86400000) : 0 }
    function noDia(iso) {
        var r = []
        for (var i = 0; i < videos.length; i++) {
            var v = videos[i]
            if (v.agendado && diaDe(v.agendado) === iso) r.push({ tipo: "agendado", v: v })
            else if (!v.agendado && v.visibilidade === "public" && diaDe(v.publicado) === iso) r.push({ tipo: "postado", v: v })
        }
        for (var k = 0; k < cards.length; k++)
            if (cards[k].data === iso && cards[k].coluna !== "postado" && cards[k].coluna !== "agendado") r.push({ tipo: "card", c: cards[k] })
        return r
    }
    function soltar() {
        var a = arrasto; arrasto = null
        if (!a) return
        if (a.tipo === "agendado" && aba === "calendario") {
            var p = gradeCal.mapFromItem(janela, arrastoPos.x, arrastoPos.y)
            if (p.x < 0 || p.y < 0 || p.x >= gradeCal.width || p.y >= gradeCal.height) return
            var i = Math.floor(p.y / (gradeCal.height / gradeCal.linhas)) * 7 + Math.floor(p.x / (gradeCal.width / 7))
            var dia = gradeCal.dias[i]
            var v = videoDe(a.id)
            if (!v || isoDia(dia) === diaDe(v.agendado)) return
            var hora = agendadoPara(v.agendado).split(" às ")[1]
            if (dia.getTime() < new Date(new Date().toDateString()).getTime()) { avisoTexto = "Não dá pra agendar no passado."; avisoOk = false; return }
            confirmar = { texto: "Mudar \"" + v.titulo + "\" para " + ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"][dia.getDay()] + ", " +
                          ("0" + dia.getDate()).slice(-2) + "/" + ("0" + (dia.getMonth() + 1)).slice(-2) + " às " + hora + "?",
                          sim: function () { painel.reagendarNoDia(a.id, isoDia(dia)) } }
        } else if (a.tipo === "card" && aba === "producao") {
            var q = quadro.mapFromItem(janela, arrastoPos.x, arrastoPos.y)
            if (q.y < 0 || q.y > quadro.height) return
            var c = Math.floor(q.x / (quadro.width / colunas.length))
            if (c >= 0 && c < colunas.length) painel.moverCard(a.id, colunas[c].id)
        }
    }

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

    component Barras: Cartao {
        id: bs
        property var itens: []
        property string sufixo: ""
        property bool porcento: false
        readonly property real total: itens.reduce(function (a, x) { return a + x.valor }, 0) || 1
        readonly property real maior: Math.max.apply(null, itens.map(function (x) { return x.valor }).concat([1]))
        height: 60 + Math.max(1, Math.min(7, itens.length)) * 35
        Text { x: 20; y: 46; visible: bs.itens.length === 0; text: "Sem dados ainda."; color: textoFraco; font { family: familia; pixelSize: 13 } }
        Column {
            x: 20; y: 44; width: bs.width - 40; spacing: 10
            Repeater {
                model: bs.itens.slice(0, 7)
                Column {
                    width: parent.width; spacing: 4
                    Row {
                        width: parent.width
                        Text { width: parent.width - pv.width; text: modelData.nome; elide: Text.ElideRight; color: textoMedio; font { family: familia; pixelSize: 12 } }
                        Text { id: pv; color: texto; font { family: familia; pixelSize: 12; weight: Font.DemiBold }
                               text: bs.porcento ? String(modelData.valor).replace(".", ",") + "%" : Math.round(100 * modelData.valor / bs.total) + "%" }
                    }
                    Rectangle { width: parent.width; height: 6; radius: 3; color: trilho
                        Rectangle { width: parent.width * modelData.valor / bs.maior; height: 6; radius: 3; color: roxo } }
                }
            }
        }
    }

    component GraficoInscritos: Canvas {
        id: gi
        property var dias: []
        onDiasChanged: requestPaint()
        onWidthChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            var n = dias.length; if (!n) return
            var maxV = 1
            for (var i = 0; i < n; i++) maxV = Math.max(maxV, dias[i].ganhos, dias[i].perdidos)
            var b = 22, meio = (height - b) * 0.66, w = width / n
            c.strokeStyle = trilho; c.beginPath(); c.moveTo(0, meio); c.lineTo(width, meio); c.stroke()
            for (var k = 0; k < n; k++) {
                var hg = (meio - 6) * dias[k].ganhos / maxV, hp = (height - b - meio - 4) * dias[k].perdidos / maxV
                c.fillStyle = verde; c.fillRect(k * w + 1, meio - hg, Math.max(1, w - 2), hg)
                c.fillStyle = vermelho; c.fillRect(k * w + 1, meio + 1, Math.max(1, w - 2), hp)
            }
            c.fillStyle = textoFraco; c.font = "11px '" + familia + "'"
            for (var q = 0; q < 5; q++) {
                var idx = Math.round(q * (n - 1) / 4), dd = dias[idx].dia
                c.textAlign = q === 0 ? "left" : q === 4 ? "right" : "center"
                c.fillText(dd.slice(8, 10) + "/" + dd.slice(5, 7), q === 0 ? 0 : q === 4 ? width : idx * w + w / 2, height - 4)
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
                model: [ { id: "inicio", nome: "Início", etapa: 0 }, { id: "calendario", nome: "Calendário", etapa: 0 },
                         { id: "producao", nome: "Produção", etapa: 0 }, { id: "videos", nome: "Vídeos", etapa: 0 },
                         { id: "comentarios", nome: "Comentários", etapa: 0 }, { id: "comunidade", nome: "Comunidade", etapa: 5 },
                         { id: "analises", nome: "Análises", etapa: 0 } ]
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
                    Rectangle { anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
                                visible: modelData.id === "comentarios" && (d.naoLidos || 0) > 0
                                height: 20; radius: 10; width: Math.max(20, tnl.implicitWidth + 12); color: roxoForte
                                Text { id: tnl; anchors.centerIn: parent; text: d.naoLidos > 99 ? "99+" : (d.naoLidos || 0); color: "white"
                                       font { family: familia; pixelSize: 11; weight: Font.DemiBold } } }
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

        // ================= CALENDÁRIO =================
        Item {
            anchors.fill: parent
            visible: aba === "calendario"
            Text { text: "Calendário"; color: texto; font { family: familia; pixelSize: 26; weight: Font.DemiBold } }
            Text { y: 36; color: textoFraco; font { family: familia; pixelSize: 13 }
                   text: "Faz " + diasSemVideo() + (diasSemVideo() === 1 ? " dia" : " dias") + " desde o último vídeo · " +
                         videos.filter(function (v) { return !v.agendado && v.visibilidade === "public" && diaDe(v.publicado).slice(0, 7) === isoDia(mesVisto).slice(0, 7) }).length +
                         " publicados em " + nomeMes(mesVisto) }
            Row {
                anchors.right: parent.right; spacing: 8
                Botao { rotulo: "‹"; width: 38; onClicado: mesVisto = new Date(mesVisto.getFullYear(), mesVisto.getMonth() - 1, 1) }
                Rectangle { width: 170; height: 38; radius: 10; color: superficie; border.color: traco
                    Text { anchors.centerIn: parent; text: nomeMes(mesVisto).charAt(0).toUpperCase() + nomeMes(mesVisto).slice(1) + " " + mesVisto.getFullYear()
                           color: texto; font { family: familia; pixelSize: 14; weight: Font.DemiBold } } }
                Botao { rotulo: "›"; width: 38; onClicado: mesVisto = new Date(mesVisto.getFullYear(), mesVisto.getMonth() + 1, 1) }
                Botao { rotulo: "Hoje"; onClicado: mesVisto = new Date(new Date().getFullYear(), new Date().getMonth(), 1) }
            }
            Row {
                y: 74; width: parent.width
                Repeater {
                    model: ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]
                    Text { width: parent.width / 7; horizontalAlignment: Text.AlignHCenter; text: modelData; color: textoFraco
                           font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                }
            }
            Item {
                id: gradeCal
                y: 98; width: parent.width; height: parent.height - y
                // 5 ou 6 semanas, o que o mês precisar.
                readonly property int linhas: Math.ceil((mesVisto.getDay() + new Date(mesVisto.getFullYear(), mesVisto.getMonth() + 1, 0).getDate()) / 7)
                readonly property var dias: {
                    var ini = new Date(mesVisto.getFullYear(), mesVisto.getMonth(), 1 - mesVisto.getDay()), r = []
                    for (var i = 0; i < linhas * 7; i++) r.push(new Date(ini.getFullYear(), ini.getMonth(), ini.getDate() + i))
                    return r
                }
                Repeater {
                    model: gradeCal.linhas * 7
                    Rectangle {
                        readonly property date dia: gradeCal.dias[index]
                        readonly property bool doMes: dia.getMonth() === mesVisto.getMonth()
                        readonly property bool hoje: isoDia(dia) === isoDia(new Date())
                        readonly property var itens: noDia(isoDia(dia))
                        x: (index % 7) * gradeCal.width / 7; y: Math.floor(index / 7) * gradeCal.height / gradeCal.linhas
                        width: gradeCal.width / 7 - 6; height: gradeCal.height / gradeCal.linhas - 6
                        radius: 10; color: doMes ? superficie : "transparent"; border.color: hoje ? roxo : doMes ? traco : "transparent"
                        opacity: doMes ? 1 : 0.4
                        Rectangle { x: 6; y: 6; width: 24; height: 24; radius: 12; color: parent.hoje ? roxoForte : "transparent"
                            Text { anchors.centerIn: parent; text: parent.parent.dia.getDate(); color: parent.parent.hoje ? "white" : textoMedio
                                   font { family: familia; pixelSize: 12; weight: Font.DemiBold } } }
                        Column {
                            x: 6; y: 34; width: parent.width - 12; spacing: 4
                            Repeater {
                                model: parent.parent.itens.slice(0, Math.max(1, Math.floor((parent.parent.height - 38) / 26)))
                                Rectangle {
                                    width: parent.width; height: 22; radius: 6
                                    color: modelData.tipo === "agendado" ? Qt.rgba(0.65, 0.55, 0.98, 0.22) : modelData.tipo === "postado" ? superficie2 : "transparent"
                                    border.color: modelData.tipo === "card" ? "#4b4266" : "transparent"
                                    opacity: arrasto && modelData.tipo === "agendado" && arrasto.id === modelData.v.id ? 0.35 : 1
                                    Row {
                                        x: 4; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                                        Thumb { visible: modelData.tipo === "postado"; width: 26; height: 15; radius: 3; fonte: modelData.v ? modelData.v.thumb : ""; rotulo: "" }
                                        Text { width: parent.parent.width - (modelData.tipo === "postado" ? 40 : 8); elide: Text.ElideRight
                                               color: modelData.tipo === "agendado" ? lilasTexto : modelData.tipo === "card" ? textoFraco : textoMedio
                                               font { family: familia; pixelSize: 11; weight: modelData.tipo === "agendado" ? Font.DemiBold : Font.Normal }
                                               readonly property color lilasTexto: "#d9ccff"
                                               text: modelData.tipo === "agendado" ? agendadoPara(modelData.v.agendado).split(" às ")[1] + " " + modelData.v.titulo
                                                   : modelData.tipo === "postado" ? modelData.v.titulo : nomeColuna(modelData.c.coluna) + ": " + modelData.c.titulo }
                                    }
                                    MouseArea {
                                        anchors.fill: parent; cursorShape: modelData.tipo === "agendado" ? Qt.OpenHandCursor : Qt.PointingHandCursor
                                        property point inicio
                                        onPressed: function (m) { inicio = Qt.point(m.x, m.y) }
                                        onPositionChanged: function (m) {
                                            if (modelData.tipo !== "agendado") return
                                            var g = mapToItem(janela, m.x, m.y)
                                            if (!arrasto && Math.abs(m.x - inicio.x) + Math.abs(m.y - inicio.y) > 8)
                                                arrasto = { tipo: "agendado", id: modelData.v.id, titulo: modelData.v.titulo }
                                            if (arrasto) arrastoPos = g
                                        }
                                        onReleased: { if (arrasto) soltar() }
                                        onClicked: { if (modelData.tipo === "card") cardAberto = modelData.c; else abrirFicha(modelData.v) }
                                    }
                                }
                            }
                            Text { visible: parent.parent.itens.length > Math.max(1, Math.floor((parent.parent.height - 38) / 26))
                                   text: "+" + (parent.parent.itens.length - Math.max(1, Math.floor((parent.parent.height - 38) / 26))) + " mais"
                                   color: textoFraco; font { family: familia; pixelSize: 10 } }
                        }
                    }
                }
            }
        }

        // ================= PRODUÇÃO =================
        Item {
            anchors.fill: parent
            visible: aba === "producao"
            Text { text: "Produção"; color: texto; font { family: familia; pixelSize: 26; weight: Font.DemiBold } }
            Text { y: 36; text: "Arraste o card pra mudar de etapa. Vídeo que sai no canal vai pra Agendado/Postado sozinho."
                   color: textoFraco; font { family: familia; pixelSize: 13 } }
            Botao { anchors.right: parent.right; rotulo: "+ Nova ideia"; principal: true
                    onClicado: cardAberto = { id: 0, titulo: "", jogo: "", coluna: "ideia", data: "", notas: "", arquivos: [], video: "" } }
            Row {
                id: quadro
                y: 76; width: parent.width; height: parent.height - y
                spacing: 12
                Repeater {
                    model: colunas
                    Rectangle {
                        id: col
                        readonly property var lista: cards.filter(function (c) { return c.coluna === modelData.id })
                        width: (quadro.width - quadro.spacing * 5) / 6; height: quadro.height
                        radius: 14; color: "#100e17"
                        border.color: arrasto && arrasto.tipo === "card" && quadro.mapFromItem(janela, arrastoPos.x, arrastoPos.y).x >= x
                                      && quadro.mapFromItem(janela, arrastoPos.x, arrastoPos.y).x < x + width ? roxo : traco
                        Text { x: 14; y: 14; text: modelData.t; color: texto; font { family: familia; pixelSize: 14; weight: Font.DemiBold } }
                        Text { anchors { right: parent.right; rightMargin: 14 } y: 15; text: col.lista.length; color: textoFraco; font { family: familia; pixelSize: 13 } }
                        Flickable {
                            x: 8; y: 44; width: parent.width - 16; height: parent.height - 52
                            contentHeight: pilha.height; clip: true; boundsBehavior: Flickable.StopAtBounds
                            interactive: !arrasto
                            Column {
                                id: pilha
                                width: parent.width; spacing: 8
                                Repeater {
                                    model: col.lista
                                    Rectangle {
                                        readonly property var vid: modelData.video ? videoDe(modelData.video) : null
                                        width: pilha.width; height: corpo.height + 20; radius: 10
                                        color: maCard.containsMouse ? superficie2 : superficie; border.color: traco
                                        opacity: arrasto && arrasto.id === modelData.id ? 0.35 : 1
                                        Column {
                                            id: corpo
                                            x: 10; y: 10; width: parent.width - 20; spacing: 6
                                            Thumb { visible: parent.parent.vid !== null; width: parent.width; height: width * 9 / 16; radius: 6
                                                    fonte: parent.parent.vid ? parent.parent.vid.thumb : ""; rotulo: "" }
                                            Text { width: parent.width; text: modelData.titulo; wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
                                                   color: texto; font { family: familia; pixelSize: 13; weight: Font.Medium } }
                                            Flow {
                                                width: parent.width; spacing: 6
                                                Etiqueta { visible: modelData.jogo !== ""; texto: modelData.jogo; cor: roxo }
                                                Etiqueta { visible: modelData.data !== ""; texto: "dia " + isoParaBr(modelData.data).slice(0, 5); cor: amarelo }
                                                Etiqueta { visible: modelData.arquivos.length > 0; cor: verde
                                                           texto: modelData.arquivos.length + (modelData.arquivos.length === 1 ? " arquivo" : " arquivos") }
                                            }
                                        }
                                        MouseArea {
                                            id: maCard; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            property point inicio
                                            onPressed: function (m) { inicio = Qt.point(m.x, m.y) }
                                            onPositionChanged: function (m) {
                                                if (!arrasto && Math.abs(m.x - inicio.x) + Math.abs(m.y - inicio.y) > 8)
                                                    arrasto = { tipo: "card", id: modelData.id, titulo: modelData.titulo }
                                                if (arrasto) arrastoPos = mapToItem(janela, m.x, m.y)
                                            }
                                            onReleased: { if (arrasto) soltar() }
                                            onClicked: cardAberto = modelData
                                        }
                                    }
                                }
                                Text { visible: col.lista.length === 0; width: pilha.width; horizontalAlignment: Text.AlignHCenter; topPadding: 12
                                       text: "vazio"; color: "#4d4760"; font { family: familia; pixelSize: 12 } }
                            }
                        }
                    }
                }
            }
        }

        // ================= COMENTÁRIOS =================
        Item {
            id: abaComent
            anchors.fill: parent
            visible: aba === "comentarios"
            property string filtro: "todos"
            property string respondendo: ""
            readonly property var lista: comentarios.filter(function (c) {
                return filtro === "naoLidos" ? !c.lido : filtro === "semResposta" ? !c.respondido : filtro === "perguntas" ? c.pergunta : true })
            Text { text: "Comentários"; color: texto; font { family: familia; pixelSize: 26; weight: Font.DemiBold } }
            Text { y: 36; color: textoFraco; font { family: familia; pixelSize: 13 }
                   text: (d.naoLidos || 0) + ((d.naoLidos || 0) === 1 ? " novo" : " novos") + " · " + comentarios.filter(function (c) { return !c.respondido && c.pergunta }).length + " perguntas sem resposta" }
            Botao { anchors.right: parent.right; rotulo: "Marcar todos como lidos"; ativo: (d.naoLidos || 0) > 0; onClicado: painel.marcarTodosLidos() }
            Row {
                y: 72; spacing: 8
                Repeater {
                    model: [ { id: "todos", t: "Todos" }, { id: "naoLidos", t: "Novos" }, { id: "semResposta", t: "Sem resposta" }, { id: "perguntas", t: "Perguntas" } ]
                    Rectangle {
                        height: 38; radius: 19; width: tfc.implicitWidth + 28
                        readonly property bool sel: abaComent.filtro === modelData.id
                        color: sel ? Qt.rgba(0.65, 0.55, 0.98, 0.18) : superficie; border.color: sel ? roxo : traco
                        Text { id: tfc; anchors.centerIn: parent; text: modelData.t; color: parent.sel ? texto : textoMedio
                               font { family: familia; pixelSize: 13; weight: parent.sel ? Font.DemiBold : Font.Normal } }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: abaComent.filtro = modelData.id }
                    }
                }
            }
            ListView {
                id: listaComent
                y: 126; width: parent.width; height: parent.height - y
                clip: true; spacing: 10; model: abaComent.lista
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                Text { visible: abaComent.lista.length === 0; anchors.horizontalCenter: parent.horizontalCenter; y: 40
                       text: "Nada por aqui."; color: textoFraco; font { family: familia; pixelSize: 14 } }
                delegate: Rectangle {
                    width: listaComent.width - 14; height: corpoC.height + 28; radius: 14
                    color: modelData.lido ? superficie : "#1a1628"; border.color: modelData.lido ? traco : "#3b3060"
                    Rectangle { visible: !modelData.lido; x: 0; y: 16; width: 3; height: 22; radius: 2; color: roxo }
                    Rectangle {
                        id: foto; x: 18; y: 16; width: 40; height: 40; radius: 20; color: "#2a2440"; clip: true
                        Text { anchors.centerIn: parent; text: (modelData.autor || "?").replace("@", "").charAt(0).toUpperCase(); color: lilas
                               readonly property color lilas: "#c4b5fd"; font { family: familia; pixelSize: 16; weight: Font.DemiBold } }
                        Image { anchors.fill: parent; source: modelData.foto; fillMode: Image.PreserveAspectCrop; visible: status === Image.Ready; asynchronous: true }
                    }
                    Column {
                        id: corpoC
                        x: 72; y: 14; width: parent.width - 72 - 18; spacing: 6
                        Row {
                            spacing: 8
                            Text { text: modelData.autor; color: texto; font { family: familia; pixelSize: 13; weight: Font.DemiBold } }
                            Text { text: haQuanto(modelData.quando); color: textoFraco; font { family: familia; pixelSize: 12 } }
                            Text { text: "em"; color: textoFraco; font { family: familia; pixelSize: 12 } }
                            Text { text: modelData.video_titulo || "vídeo"; color: roxo; font { family: familia; pixelSize: 12; weight: Font.Medium }
                                   width: Math.min(implicitWidth, corpoC.width * 0.45); elide: Text.ElideRight
                                   MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { var v = videoDe(modelData.video); if (v) abrirFicha(v) } } }
                            Etiqueta { visible: !!modelData.pergunta && !modelData.respondido; texto: "Pergunta"; cor: amarelo }
                            Etiqueta { visible: !!modelData.respondido; texto: "Respondido"; cor: verde }
                        }
                        Text { width: parent.width; text: modelData.texto; wrapMode: Text.Wrap; color: textoMedio; font { family: familia; pixelSize: 13 }
                               maximumLineCount: 8; elide: Text.ElideRight; lineHeight: 1.15 }
                        Row {
                            spacing: 18
                            Text { text: modelData.likes + (modelData.likes === 1 ? " like" : " likes"); color: textoFraco; font { family: familia; pixelSize: 12 } }
                            Text { text: modelData.respostas + (modelData.respostas === 1 ? " resposta" : " respostas"); color: textoFraco; font { family: familia; pixelSize: 12 } }
                            Text { text: "Responder"; color: roxo; font { family: familia; pixelSize: 12; weight: Font.DemiBold }
                                   MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor
                                               onClicked: { abaComent.respondendo = abaComent.respondendo === modelData.id ? "" : modelData.id; avisoTexto = "" } } }
                            Text { visible: !modelData.lido; text: "Marcar como lido"; color: textoMedio; font { family: familia; pixelSize: 12 }
                                   MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor; onClicked: painel.marcarLido(modelData.id) } }
                            Text { text: "Abrir no YouTube"; color: textoMedio; font { family: familia; pixelSize: 12 }
                                   MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor
                                               onClicked: painel.abrirLink("https://www.youtube.com/watch?v=" + modelData.video + "&lc=" + modelData.id) } }
                        }
                        Column {
                            visible: abaComent.respondendo === modelData.id
                            width: parent.width; spacing: 8
                            ScrollView {
                                width: parent.width; height: 80
                                background: Rectangle { radius: 10; color: superficie2; border.color: campoResp.activeFocus ? roxo : traco }
                                TextArea { id: campoResp; color: texto; font.family: familia; font.pixelSize: 13; wrapMode: TextArea.Wrap; padding: 12
                                           background: null; selectByMouse: true; placeholderText: "Responder como Lelokz…"; placeholderTextColor: "#5a536d" }
                            }
                            Row {
                                spacing: 8
                                Botao { rotulo: ocupado ? "Enviando…" : "Responder"; principal: true; ativo: !ocupado && campoResp.text.trim() !== ""
                                        onClicado: { painel.responder(modelData.id, campoResp.text); campoResp.text = ""; abaComent.respondendo = "" } }
                                Botao { rotulo: "Cancelar"; onClicado: abaComent.respondendo = "" }
                            }
                        }
                    }
                }
            }
        }

        // ================= ANÁLISES =================
        Flickable {
            anchors.fill: parent
            visible: aba === "analises"
            Component.onCompleted: if (typeof rolarInicial !== "undefined" && rolarInicial > 0) contentY = rolarInicial
            contentHeight: colAn.height; clip: true; boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            Column {
                id: colAn
                width: parent.width - 14; spacing: 16
                Column {
                    spacing: 6
                    Text { text: "Análises"; color: texto; font { family: familia; pixelSize: 26; weight: Font.DemiBold } }
                    Text { text: "Últimos 28 dias. O YouTube entrega estes números com uns 2 dias de atraso."; color: textoFraco; font { family: familia; pixelSize: 13 } }
                }
                Row {
                    id: linhaAn
                    width: parent.width; height: 120; spacing: 16
                    readonly property var d28: (d.dias || []).slice(-28)
                    readonly property int ganhos: d28.reduce(function (a, x) { return a + x.ganhos }, 0)
                    readonly property int perdidos: d28.reduce(function (a, x) { return a + x.perdidos }, 0)
                    readonly property int likes: d28.reduce(function (a, x) { return a + x.likes }, 0)
                    Numero { width: (parent.width - 48) / 4; height: parent.height; titulo: "Inscritos ganhos"; valor: "+" + mil(linhaAn.ganhos); detalhe: "pessoas que se inscreveram"; corDetalhe: verde }
                    Numero { width: (parent.width - 48) / 4; height: parent.height; titulo: "Inscritos perdidos"; valor: "−" + mil(linhaAn.perdidos); detalhe: "saíram do canal"; corDetalhe: vermelho }
                    Numero { width: (parent.width - 48) / 4; height: parent.height; titulo: "Saldo"; valor: (linhaAn.ganhos - linhaAn.perdidos >= 0 ? "+" : "−") + mil(Math.abs(linhaAn.ganhos - linhaAn.perdidos))
                             detalhe: "ganhos menos perdidos" }
                    Numero { width: (parent.width - 48) / 4; height: parent.height; titulo: "Likes"; valor: mil(linhaAn.likes); detalhe: "em todos os vídeos" }
                }
                Cartao {
                    width: parent.width; height: 230; titulo: "Inscritos por dia · 90 dias (verde ganhou, vermelho perdeu)"
                    GraficoInscritos { anchors { fill: parent; topMargin: 46; leftMargin: 20; rightMargin: 20; bottomMargin: 12 } dias: d.dias || [] }
                }
                Cartao {
                    id: cTop
                    width: parent.width; height: 70 + Math.max(1, (analises.top || []).length) * 54; titulo: "Os vídeos que mais trouxeram views"
                    Text { x: 20; y: 46; visible: !(analises.top || []).length; text: "Sem dados ainda."; color: textoFraco; font { family: familia; pixelSize: 13 } }
                    Column {
                        x: 20; y: 44; width: parent.width - 40; spacing: 8
                        Repeater {
                            model: analises.top || []
                            Rectangle {
                                readonly property var v: videoDe(modelData.video)
                                width: parent.width; height: 46; radius: 8; color: maTop.containsMouse ? superficie2 : "transparent"
                                Text { x: 6; anchors.verticalCenter: parent.verticalCenter; text: index + 1; color: textoFraco; width: 18
                                       font { family: familia; pixelSize: 13; weight: Font.DemiBold } }
                                Thumb { x: 30; anchors.verticalCenter: parent.verticalCenter; width: 64; height: 36; radius: 5; fonte: parent.v ? parent.v.thumb : ""; rotulo: "" }
                                Text { x: 108; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 108 - 330; elide: Text.ElideRight
                                       text: parent.v ? parent.v.titulo : modelData.video; color: texto; font { family: familia; pixelSize: 13 } }
                                Row {
                                    anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                                    Text { width: 110; horizontalAlignment: Text.AlignRight; text: mil(modelData.views) + " views"; color: texto; font { family: familia; pixelSize: 13; weight: Font.DemiBold } }
                                    Text { width: 120; horizontalAlignment: Text.AlignRight; text: "+" + mil(modelData.inscritos) + " inscritos"; color: verde; font { family: familia; pixelSize: 13 } }
                                    Text { width: 90; horizontalAlignment: Text.AlignRight; text: mil(modelData.minutos / 60) + " h"; color: textoFraco; font { family: familia; pixelSize: 13 } }
                                }
                                MouseArea { id: maTop; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (parent.v) abrirFicha(parent.v) }
                            }
                        }
                    }
                }
                Grid {
                    width: parent.width; columns: 2; spacing: 16
                    readonly property real larg: (width - spacing) / 2
                    Barras { width: parent.larg; titulo: "De onde vem o público"; itens: analises.origens || [] }
                    Barras { width: parent.larg; titulo: "Países"; itens: analises.paises || [] }
                    Barras { width: parent.larg; titulo: "Idade de quem assiste"; itens: analises.idades || []; porcento: true }
                    Barras { width: parent.larg; titulo: "Aparelhos"; itens: analises.aparelhos || [] }
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
                var ag = dataDe(ficha.agendado)
                campoDia.text = ag ? ("0" + ag.getDate()).slice(-2) + "/" + ("0" + (ag.getMonth() + 1)).slice(-2) + "/" + ag.getFullYear() : ""
                campoHora.text = ag ? ("0" + ag.getHours()).slice(-2) + ":" + ("0" + ag.getMinutes()).slice(-2) : ""
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
                    width: parent.width; height: Math.max(110, cFicha.height - 458)
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
                Item { width: 1; height: 6 }
                Text { text: ficha && ficha.agendado ? "AGENDADO PARA" : "AGENDAR (vídeo privado sai sozinho no dia)"; color: textoFraco
                       font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                Row {
                    spacing: 8
                    enabled: ficha !== null && ficha.visibilidade === "private"
                    opacity: enabled ? 1 : 0.4
                    TextField { id: campoDia; width: 130; height: 38; placeholderText: "14/11/2026"; placeholderTextColor: "#5a536d"
                                color: texto; font.family: familia; font.pixelSize: 13; leftPadding: 12; selectByMouse: true
                                background: Rectangle { radius: 10; color: superficie2; border.color: campoDia.activeFocus ? roxo : traco } }
                    TextField { id: campoHora; width: 84; height: 38; placeholderText: "18:00"; placeholderTextColor: "#5a536d"
                                color: texto; font.family: familia; font.pixelSize: 13; leftPadding: 12; selectByMouse: true
                                background: Rectangle { radius: 10; color: superficie2; border.color: campoHora.activeFocus ? roxo : traco } }
                    Botao { rotulo: ficha && ficha.agendado ? "Mudar" : "Agendar"; ativo: !ocupado
                            onClicado: painel.agendar(ficha.id, campoDia.text, campoHora.text) }
                    Botao { visible: ficha !== null && ficha.agendado !== ""; rotulo: "Tirar do agendamento"; ativo: !ocupado
                            onClicado: confirmar = { texto: "Tirar \"" + ficha.titulo + "\" do agendamento? Ele continua privado e não sai sozinho.",
                                                     sim: function () { painel.desagendar(ficha.id) } } }
                }
                Text { visible: ficha !== null && ficha.visibilidade !== "private"; color: textoFraco; font { family: familia; pixelSize: 11 }
                       text: "Este já saiu: só dá pra agendar vídeo privado." }
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

    // ================= O EDITOR DO CARD =================
    Rectangle {
        anchors.fill: parent
        visible: cardAberto !== null
        color: Qt.rgba(0.02, 0.01, 0.05, 0.72)
        MouseArea { anchors.fill: parent; onClicked: cardAberto = null }
        onVisibleChanged: if (visible) {
            cTitulo.text = cardAberto.titulo; cJogo.text = cardAberto.jogo; cData.text = isoParaBr(cardAberto.data)
            cNotas.text = cardAberto.notas; cColuna.valor = cardAberto.coluna; cArquivos.lista = cardAberto.arquivos.slice(); cApagar.certeza = false
        }
        Rectangle {
            anchors.centerIn: parent
            width: 640; height: Math.min(parent.height - 60, 640)
            radius: 18; color: superficie; border.color: traco
            MouseArea { anchors.fill: parent }
            Column {
                x: 28; y: 26; width: parent.width - 56; spacing: 8
                Text { text: cardAberto && cardAberto.id ? "Card" : "Nova ideia"; color: texto; font { family: familia; pixelSize: 20; weight: Font.DemiBold } }
                Item { width: 1; height: 4 }
                Text { text: "TÍTULO"; color: textoFraco; font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                TextField { id: cTitulo; width: parent.width; height: 42; color: texto; font.family: familia; font.pixelSize: 14; leftPadding: 12; selectByMouse: true
                            placeholderText: "Do que é o vídeo?"; placeholderTextColor: "#5a536d"
                            background: Rectangle { radius: 10; color: superficie2; border.color: cTitulo.activeFocus ? roxo : traco } }
                Row {
                    spacing: 12
                    Column { spacing: 8
                        Text { text: "JOGO"; color: textoFraco; font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                        TextField { id: cJogo; width: 280; height: 40; color: texto; font.family: familia; font.pixelSize: 13; leftPadding: 12; selectByMouse: true
                                    placeholderText: "Doors, Minecraft…"; placeholderTextColor: "#5a536d"
                                    background: Rectangle { radius: 10; color: superficie2; border.color: cJogo.activeFocus ? roxo : traco } } }
                    Column { spacing: 8
                        Text { text: "DATA PLANEJADA"; color: textoFraco; font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                        TextField { id: cData; width: 160; height: 40; color: texto; font.family: familia; font.pixelSize: 13; leftPadding: 12; selectByMouse: true
                                    placeholderText: "14/11/2026"; placeholderTextColor: "#5a536d"
                                    background: Rectangle { radius: 10; color: superficie2; border.color: cData.activeFocus ? roxo : (cData.text && !brParaIso(cData.text) ? vermelho : traco) } } }
                }
                Text { text: "ETAPA"; color: textoFraco; font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                Flow {
                    id: cColuna
                    property string valor: "ideia"
                    width: parent.width; spacing: 6
                    Repeater {
                        model: colunas
                        Rectangle {
                            height: 32; radius: 8; width: tc.implicitWidth + 22
                            readonly property bool sel: cColuna.valor === modelData.id
                            color: sel ? Qt.rgba(0.65, 0.55, 0.98, 0.18) : superficie2; border.color: sel ? roxo : traco
                            Text { id: tc; anchors.centerIn: parent; text: modelData.t; color: parent.sel ? texto : textoMedio; font { family: familia; pixelSize: 12 } }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: cColuna.valor = modelData.id }
                        }
                    }
                }
                Text { text: "NOTAS"; color: textoFraco; font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                ScrollView {
                    width: parent.width; height: 110
                    background: Rectangle { radius: 10; color: superficie2; border.color: cNotas.activeFocus ? roxo : traco }
                    TextArea { id: cNotas; color: texto; font.family: familia; font.pixelSize: 13; wrapMode: TextArea.Wrap; padding: 12; background: null; selectByMouse: true
                               placeholderText: "Roteiro, ideias de thumb, o que gravar…"; placeholderTextColor: "#5a536d" }
                }
                Row {
                    width: parent.width
                    Text { width: parent.width - btArq.width; text: "ARQUIVOS (gravação, prévia da decupagem…)"; color: textoFraco; anchors.verticalCenter: parent.verticalCenter
                           font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
                    Botao { id: btArq; rotulo: "Ligar arquivo"; height: 32; onClicado: escolherArquivo.open() }
                }
                Column {
                    id: cArquivos
                    property var lista: []
                    width: parent.width; spacing: 4
                    Repeater {
                        model: cArquivos.lista
                        Rectangle {
                            width: cArquivos.width; height: 32; radius: 8; color: superficie2
                            Text { x: 12; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 120; elide: Text.ElideMiddle
                                   text: modelData.split("/").pop(); color: textoMedio; font { family: familia; pixelSize: 12 } }
                            Text { anchors { right: parent.right; rightMargin: 46; verticalCenter: parent.verticalCenter } text: "Abrir"; color: roxo
                                   font { family: familia; pixelSize: 12; weight: Font.DemiBold }
                                   MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor; onClicked: painel.abrirArquivo(modelData) } }
                            Text { anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter } text: "✕"; color: textoFraco
                                   font { family: familia; pixelSize: 12 }
                                   MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor
                                               onClicked: { var l = cArquivos.lista.slice(); l.splice(index, 1); cArquivos.lista = l } } }
                        }
                    }
                    Text { visible: cArquivos.lista.length === 0; text: "Nenhum arquivo ligado."; color: "#5a536d"; font { family: familia; pixelSize: 12 } }
                }
            }
            Row {
                anchors { left: parent.left; bottom: parent.bottom; margins: 24 }
                Botao { id: cApagar; property bool certeza: false; visible: cardAberto !== null && cardAberto.id > 0
                        rotulo: certeza ? "Clica de novo pra apagar" : "Apagar"
                        onClicado: { if (!certeza) { certeza = true; return } painel.apagarCard(cardAberto.id); cardAberto = null } }
            }
            Row {
                anchors { right: parent.right; bottom: parent.bottom; margins: 24 }
                spacing: 10
                Botao { rotulo: "Cancelar"; onClicado: cardAberto = null }
                Botao { rotulo: "Salvar"; principal: true; ativo: cTitulo.text.trim() !== "" && (!cData.text || brParaIso(cData.text) !== "")
                        onClicado: {
                            var campos = { titulo: cTitulo.text, jogo: cJogo.text.trim(), data: brParaIso(cData.text), notas: cNotas.text,
                                           coluna: cColuna.valor, arquivos: cArquivos.lista }
                            if (cardAberto.id) painel.salvarCard(cardAberto.id, campos); else painel.criarCard(campos)
                            cardAberto = null
                        } }
            }
        }
    }

    FileDialog {
        id: escolherArquivo
        title: "Ligar um arquivo ao card"
        currentFolder: "file:///mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Estudio/Gravacoes"
        onAccepted: { var l = cArquivos.lista.slice(); l.push(painel.caminhoDe(selectedFile.toString())); cArquivos.lista = l }
    }

    // ================= CONFIRMAR =================
    Rectangle {
        anchors.fill: parent
        visible: confirmar !== null
        color: Qt.rgba(0.02, 0.01, 0.05, 0.72)
        MouseArea { anchors.fill: parent; onClicked: confirmar = null }
        Rectangle {
            anchors.centerIn: parent; width: 460; height: txtConf.height + 110
            radius: 16; color: superficie; border.color: traco
            MouseArea { anchors.fill: parent }
            Text { id: txtConf; x: 26; y: 26; width: parent.width - 52; wrapMode: Text.WordWrap; text: confirmar ? confirmar.texto : ""
                   color: texto; font { family: familia; pixelSize: 15 } }
            Row {
                anchors { right: parent.right; bottom: parent.bottom; margins: 20 }
                spacing: 10
                Botao { rotulo: "Não"; onClicado: confirmar = null }
                Botao { rotulo: "Sim"; principal: true; onClicado: { var f = confirmar.sim; confirmar = null; f() } }
            }
        }
    }

    // o que está sendo arrastado, seguindo o mouse
    Rectangle {
        visible: arrasto !== null
        x: arrastoPos.x + 10; y: arrastoPos.y + 6
        width: Math.min(260, ta.implicitWidth + 24); height: 30; radius: 8; color: roxoForte; opacity: 0.92
        Text { id: ta; x: 12; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 24; elide: Text.ElideRight
               text: arrasto ? arrasto.titulo : ""; color: "white"; font { family: familia; pixelSize: 12; weight: Font.DemiBold } }
    }

    // aviso solto (fora da ficha: agendar pelo calendário, produção)
    Rectangle {
        visible: avisoTexto !== "" && ficha === null && cardAberto === null
        anchors { horizontalCenter: conteudo.horizontalCenter; bottom: parent.bottom; bottomMargin: 20 }
        height: 40; radius: 20; width: tav.implicitWidth + 40
        color: avisoOk ? "#16301f" : "#3a1a1f"; border.color: avisoOk ? verde : vermelho
        Text { id: tav; anchors.centerIn: parent; text: avisoTexto; color: avisoOk ? verde : vermelho; font { family: familia; pixelSize: 13; weight: Font.Medium } }
        Timer { running: parent.visible; interval: 5000; onTriggered: avisoTexto = "" }
    }

    FileDialog {
        id: escolherThumb
        title: "Escolha a nova thumb (JPG ou PNG, até 2 MB)"
        nameFilters: ["Imagens (*.jpg *.jpeg *.png)"]
        onAccepted: painel.trocarThumb(ficha.id, selectedFile.toString())
    }
}
