import QtQuick
import QtQuick.Controls.Basic

// O painel do modo code (beta 0.18.0, 10/11/2026): à direita do chat, o que a
// voz resume. O projeto, os arquivos mexidos (+ entrou, − saiu), o diff
// colorido de cada um e os botões Commit e Push (o clique já é o OK do Léo).
Rectangle {
    id: raiz
    property var tema
    property string nome: ""
    property string caminho: ""
    property var mudancas: null        // o evento "mudancas"
    property bool ocupado: false       // o Jarvis está trabalhando
    property string escolhido: ""      // o arquivo do diff ("" = todos)
    signal atualizar()
    signal commit()
    signal push()
    signal sair()
    signal trocar()

    color: tema.lateral
    readonly property var arquivos: mudancas && mudancas.arquivos ? mudancas.arquivos : []
    readonly property int mais: arquivos.reduce(function (a, x) { return a + x.mais }, 0)
    readonly property int menos: arquivos.reduce(function (a, x) { return a + x.menos }, 0)
    onCaminhoChanged: escolhido = ""

    function trechoDe(diff, arquivo) {
        if (!arquivo) return diff;
        var partes = diff.split(/\n(?=diff --git )/);
        for (var i = 0; i < partes.length; i++)
            if (partes[i].indexOf(" b/" + arquivo) >= 0) return partes[i];
        return "";
    }
    function colorir(texto) {
        var linhas = texto.split("\n").slice(0, 3000), saida = [];
        for (var i = 0; i < linhas.length; i++) {
            var l = linhas[i], cor = "#9aa3b5";
            if (l.indexOf("+++") === 0 || l.indexOf("---") === 0 || l.indexOf("index ") === 0) cor = "#5f687c";
            else if (l.charAt(0) === "+") cor = "#4ade80";
            else if (l.charAt(0) === "-") cor = "#f87171";
            else if (l.indexOf("@@") === 0) cor = "#a78bfa";
            else if (l.indexOf("diff --git") === 0) { cor = "#e6ebf2"; l = "▸ " + l.split(" b/").pop(); }
            var e = l.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/ /g, "&nbsp;");
            saida.push("<span style=\"color:" + cor + "\">" + (e || "&nbsp;") + "</span>");
        }
        return saida.join("<br>");
    }

    Rectangle { width: 1; height: parent.height; color: tema.traco }

    component BotaoPainel: Rectangle {
        id: bp
        property string rotulo
        property bool principal: false
        property bool ativo: true
        signal clicado()
        height: 34; radius: 8; width: tbp.implicitWidth + 26
        opacity: ativo ? 1 : 0.4
        color: principal ? (mbp.containsMouse && ativo ? Qt.lighter(raiz.tema.persona, 1.15) : raiz.tema.persona)
                         : (mbp.containsMouse && ativo ? raiz.tema.realce : raiz.tema.superficie2)
        border.width: principal ? 0 : 1
        border.color: raiz.tema.traco
        Text { id: tbp; anchors.centerIn: parent; text: bp.rotulo; color: bp.principal ? "#0a0c10" : raiz.tema.texto
               font.family: raiz.tema.familia; font.pixelSize: 13; font.weight: Font.DemiBold }
        MouseArea { id: mbp; anchors.fill: parent; hoverEnabled: true; enabled: bp.ativo
                    cursorShape: Qt.PointingHandCursor; onClicked: bp.clicado() }
    }

    Column {
        id: cabeca
        x: 20; y: 16; width: parent.width - 40; spacing: 4
        Text { text: "MODO CODE"; color: raiz.tema.persona; font.family: raiz.tema.familia; font.pixelSize: 11
               font.letterSpacing: 1.3; font.weight: Font.DemiBold }
        Row {
            width: parent.width; spacing: 8
            Text { width: parent.width - botoesTopo.width - 8; elide: Text.ElideRight; text: raiz.nome.replace(/^Projeto /, "")
                   color: raiz.tema.texto; font.family: raiz.tema.familia; font.pixelSize: 18; font.weight: Font.DemiBold
                   anchors.verticalCenter: parent.verticalCenter }
            Row {
                id: botoesTopo
                spacing: 6; anchors.verticalCenter: parent.verticalCenter
                BotaoPainel { rotulo: "Trocar"; height: 28; ativo: !raiz.ocupado; onClicado: raiz.trocar() }
                BotaoPainel { rotulo: "Sair"; height: 28; ativo: !raiz.ocupado; onClicado: raiz.sair() }
            }
        }
        Text {
            width: parent.width; elide: Text.ElideRight
            color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 12
            text: !raiz.mudancas ? "Lendo o projeto…"
                : !raiz.mudancas.git ? "Sem git: as mudanças aparecem só na conversa."
                : (raiz.mudancas.ramo ? "ramo " + raiz.mudancas.ramo + " · " : "")
                  + (raiz.arquivos.length === 0 ? "nada mudado" : raiz.arquivos.length + (raiz.arquivos.length === 1 ? " arquivo" : " arquivos"))
                  + (raiz.mudancas.a_frente > 0 ? " · " + raiz.mudancas.a_frente + " commit" + (raiz.mudancas.a_frente === 1 ? "" : "s") + " esperando push" : "")
        }
        Row {
            visible: raiz.arquivos.length > 0; spacing: 10
            Text { text: "+" + raiz.mais; color: "#4ade80"; font.family: raiz.tema.mono; font.pixelSize: 12 }
            Text { text: "−" + raiz.menos; color: "#f87171"; font.family: raiz.tema.mono; font.pixelSize: 12 }
        }
    }

    // os arquivos
    ListView {
        id: lista
        anchors { top: cabeca.bottom; topMargin: 12; left: parent.left; right: parent.right; leftMargin: 12; rightMargin: 12 }
        height: Math.min(contentHeight, raiz.height * 0.32)
        clip: true; spacing: 2; boundsBehavior: Flickable.StopAtBounds
        model: raiz.arquivos
        delegate: Rectangle {
            required property var modelData
            width: lista.width; height: 30; radius: 6
            readonly property bool sel: raiz.escolhido === modelData.arquivo
            color: sel ? raiz.tema.realce : maArq.containsMouse ? raiz.tema.superficie2 : "transparent"
            Rectangle { x: 10; anchors.verticalCenter: parent.verticalCenter; width: 7; height: 7; radius: 4
                        color: modelData.estado === "novo" ? "#4ade80" : modelData.estado === "apagado" ? "#f87171" : "#fbbf24" }
            Text { x: 26; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 26 - contas.width - 14
                   elide: Text.ElideMiddle; text: modelData.arquivo; color: raiz.tema.textoMedio
                   font.family: raiz.tema.mono; font.pixelSize: 12 }
            Row {
                id: contas
                anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                spacing: 6
                Text { text: "+" + modelData.mais; color: "#4ade80"; font.family: raiz.tema.mono; font.pixelSize: 11 }
                Text { text: "−" + modelData.menos; color: "#f87171"; font.family: raiz.tema.mono; font.pixelSize: 11 }
            }
            MouseArea { id: maArq; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: raiz.escolhido = parent.sel ? "" : modelData.arquivo }
        }
    }

    // o diff
    Rectangle {
        id: caixaDiff
        anchors { top: lista.bottom; topMargin: 10; left: parent.left; right: parent.right; bottom: rodape.top
                  leftMargin: 12; rightMargin: 12; bottomMargin: 10 }
        radius: 10; color: raiz.tema.codigo; border.width: 1; border.color: raiz.tema.traco
        visible: raiz.mudancas && raiz.mudancas.git
        Text { anchors.centerIn: parent; visible: raiz.arquivos.length === 0; text: "Quando ele mexer em algo, aparece aqui."
               color: raiz.tema.muitoFraco; font.family: raiz.tema.familia; font.pixelSize: 13 }
        Flickable {
            anchors { fill: parent; margins: 10 }
            clip: true; boundsBehavior: Flickable.StopAtBounds
            contentWidth: width; contentHeight: textoDiff.height
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            TextEdit {
                id: textoDiff
                width: parent.width
                readOnly: true; selectByMouse: true
                textFormat: TextEdit.RichText
                wrapMode: TextEdit.WrapAnywhere
                font.family: raiz.tema.mono; font.pixelSize: 12
                selectionColor: raiz.tema.tracoForte
                text: raiz.mudancas && raiz.mudancas.diff ? raiz.colorir(raiz.trechoDe(raiz.mudancas.diff, raiz.escolhido)) : ""
            }
        }
    }

    Row {
        id: rodape
        anchors { left: parent.left; bottom: parent.bottom; margins: 14 }
        spacing: 8
        BotaoPainel { rotulo: "Atualizar"; onClicado: raiz.atualizar() }
        BotaoPainel { rotulo: "Commit"; principal: true; ativo: !raiz.ocupado && raiz.arquivos.length > 0; onClicado: raiz.commit() }
        BotaoPainel { rotulo: "Push"; ativo: !raiz.ocupado && !!raiz.mudancas && raiz.mudancas.remoto && raiz.mudancas.a_frente > 0
                      onClicado: raiz.push() }
    }
}
