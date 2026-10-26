import QtQuick
import QtQuick.Dialogs

// A barra de escrever da janela grande: o campo (várias linhas; Enter envia,
// Shift+Enter quebra a linha), os seletores de persona, cérebro e esforço, o
// clipe e o enviar. Os anexos (clipe ou arrastados para a janela) esperam em
// cima do campo, com miniatura e ✕, e vão JUNTO da mensagem.
Item {
    id: raiz
    property var tema
    property bool conectado: false
    property string estado: "dormindo"
    property string modelo: "auto"
    property string esforco: "medium"
    property string persona: "jarvis"
    property bool menusParaCima: true
    // Ele está trabalhando: com o campo vazio, o enviar vira o Parar.
    property bool trabalhando: false
    property var anexos: []          // URLs (file://...) esperando a mensagem
    signal enviar(string texto)
    signal enviarComAnexos(string texto, var arquivos)
    signal avisar(string texto)
    signal escolherModelo(string valor)
    signal escolherEsforco(string valor)
    signal escolherPersona(string valor)
    signal parar()

    implicitHeight: coluna.height

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

    function tirar(u) { raiz.anexos = raiz.anexos.filter(function (x) { return x !== u; }); }
    function nomeDe(u) { return decodeURIComponent(u.toString().split("/").pop()); }
    function ehImagem(u) { return /\.(png|jpe?g|gif|webp|bmp)$/i.test(u.toString()); }

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

    readonly property var opcoesPersona: [
        { valor: "jarvis", nome: "Jarvis", descricao: "O mordomo de humor seco" },
        { valor: "friday", nome: "Friday", descricao: "Carinhosa e animada" },
    ]
    readonly property var opcoesModelo: [
        { valor: "auto", nome: "Automático", descricao: "O Sonnet atende e chama o Opus no pedido pesado" },
        { valor: "haiku", nome: "Haiku", descricao: "O mais rápido" },
        { valor: "sonnet", nome: "Sonnet", descricao: "Equilibrado" },
        { valor: "opus", nome: "Opus", descricao: "O mais inteligente, mais lento" },
    ]
    readonly property var opcoesEsforco: [
        { valor: "low", nome: "Baixo", descricao: "Responde rápido, pensa pouco" },
        { valor: "medium", nome: "Médio", descricao: "O padrão" },
        { valor: "high", nome: "Alto", descricao: "Pensa mais antes de responder" },
        { valor: "xhigh", nome: "Muito alto", descricao: "Para coisa difícil" },
        { valor: "max", nome: "Máximo", descricao: "Tudo o que ele tem (mais lento)" },
    ]

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

    Column {
        id: coluna
        width: parent.width
        spacing: 10

        // -- os anexos esperando a mensagem ---------------------------------
        Flickable {
            width: parent.width
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
                        width: Math.min(220, 54 + nome.implicitWidth + 40)
                        height: 56
                        radius: 12
                        color: raiz.tema.superficie
                        border.width: 1
                        border.color: raiz.tema.traco
                        Rectangle {
                            id: miniatura
                            x: 6; anchors.verticalCenter: parent.verticalCenter
                            width: 44; height: 44; radius: 8
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
                            Icone {
                                anchors.centerIn: parent
                                visible: !raiz.ehImagem(modelData)
                                caminho: raiz.tema.icones.clipe
                                cor: raiz.tema.textoFraco
                                tamanho: 18
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
                        }
                        Rectangle {
                            id: fechar
                            anchors { right: parent.right; rightMargin: 6; verticalCenter: parent.verticalCenter }
                            width: 24; height: 24; radius: 12
                            color: areaFechar.containsMouse ? raiz.tema.traco : "transparent"
                            Icone {
                                anchors.centerIn: parent
                                caminho: raiz.tema.icones.fechar
                                cor: areaFechar.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco
                                tamanho: 14
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

        // -- a caixa ------------------------------------------------------
        Rectangle {
            id: caixa
            width: parent.width
            height: rolagem.height + 62
            radius: 18
            color: raiz.tema.superficie
            border.width: 1
            border.color: campo.activeFocus ? raiz.tema.tracoForte : raiz.tema.traco
            Behavior on border.color { ColorAnimation { duration: raiz.tema.rapido } }

            Flickable {
                id: rolagem
                x: 18; y: 14
                width: parent.width - 36
                height: Math.min(Math.max(campo.implicitHeight, 26), 220)
                contentHeight: campo.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                function seguirCursor(r) {
                    if (contentY >= r.y) contentY = r.y;
                    else if (contentY + height <= r.y + r.height) contentY = r.y + r.height - height;
                }

                TextEdit {
                    id: campo
                    width: rolagem.width
                    wrapMode: TextEdit.Wrap
                    color: raiz.tema.texto
                    selectionColor: raiz.tema.tracoForte
                    selectByMouse: true
                    font.family: raiz.tema.familia
                    font.pixelSize: 15
                    onCursorRectangleChanged: rolagem.seguirCursor(cursorRectangle)
                    Keys.onPressed: function (evento) {
                        if ((evento.key === Qt.Key_Return || evento.key === Qt.Key_Enter)
                                && !(evento.modifiers & Qt.ShiftModifier)) {
                            evento.accepted = true;
                            raiz.mandar();
                        } else if (evento.matches(StandardKey.Paste) && typeof ponte !== "undefined") {
                            // Imagem ou arquivo copiado vira anexo; texto cola normal.
                            var colados = ponte.colar();
                            if (colados.length > 0) {
                                evento.accepted = true;
                                for (var i = 0; i < colados.length; i++)
                                    raiz.adicionar(colados[i]);
                            }
                        }
                    }
                }
                Text {
                    visible: campo.text === "" && !campo.preeditText
                    text: !raiz.conectado ? "Esperando o Jarvis…"
                        : raiz.estado === "escutando" ? "Te ouvindo…"
                        : raiz.anexos.length > 0 ? "Fala sobre o anexo, ou só envia"
                        : "Fala ou escreve pro Jarvis…"
                    color: raiz.tema.muitoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 15
                }
            }

            // Clicar no vazio da caixa também foca o campo.
            TapHandler { onTapped: campo.forceActiveFocus() }

            Row {
                id: seletores
                x: 12
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 10
                spacing: 8
                Seletor {
                    tema: raiz.tema
                    rotulo: "Persona"
                    opcoes: raiz.opcoesPersona
                    valor: raiz.persona
                    corDaBola: raiz.tema.persona
                    paraCima: raiz.menusParaCima
                    onEscolhido: function (v) { raiz.escolherPersona(v) }
                }
                Seletor {
                    tema: raiz.tema
                    rotulo: "Cérebro"
                    opcoes: raiz.opcoesModelo
                    valor: raiz.modelo
                    icone: raiz.tema.icones.raio
                    iconeCheio: true
                    paraCima: raiz.menusParaCima
                    onEscolhido: function (v) { raiz.escolherModelo(v) }
                }
                Seletor {
                    tema: raiz.tema
                    rotulo: "Esforço"
                    opcoes: raiz.opcoesEsforco
                    valor: raiz.esforco
                    icone: "M4 18h3v-3H4zM10.5 18h3v-7h-3zM17 18h3V7h-3z"
                    iconeCheio: true
                    paraCima: raiz.menusParaCima
                    onEscolhido: function (v) { raiz.escolherEsforco(v) }
                }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: seletores.verticalCenter
                spacing: 6

                Rectangle {
                    width: 34; height: 34; radius: 9
                    color: areaClipe.containsMouse ? raiz.tema.superficie2 : "transparent"
                    Icone {
                        anchors.centerIn: parent
                        caminho: raiz.tema.icones.clipe
                        cor: areaClipe.containsMouse ? raiz.tema.texto : raiz.tema.textoFraco
                        tamanho: 19
                        espessura: 1.6
                    }
                    MouseArea {
                        id: areaClipe
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: escolher.open()
                    }
                }
                Rectangle {
                    readonly property bool temTexto: campo.text.trim() !== "" || raiz.anexos.length > 0
                    // Trabalhando e sem nada escrito: Parar. Com texto, envia
                    // (a fala nova entra na tarefa, como falar no meio).
                    readonly property bool modoParar: raiz.trabalhando && !temTexto
                    readonly property bool ativo: raiz.conectado && (temTexto || modoParar)
                    width: 34; height: 34; radius: 10
                    color: modoParar ? raiz.tema.texto : raiz.tema.persona
                    opacity: ativo ? (areaEnviar.containsMouse ? 1.0 : 0.92) : 0.3
                    scale: areaEnviar.containsPress && ativo ? 0.92 : 1.0
                    Behavior on opacity { NumberAnimation { duration: raiz.tema.rapido } }
                    Behavior on scale { NumberAnimation { duration: 110 } }
                    Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
                    Icone {
                        anchors.centerIn: parent
                        visible: !parent.modoParar
                        caminho: raiz.tema.icones.enviar
                        cor: "#06101d"
                        tamanho: 17
                        espessura: 2.3
                    }
                    Rectangle { // o quadrado do Parar
                        anchors.centerIn: parent
                        visible: parent.modoParar
                        width: 11; height: 11; radius: 2.5
                        color: raiz.tema.fundo
                    }
                    MouseArea {
                        id: areaEnviar
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: parent.ativo ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: parent.modoParar ? raiz.parar() : raiz.mandar()
                    }
                    ToolTipSimples {
                        tema: raiz.tema
                        visivel: areaEnviar.containsMouse && parent.modoParar
                        texto: "Parar"
                    }
                }
            }
        }

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: "Enter envia · Shift+Enter quebra a linha · arraste ou cole (Ctrl+V) imagens e arquivos"
            color: raiz.tema.muitoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 12
        }
    }
}
