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
    // O modo Local (o modelo do Ollama no PC): só aparece se o Ollama responder.
    property bool localDisponivel: false
    property string localNome: ""
    property string esforco: "medium"
    property string persona: "jarvis"
    property bool menusParaCima: true
    // Ele está trabalhando: com o campo vazio, o enviar vira o Parar.
    property bool trabalhando: false
    property var anexos: []          // URLs (file://...) esperando a mensagem
    // A voz no campo (beta 0.18.5): o nível do microfone, o que ele está
    // fazendo agora e se a dica de baixo aparece.
    property real nivel: 0.0
    property string fazendo: ""
    property bool mostrarDica: true
    property bool digitando: false   // começou a escrever: o campo volta no lugar da voz
    readonly property bool vozAtiva: conectado && ["ouvindo", "escutando", "pensando", "falando"].indexOf(estado) >= 0
    readonly property bool modoVoz: vozAtiva && !digitando && campo.text === "" && anexos.length === 0
    readonly property color corVoz: tema.corDoEstado(estado)
    onEstadoChanged: if (estado === "dormindo") digitando = false
    readonly property string nomePersona: persona === "friday" ? "Friday" : "Jarvis"
    signal enviar(string texto)
    signal enviarComAnexos(string texto, var arquivos)
    signal avisar(string texto)
    signal escolherModelo(string valor)
    signal escolherEsforco(string valor)
    signal escolherPersona(string valor)
    // O modo code (etapa 3 do tchan): quanto ele faz sozinho.
    property bool emCode: false
    property string permissao: "auto"
    signal escolherPermissao(string valor)
    readonly property var opcoesPermissao: [
        { valor: "auto", nome: "Automático", descricao: "Faz e te conta" },
        { valor: "perguntar", nome: "Perguntar antes", descricao: "Pede teu “pode” antes de mudar cada arquivo" },
        { valor: "plano", nome: "Plano primeiro", descricao: "Conta o plano, espera o OK e só então mexe" },
        { valor: "olhar", nome: "Só olhar", descricao: "Lê e explica, não muda nada" },
    ]
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
            raiz.avisar("a NOVA não está do outro lado — não foi enviado");
            return;
        }
        if (raiz.anexos.length > 0)
            raiz.enviarComAnexos(texto, raiz.anexos);
        else
            raiz.enviar(texto);
        campo.text = "";
        raiz.anexos = [];
        raiz.digitando = false;
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
    ].concat(localDisponivel || modelo === "local"
             ? [{ valor: "local", nome: "Local (" + localNome + ")", descricao: "No seu PC, sem internet; pergunta antes de agir" }]
             : [])
    readonly property var opcoesEsforco: [
        { valor: "low", nome: "Baixo", descricao: "Responde rápido, pensa pouco" },
        { valor: "medium", nome: "Médio", descricao: "O padrão" },
        { valor: "high", nome: "Alto", descricao: "Pensa mais antes de responder" },
        { valor: "xhigh", nome: "Muito alto", descricao: "Para coisa difícil" },
        { valor: "max", nome: "Máximo", descricao: "Tudo o que ele tem (mais lento)" },
    ]

    FileDialog {
        id: escolher
        title: "Anexar à conversa"
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
            height: (raiz.modoVoz ? 44 : rolagem.height) + 62 + (cabecalho.visible ? 26 : 0)
            Behavior on height { NumberAnimation { duration: raiz.tema.rapido; easing.type: Easing.OutCubic } }
            radius: 18
            color: raiz.tema.fundoCampo
            border.width: 1
            // Com a voz ativa, a borda pega a cor do estado (verde ouvindo, roxo
            // pensando, âmbar falando); senão, um contorno fino e limpo.
            border.color: raiz.vozAtiva ? Qt.rgba(raiz.corVoz.r, raiz.corVoz.g, raiz.corVoz.b, 0.6)
                        : campo.activeFocus ? raiz.tema.persona : raiz.tema.bordaCampo
            Behavior on border.color { ColorAnimation { duration: raiz.tema.normal } }

            // Um brilho bem leve por fora, na cor da voz (no lugar de sombra escura).
            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                z: -1
                radius: parent.radius + 4
                color: "transparent"
                border.width: 4
                border.color: Qt.rgba(raiz.corVoz.r, raiz.corVoz.g, raiz.corVoz.b, raiz.vozAtiva ? 0.10 : 0)
                Behavior on border.color { ColorAnimation { duration: raiz.tema.normal } }
            }
            // Um fio de luz no alto da caixa: dá relevo sem sombra.
            Rectangle {
                x: parent.radius; y: 1
                width: parent.width - 2 * parent.radius; height: 1
                color: raiz.tema.claro ? "transparent" : Qt.rgba(1, 1, 1, 0.05)
            }

            // Dormindo ou com o campo em uso: uma linha fina com o estado da voz.
            Row {
                id: cabecalho
                x: 18; y: 14
                spacing: 8
                visible: raiz.conectado && !raiz.modoVoz && raiz.mostrarDica === false
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 8; height: 8; radius: 4
                    color: raiz.corVoz
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: raiz.estado === "dormindo" ? "Dormindo · esperando o \u201cHey " + raiz.nomePersona + "\u201d"
                        : raiz.estado === "ouvindo" ? "Acordado · pode falar"
                        : raiz.estado === "escutando" ? "Te ouvindo…"
                        : raiz.estado === "pensando" ? "Pensando…"
                        : "Falando…"
                    color: raiz.tema.textoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 13
                }
            }

            // A voz no lugar do campo: a onda, o que está acontecendo e o Parar.
            Item {
                id: linhaVoz
                x: 18; y: 12
                width: parent.width - 36
                height: 44
                visible: opacity > 0
                opacity: raiz.modoVoz ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: raiz.tema.rapido } }

                // A onda: segue o microfone quando ele te ouve; viva quando fala.
                Row {
                    id: onda
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 3
                    visible: raiz.estado !== "pensando"
                    property var alturas: [6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6]
                    Timer {
                        running: linhaVoz.visible && onda.visible
                        interval: 90
                        repeat: true
                        onTriggered: {
                            var amp = raiz.estado === "escutando" ? Math.max(0.12, Math.min(1, raiz.nivel * 3.2))
                                    : raiz.estado === "falando" ? 0.75 : 0.14;
                            var a = [];
                            for (var i = 0; i < 11; i++) {
                                var meio = 1 - Math.abs(i - 5) / 7;
                                a.push(5 + 25 * amp * meio * (0.45 + Math.random() * 0.55));
                            }
                            onda.alturas = a;
                        }
                    }
                    Repeater {
                        model: 11
                        Rectangle {
                            required property int index
                            anchors.verticalCenter: parent.verticalCenter
                            width: 4; radius: 2
                            height: onda.alturas[index]
                            color: raiz.corVoz
                            Behavior on height { NumberAnimation { duration: 90 } }
                        }
                    }
                }
                // Pensando: três pontos que respiram.
                Row {
                    id: pontos
                    anchors.verticalCenter: parent.verticalCenter
                    visible: raiz.estado === "pensando"
                    spacing: 6
                    Repeater {
                        model: 3
                        Rectangle {
                            required property int index
                            width: 8; height: 8; radius: 4
                            color: raiz.corVoz
                            SequentialAnimation on opacity {
                                running: pontos.visible
                                loops: Animation.Infinite
                                PauseAnimation { duration: index * 160 }
                                NumberAnimation { from: 0.25; to: 1; duration: 380 }
                                NumberAnimation { from: 1; to: 0.25; duration: 380 }
                                PauseAnimation { duration: (2 - index) * 160 }
                            }
                        }
                    }
                }
                Text {
                    id: rotuloVoz
                    anchors.left: onda.visible ? onda.right : pontos.right
                    anchors.leftMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: raiz.estado === "ouvindo" ? "Pode falar…"
                        : raiz.estado === "escutando" ? "Ouvindo…"
                        : raiz.estado === "pensando" ? "Pensando…" : "Falando…"
                    color: raiz.tema.texto
                    font.family: raiz.tema.familia
                    font.pixelSize: 16
                    font.weight: Font.Medium
                }
                Text {
                    anchors.left: rotuloVoz.right
                    anchors.leftMargin: 8
                    anchors.right: botaoParar.left
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                    text: raiz.estado === "ouvindo" ? "ou escreve aqui"
                        : raiz.estado === "escutando" ? ""
                        : raiz.estado === "pensando" ? raiz.fazendo
                        : "fala \u201cpara\u201d ou toca pra cortar"
                    color: raiz.tema.textoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 14
                }
                Rectangle {
                    id: botaoParar
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: linhaParar.width + 26
                    height: 34
                    radius: 10
                    color: Qt.rgba(raiz.corVoz.r, raiz.corVoz.g, raiz.corVoz.b, areaParar.containsMouse ? 0.26 : 0.15)
                    Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
                    Row {
                        id: linhaParar
                        anchors.centerIn: parent
                        spacing: 8
                        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10; radius: 2; color: raiz.corVoz }
                        Text {
                            text: raiz.estado === "ouvindo" || raiz.estado === "escutando" ? "Dormir" : "Parar"
                            color: raiz.corVoz
                            font.family: raiz.tema.familia
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                    }
                    MouseArea {
                        id: areaParar
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: raiz.parar()
                    }
                }
            }

            Flickable {
                id: rolagem
                x: 18; y: cabecalho.visible ? 40 : 14
                visible: !raiz.modoVoz
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
                    onTextChanged: if (text !== "") raiz.digitando = true
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
                    text: !raiz.conectado ? "Esperando a NOVA…"
                        : raiz.estado === "escutando" ? "Te ouvindo…"
                        : raiz.anexos.length > 0 ? "Fala sobre o anexo, ou só envia"
                        : (raiz.persona === "friday" ? "Fala ou escreve pra Friday…" : "Fala ou escreve pro Jarvis…")
                    color: raiz.tema.muitoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 15
                }
            }

            // Clicar no vazio da caixa também foca o campo (e, com a voz no
            // lugar, abre o campo pra escrever).
            TapHandler { onTapped: { raiz.digitando = true; campo.forceActiveFocus(); } }

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
                Seletor {
                    visible: raiz.emCode
                    tema: raiz.tema
                    rotulo: "Quanto ele faz sozinho"
                    opcoes: raiz.opcoesPermissao
                    valor: raiz.permissao
                    icone: raiz.tema.icones.escudo
                    destaque: raiz.tema.pergunta
                    rodape: "Pela voz: “modo plano”, “pergunta antes”, “pode fazer sozinho”, “só olhar”"
                    paraCima: raiz.menusParaCima
                    onEscolhido: function (v) { raiz.escolherPermissao(v) }
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
            visible: raiz.mostrarDica
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: "Enter envia · Shift+Enter quebra a linha · arraste ou cole (Ctrl+V) imagens e arquivos"
            color: raiz.tema.muitoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 12
        }
    }
}
