import QtQuick
import QtQuick.Shapes
import QtQuick.Dialogs

// A barra de escrita, no estilo do app do celular (out/2026, pedido do Léo):
// o campo com o enviar dentro e, à direita, UM clipe (antes eram três ícones
// de enfeite: clipe, imagem e vídeo). O que vem do clipe — ou é arrastado
// para a janela — fica em cima do campo, com miniatura e ✕, esperando a
// mensagem, e vai JUNTO dela.
Item {
    id: raiz
    property var tema
    property string estado: "dormindo"
    property bool conectado: false
    property color corDoEstado: "#4da3ff"
    property var anexos: []          // URLs (file://...) esperando a mensagem
    signal enviar(string texto)
    signal enviarComAnexos(string texto, var arquivos)
    signal avisar(string texto)

    implicitHeight: 64 + (anexos.length > 0 ? fileira.height + 8 : 0)

    function focar() { campo.forceActiveFocus(); }

    function adicionar(url) {
        var u = url.toString();
        if (raiz.anexos.indexOf(u) >= 0)
            return;
        if (raiz.anexos.length >= 10) {
            raiz.avisar("no máximo dez anexos por mensagem");
            return;
        }
        raiz.anexos = raiz.anexos.concat([u]);
    }

    function tirar(u) {
        raiz.anexos = raiz.anexos.filter(function (x) { return x !== u; });
    }

    function nomeDe(u) {
        return decodeURIComponent(u.toString().split("/").pop());
    }

    function ehImagem(u) {
        return /\.(png|jpe?g|gif|webp|bmp)$/i.test(u.toString());
    }

    FileDialog {
        id: escolher
        title: "Anexar ao Jarvis"
        fileMode: FileDialog.OpenFiles
        onAccepted: {
            for (var i = 0; i < selectedFiles.length; i++)
                raiz.adicionar(selectedFiles[i]);
            campo.forceActiveFocus();
        }
    }

    // -- os anexos esperando a mensagem ------------------------------------
    Flickable {
        id: fileira
        anchors { top: parent.top; left: parent.left; right: parent.right }
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        height: raiz.anexos.length > 0 ? 56 : 0
        visible: raiz.anexos.length > 0
        contentWidth: linhaDeAnexos.width
        flickableDirection: Flickable.HorizontalFlick
        clip: true

        Row {
            id: linhaDeAnexos
            spacing: 8
            Repeater {
                model: raiz.anexos
                Rectangle {
                    required property var modelData
                    width: Math.min(200, 54 + nome.implicitWidth + 40)
                    height: 56
                    radius: 12
                    color: raiz.tema.superficie
                    border.width: 1
                    border.color: raiz.tema.traco

                    Rectangle {
                        id: miniatura
                        x: 6; anchors.verticalCenter: parent.verticalCenter
                        width: 44; height: 44
                        radius: 8
                        color: raiz.tema.traco
                        clip: true
                        Image {
                            anchors.fill: parent
                            visible: raiz.ehImagem(modelData)
                            source: raiz.ehImagem(modelData) ? modelData : ""
                            sourceSize: Qt.size(88, 88)
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: !raiz.ehImagem(modelData)
                            text: /\.(mp4|mkv|webm|mov|avi)$/i.test(modelData) ? "▶" : "📄"
                            color: raiz.tema.textoFraco
                            font.pixelSize: 16
                        }
                    }
                    Text {
                        id: nome
                        anchors { left: miniatura.right; leftMargin: 8; right: fechar.left; rightMargin: 2 }
                        anchors.verticalCenter: parent.verticalCenter
                        text: raiz.nomeDe(modelData)
                        elide: Text.ElideMiddle
                        color: raiz.tema.texto
                        font.family: raiz.tema.familia
                        font.pixelSize: 12
                        renderType: Text.NativeRendering
                    }
                    Rectangle {
                        id: fechar
                        anchors { right: parent.right; rightMargin: 6; verticalCenter: parent.verticalCenter }
                        width: 24; height: 24; radius: 12
                        color: areaFechar.containsMouse ? raiz.tema.traco : "transparent"
                        Text {
                            anchors.centerIn: parent
                            text: "✕"
                            color: areaFechar.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco
                            font.pixelSize: 12
                        }
                        MouseArea {
                            id: areaFechar
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: raiz.tirar(modelData)
                        }
                    }
                }
            }
        }
    }

    // -- o campo, com o enviar dentro ----------------------------------------
    Rectangle {
        id: caixa
        anchors {
            bottom: parent.bottom; bottomMargin: 11
            left: parent.left; leftMargin: 14
            right: clipe.left; rightMargin: 8
        }
        height: 42
        radius: 21
        color: raiz.tema.superficie
        border.width: 1
        border.color: campo.activeFocus ? raiz.corDoEstado : raiz.tema.traco
        Behavior on border.color { ColorAnimation { duration: raiz.tema.rapido } }

        TextInput {
            id: campo
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: botao.visible ? 46 : 16
            verticalAlignment: TextInput.AlignVCenter
            color: raiz.tema.texto
            font.family: raiz.tema.familia
            font.pixelSize: 14
            renderType: Text.NativeRendering
            selectionColor: raiz.corDoEstado
            clip: true
            onAccepted: raiz.mandar()
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 16
            visible: campo.text === ""
            text: !raiz.conectado ? "esperando o Jarvis…"
                : raiz.estado === "escutando" ? "ouvindo você…"
                : raiz.estado === "pensando" ? "pensando…"
                : raiz.anexos.length > 0 ? "fala sobre o anexo, ou só envia"
                : "fale, ou escreva aqui"
            color: raiz.tema.textoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 14
            renderType: Text.NativeRendering
            opacity: 0.9
        }

        // Enviar: aparece quando há o que mandar, e acende com alguém do outro lado.
        Item {
            id: botao
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            anchors.rightMargin: 4
            width: 34; height: 34
            visible: campo.text.trim() !== "" || raiz.anexos.length > 0
            readonly property bool ativo: visible && raiz.conectado

            Rectangle {
                anchors.fill: parent
                radius: 17
                color: botao.ativo ? raiz.corDoEstado : raiz.tema.traco
                opacity: botao.ativo ? (areaBotao.containsMouse ? 1.0 : 0.9) : 0.6
                scale: areaBotao.containsPress && botao.ativo ? 0.9 : 1.0
                Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
                Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutQuad } }
            }
            Shape {
                anchors.centerIn: parent
                width: 18; height: 18
                ShapePath {
                    fillColor: "transparent"
                    strokeColor: botao.ativo ? raiz.tema.fundo : raiz.tema.textoFraco
                    strokeWidth: 1.8
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    PathSvg { path: "M9 15 V3 M4 8 L9 3 L14 8" }
                }
            }
            MouseArea {
                id: areaBotao
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: botao.ativo ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: raiz.mandar()
            }
        }
    }

    // -- o clipe, à direita ---------------------------------------------------
    Rectangle {
        id: clipe
        anchors { right: parent.right; rightMargin: 14; verticalCenter: caixa.verticalCenter }
        width: 42; height: 42; radius: 21
        color: areaClipe.containsMouse ? raiz.tema.traco : raiz.tema.superficie
        border.width: 1
        border.color: raiz.tema.traco
        scale: areaClipe.containsPress ? 0.92 : 1.0
        Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
        Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutQuad } }
        Shape {
            anchors.centerIn: parent
            width: 24; height: 24
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: "transparent"
                strokeColor: areaClipe.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco
                strokeWidth: 1.5
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: "M16.8 7.2 L9 15 a2.4 2.4 0 0 0 3.4 3.4 L20 10.8 a4.2 4.2 0 0 0-6-6 L5.6 13.2 a6.2 6.2 0 0 0 8.8 8.8 L21 15.4" }
            }
        }
        MouseArea {
            id: areaClipe
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: escolher.open()
        }
    }

    function mandar() {
        var texto = campo.text.trim();
        if (texto === "" && raiz.anexos.length === 0)
            return;
        if (!raiz.conectado) {
            raiz.avisar("o Jarvis não está do outro lado — não foi enviado");
            return;
        }
        if (raiz.anexos.length > 0)
            raiz.enviarComAnexos(texto, raiz.anexos);
        else
            raiz.enviar(texto);
        campo.text = "";
        raiz.anexos = [];
    }
}
