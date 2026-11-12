import QtQuick
import QtQuick.Window

// A barrinha do Modo Ajudante (12/11/2026), a aprovada pelo Léo em vídeo: fica
// embaixo, no meio da tela, um pouco acima da barra de tarefas. Entra como uma
// bolinha que estica (mola); VERDE te ouvindo, ROXO pensando, na COR DA PERSONA
// falando; as barrinhas mexem de verdade com o volume (o do microfone quando
// ele fala, o da voz dela quando ela fala), faíscas nas batidas fortes, borda
// que gira pensando. A legenda anda JUNTO com a fala: cada frase aparece no
// tempo do áudio dela (evento fala_trecho), nunca num ritmo fixo.
Window {
    id: barra
    width: 980; height: 230
    x: Screen.virtualX + (Screen.width - width) / 2
    y: Screen.virtualY + Screen.desktopAvailableHeight - height + 6
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
    title: "NOVA · Modo Ajudante"

    property string estado: "dormindo"       // o da NOVA
    property real nivelMic: 0
    property color corPersona: "#4da3ff"
    property string nomePersona: "JARVIS"
    signal fechar()

    // ---- o que a barra mostra agora ----
    property real abrindo: 0                 // 0 -> 1 (a mola de entrar)
    property real nivelFala: 0
    property string legenda: ""
    property string rotulo: ""
    property var frase: null                 // {texto, dur, t0}
    property real ultimaFala: 0
    property bool pausado: false

    readonly property string modo: estado === "pensando" ? "pensando"
        : (estado === "falando" ? "falando" : (estado === "escutando" || estado === "ouvindo") ? "ouvindo" : "parado")
    readonly property color corAlvo: pausado ? "#ffb454" : modo === "ouvindo" ? "#38d39f" : modo === "pensando" ? "#9b7bff" : corPersona

    onVisibleChanged: if (visible) { abrindo = 0; entrar.restart() }
    NumberAnimation { id: entrar; target: barra; property: "abrindo"; from: 0; to: 1; duration: 900 }

    Connections {
        target: typeof ponte !== "undefined" ? ponte : null
        ignoreUnknownSignals: true
        function onFalaTrecho(texto, dur) {
            if (texto) barra.frase = { texto: texto, dur: Math.max(0.3, dur), t0: Date.now() / 1000 }
            barra.ultimaFala = Date.now() / 1000
        }
        function onFalaNivel(v) { barra.nivelFala = v }
        function onPausaMudou(p) { barra.pausado = p }
        function onVoceDisse(texto, origem) { barra.frase = null; barra.legenda = texto; barra.rotulo = "VOCÊ" }
        function onEstadoMudou(e) {
            if (e === "pensando") { barra.frase = null; barra.legenda = "Pensando…"; barra.rotulo = barra.nomePersona }
            else if ((e === "escutando" || e === "ouvindo") && !barra.frase) { barra.legenda = "Ouvindo…"; barra.rotulo = "TE OUVINDO" }
        }
    }

    // A legenda da frase que está tocando: as letras aparecem no tempo do áudio dela.
    function legendaDaFala() {
        if (pausado) return "Pausado. Fala “continua” quando quiser."
        if (!frase) return legenda
        var k = Math.min(1, (Date.now() / 1000 - frase.t0) / (frase.dur * 0.94))
        var n = Math.max(1, Math.round(frase.texto.length * k))
        // não corta palavra no meio: anda até o fim da palavra que está sendo dita
        var fim = frase.texto.indexOf(" ", n); if (k >= 1 || fim < 0) fim = frase.texto.length
        return frase.texto.slice(0, Math.min(fim, n + 2))
    }

    Timer { interval: 16; running: barra.visible; repeat: true; onTriggered: tela.requestPaint() }

    Canvas {
        id: tela
        anchors.fill: parent
        renderTarget: Canvas.FramebufferObject
        property var alt: []
        property var parts: []
        property real rmsS: 0
        property real brilho: 0
        property var cor: [77, 163, 255]
        property int f: 0
        property real ultimoNivel: 0
        function rgba(c, a) { return "rgba(" + (c[0] | 0) + "," + (c[1] | 0) + "," + (c[2] | 0) + "," + a + ")" }
        function clara(c, k) { return [c[0] + (255 - c[0]) * k, c[1] + (255 - c[1]) * k, c[2] + (255 - c[2]) * k] }
        function mola(t) { t = Math.min(1, Math.max(0, t)); return 1 - Math.exp(-6 * t) * Math.cos(9 * t) }
        function pilula(g, x, y, w, h) {
            var r = h / 2; g.beginPath(); g.moveTo(x + r, y); g.lineTo(x + w - r, y); g.arc(x + w - r, y + r, r, -Math.PI / 2, Math.PI / 2)
            g.lineTo(x + r, y + h); g.arc(x + r, y + r, r, Math.PI / 2, 3 * Math.PI / 2); g.closePath()
        }
        onPaint: {
            var g = getContext("2d"); g.reset(); f++
            var N = 56; if (alt.length !== N) { alt = []; for (var i0 = 0; i0 < N; i0++) alt.push(4) }
            var alvo = [barra.corAlvo.r * 255, barra.corAlvo.g * 255, barra.corAlvo.b * 255]
            for (var c = 0; c < 3; c++) cor[c] += (alvo[c] - cor[c]) * 0.14
            var modo = barra.pausado ? "parado" : barra.modo
            var rms = modo === "falando" ? barra.nivelFala : modo === "ouvindo" ? barra.nivelMic : 0
            rmsS += (rms - rmsS) * (rms > rmsS ? 0.6 : 0.18)
            var cx = width / 2, base = height - 50
            var k = barra.abrindo
            var w = 72 + (820 - 72) * mola((k - 0.25) / 0.75), h = 72 * Math.min(1, mola(k * 2.2))
            w += rmsS * 26
            var x = cx - w / 2, y = base - h / 2
            brilho += ((modo === "pensando" ? 0.55 : 0.35 + rmsS * 0.9) - brilho) * 0.15
            // o brilho em volta: contornos translúcidos em camadas (a sombra borrada do
            // Canvas é calculada no processador e travava a janela)
            if (h > 8) for (var b = 7; b >= 1; b--) {
                var e = b * (4 + brilho * 4)
                g.strokeStyle = rgba(cor, Math.min(1, brilho) * 0.05); g.lineWidth = e
                pilula(g, x, y, w, h); g.stroke()
            }
            pilula(g, x, y, w, h); g.fillStyle = "rgba(9,12,18,0.93)"; g.fill()
            var gb = g.createConicalGradient(cx, base, f * (modo === "pensando" ? 0.16 : 0.035))
            gb.addColorStop(0, rgba(clara(cor, 0.5), 1)); gb.addColorStop(0.25, rgba(cor, 0.35)); gb.addColorStop(0.5, rgba(cor, 0.9))
            gb.addColorStop(0.75, rgba(cor, 0.3)); gb.addColorStop(1, rgba(clara(cor, 0.5), 1))
            g.lineWidth = 2; g.strokeStyle = gb; pilula(g, x, y, w, h); g.stroke()
            // as barrinhas: o volume de verdade espalhado do meio pras pontas
            var ix = x + 82, iw = Math.max(0, w - 82 - 70), passo = iw / N
            var vis = Math.max(0, (k - 0.35) / 0.65)
            for (var i = 0; i < N; i++) {
                var d = Math.abs(i - (N - 1) / 2) / ((N - 1) / 2), a
                if (modo === "falando" || modo === "ouvindo") {
                    var mexe = 0.55 + 0.45 * Math.sin(f * 0.37 + i * 1.7) * Math.cos(f * 0.21 + i * 0.6)
                    a = 4 + rmsS * 48 * (1 - d * 0.55) * mexe
                } else if (modo === "pensando") a = 6 + 14 * (0.5 + 0.5 * Math.sin(i * 0.42 - f * 0.38)) * (1 - d * 0.5)
                else a = 4 + 2 * Math.sin(f * 0.09 + i * 0.5)
                alt[i] += (a - alt[i]) * (a > alt[i] ? 0.55 : 0.2)
                var mostra = Math.max(0, Math.min(1, vis * 1.6 - d * 0.6)); if (mostra <= 0) continue
                var hb = alt[i] * mostra, bx = ix + i * passo + passo * 0.22, bw = passo * 0.56
                var gr = g.createLinearGradient(0, base - hb / 2, 0, base + hb / 2)
                gr.addColorStop(0, rgba(clara(cor, 0.55), 0.95)); gr.addColorStop(0.5, rgba(cor, 1)); gr.addColorStop(1, rgba(clara(cor, 0.55), 0.95))
                g.fillStyle = gr; g.globalAlpha = 0.55 + 0.45 * (1 - d)
                var hh = Math.max(bw, hb)
                g.beginPath(); g.roundedRect(bx, base - hh / 2, bw, hh, bw / 2, bw / 2); g.fill(); g.globalAlpha = 1
                if (rmsS > 0.35 && hb > 34 && Math.random() < 0.05)
                    parts.push({ x: bx + bw / 2, y: base - hb / 2, vy: -1.2 - Math.random() * 1.6, vx: (Math.random() - 0.5) * 0.8, v: 1 })
            }
            var vivas = []
            for (var p = 0; p < parts.length; p++) { var q = parts[p]; q.x += q.vx; q.y += q.vy; q.vy *= 0.985; q.v -= 0.022; if (q.v > 0) vivas.push(q) }
            parts = vivas
            g.save(); g.globalCompositeOperation = "lighter"
            for (p = 0; p < parts.length; p++) { g.fillStyle = rgba(clara(cor, 0.4), parts[p].v * 0.9); g.beginPath(); g.arc(parts[p].x, parts[p].y, 2.2 + parts[p].v * 1.5, 0, 7); g.fill() }
            g.restore()
            // a legenda
            var texto = barra.legendaDaFala()
            if (k > 0.8 && texto) {
                var rot = barra.pausado ? "PAUSADO" : barra.frase ? barra.nomePersona : barra.rotulo
                g.font = "500 22px 'Inter Variable'"
                var tw = Math.min(width - 80, Math.max(g.measureText(texto).width, 160)), lx = cx - tw / 2 - 22, ly = base - 104
                g.fillStyle = "rgba(9,12,18,0.88)"; g.beginPath(); g.roundedRect(lx, ly, tw + 44, 52, 16, 16); g.fill()
                g.strokeStyle = rgba(cor, 0.4); g.lineWidth = 1; g.stroke()
                g.fillStyle = rgba(cor, 1); g.font = "700 10px 'Inter Variable'"; g.textBaseline = "alphabetic"
                g.fillText(rot.split("").join(" "), lx + 22, ly - 8)
                g.fillStyle = "#e6ebf2"; g.font = "500 22px 'Inter Variable'"; g.textBaseline = "middle"
                g.fillText(texto, lx + 22, ly + 27)
                if (!barra.pausado && barra.frase && texto.length < barra.frase.texto.length) {
                    var cxx = lx + 22 + Math.min(tw, g.measureText(texto).width) + 4
                    g.fillStyle = rgba(cor, (f % 16) < 9 ? 1 : 0.2); g.fillRect(cxx, ly + 15, 3, 24)
                }
            }
            // os botões: pausar/continuar e fechar (sai do Modo Ajudante)
            if (w > 300 && h > 40) {
                g.globalAlpha = Math.min(1, (w - 300) / 300)
                g.fillStyle = barra.pausado ? rgba(cor, 0.25) : "#181e29"; g.beginPath(); g.arc(x + w - 80, base, 15, 0, 7); g.fill()
                g.strokeStyle = barra.pausado ? rgba(cor, 0.8) : "#2a3446"; g.lineWidth = 1; g.stroke()
                g.fillStyle = barra.pausado ? rgba(cor, 1) : "#b9c1cf"
                if (barra.pausado) { g.beginPath(); g.moveTo(x + w - 84, base - 6); g.lineTo(x + w - 74, base); g.lineTo(x + w - 84, base + 6); g.closePath(); g.fill() }
                else { g.fillRect(x + w - 85, base - 6, 3, 12); g.fillRect(x + w - 78, base - 6, 3, 12) }
                g.fillStyle = "#181e29"; g.beginPath(); g.arc(x + w - 40, base, 15, 0, 7); g.fill()
                g.strokeStyle = "#2a3446"; g.lineWidth = 1; g.stroke()
                g.fillStyle = "#b9c1cf"; g.font = "600 12px 'Inter Variable'"; g.textAlign = "center"; g.textBaseline = "middle"
                g.fillText("✕", x + w - 40, base + 1); g.textAlign = "start"; g.globalAlpha = 1
            }
            atomo.x = x + 36 - atomo.width / 2; atomo.y = base - atomo.height / 2
            atomo.scale = Math.min(1, mola(k * 2)) * (1 + rmsS * 0.12)
        }
    }

    // O átomo da NOVA na ponta esquerda (o mesmo da janela): gira mais rápido pensando.
    Esfera {
        id: atomo
        width: 62; height: 62
        cor: barra.corAlvo
        corDeFundo: "#090c12"
        velocidade: barra.modo === "pensando" ? 3.2 : barra.modo === "parado" ? 0.7 : 1.5
        nivel: barra.modo === "falando" ? barra.nivelFala : barra.nivelMic
        sendoVista: barra.visible
    }

    MouseArea {   // o ❚❚ pausa/continua, sem cancelar
        x: barra.width / 2 + 330 - 17; y: barra.height - 50 - 18
        width: 34; height: 36
        cursorShape: Qt.PointingHandCursor
        onClicked: if (typeof ponte !== "undefined") ponte.pausar()
    }
    MouseArea {   // o X fecha o Modo Ajudante
        x: barra.width / 2 + 370 - 17; y: barra.height - 50 - 18
        width: 34; height: 36
        cursorShape: Qt.PointingHandCursor
        onClicked: barra.fechar()
    }
}
