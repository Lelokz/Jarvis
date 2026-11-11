import QtQuick
import QtQuick.Controls.Basic

// O lado direito do modo code (etapa 3 do tchan, 11/11/2026; antes era o
// CodePainel da beta 0.18.0). Os botões do topo abrem e fecham cada painel, e
// os abertos se empilham, como no desenho aprovado:
//
//   Mudanças  os arquivos mexidos desde o último commit, o antes/depois de
//             cada um (com o número da linha), Desfazer arquivo, Commit, Push;
//   Plano     a lista de tarefas dele, ticando sozinha;
//   Terminal  os comandos que ele roda e o que respondem, ao vivo;
//   Contexto  projeto, ramo, onde mexeu e quanto da conversa já foi usado.
Rectangle {
    id: raiz
    property var tema
    property string caminho: ""
    property var mudancas: null        // o evento "mudancas"
    property var plano: []             // [{texto, estado}]
    property var contexto: null        // {pct, usados, max}
    property var terminal              // ListModel {id, cmd, saida, erro, pronto}
    property bool ocupado: false
    property bool verMudancas: true
    property bool verTerminal: false
    property bool verPlano: false
    property bool verContexto: false
    property string escolhido: ""      // o arquivo do diff
    signal fechar(string painel)
    signal commit()
    signal push()
    signal desfazerArquivo(string arquivo)

    color: tema.lateral
    readonly property var arquivos: mudancas && mudancas.arquivos ? mudancas.arquivos : []
    readonly property int mais: arquivos.reduce(function (a, x) { return a + x.mais }, 0)
    readonly property int menos: arquivos.reduce(function (a, x) { return a + x.menos }, 0)
    readonly property int feitos: plano.filter(function (p) { return p.estado === "completed" }).length
    onCaminhoChanged: escolhido = ""
    onArquivosChanged: {
        var nomes = arquivos.map(function (a) { return a.arquivo });
        if (nomes.indexOf(escolhido) < 0) escolhido = nomes.length ? nomes[0] : "";
    }
    function escolher(arquivo) { if (arquivo) escolhido = arquivo }

    // -- o diff, linha por linha (número, sinal, cor de fundo) ----------------
    function trechoDe(diff, arquivo) {
        if (!arquivo) return diff;
        var partes = diff.split(/\n(?=diff --git )/);
        for (var i = 0; i < partes.length; i++)
            if (partes[i].indexOf(" b/" + arquivo) >= 0) return partes[i];
        return "";
    }
    function linhasDoDiff(texto) {
        var saida = [], velha = 0, nova = 0, linhas = texto.split("\n");
        for (var i = 0; i < linhas.length && saida.length < 3000; i++) {
            var l = linhas[i];
            if (l.indexOf("diff --git") === 0 || l.indexOf("index ") === 0 || l.indexOf("+++") === 0
                    || l.indexOf("---") === 0 || l === "novo arquivo" || l.indexOf("new file") === 0
                    || l.indexOf("deleted file") === 0 || l.indexOf("similarity") === 0) {
                if (l.indexOf("+++ b/") === 0 && l.indexOf("novo arquivo") < 0) { velha = 0; nova = 1; }
                continue;
            }
            if (l.indexOf("@@") === 0) {
                var m = /@@ -(\d+)(?:,\d+)? \+(\d+)/.exec(l);
                if (m) { velha = parseInt(m[1]); nova = parseInt(m[2]); }
                var resto = l.replace(/^@@[^@]*@@\s?/, "");
                saida.push({ t: "@", n: "", x: resto ? "@@ " + resto + " @@" : "@@" });
                continue;
            }
            if (l === "" && i === linhas.length - 1) continue;
            var c = l.charAt(0);
            if (c === "+") { saida.push({ t: "+", n: nova || "", x: "+ " + l.slice(1) }); if (nova) nova++; }
            else if (c === "-") { saida.push({ t: "-", n: velha || "", x: "- " + l.slice(1) }); if (velha) velha++; }
            else if (c === "(" ) saida.push({ t: "@", n: "", x: l });
            else { saida.push({ t: " ", n: nova || "", x: "  " + l.slice(1) }); if (velha) velha++; if (nova) nova++; }
        }
        return saida;
    }

    Rectangle { width: 1; height: parent.height; color: tema.traco }

    component BotaoPainel: Rectangle {
        id: bp
        property string rotulo
        property string icone: ""
        property bool principal: false
        property bool ativo: true
        signal clicado()
        height: 34; radius: 8; width: linhaBp.implicitWidth + 26
        opacity: ativo ? 1 : 0.4
        color: principal ? (mbp.containsMouse && ativo ? Qt.lighter(raiz.tema.persona, 1.12) : raiz.tema.persona)
                         : (mbp.containsMouse && ativo ? raiz.tema.realce : raiz.tema.superficie2)
        border.width: principal ? 0 : 1
        border.color: raiz.tema.traco
        Row {
            id: linhaBp
            anchors.centerIn: parent; spacing: 6
            Icone { visible: bp.icone !== ""; anchors.verticalCenter: parent.verticalCenter; caminho: bp.icone
                    cor: raiz.tema.texto; tamanho: 13; espessura: 1.8 }
            Text { anchors.verticalCenter: parent.verticalCenter; text: bp.rotulo
                   color: bp.principal ? "#0a0c10" : raiz.tema.texto
                   font.family: raiz.tema.familia; font.pixelSize: 13; font.weight: Font.DemiBold }
        }
        MouseArea { id: mbp; anchors.fill: parent; hoverEnabled: true; enabled: bp.ativo
                    cursorShape: Qt.PointingHandCursor; onClicked: bp.clicado() }
    }

    component Cabeca: Item {
        id: cb
        property string titulo
        property string detalhe
        property string painel
        width: parent ? parent.width : 300
        height: 46
        Row {
            x: 18; anchors.verticalCenter: parent.verticalCenter; spacing: 10
            Text { anchors.verticalCenter: parent.verticalCenter; text: cb.titulo
                   color: raiz.tema.texto; font.family: raiz.tema.familia; font.pixelSize: 14; font.weight: Font.DemiBold }
            Text { anchors.verticalCenter: parent.verticalCenter; text: cb.detalhe
                   color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 12 }
        }
        Rectangle {
            anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
            width: 26; height: 26; radius: 6
            color: mcb.containsMouse ? raiz.tema.superficie2 : "transparent"
            Icone { anchors.centerIn: parent; caminho: raiz.tema.icones.fechar; tamanho: 13; espessura: 1.7
                    cor: mcb.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco }
            MouseArea { id: mcb; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: raiz.fechar(cb.painel) }
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: raiz.tema.traco }
    }

    // Plano e Contexto têm a altura do que mostram; Mudanças e Terminal
    // dividem o resto.
    readonly property int flexiveis: (verMudancas ? 1 : 0) + (verTerminal ? 1 : 0)
    readonly property real sobra: height - (verPlano ? secPlano.height : 0) - (verContexto ? secContexto.height : 0)
    readonly property real alturaFlex: flexiveis ? Math.max(160, sobra / flexiveis) : 0

    Column {
        width: parent.width - 1
        x: 1

        // == Mudanças ===========================================================
        Item {
            id: secMudancas
            visible: raiz.verMudancas
            width: parent.width
            height: visible ? raiz.alturaFlex : 0

            Cabeca {
                id: cabMud
                painel: "mudancas"; titulo: "Mudanças"
                detalhe: !raiz.mudancas ? "lendo…" : !raiz.mudancas.git ? "sem git"
                       : raiz.arquivos.length === 0 ? "nada mudado"
                       : (raiz.arquivos.length === 1 ? "1 arquivo" : raiz.arquivos.length + " arquivos")
                         + " · +" + raiz.mais + " −" + raiz.menos
            }
            ListView {
                id: lista
                anchors { top: cabMud.bottom; topMargin: 8; left: parent.left; right: parent.right; leftMargin: 10; rightMargin: 10 }
                height: Math.min(contentHeight, parent.height * 0.3)
                clip: true; spacing: 2; boundsBehavior: Flickable.StopAtBounds
                model: raiz.arquivos
                delegate: Rectangle {
                    required property var modelData
                    width: lista.width; height: 29; radius: 6
                    readonly property bool sel: raiz.escolhido === modelData.arquivo
                    color: sel ? raiz.tema.realce : maArq.containsMouse ? raiz.tema.superficie2 : "transparent"
                    Rectangle { x: 10; anchors.verticalCenter: parent.verticalCenter; width: 7; height: 7; radius: 4
                                color: modelData.estado === "novo" ? "#4ade80" : modelData.estado === "apagado" ? "#f87171" : "#fbbf24" }
                    Text { x: 27; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 27 - contas.width - 14
                           elide: Text.ElideMiddle; text: modelData.arquivo; color: parent.sel ? raiz.tema.texto : raiz.tema.textoMedio
                           font.family: raiz.tema.mono; font.pixelSize: 13 }
                    Row {
                        id: contas
                        anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                        spacing: 6
                        Text { text: "+" + modelData.mais; color: "#4ade80"; font.family: raiz.tema.mono; font.pixelSize: 12 }
                        Text { visible: modelData.estado !== "novo"; text: "−" + modelData.menos; color: "#f87171"
                               font.family: raiz.tema.mono; font.pixelSize: 12 }
                    }
                    MouseArea { id: maArq; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: raiz.escolhido = modelData.arquivo }
                }
            }
            Rectangle {
                id: caixaDiff
                anchors { top: lista.bottom; topMargin: 10; left: parent.left; right: parent.right; bottom: rodape.top
                          leftMargin: 12; rightMargin: 12; bottomMargin: 10 }
                radius: 10; color: raiz.tema.codigo; border.width: 1; border.color: raiz.tema.traco
                clip: true
                Text {
                    anchors.centerIn: parent; width: parent.width - 40; horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    visible: !raiz.mudancas || !raiz.mudancas.git || raiz.arquivos.length === 0
                    text: !raiz.mudancas ? "Lendo o projeto…"
                        : !raiz.mudancas.git ? "Esse projeto não tem git: as mudanças aparecem só no cartão de cada resposta."
                        : "Quando ele mexer em algo, aparece aqui."
                    color: raiz.tema.muitoFraco; font.family: raiz.tema.familia; font.pixelSize: 13
                }
                ListView {
                    id: linhasDiff
                    anchors { fill: parent; topMargin: 10; bottomMargin: 10 }
                    clip: true; boundsBehavior: Flickable.StopAtBounds
                    model: raiz.mudancas && raiz.mudancas.diff ? raiz.linhasDoDiff(raiz.trechoDe(raiz.mudancas.diff, raiz.escolhido)) : []
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: Rectangle {
                        required property var modelData
                        width: linhasDiff.width
                        height: Math.max(21, txtLinha.implicitHeight + 2)
                        color: modelData.t === "+" ? (raiz.tema.claro ? "#e6f6ea" : "#11251a")
                             : modelData.t === "-" ? (raiz.tema.claro ? "#fbe9ea" : "#2a1418") : "transparent"
                        Text { x: 8; width: 32; horizontalAlignment: Text.AlignRight; y: 2
                               text: modelData.n; color: raiz.tema.muitoFraco; font.family: raiz.tema.mono; font.pixelSize: 12 }
                        Text {
                            id: txtLinha
                            x: 50; y: 1; width: parent.width - 58
                            wrapMode: Text.WrapAnywhere
                            text: modelData.x
                            textFormat: Text.PlainText
                            color: modelData.t === "+" ? "#4ade80" : modelData.t === "-" ? "#f87171"
                                 : modelData.t === "@" ? "#a78bfa" : raiz.tema.textoMedio
                            font.family: raiz.tema.mono; font.pixelSize: 12
                        }
                    }
                }
            }
            Rectangle { anchors.bottom: rodape.top; anchors.bottomMargin: 0; width: parent.width; height: 1; color: raiz.tema.traco }
            Item {
                id: rodape
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: 60
                property bool confirmar: false
                Timer { id: esfriar; interval: 4000; onTriggered: rodape.confirmar = false }
                BotaoPainel {
                    anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter }
                    icone: rodape.confirmar ? "" : raiz.tema.icones.desfazer
                    rotulo: rodape.confirmar ? "Clica de novo pra desfazer" : "Desfazer arquivo"
                    ativo: !raiz.ocupado && raiz.escolhido !== "" && !!raiz.mudancas && raiz.mudancas.git
                    color: rodape.confirmar ? Qt.rgba(0.9, 0.28, 0.3, 0.22) : (mbpD.containsMouse ? raiz.tema.realce : raiz.tema.superficie2)
                    MouseArea { id: mbpD; anchors.fill: parent; hoverEnabled: true; enabled: parent.ativo
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (!rodape.confirmar) { rodape.confirmar = true; esfriar.restart(); return; }
                                    rodape.confirmar = false;
                                    raiz.desfazerArquivo(raiz.escolhido);
                                } }
                }
                Row {
                    anchors { right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
                    spacing: 8
                    BotaoPainel { rotulo: "Commit"; principal: true; ativo: !raiz.ocupado && raiz.arquivos.length > 0; onClicado: raiz.commit() }
                    BotaoPainel { rotulo: "Push"; ativo: !raiz.ocupado && !!raiz.mudancas && raiz.mudancas.remoto && raiz.mudancas.a_frente > 0
                                  onClicado: raiz.push() }
                }
            }
        }
        Rectangle { visible: raiz.verMudancas && (raiz.verPlano || raiz.verTerminal || raiz.verContexto); width: parent.width; height: 1; color: raiz.tema.tracoForte }

        // == Plano ==============================================================
        Item {
            id: secPlano
            visible: raiz.verPlano
            width: parent.width
            height: visible ? cabPlano.height + Math.min(colPlano.height + 18, raiz.height * 0.4) : 0
            Cabeca {
                id: cabPlano
                painel: "plano"; titulo: "Plano"
                detalhe: raiz.plano.length ? raiz.feitos + " de " + raiz.plano.length + " feitos" : ""
            }
            Flickable {
                anchors { top: cabPlano.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
                contentHeight: colPlano.height + 18; clip: true; boundsBehavior: Flickable.StopAtBounds
                Column {
                    id: colPlano
                    x: 18; y: 12; width: parent.width - 36; spacing: 4
                    Text {
                        visible: raiz.plano.length === 0
                        width: parent.width; wrapMode: Text.WordWrap; bottomPadding: 6
                        text: "Quando ele fizer um trabalho de vários passos, o plano aparece aqui e vai ticando sozinho."
                        color: raiz.tema.muitoFraco; font.family: raiz.tema.familia; font.pixelSize: 13
                    }
                    Repeater {
                        model: raiz.plano
                        Item {
                            required property var modelData
                            readonly property bool feito: modelData.estado === "completed"
                            readonly property bool agora: modelData.estado === "in_progress"
                            width: colPlano.width; height: Math.max(32, txtPlano.implicitHeight + 12)
                            Rectangle {
                                x: 0; y: 7; width: 18; height: 18; radius: 5
                                color: parent.feito ? "#22c55e" : "transparent"
                                border.width: parent.feito ? 0 : 1.5
                                border.color: parent.agora ? raiz.tema.persona : raiz.tema.tracoForte
                                Icone { anchors.centerIn: parent; visible: parent.parent.feito; caminho: raiz.tema.icones.certo
                                        cor: "#0a0c10"; tamanho: 13; espessura: 2.4 }
                            }
                            Text {
                                id: txtPlano
                                x: 30; y: 6; width: parent.width - 30
                                wrapMode: Text.WordWrap
                                text: modelData.texto
                                font.strikeout: parent.feito
                                color: parent.feito ? raiz.tema.textoFraco : raiz.tema.texto
                                font.family: raiz.tema.familia; font.pixelSize: 14
                            }
                        }
                    }
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: raiz.tema.tracoForte
                        visible: raiz.verTerminal || raiz.verContexto }
        }

        // == Terminal ===========================================================
        Item {
            id: secTerminal
            visible: raiz.verTerminal
            width: parent.width
            height: visible ? raiz.alturaFlex : 0
            Cabeca {
                id: cabTerm
                painel: "terminal"; titulo: "Terminal"
                detalhe: raiz.ocupado ? "ao vivo" : (raiz.terminal && raiz.terminal.count ? "" : "vazio")
            }
            Rectangle {
                anchors { top: cabTerm.bottom; topMargin: 6; left: parent.left; right: parent.right; bottom: parent.bottom
                          leftMargin: 12; rightMargin: 12; bottomMargin: 12 }
                radius: 10; color: raiz.tema.claro ? "#11151c" : "#07090d"; border.width: 1; border.color: raiz.tema.traco
                ListView {
                    id: listaTerm
                    anchors { fill: parent; margins: 14 }
                    clip: true; boundsBehavior: Flickable.StopAtBounds
                    model: raiz.terminal
                    spacing: 4
                    onCountChanged: Qt.callLater(positionViewAtEnd)
                    onContentHeightChanged: if (!moving) Qt.callLater(positionViewAtEnd)
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    header: Text {
                        width: listaTerm.width; bottomPadding: 4
                        text: raiz.caminho.replace(/^\/home\/[^\/]+/, "~")
                        color: "#5f687c"; font.family: raiz.tema.mono; font.pixelSize: 12; elide: Text.ElideMiddle
                    }
                    footer: Text {
                        topPadding: 4
                        text: "$ <span style=\"background:#e6ebf2\">&nbsp;</span>"
                        textFormat: Text.RichText
                        color: "#e6ebf2"; font.family: raiz.tema.mono; font.pixelSize: 12
                        SequentialAnimation on opacity {
                            loops: Animation.Infinite; running: raiz.verTerminal
                            NumberAnimation { to: 0.2; duration: 600 } NumberAnimation { to: 1; duration: 600 }
                        }
                    }
                    delegate: Text {
                        required property string cmd
                        required property string saida
                        required property bool erro
                        required property bool pronto
                        width: listaTerm.width
                        wrapMode: Text.WrapAnywhere
                        textFormat: Text.RichText
                        font.family: raiz.tema.mono; font.pixelSize: 12
                        text: raiz.htmlDoTerminal(cmd, saida, erro, pronto)
                    }
                    Text {
                        anchors.centerIn: parent; visible: !raiz.terminal || raiz.terminal.count === 0
                        text: "Os comandos que ele roda aparecem aqui."
                        color: "#4d5568"; font.family: raiz.tema.familia; font.pixelSize: 13
                    }
                }
            }
        }

        // == Contexto ===========================================================
        Rectangle {
            id: secContexto
            visible: raiz.verContexto
            width: parent.width
            height: visible ? gradeCtx.height + 36 : 0
            color: "transparent"
            Rectangle { width: parent.width; height: 1; color: raiz.tema.tracoForte; visible: raiz.verMudancas || raiz.verPlano || raiz.verTerminal }
            Rectangle {
                anchors { right: parent.right; rightMargin: 10; top: parent.top; topMargin: 10 }
                width: 26; height: 26; radius: 6
                color: mctx.containsMouse ? raiz.tema.superficie2 : "transparent"
                Icone { anchors.centerIn: parent; caminho: raiz.tema.icones.fechar; tamanho: 13; espessura: 1.7
                        cor: mctx.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco }
                MouseArea { id: mctx; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: raiz.fechar("contexto") }
            }
            Grid {
                id: gradeCtx
                x: 18; y: 18; columns: 2; columnSpacing: 20; rowSpacing: 10
                readonly property real col2: raiz.width - 18 - 100 - 20 - 46
                component Rotulo: Text { width: 100; color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 13 }
                component Valor: Text { width: gradeCtx.col2; elide: Text.ElideMiddle; color: raiz.tema.texto
                                        font.family: raiz.tema.familia; font.pixelSize: 13 }
                Rotulo { text: "Projeto" }
                Valor { text: raiz.caminho.replace(/^\/home\/[^\/]+/, "~") }
                Rotulo { text: "Ramo" }
                Valor {
                    text: !raiz.mudancas || !raiz.mudancas.git ? "sem git"
                        : (raiz.mudancas.ramo || "?") + " · " + (raiz.mudancas.a_frente > 0
                            ? raiz.mudancas.a_frente + " commit" + (raiz.mudancas.a_frente === 1 ? "" : "s") + " esperando push"
                            : "sem commit esperando")
                }
                Rotulo { text: "Mexeu em" }
                Valor {
                    elide: Text.ElideRight
                    text: raiz.arquivos.length ? raiz.arquivos.map(function (a) { return a.arquivo.split("/").pop() }).join(", ") : "nada ainda"
                }
                Rotulo { text: "Conversa" }
                Column {
                    width: gradeCtx.col2; spacing: 7
                    Text { text: raiz.contexto ? raiz.contexto.pct + "% do espaço usado" : "aparece depois da 1ª resposta"
                           color: raiz.contexto ? raiz.tema.texto : raiz.tema.textoFraco
                           font.family: raiz.tema.familia; font.pixelSize: 13 }
                    Rectangle {
                        width: parent.width; height: 5; radius: 3; color: raiz.tema.superficie2
                        Rectangle {
                            height: parent.height; radius: 3
                            width: parent.width * Math.min(1, (raiz.contexto ? raiz.contexto.pct : 0) / 100)
                            color: !raiz.contexto ? "transparent" : raiz.contexto.pct >= 85 ? "#f87171"
                                 : raiz.contexto.pct >= 65 ? "#fbbf24" : raiz.tema.persona
                            Behavior on width { NumberAnimation { duration: raiz.tema.normal } }
                        }
                    }
                }
            }
        }
    }

    // A saída de um comando, pintada: o que passou em verde, o que falhou em
    // vermelho, o resto apagado. As últimas 40 linhas.
    function esc(t) { return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/  /g, " &nbsp;") }
    function htmlDoTerminal(cmd, saida, erro, pronto) {
        var h = "<span style=\"color:#e6ebf2\">$ " + esc(cmd.split("\n")[0]) + (cmd.indexOf("\n") >= 0 ? " …" : "") + "</span>";
        if (!pronto) return h + "<br><span style=\"color:#5f687c\">rodando…</span>";
        var linhas = saida.replace(/\s+$/, "").split("\n");
        if (linhas.length === 1 && linhas[0] === "") return h;
        var corte = linhas.length > 40 ? linhas.length - 40 : 0;
        if (corte) h += "<br><span style=\"color:#4d5568\">… " + corte + " linhas antes</span>";
        for (var i = corte; i < linhas.length; i++) {
            var l = linhas[i], cor = "#9aa3b5";
            if (/(^|\s)(✓|✔|PASS\b|ok\b|passed|passou|sucesso)/i.test(l) && !/\b[1-9]\d* (failed|falh)/i.test(l)) cor = "#4ade80";
            if (/(✗|✕|×|FAIL\b|failed|error|erro\b|Traceback|exception)/i.test(l)) cor = "#f87171";
            if (/^Tests?:/.test(l) || /\d+ (failed|passed)/.test(l))
                l = esc(l).replace(/(\d+ failed)/g, "<span style=\"color:#f87171\">$1</span>")
                          .replace(/(\d+ passed)/g, "<span style=\"color:#4ade80\">$1</span>");
            else l = esc(l);
            h += "<br><span style=\"color:" + cor + "\">" + (l || "&nbsp;") + "</span>";
        }
        if (erro) h += "<br><span style=\"color:#f87171\">(saiu com erro)</span>";
        return h;
    }
}
