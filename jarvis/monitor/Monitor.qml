import QtQuick
import QtQuick.Window

// O Monitor do Sistema, como o protótipo que o Léo aprovou em 08/11/2026:
// um cartão por peça, número grande, e a cor diz o estado de longe
// (azul tranquilo, amarelo puxado, vermelho no limite).
Window {
    id: janela
    width: 940; height: 600
    minimumWidth: 940; minimumHeight: 600
    visible: true
    color: "#0a0c10"
    title: "Monitor do Sistema"

    readonly property string familia: "Inter Variable"
    readonly property color superficie: "#131821"
    readonly property color traco: "#1f2734"
    readonly property color trilho: "#1c2330"
    readonly property color texto: "#e6ebf2"
    readonly property color textoMedio: "#b9c1cf"
    readonly property color textoFraco: "#7e879b"
    readonly property color azul: "#4da3ff"
    readonly property color amarelo: "#ffb454"
    readonly property color vermelho: "#ff6b6b"
    readonly property color corCache: "#7387a8"

    readonly property var d: monitor.dados
    readonly property bool pronto: d.cpu !== undefined
    readonly property var gpu: d.gpu || null
    readonly property var cpu: d.cpu || ({ nome: "", nucleos: 0, uso: 0, temp: null })
    readonly property var ram: d.ram || ({ total: 1, usada: 0, cache: 0, livre: 0 })
    readonly property var discos: d.discos || []

    function corPara(v, chave) {
        if (v === null || v === undefined) return azul
        var l = limites[chave]
        return v >= l[1] ? vermelho : v >= l[0] ? amarelo : azul
    }
    function pior(a, b) { return (a === vermelho || b === vermelho) ? vermelho : (a === amarelo || b === amarelo) ? amarelo : azul }
    function palavra(c) { return c === vermelho ? "No limite" : c === amarelo ? "Puxado" : "Tranquilo" }
    function virgula(x, casas) { return Number(x).toFixed(casas).replace(".", ",") }

    // ---- componentes ----
    component Anel: Item {
        id: anel
        property real valor: 0
        property color cor: azul
        property string legenda: "uso"
        Behavior on valor { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
        Behavior on cor { ColorAnimation { duration: 400 } }
        onValorChanged: tela.requestPaint()
        onCorChanged: tela.requestPaint()
        width: 168; height: 168
        Canvas {
            id: tela
            anchors.fill: parent
            onPaint: {
                var c = getContext("2d"); c.reset()
                var r = width / 2 - 10, cx = width / 2, cy = height / 2
                var ini = Math.PI * 0.75, fim = Math.PI * 2.25
                c.lineCap = "round"; c.lineWidth = 12
                c.strokeStyle = trilho; c.beginPath(); c.arc(cx, cy, r, ini, fim); c.stroke()
                if (anel.valor > 0.5) {
                    c.strokeStyle = anel.cor
                    c.beginPath(); c.arc(cx, cy, r, ini, ini + (fim - ini) * Math.min(100, anel.valor) / 100); c.stroke()
                }
            }
        }
        Column {
            anchors.centerIn: parent
            spacing: -2
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                Text { id: numAnel; text: Math.round(anel.valor); color: texto; font { family: familia; pixelSize: 46; weight: Font.DemiBold } }
                Text { text: "%"; color: textoFraco; font { family: familia; pixelSize: 20; weight: Font.Medium }
                       anchors.baseline: numAnel.baseline }
            }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: anel.legenda; color: textoFraco; font { family: familia; pixelSize: 13 } }
        }
    }

    component Barra: Rectangle {
        property real fracao: 0
        property color corBarra: azul
        Behavior on fracao { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
        height: 10; radius: height / 2; color: trilho
        Rectangle {
            width: Math.max(parent.height, parent.width * Math.min(1, parent.fracao)); height: parent.height; radius: parent.radius
            color: parent.corBarra; visible: parent.fracao > 0
            Behavior on color { ColorAnimation { duration: 400 } }
        }
    }

    component Termometro: Column {
        id: termo
        property var graus: null
        property real maximo: 100
        property color cor: azul
        spacing: 8
        Text { text: "TEMPERATURA"; color: textoFraco; font { family: familia; pixelSize: 11; letterSpacing: 1.2; weight: Font.Medium } }
        Row {
            Text { id: numTermo; text: termo.graus === null ? "—" : Math.round(termo.graus); color: termo.cor
                   font { family: familia; pixelSize: 38; weight: Font.DemiBold }
                   Behavior on color { ColorAnimation { duration: 400 } } }
            Text { text: "°C"; color: textoFraco; font { family: familia; pixelSize: 18 }
                   visible: termo.graus !== null
                   anchors.baseline: numTermo.baseline }
        }
        Barra { width: 150; height: 8; fracao: termo.graus === null ? 0 : termo.graus / termo.maximo; corBarra: termo.cor }
    }

    component Selo: Rectangle {
        id: selo
        property color cor: azul
        Behavior on cor { ColorAnimation { duration: 400 } }
        height: 24; radius: 12
        width: rotulo.implicitWidth + 26
        color: Qt.rgba(cor.r, cor.g, cor.b, 0.13)
        Rectangle { x: 10; anchors.verticalCenter: parent.verticalCenter; width: 6; height: 6; radius: 3; color: selo.cor }
        Text { id: rotulo; x: 20; anchors.verticalCenter: parent.verticalCenter; text: palavra(selo.cor); color: selo.cor
               font { family: familia; pixelSize: 12; weight: Font.Medium } }
    }

    component Cartao: Rectangle {
        id: cartao
        property string titulo
        property string subtitulo
        property color cor: azul
        radius: 16; color: superficie; border.color: traco
        Text { x: 22; y: 18; text: cartao.titulo; color: texto; font { family: familia; pixelSize: 16; weight: Font.DemiBold } }
        Text { x: 22; y: 40; width: cartao.width - 44; elide: Text.ElideRight; text: cartao.subtitulo; color: textoFraco
               font { family: familia; pixelSize: 12 } }
        Selo { cor: cartao.cor; anchors { right: parent.right; top: parent.top; margins: 18 } }
    }

    component Peca: Cartao {
        id: peca
        property real uso: 0
        property var temp: null
        property string chaveTemp: "temp_cpu"
        readonly property color corUso: janela.corPara(uso, "uso")
        readonly property color corTemp: janela.corPara(temp, chaveTemp)
        cor: pior(corUso, corTemp)
        Anel { x: 22; y: 62; valor: peca.uso; cor: peca.corUso }
        Termometro { x: Math.max(240, peca.width * 0.55); y: 100; graus: peca.temp; cor: peca.corTemp }
    }

    component Disco: Cartao {
        id: disco
        property var info
        readonly property real pct: info.pct
        titulo: info.titulo
        subtitulo: info.tamanho + " GB · " + (info.papel || info.modelo)
        cor: janela.corPara(pct, "disco")
        Row {
            x: 22; y: 74
            Text { id: numDisco; text: Math.round(disco.pct); color: texto; font { family: familia; pixelSize: 40; weight: Font.DemiBold } }
            Text { text: "% usado"; color: textoFraco; font { family: familia; pixelSize: 15 }
                   anchors.baseline: numDisco.baseline }
        }
        Barra { x: 22; y: 134; width: disco.width - 44; fracao: disco.pct / 100; corBarra: disco.cor }
        Text { x: 22; y: 156; text: Math.round(disco.info.usado) + " GB usados"; color: textoMedio; font { family: familia; pixelSize: 13 } }
        Text { x: 22; y: 178; text: Math.round(disco.info.livre) + " GB livres de " + Math.round(disco.info.total)
               color: textoFraco; font { family: familia; pixelSize: 13 } }
    }

    // ---- tela ----
    Image {
        x: 28; y: 24; width: 30; height: 30
        source: "image://atomo/4da3ff"
        sourceSize: Qt.size(60, 60)
        smooth: true
    }
    Text { x: 70; y: 22; text: "Monitor do Sistema"; color: texto; font { family: familia; pixelSize: 20; weight: Font.DemiBold } }
    Text { x: 70; y: 47; text: pronto ? "Atualiza a cada segundo" : "Lendo o PC…"; color: textoFraco; font { family: familia; pixelSize: 12 } }

    Item {
        id: conteudo
        anchors { fill: parent; leftMargin: 24; rightMargin: 24; topMargin: 80; bottomMargin: 24 }
        opacity: pronto ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 280 } }
        readonly property int vao: 16
        readonly property real alturaCima: (height - vao) * 0.49

        // Em cima: placa de vídeo e processador (sem placa NVIDIA, o processador ocupa a linha).
        Row {
            id: cima
            width: parent.width; height: conteudo.alturaCima
            spacing: conteudo.vao
            Peca {
                visible: gpu !== null
                width: (cima.width - conteudo.vao) / 2; height: cima.height
                titulo: "Placa de vídeo"
                subtitulo: gpu ? gpu.nome + " · " + virgula(gpu.memoria_usada, 1) + " de " + virgula(gpu.memoria_total, 0) + " GB de memória" : ""
                uso: gpu ? gpu.uso : 0; temp: gpu ? gpu.temp : null; chaveTemp: "temp_gpu"
            }
            Peca {
                width: gpu !== null ? (cima.width - conteudo.vao) / 2 : cima.width; height: cima.height
                titulo: "Processador"
                subtitulo: cpu.nome + " · " + cpu.nucleos + " núcleos"
                uso: cpu.uso; temp: cpu.temp; chaveTemp: "temp_cpu"
            }
        }

        // Embaixo: a RAM e um cartão por disco (o HD novo entra sozinho aqui).
        Row {
            id: baixo
            y: cima.height + conteudo.vao
            width: parent.width; height: parent.height - y
            spacing: conteudo.vao
            readonly property real larguraDisco: discos.length ? (width - larguraRam - spacing * discos.length) / discos.length : 0
            readonly property real larguraRam: discos.length ? Math.max(360, width * 0.41) : width

            Cartao {
                id: cRam
                width: baixo.larguraRam; height: baixo.height
                readonly property real pct: 100 * ram.usada / ram.total
                titulo: "Memória RAM"; subtitulo: virgula(ram.total, 1) + " GB no total"
                cor: janela.corPara(pct, "ram")
                Row {
                    x: 22; y: 74
                    Text { id: numRam; text: virgula(ram.usada, 1); color: texto; font { family: familia; pixelSize: 40; weight: Font.DemiBold } }
                    Text { text: " GB em uso"; color: textoFraco; font { family: familia; pixelSize: 15 }
                   anchors.baseline: numRam.baseline }
                }
                // Uma barra em três partes: em uso | em cache | livre.
                Item {
                    id: trilhoRam
                    x: 22; y: 134; width: cRam.width - 44; height: 10
                    property real fUso: ram.usada / ram.total
                    property real fCache: ram.cache / ram.total
                    Behavior on fUso { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                    Behavior on fCache { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                    Rectangle { anchors.fill: parent; radius: 5; color: trilho }
                    Rectangle { id: bUso; width: parent.width * trilhoRam.fUso; height: 10; radius: 5; color: cRam.cor
                                Behavior on color { ColorAnimation { duration: 400 } } }
                    Rectangle { x: bUso.width + 2; width: Math.max(0, parent.width * trilhoRam.fCache - 2); height: 10; radius: 5
                                color: corCache; opacity: 0.55 }
                }
                Column {
                    x: 22; y: 160; spacing: 8
                    Repeater {
                        model: [ { c: cRam.cor, t: "Em uso", v: ram.usada },
                                 { c: corCache, t: "Em cache (o Linux solta se precisar)", v: ram.cache },
                                 { c: "#3a4458", t: "Livre", v: ram.livre } ]
                        Row {
                            spacing: 8
                            Rectangle { width: 8; height: 8; radius: 4; color: modelData.c; anchors.verticalCenter: parent.verticalCenter }
                            Text { width: cRam.width - 44 - 16 - 64; text: modelData.t; color: textoMedio; font { family: familia; pixelSize: 13 } }
                            Text { width: 64; horizontalAlignment: Text.AlignRight; text: virgula(modelData.v, 1) + " GB"; color: texto
                                   font { family: familia; pixelSize: 13; weight: Font.Medium } }
                        }
                    }
                }
            }

            Repeater {
                // Pelo número de discos, não pela lista: a lista nova a cada segundo
                // recriaria os cartões (e as barras não deslizariam).
                model: discos.length
                Disco { width: baixo.larguraDisco; height: baixo.height; info: discos[index] }
            }
        }
    }
}
