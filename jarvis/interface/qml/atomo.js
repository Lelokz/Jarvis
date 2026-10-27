.pragma library
// O átomo da NOVA desenhado em 2D (o definitivo, 27/10/2026): a mesma geometria
// do 3D do site (site/atomo3d.js), projetada em perspectiva num Canvas. O Qt
// daqui não tem 3D, então as contas de rotação e câmera são feitas à mão.
//
//   var estado = Atomo.novo()
//   Atomo.desenhar(ctx, largura, altura, t, [r, g, b], { estado: estado, fundo: [r, g, b], brilho: 1, traco: 1 })
//
// Ordem do desenho (o "atrás" do 3D): brilho em volta, o que fica atrás do
// núcleo, o núcleo (opaco, esconde o de trás), e o que fica na frente.
//
// Rápido de propósito (o Canvas do Qt roda isto a cada quadro): cada argola
// vira UMA matriz por quadro (o ponto u da faixa é sen·c0 − cos·c1 + w·c2),
// o que não muda (senos, vãos) é calculado uma vez em novo(), e cada linha
// de uma argola é um caminho só por lado (atrás/frente), já com os vãos.
// Abaixo de 64 px vale o desenho simples: sem marcações, pontos nem malha.

var RN = 0.62;        // raio do núcleo
var DIAMETRO = 4;     // o átomo inteiro, com a folga do brilho
var TG = Math.tan(16 * Math.PI / 180);   // metade do campo de visão (32°)
var N = 192;          // pedaços de cada argola (múltiplo de 48, 6 e 3)
var TAU = Math.PI * 2;
var BRANCO = [255, 255, 255];

// As argolas: 0 = a externa (faixa larga, marcações, 3 partes);
// 1 = a interna (fio duplo tracejado); 2 = a do meio (elipse com pontos).
var FORMATOS = [
    { raio: 1.62, largura: 0.12, elipse: [1, 1],       bola: 0.05,  bolinhas: 3, vel: 0.13, giro: 0.5,   sentido: 1 },
    { raio: 1.3,  largura: 0.05, elipse: [1, 1],       bola: 0.038, bolinhas: 2, vel: 0.17, giro: -0.42, sentido: -1 },
    { raio: 1.45, largura: 0.08, elipse: [1.16, 0.84], bola: 0.044, bolinhas: 3, vel: 0.15, giro: 0.6,   sentido: 1 }
];
// As linhas de luz de cada argola: [w através da faixa (0 a 1), força].
var LINHAS = [[[0.06, 1], [0.94, 1]], [[0.25, 1.1], [0.75, 1.1]], [[0.1, 1], [0.9, 1]]];
var ENCHE = [0.11, 0, 0.07];   // o fundo translúcido da faixa

function _fr(x) { return x - Math.floor(x); }
function _mostra(i, a) {   // o vão / o tracejado de cada argola
    var fase = i * 0.37, s;
    if (i === 0) { s = _fr(a * 3 + fase); return s > 0.005 && s < 0.955; }
    if (i === 1) { s = _fr(a * 48 + fase); return s < 0.62; }
    s = _fr(a * 6 + fase); return s > 0.004 && s < 0.979;
}

