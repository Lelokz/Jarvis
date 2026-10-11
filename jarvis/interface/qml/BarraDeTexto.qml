import QtQuick
import QtQuick.Shapes

// A barra de escrita: a saída quando o Whisper erra, e o jeito de mandar
// comando sem falar. O que ele entende daqui é exatamente o que entende da
// voz — do outro lado da ponte é o mesmo caminho.
Item {
    id: raiz
    property var tema
    property string estado: "dormindo"
    property bool conectado: false
    property color corDoEstado: "#4da3ff"
    signal enviar(string texto)
    signal avisar(string texto)

    implicitHeight: 76

    function focar() { campo.forceActiveFocus(); }

    Rectangle {
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: 1
        color: raiz.tema.traco
    }

    Row {
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: 14
        spacing: 2

        AnexoIcone {
            tema: raiz.tema
            // clipe de papel
            traco: "M16.8 7.2 L9 15 a2.4 2.4 0 0 0 3.4 3.4 L20 10.8 a4.2 4.2 0 0 0-6-6 L5.6 13.2 a6.2 6.2 0 0 0 8.8 8.8 L21 15.4"
            onTocado: raiz.avisar("anexar arquivo ainda não — é de outra etapa")
        }
        AnexoIcone {
            tema: raiz.tema
            // imagem
            traco: "M4 6 h16 v12 h-16 z M9.5 10.5 a1.3 1.3 0 1 0 0.01 0 M5.5 17 l4.5-4.5 3 3 2.5-2.5 3 4"
            onTocado: raiz.avisar("anexar imagem ainda não — é de outra etapa")
        }
        AnexoIcone {
            tema: raiz.tema
            // vídeo
            traco: "M4 7 h11 v10 h-11 z M15.5 11 l4.5-2.6 v7.2 l-4.5-2.6"
            onTocado: raiz.avisar("anexar vídeo ainda não — é de outra etapa")
        }
    }

    Rectangle {
        id: caixa
        anchors {
            verticalCenter: parent.verticalCenter
            left: parent.left; leftMargin: 132
            right: parent.right; rightMargin: 62
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
            anchors.rightMargin: 16
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
                : "fale, ou escreva aqui"
            color: raiz.tema.textoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 14
            renderType: Text.NativeRendering
            opacity: 0.9
        }
    }

    // Enviar. Acende quando há texto E alguém do outro lado.
    Item {
        id: botao
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: 14
        width: 36; height: 36
        readonly property bool ativo: campo.text.trim() !== "" && raiz.conectado

        Rectangle {
            anchors.fill: parent
            radius: 18
            color: botao.ativo ? raiz.corDoEstado : raiz.tema.superficie
            opacity: botao.ativo ? (areaBotao.containsMouse ? 1.0 : 0.9) : 0.55
            scale: areaBotao.containsPress && botao.ativo ? 0.9 : 1.0
            Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
            Behavior on opacity { NumberAnimation { duration: raiz.tema.rapido } }
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

    function mandar() {
        var texto = campo.text.trim();
        if (texto === "")
            return;
        if (!raiz.conectado) {
            raiz.avisar("o Jarvis não está do outro lado — o texto não foi enviado");
            return;
        }
        raiz.enviar(texto);
        campo.text = "";
    }
}
