import QtQuick
import QtQuick.Controls.Basic

// As Memórias (25/10/2026): a lista de tudo que o Jarvis guarda (o que ele e
// a Friday sabem do Léo, cada grupo de WhatsApp, cada pessoa) e, ao tocar,
// a memória aberta para editar e salvar. Cada uma é um arquivo de texto que
// o próprio Jarvis cria (jarvis/memorias.py); memória nova aparece sozinha.
// Salvar não passa por cima do que o Jarvis escreveu enquanto o Léo editava:
// vem o aviso, e ele escolhe.
Item {
    id: raiz
    property var tema
    property var lista: []
    property bool carregando: false
    // A memória aberta ("" = a lista).
    property string aberta: ""
    property string titulo: ""
    property string original: ""
    property string versao: ""
    property bool salvando: false
    property bool conflito: false
    property string textoDoJarvis: ""
    property string versaoDoJarvis: ""
    readonly property bool mudou: aberta !== "" && editor.text !== original

    signal copiar(string texto)
    signal pedirLista()
    signal pedirAbrir(string id)
    signal pedirSalvar(string id, string texto, string versao)
    signal avisar(string texto)

    function voltarParaLista() {
        aberta = ""; conflito = false; salvando = false;
    }
    function abrir(id, t, texto, v) {
        aberta = id; titulo = t; original = texto; versao = v;
        editor.text = texto; conflito = false; salvando = false;
    }
    function salvou(id, ok, temConflito, texto, v) {
        if (id !== aberta) return;
        salvando = false;
        if (ok) {
            original = texto; versao = v; conflito = false;
            raiz.avisar("Memória salva");
            raiz.pedirLista();
        } else if (temConflito) {
            conflito = true; textoDoJarvis = texto; versaoDoJarvis = v;
        }
    }
    function quando(iso) {
        // "2026-10-25T16:50" -> "25/10 às 16:50"
        if (!iso || iso.length < 16) return "";
        return iso.substr(8, 2) + "/" + iso.substr(5, 2) + " às " + iso.substr(11, 5);
    }
    function rotuloDoTipo(tipo) {
        switch (tipo) {
        case "personas": return "O que o Jarvis e a Friday sabem de ti";
        case "recados":  return "Recados marcados do Jarvis";
        case "grupo":    return "Grupo de WhatsApp";
        case "pessoa":   return "Pessoa";
        default:         return "";
        }
    }
    function letraDoTipo(tipo) {
        switch (tipo) {
        case "personas": return "★";
        case "recados":  return "⏰";
        case "grupo":    return "👥";
        case "pessoa":   return "👤";
        default:         return "•";
        }
    }

    // -- a lista ---------------------------------------------------------------
    Flickable {
        anchors.fill: parent
        visible: raiz.aberta === ""
        contentHeight: colunaLista.height + 80
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {
            contentItem: Rectangle { implicitWidth: 6; radius: 3; color: raiz.tema.tracoForte; opacity: parent.active ? 0.9 : 0.0 }
        }
        Column {
            id: colunaLista
            x: Math.max(32, (parent.width - width) / 2)
            y: 40
            width: Math.min(780, raiz.width - 64)
            spacing: 6
            Text {
                text: "Memórias"
                color: raiz.tema.texto
                font.family: raiz.tema.familia
                font.pixelSize: 28
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Tudo o que o Jarvis guarda. Toca numa pra ler, corrigir e salvar."
                color: raiz.tema.textoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 14
            }
            Item { width: 1; height: 18 }
            Text {
                visible: raiz.carregando || raiz.lista.length === 0
                text: raiz.carregando ? "Carregando…" : "Nenhuma memória ainda."
                color: raiz.tema.textoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 15
            }
            Repeater {
                model: raiz.lista
                delegate: Rectangle {
                    required property var modelData
                    width: colunaLista.width
                    height: 68
                    radius: 14
                    color: area.containsMouse ? raiz.tema.superficie2 : raiz.tema.lateral
                    border.width: 1
                    border.color: raiz.tema.traco
                    Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
                    Rectangle {
                        id: bola
                        x: 16; anchors.verticalCenter: parent.verticalCenter
                        width: 36; height: 36; radius: 10
                        color: raiz.tema.realce
                        Text {
                            anchors.centerIn: parent
                            text: raiz.letraDoTipo(modelData.tipo)
                            color: raiz.tema.persona
                            font.pixelSize: 17
                        }
                    }
                    Column {
                        anchors { left: bola.right; leftMargin: 14; right: data.left; rightMargin: 12; verticalCenter: parent.verticalCenter }
                        spacing: 3
                        Text {
                            width: parent.width
                            elide: Text.ElideRight
                            text: modelData.titulo
                            color: raiz.tema.texto
                            font.family: raiz.tema.familia
                            font.pixelSize: 16
                            font.weight: Font.Medium
                        }
                        Text {
                            width: parent.width
                            elide: Text.ElideRight
                            text: raiz.rotuloDoTipo(modelData.tipo)
                            color: raiz.tema.textoFraco
                            font.family: raiz.tema.familia
                            font.pixelSize: 13
                        }
                    }
                    Text {
                        id: data
                        anchors { right: parent.right; rightMargin: 18; verticalCenter: parent.verticalCenter }
                        text: raiz.quando(modelData.atualizado)
                        color: raiz.tema.muitoFraco
                        font.family: raiz.tema.familia
                        font.pixelSize: 12
                    }
                    MouseArea {
                        id: area
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { raiz.titulo = modelData.titulo; raiz.pedirAbrir(modelData.id) }
                    }
                }
            }
        }
    }

    // -- a memória aberta ----------------------------------------------------------
    Item {
        anchors.fill: parent
        visible: raiz.aberta !== ""
        Item {
            id: cabecalho
            x: Math.max(32, (parent.width - width) / 2)
            y: 28
            width: Math.min(780, raiz.width - 64)
            height: 44
            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                Rectangle {
                    width: 34; height: 34; radius: 10
                    color: voltar.containsMouse ? raiz.tema.superficie2 : "transparent"
                    Icone { anchors.centerIn: parent; caminho: raiz.tema.icones.voltar; cor: raiz.tema.textoMedio; tamanho: 18; espessura: 2.2 }
                    MouseArea {
                        id: voltar
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (raiz.mudou) raiz.avisar("Alteração descartada (não salva)");
                            raiz.voltarParaLista(); raiz.pedirLista();
                        }
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: raiz.titulo
                    color: raiz.tema.texto
                    font.family: raiz.tema.familia
                    font.pixelSize: 22
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    width: Math.min(implicitWidth, cabecalho.width - 230)
                }
            }
            Row {
                anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                spacing: 8
                Rectangle {
                    visible: raiz.mudou && !raiz.conflito
                    width: desfazerTxt.implicitWidth + 28; height: 34; radius: 10
                    color: desfazer.containsMouse ? raiz.tema.superficie2 : "transparent"
                    border.width: 1; border.color: raiz.tema.traco
                    Text { id: desfazerTxt; anchors.centerIn: parent; text: "Desfazer"; color: raiz.tema.textoMedio; font.family: raiz.tema.familia; font.pixelSize: 14 }
                    MouseArea { id: desfazer; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: editor.text = raiz.original }
                }
                Rectangle {
                    width: salvarTxt.implicitWidth + 32; height: 34; radius: 10
                    opacity: raiz.mudou && !raiz.salvando && !raiz.conflito ? 1.0 : 0.4
                    color: raiz.tema.persona
                    Text { id: salvarTxt; anchors.centerIn: parent; text: raiz.salvando ? "Salvando…" : "Salvar"; color: "#06101d"; font.family: raiz.tema.familia; font.pixelSize: 14; font.weight: Font.DemiBold }
                    MouseArea {
                        anchors.fill: parent
                        enabled: raiz.mudou && !raiz.salvando && !raiz.conflito
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { raiz.salvando = true; raiz.pedirSalvar(raiz.aberta, editor.text, raiz.versao) }
                    }
                }
            }
        }

        // O Jarvis mudou a memória enquanto o Léo editava: nada foi salvo ainda.
        Rectangle {
            id: faixaConflito
            visible: raiz.conflito
            anchors { top: cabecalho.bottom; topMargin: 10 }
            x: cabecalho.x
            width: cabecalho.width
            height: visible ? colunaConflito.height + 24 : 0
            radius: 12
            color: raiz.tema.superficie
            border.width: 1
            border.color: raiz.tema.pergunta
            Column {
                id: colunaConflito
                x: 16; y: 12
                width: parent.width - 32
                spacing: 10
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "O Jarvis mudou esta memória enquanto tu editava. Nada foi salvo ainda: escolhe o que fica."
                    color: raiz.tema.texto
                    font.family: raiz.tema.familia
                    font.pixelSize: 14
                }
                Row {
                    spacing: 8
                    Rectangle {
                        width: usarTxt.implicitWidth + 28; height: 32; radius: 9
                        color: usar.containsMouse ? raiz.tema.superficie2 : "transparent"
                        border.width: 1; border.color: raiz.tema.traco
                        Text { id: usarTxt; anchors.centerIn: parent; text: "Usar a do Jarvis"; color: raiz.tema.textoMedio; font.family: raiz.tema.familia; font.pixelSize: 13 }
                        MouseArea {
                            id: usar; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: raiz.abrir(raiz.aberta, raiz.titulo, raiz.textoDoJarvis, raiz.versaoDoJarvis)
                        }
                    }
                    Rectangle {
                        width: porCimaTxt.implicitWidth + 28; height: 32; radius: 9
                        color: raiz.tema.persona
                        Text { id: porCimaTxt; anchors.centerIn: parent; text: "Salvar a minha por cima"; color: "#06101d"; font.family: raiz.tema.familia; font.pixelSize: 13; font.weight: Font.DemiBold }
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                raiz.conflito = false; raiz.salvando = true;
                                raiz.pedirSalvar(raiz.aberta, editor.text, raiz.versaoDoJarvis);
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            anchors { top: faixaConflito.visible ? faixaConflito.bottom : cabecalho.bottom; topMargin: 14; bottom: parent.bottom; bottomMargin: 28 }
            x: cabecalho.x
            width: cabecalho.width
            radius: 14
            color: raiz.tema.lateral
            border.width: 1
            border.color: editor.activeFocus ? raiz.tema.persona : raiz.tema.traco
            Flickable {
                id: rolagemEditor
                anchors { fill: parent; margins: 4 }
                contentWidth: width
                contentHeight: editor.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {
                    contentItem: Rectangle { implicitWidth: 6; radius: 3; color: raiz.tema.tracoForte; opacity: parent.active ? 0.9 : 0.0 }
                }
                TextEdit {
                    id: editor
                    width: rolagemEditor.width
                    height: Math.max(implicitHeight, rolagemEditor.height)
                    padding: 20
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    color: raiz.tema.texto
                    selectionColor: raiz.tema.realce
                    font.family: raiz.tema.familia
                    font.pixelSize: 15
                    onCursorRectangleChanged: {
                        // acompanha o cursor ao digitar no fim
                        if (cursorRectangle.y + 40 > rolagemEditor.contentY + rolagemEditor.height)
                            rolagemEditor.contentY = cursorRectangle.y + 40 - rolagemEditor.height;
                        else if (cursorRectangle.y < rolagemEditor.contentY)
                            rolagemEditor.contentY = cursorRectangle.y;
                    }
                }
            }
        }
    }
}