// A casca geodésica: icosaedro com cada face partida em 9 (o "detail 2" do
// three.js), os vértices empurrados para a esfera.
function _geodesica() {
    var p = (1 + Math.sqrt(5)) / 2;
    var v = [[-1, p, 0], [1, p, 0], [-1, -p, 0], [1, -p, 0], [0, -1, p], [0, 1, p], [0, -1, -p], [0, 1, -p],
             [p, 0, -1], [p, 0, 1], [-p, 0, -1], [-p, 0, 1]];
    var f = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6],
             [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]];
    var pontos = [], chave = {}, faces = [], D = 3, i, l, m;
    function ponto(x, y, z) {
        var n = Math.sqrt(x * x + y * y + z * z); x /= n; y /= n; z /= n;
        var k = Math.round(x * 1e4) + "," + Math.round(y * 1e4) + "," + Math.round(z * 1e4);
        if (chave[k] === undefined) { chave[k] = pontos.length / 3; pontos.push(x * RN, y * RN, z * RN); }
        return chave[k];
    }
    for (i = 0; i < f.length; i++) {
        var a = v[f[i][0]], b = v[f[i][1]], c = v[f[i][2]], grade = [];
        for (l = 0; l <= D; l++) {
            grade.push([]);
            for (m = 0; m <= D - l; m++) {
                var u = l / D, w = m / D;
                grade[l].push(ponto(a[0] + (b[0] - a[0]) * u + (c[0] - a[0]) * w,
                                    a[1] + (b[1] - a[1]) * u + (c[1] - a[1]) * w,
                                    a[2] + (b[2] - a[2]) * u + (c[2] - a[2]) * w));
            }
        }
        for (l = 0; l < D; l++)
            for (m = 0; m < D - l; m++) {
                faces.push(grade[l][m], grade[l + 1][m], grade[l][m + 1]);
                if (m < D - l - 1) faces.push(grade[l + 1][m], grade[l + 1][m + 1], grade[l][m + 1]);
            }
    }
    var arestas = [], vista = {};
    for (i = 0; i < faces.length; i += 3)
        for (var e = 0; e < 3; e++) {
            var x0 = faces[i + e], x1 = faces[i + (e + 1) % 3], k2 = Math.min(x0, x1) * 1000 + Math.max(x0, x1);
            if (!vista[k2]) { vista[k2] = true; arestas.push(x0, x1); }
        }
    return { pontos: pontos, faces: faces, arestas: arestas, n: pontos.length / 3 };
}

function novo() {
    var g = _geodesica(), sorteio = [], i, k;
    for (i = 0; i < g.faces.length / 3; i++) sorteio.push(Math.random());
    var sen = [], cos = [], mostra = [[], [], []];
    for (k = 0; k <= N; k++) { sen.push(Math.sin(k / N * TAU)); cos.push(Math.cos(k / N * TAU)); }
    for (i = 0; i < 3; i++) for (k = 0; k < N; k++) mostra[i].push(_mostra(i, (k + 0.5) / N));
    return { geo: g, sorteio: sorteio, sen: sen, cos: cos, mostra: mostra,
             px: new Array(g.n), py: new Array(g.n), pz: new Array(g.n) };
}

function _rgba(c, a) { return "rgba(" + (c[0] | 0) + "," + (c[1] | 0) + "," + (c[2] | 0) + "," + (a < 0 ? 0 : a > 1 ? 1 : a).toFixed(3) + ")"; }
function _mistura(c, d, k) { return [c[0] + (d[0] - c[0]) * k, c[1] + (d[1] - c[1]) * k, c[2] + (d[2] - c[2]) * k]; }

// Matriz 3×3 (linha a linha, 9 números) e produto.
function _mul(a, b) {
    return [a[0] * b[0] + a[1] * b[3] + a[2] * b[6], a[0] * b[1] + a[1] * b[4] + a[2] * b[7], a[0] * b[2] + a[1] * b[5] + a[2] * b[8],
            a[3] * b[0] + a[4] * b[3] + a[5] * b[6], a[3] * b[1] + a[4] * b[4] + a[5] * b[7], a[3] * b[2] + a[4] * b[5] + a[5] * b[8],
            a[6] * b[0] + a[7] * b[3] + a[8] * b[6], a[6] * b[1] + a[7] * b[4] + a[8] * b[7], a[6] * b[2] + a[7] * b[5] + a[8] * b[8]];
}
function _Rx(a) { var c = Math.cos(a), s = Math.sin(a); return [1, 0, 0, 0, c, -s, 0, s, c]; }
function _Ry(a) { var c = Math.cos(a), s = Math.sin(a); return [c, 0, s, 0, 1, 0, -s, 0, c]; }
function _Rz(a) { var c = Math.cos(a), s = Math.sin(a); return [c, -s, 0, s, c, 0, 0, 0, 1]; }

function desenhar(ctx, W, H, t, cor, op) {
    op = op || {};
    var est = op.estado, fundo = op.fundo || [10, 12, 16];
    var brilho = op.brilho === undefined ? 1 : op.brilho, traco = op.traco || 1;
    var lado = Math.min(W, H), cx = W / 2, cy = H / 2, simples = lado < 64;
    var camZ = (DIAMETRO / 2) / TG, esc = (lado / 2) / TG;
    // O balanço do átomo inteiro (o three.js gira em X·Y·Z).
    var Ra = _mul(_Rx(Math.sin(t * 0.17) * 0.12), _Ry(Math.sin(t * 0.22) * 0.35));
    var fino = Math.max(simples ? 1 : 0.8, lado * 0.0026) * (simples ? 1.4 : 1);
    var i, k, j, g, p, a;

    ctx.save();
    ctx.clearRect(0, 0, W, H);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.globalCompositeOperation = "lighter";

    // --- O brilho em volta do núcleo (o halo do 3D) ---------------------------
    var rh = 1.7 * esc / camZ;
    g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rh);
    g.addColorStop(0, _rgba(cor, 0.30 * brilho)); g.addColorStop(0.22, _rgba(cor, 0.12 * brilho)); g.addColorStop(1, _rgba(cor, 0));
    ctx.fillStyle = g; ctx.fillRect(cx - rh, cy - rh, rh * 2, rh * 2);

    // --- As argolas: uma matriz por argola, e o ponto (u, w) na tela ----------
    var A = [];
    for (i = 0; i < 3; i++) {
        var F = FORMATOS[i];
        var M = _mul(Ra, _mul(_Rz(i * Math.PI / 3), _Rx(1.2 + i * 0.7 + t * F.giro)));
        var R0 = F.raio * F.elipse[0], R1 = F.raio * F.elipse[1], L = F.largura * traco;
        A.push({ F: F, L: L,
                 // a e b: o círculo (já na elipse); c: através da faixa
                 a0: M[0] * R0, a1: M[3] * R0, a2: M[6] * R0, b0: M[1] * R1, b1: M[4] * R1, b2: M[7] * R1,
                 c0: M[2] * L, c1: M[5] * L, c2: M[8] * L });
    }
    // Ponto da argola: sen/cos de u e w (0 a 1). Devolve [x, y, z, escala].
    function ponto(Ai, s, c, w) {
        var ww = w - 0.5;
        var X = s * Ai.a0 - c * Ai.b0 + ww * Ai.c0, Y = s * Ai.a1 - c * Ai.b1 + ww * Ai.c1, Z = s * Ai.a2 - c * Ai.b2 + ww * Ai.c2;
        var f = esc / (camZ - Z);
        return [cx + X * f, cy - Y * f, Z, f];
    }
    // Uma volta inteira de pontos (para uma linha da faixa).
    function volta(Ai, w) {
        var r = new Array(N + 1);
        for (var q = 0; q <= N; q++) r[q] = ponto(Ai, est.sen[q], est.cos[q], w);
        return r;
    }

    function argola(i, frente) {
        var Ai = A[i], vis = est.mostra[i], linhas = simples ? [[0.5, 1.6]] : LINHAS[i], pts, aqui, ligado, b;
        for (j = 0; j < linhas.length; j++) {
            pts = Ai["w" + j] || (Ai["w" + j] = volta(Ai, linhas[j][0]));
            ctx.beginPath(); ligado = false;
            for (k = 0; k < N; k++) {
                aqui = (simples || vis[k]) && ((pts[k][2] + pts[k + 1][2]) >= 0) === frente;
                if (aqui) { if (!ligado) ctx.moveTo(pts[k][0], pts[k][1]); ctx.lineTo(pts[k + 1][0], pts[k + 1][1]); }
                ligado = aqui;
            }
            ctx.strokeStyle = _rgba(cor, 0.6 * linhas[j][1]); ctx.lineWidth = fino * (i === 0 ? 1.3 : 1.1); ctx.stroke();
        }
        if (simples) return;
        // O fundo translúcido da faixa (entre as bordas).
        if (ENCHE[i] > 0) {
            var e0 = Ai.e0 || (Ai.e0 = volta(Ai, 0)), e1 = Ai.e1 || (Ai.e1 = volta(Ai, 1));
            ctx.beginPath();
            for (k = 0; k < N; k++) {
                if (!vis[k] || ((e0[k][2] + e1[k + 1][2]) >= 0) !== frente) continue;
                ctx.moveTo(e0[k][0], e0[k][1]); ctx.lineTo(e0[k + 1][0], e0[k + 1][1]);
                ctx.lineTo(e1[k + 1][0], e1[k + 1][1]); ctx.lineTo(e1[k][0], e1[k][1]); ctx.closePath();
            }
            ctx.fillStyle = _rgba(cor, ENCHE[i]); ctx.fill();
        }
        // As marcações da externa (atravessando o meio da faixa).
        if (i === 0) {
            ctx.beginPath();
            for (k = 0; k < 120; k++) {
                a = (k + 0.04) / 120;
                if (!_mostra(0, a)) continue;
                var s = Math.sin(a * TAU), c = Math.cos(a * TAU);
                p = ponto(Ai, s, c, 0.3);
                if ((p[2] >= 0) !== frente) continue;
                b = ponto(Ai, s, c, 0.7);
                ctx.moveTo(p[0], p[1]); ctx.lineTo(b[0], b[1]);
            }
            ctx.strokeStyle = _rgba(cor, 0.3); ctx.lineWidth = fino * 0.8; ctx.stroke();
        }
        // Os pontos de luz da elipse (18): dois círculos, um largo e fraco e um forte.
        if (i === 2) {
            var claro = _rgba(_mistura(cor, BRANCO, 0.4), 0.95), halo = _rgba(cor, 0.25);
            for (k = 0; k < 18; k++) {
                a = _fr((k + 0.5 - 0.74) / 18);
                if (!_mostra(2, a)) continue;
                p = ponto(Ai, Math.sin(a * TAU), Math.cos(a * TAU), 0.5);
                if ((p[2] >= 0) !== frente) continue;
                var r = Math.max(0.8, Ai.L * 0.24 * p[3]);
                ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(p[0], p[1], r * 2.4, 0, TAU); ctx.fill();
                ctx.fillStyle = claro; ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, TAU); ctx.fill();
            }
        }
    }

    // As bolinhas e os rastros (o rastro fica ATRÁS dela, no sentido de onde
    // veio): três trechos por rastro, cada um mais grosso e mais forte perto dela.
    var TRECHOS = [[0.0, 0.45, 0.25], [0.45, 0.75, 0.6], [0.75, 1.0, 1.0]];
    function bolinhas(i, frente) {
        var Ai = A[i], F = Ai.F, bola = F.bola * Math.sqrt(simples ? 2.5 : traco), comp = 0.55 / F.bolinhas;
        for (var b = 0; b < F.bolinhas; b++) {
            var u = i * 0.3 + t * F.vel * F.sentido + b / F.bolinhas;
            for (var q = 0; q < TRECHOS.length; q++) {
                var T = TRECHOS[q], kk = T[2], um = u - F.sentido * comp * (1 - (T[0] + T[1]) / 2);
                var meio = ponto(Ai, Math.sin(um * TAU), Math.cos(um * TAU), 0.5);
                if ((meio[2] >= 0) !== frente) continue;
                ctx.beginPath();
                for (j = 0; j <= 5; j++) {
                    var uu = u - F.sentido * comp * (1 - (T[0] + (T[1] - T[0]) * j / 5));
                    p = ponto(Ai, Math.sin(uu * TAU), Math.cos(uu * TAU), 0.5);
                    if (j === 0) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]);
                }
                var larg = Math.max(0.8, bola * 0.9 * (0.2 + 0.8 * kk) * meio[3]);
                ctx.strokeStyle = _rgba(cor, kk * kk * 0.22 * brilho); ctx.lineWidth = larg * 4.5; ctx.stroke();
                ctx.strokeStyle = _rgba(_mistura(cor, BRANCO, kk * 0.6), Math.min(1, kk * kk * 1.7)); ctx.lineWidth = larg * 1.3; ctx.stroke();
            }
            var c = ponto(Ai, Math.sin(u * TAU), Math.cos(u * TAU), 0.5);
            if ((c[2] >= 0) !== frente) continue;
            var rb = Math.max(1.2, bola * c[3]);
            g = ctx.createRadialGradient(c[0], c[1], 0, c[0], c[1], rb * 6);
            g.addColorStop(0, _rgba(_mistura(cor, BRANCO, 0.7), 0.8 * brilho)); g.addColorStop(0.3, _rgba(cor, 0.3 * brilho)); g.addColorStop(1, _rgba(cor, 0));
            ctx.fillStyle = g; ctx.fillRect(c[0] - rb * 6, c[1] - rb * 6, rb * 12, rb * 12);
            ctx.beginPath(); ctx.arc(c[0], c[1], rb, 0, TAU);
            ctx.fillStyle = _rgba(_mistura(cor, BRANCO, 0.75), 1); ctx.fill();
        }
    }

    for (i = 0; i < 3; i++) { argola(i, false); bolinhas(i, false); }

    // --- O núcleo: disco opaco (esconde o que está atrás) com a borda acesa ----
    ctx.globalCompositeOperation = "source-over";
    var rn = RN * esc / camZ;
    g = ctx.createRadialGradient(cx - rn * 0.15, cy - rn * 0.2, 0, cx, cy, rn);
    g.addColorStop(0, _rgba(_mistura(fundo, _mistura(cor, BRANCO, 0.45), 0.42), 1));
    g.addColorStop(0.55, _rgba(_mistura(fundo, cor, 0.24), 1));
    g.addColorStop(0.86, _rgba(_mistura(fundo, cor, 0.42), 1));
    g.addColorStop(1, _rgba(_mistura(fundo, cor, 0.85), 1));
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, rn, 0, TAU); ctx.fill();
    ctx.globalCompositeOperation = "lighter";
    // O brilho da borda, vazando para fora (o bloom do 3D).
    g = ctx.createRadialGradient(cx, cy, rn * 0.82, cx, cy, rn * 1.45);
    g.addColorStop(0, _rgba(cor, 0)); g.addColorStop(0.3, _rgba(cor, 0.32 * brilho)); g.addColorStop(1, _rgba(cor, 0));
    ctx.fillStyle = g; ctx.fillRect(cx - rn * 1.5, cy - rn * 1.5, rn * 3, rn * 3);

    if (!simples) {
        // O plasma: três manchas de luz que andam devagar por dentro.
        for (i = 0; i < 3; i++) {
            var ang = t * (0.35 + i * 0.13) + i * 2.1, mx = cx + Math.cos(ang) * rn * 0.42, my = cy + Math.sin(ang * 1.3) * rn * 0.38;
            g = ctx.createRadialGradient(mx, my, 0, mx, my, rn * 0.55);
            g.addColorStop(0, _rgba(cor, 0.16)); g.addColorStop(1, _rgba(cor, 0));
            ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, rn, 0, TAU); ctx.fill();
        }
        // A casca geodésica (só a metade da frente: a de trás fica escondida).
        var Mn = _mul(Ra, _mul(_Rx(t * 0.05), _Ry(t * 0.12))), geo = est.geo, pt = geo.pontos;
        var X = est.px, Y = est.py, Z = est.pz;
        for (i = 0; i < geo.n; i++) {
            var x = pt[i * 3], y = pt[i * 3 + 1], z = pt[i * 3 + 2];
            var zz = Mn[6] * x + Mn[7] * y + Mn[8] * z, f = esc / (camZ - zz);
            X[i] = cx + (Mn[0] * x + Mn[1] * y + Mn[2] * z) * f;
            Y[i] = cy - (Mn[3] * x + Mn[4] * y + Mn[5] * z) * f;
            Z[i] = zz;
        }
        var fc = geo.faces;
        for (i = 0; i < fc.length; i += 3) {   // os painéis que acendem devagar
            var on = Math.sin(t * 0.6 + est.sorteio[i / 3] * 40) * 0.5 + 0.5;
            if (on < 0.83) continue;
            if (Z[fc[i]] + Z[fc[i + 1]] + Z[fc[i + 2]] < 0) continue;
            on = (on - 0.82) / 0.18;
            ctx.beginPath(); ctx.moveTo(X[fc[i]], Y[fc[i]]); ctx.lineTo(X[fc[i + 1]], Y[fc[i + 1]]); ctx.lineTo(X[fc[i + 2]], Y[fc[i + 2]]); ctx.closePath();
            ctx.fillStyle = _rgba(cor, on * on * (3 - 2 * on) * 0.35); ctx.fill();
        }
        var ar = geo.arestas;
        ctx.beginPath();
        for (i = 0; i < ar.length; i += 2) {
            if (Z[ar[i]] + Z[ar[i + 1]] < -0.05) continue;
            ctx.moveTo(X[ar[i]], Y[ar[i]]); ctx.lineTo(X[ar[i + 1]], Y[ar[i + 1]]);
        }
        ctx.strokeStyle = _rgba(_mistura(cor, BRANCO, 0.15), 0.55); ctx.lineWidth = Math.max(0.6, lado * 0.0018); ctx.stroke();
        ctx.fillStyle = _rgba(_mistura(cor, BRANCO, 0.4), 0.9);
        var rp = Math.max(0.7, lado * 0.0025);
        for (i = 0; i < geo.n; i++) if (Z[i] > 0) ctx.fillRect(X[i] - rp, Y[i] - rp, rp * 2, rp * 2);
    }

    for (i = 0; i < 3; i++) { argola(i, true); bolinhas(i, true); }
    ctx.restore();
}
