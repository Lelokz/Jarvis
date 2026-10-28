import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs

// Ajustes (beta 0.17.0, como as configurações do Claude; protótipo aprovado
// pelo Léo em 27/10/2026): um painel por cima da janela, com o fundo
// escurecido, as categorias à esquerda e o conteúdo da escolhida à direita.
// Fecha no X, no Esc ou clicando fora. O que se troca toda hora (cérebro,
// esforço, persona) continua na barra de escrever.
Item {
    id: raiz
    property var tema
    property bool aberto: false
    signal fechar()

    property bool conectado: false
    property string conversa: ""
    property string modelo: ""
    property string esforco: ""
    property string persona: "jarvis"
    property string corFriday: ""
    signal escolherPersona(string valor)
    // O uso da assinatura (0 a 1; -1 = ainda não sei) e quando cada um renova.
    property real usoCinco: -1
    property real voltaCinco: 0
    property real usoSemana: -1
    property real voltaSemana: 0
    // O evento "som" da ponte (jarvis/som.py): aparelhos, padrão e escolha.
    property var som: null
    signal escolherSom(string tipo, string aparelho)
    // O evento "ajustes": volume, notificações, nome, grupo e as conexões.
    property var ajustes: null
    signal mudarVolume(int volume)
    signal mudarNome(string nome)
    signal mudarGrupo(bool ligado)

    property string aba: "geral"
    onAbaChanged: fecharPasso()

    // O passo a passo aberto (o id da conexão, "" = a lista) e a última
    // resposta do PC para ele (o evento "conexao", jarvis/conectar.py).
    property string passo: ""
    property var conexao: ({})
    signal pedirConexao(string id, string acao, string valor)
    readonly property var cp: conexao && conexao.id === passo ? conexao : ({})
    readonly property string estadoPasso: cp.estado === "conectado" ? "conectado" : estadoDe(passo).estado
    function abrirPasso(id) {
        fecharPasso();
        passo = id;
        conexao = ({});
        rolagem.contentY = 0;
        // O WhatsApp sobe a ponte e mostra o QR; o Fora de casa liga o acesso
        // sozinho quando o celular aparece. Os outros só olham.
        if (id !== "relogio" && id !== "atalhos")
            pedirConexao(id, id === "whatsapp" && estadoDe(id).estado !== "conectado" || id === "fora" ? "conectar" : "estado", "");
    }
    function fecharPasso() {
        if (passo === "whatsapp" && cp.estado === "esperando")
            pedirConexao("whatsapp", "cancelar", "");
        if (passo !== "") pedirAjustes();
        passo = "";
    }
    signal pedirAjustes()
    Timer {
        interval: 2000
        repeat: true
        running: raiz.aberto && raiz.passo !== "" && raiz.passo !== "relogio" && raiz.passo !== "atalhos"
        onTriggered: raiz.pedirConexao(raiz.passo, raiz.passo === "fora" ? "conectar" : "estado", "")
    }

    readonly property var categorias: [
        { grupo: "Preferências", itens: [
            { id: "geral", nome: "Geral", icone: "geral" },
            { id: "voz", nome: "Voz e som", icone: "voz" },
            { id: "avisos", nome: "Avisos", icone: "sino" },
            { id: "uso", nome: "Uso", icone: "uso" } ] },
        { grupo: "Personalização", itens: [
            { id: "personas", nome: "Personas", icone: "personas" },
            { id: "conexoes", nome: "Conexões", icone: "conexoes" } ] },
        { grupo: "", itens: [
            { id: "sobre", nome: "Sobre a NOVA", icone: "sobre" } ] },
    ]

    // As conexões: nome e descrição aqui; o estado vem do PC (jarvis/conexoes.py).
    // `precisa`: a que tem que estar conectada antes (o cartão mostra "Precisa do…").
    readonly property var conexoes: [
        { id: "whatsapp", nome: "WhatsApp", icone: "whats", descricao: "Ler e mandar mensagens, e avisar quem te escreveu." },
        { id: "grupo", nome: "Grupo do WhatsApp", icone: "grupo", precisa: "whatsapp", descricao: "Responde no grupo da família quando chamam o Jarvis." },
        { id: "fora", nome: "Fora de casa", icone: "globo", descricao: "O celular falar com o PC, em casa ou na rua (Tailscale)." },
        { id: "celular", nome: "Celular", icone: "celular", precisa: "fora", descricao: "O app NOVA: conversar e receber avisos pelo celular." },
        { id: "relogio", nome: "Relógio", icone: "relogio", precisa: "celular", descricao: "Falar pelo relógio (Wear OS)." },
        { id: "musica", nome: "Música", icone: "musica", descricao: "Tocar música e vídeo do YouTube pelo PC." },
        { id: "atalhos", nome: "Atalhos", icone: "raio", descricao: "Programas e pastas que ele abre pelo nome." },
    ]
    function infoDe(id) {
        for (var i = 0; i < conexoes.length; i++)
            if (conexoes[i].id === id) return conexoes[i];
        return {};
    }
    // "Precisa do WhatsApp" se a de antes não está conectada; "" se pode.
    function faltaPara(id) {
        var antes = infoDe(id).precisa;
        if (!antes) return "";
        var e = estadoDe(antes).estado;
        return e === "conectado" || e === "pronto" ? "" : "Precisa do " + infoDe(antes).nome;
    }
    function estadoDe(id) {
        var lista = raiz.ajustes && raiz.ajustes.conexoes ? raiz.ajustes.conexoes : [];
        for (var i = 0; i < lista.length; i++)
            if (lista[i].id === id) return lista[i];
        return { estado: "", detalhe: "" };
    }

    // "Padrão do sistema" primeiro (com o aparelho que ele é agora), depois
    // todos os aparelhos que o Linux enxerga.
    function opcoesDeSom(aparelhos, padrao) {
        var lista = [{ valor: "", nome: "Padrão" + (padrao ? " (" + padrao + ")" : ""),
                       descricao: "Acompanha o padrão das configurações de som do Linux" }];
        for (var i = 0; i < (aparelhos || []).length; i++)
            lista.push({ valor: aparelhos[i].id, nome: aparelhos[i].nome, descricao: "" });
        return lista;
    }

    function quandoRenova(seg, comDia) {
        if (!seg) return "";
        var d = new Date(seg * 1000);
        var hora = ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
        if (!comDia) return "renova às " + hora;
        var dias = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
        return "renova " + dias[d.getDay()] + " " + d.getDate() + "/" + (d.getMonth() + 1) + ", " + hora;
    }

    readonly property var nomes: ({
        auto: "Automático (Sonnet + Opus)", haiku: "Haiku", sonnet: "Sonnet", opus: "Opus",
        low: "Baixo", medium: "Médio", high: "Alto", xhigh: "Muito alto", max: "Máximo"
    })

    visible: opacity > 0
    opacity: aberto ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: raiz.tema.rapido } }
    onAbertoChanged: if (aberto) painel.forceActiveFocus(); else fecharPasso()

    // -- as peças das páginas -------------------------------------------------

    // Um bloco com título (e, se quiser, uma linha explicando).
    component Secao: Column {
        property string titulo: ""
        property string dica: ""
        width: parent ? parent.width : 0
        spacing: 0
        bottomPadding: 26
        Text {
            text: parent.titulo
            color: raiz.tema.texto
            font.family: raiz.tema.familia
            font.pixelSize: 15
            font.weight: Font.DemiBold
            bottomPadding: parent.dica ? 4 : 6
        }
        Text {
            visible: !!parent.dica
            width: parent.width
            wrapMode: Text.WordWrap
            text: parent.dica
            color: raiz.tema.textoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 13
            bottomPadding: 10
        }
    }

    // Uma linha de ajuste: o nome (e a explicação) à esquerda, o controle à direita.
    component Linha: Item {
        property string titulo: ""
        property string descricao: ""
        property bool ultima: false
        default property alias controle: lugar.data
        width: parent ? parent.width : 0
        height: Math.max(56, textos.height + 22)
        Column {
            id: textos
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - lugar.width - 24
            spacing: 3
            Text {
                text: titulo
                color: raiz.tema.texto
                font.family: raiz.tema.familia
                font.pixelSize: 14
            }
            Text {
                visible: !!descricao
                width: parent.width
                wrapMode: Text.WordWrap
                text: descricao
                color: raiz.tema.textoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 13
            }
        }
        Item {
            id: lugar
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: childrenRect.width
            height: childrenRect.height
        }
        Rectangle {
            visible: !ultima
            anchors.bottom: parent.bottom
            width: parent.width; height: 1
            color: raiz.tema.traco
        }
    }

    component Interruptor: Rectangle {
        id: chave
        property bool ligado: false
        signal trocou()
        width: 40; height: 23; radius: 12
        color: ligado ? raiz.tema.persona : raiz.tema.tracoForte
        Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }
        Rectangle {
            y: 3; width: 17; height: 17; radius: 9
            x: chave.ligado ? chave.width - width - 3 : 3
            color: chave.ligado ? "#ffffff" : raiz.tema.textoMedio
            Behavior on x { NumberAnimation { duration: raiz.tema.rapido; easing.type: Easing.OutCubic } }
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: chave.trocou()
        }
    }

    component Valor: Text {
        color: raiz.tema.textoMedio
        font.family: raiz.tema.familia
        font.pixelSize: 14
    }

    component Tecla: Rectangle {
        property string texto: ""
        width: rotulo.implicitWidth + 16
        height: 24
        radius: 6
        color: raiz.tema.superficie2
        border.width: 1
        border.color: raiz.tema.tracoForte
        Text {
            id: rotulo
            anchors.centerIn: parent
            text: parent.texto
            color: raiz.tema.textoMedio
            font.family: raiz.tema.familia
            font.pixelSize: 12
        }
    }

    // Um botão pequeno: o forte é o azul (Conectar), o outro só contornado.
    component Botao: Rectangle {
        id: botaoP
        property string texto: ""
        property bool forte: false
        signal clicado()
        width: textoBotao.implicitWidth + 26
        height: 32
        radius: 9
        color: forte ? (areaBotao.containsMouse ? Qt.lighter(raiz.tema.persona, 1.1) : raiz.tema.persona)
                     : (areaBotao.containsMouse ? raiz.tema.superficie2 : "transparent")
        border.width: forte ? 0 : 1
        border.color: raiz.tema.tracoForte
        Text {
            id: textoBotao
            anchors.centerIn: parent
            text: botaoP.texto
            color: botaoP.forte ? "#06101c" : raiz.tema.textoMedio
            font.family: raiz.tema.familia
            font.pixelSize: 13
            font.weight: botaoP.forte ? Font.DemiBold : Font.Normal
        }
        MouseArea { id: areaBotao; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: botaoP.clicado() }
    }

    // Desconectar sem pop-up: o 1º toque pede o 2º ("Toca de novo…") por 4 s.
    component BotaoConfirmar: Botao {
        id: confirmar
        property bool armado: false
        signal confirmado()
        property string textoNormal: ""
        Component.onCompleted: textoNormal = texto
        texto: armado ? "Toca de novo pra confirmar" : textoNormal
        onClicado: { if (armado) { armado = false; confirmado() } else { armado = true; desarmar.restart() } }
        Timer { id: desarmar; interval: 4000; onTriggered: confirmar.armado = false }
    }

    // Um passo do passo a passo: a bolinha (número, ✓ ou a azul de agora), o
    // texto e, embaixo, o que mais precisar (um comando, a espera).
    component Passo: Item {
        id: passoItem
        property int numero: 1
        property bool feito: false
        property bool agora: false
        property bool ultimo: false
        property string titulo: ""
        property string dica: ""
        default property alias extra: extraPasso.data
        width: parent ? parent.width : 0
        height: colPasso.height + 22
        Rectangle {
            y: 11
            width: 24; height: 24; radius: 12
            color: passoItem.feito ? Qt.rgba(0.22, 0.83, 0.62, 0.15) : passoItem.agora ? raiz.tema.persona : raiz.tema.superficie2
            Text {
                anchors.centerIn: parent
                text: passoItem.feito ? "✓" : passoItem.numero
                color: passoItem.feito ? "#38d39f" : passoItem.agora ? "#06101c" : raiz.tema.textoMedio
                font.family: raiz.tema.familia
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
        }
        Column {
            id: colPasso
            x: 37; y: 11
            width: parent.width - 37
            spacing: 3
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                textFormat: Text.StyledText
                text: passoItem.titulo
                color: passoItem.agora ? raiz.tema.texto : raiz.tema.textoMedio
                font.family: raiz.tema.familia
                font.pixelSize: 14
            }
            Text {
                visible: !!passoItem.dica
                width: parent.width
                wrapMode: Text.WordWrap
                text: passoItem.dica
                color: raiz.tema.textoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 13
            }
            Column { id: extraPasso; width: parent.width; topPadding: children.length ? 6 : 0; spacing: 6 }
        }
        Rectangle { visible: !passoItem.ultimo; anchors.bottom: parent.bottom; width: parent.width; height: 1; color: raiz.tema.traco }
    }

    // Um comando para copiar e rodar no terminal (o que pede senha de administrador).
    component Comando: Rectangle {
        id: comandoC
        property string texto: ""
        property bool copiado: false
        width: parent ? parent.width : 0
        height: 44
        radius: 10
        color: "#07090d"
        border.width: 1
        border.color: raiz.tema.tracoForte
        Text {
            x: 12
            width: parent.width - 24 - copiar.width
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            text: comandoC.texto
            color: raiz.tema.texto
            font.family: "monospace"
            font.pixelSize: 13
        }
        TextEdit { id: area; visible: false; text: comandoC.texto }
        Botao {
            id: copiar
            anchors.right: parent.right
            anchors.rightMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            texto: comandoC.copiado ? "Copiado" : "Copiar"
            onClicado: { area.selectAll(); area.copy(); comandoC.copiado = true }
        }
    }

    component Espera: Row {
        property string texto: ""
        spacing: 9
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 8; height: 8; radius: 4
            color: raiz.tema.persona
            SequentialAnimation on opacity { loops: Animation.Infinite; NumberAnimation { to: 0.3; duration: 700 } NumberAnimation { to: 1; duration: 700 } }
        }
        Text { text: parent.texto; color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 13 }
    }

    component Nota: Rectangle {
        property string texto: ""
        width: parent ? parent.width : 0
        height: textoNota.height + 24
        radius: 12
        color: raiz.tema.superficie
        border.width: 1
        border.color: raiz.tema.traco
        Icone { x: 13; y: 13; caminho: raiz.tema.icones.sobre || ""; cor: raiz.tema.persona; tamanho: 16 }
        Text {
            id: textoNota
            x: 40; y: 12
            width: parent.width - 54
            wrapMode: Text.WordWrap
            text: parent.texto
            color: raiz.tema.textoFraco
            font.family: raiz.tema.familia
            font.pixelSize: 13
            lineHeight: 1.15
        }
    }

    // A caixa do QR (WhatsApp e celular), com a espera e uma linha embaixo.
    component CaixaQr: Rectangle {
        id: caixa
        property string qr: ""
        property string espera: ""
        property string rodape: ""
        default property alias extra: extraCaixa.data
        width: 300
        height: colCaixa.height + 36
        radius: 16
        color: raiz.tema.superficie
        border.width: 1
        border.color: raiz.tema.traco
        Column {
            id: colCaixa
            y: 18
            width: parent.width
            spacing: 12
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 216; height: 216; radius: 12
                color: caixa.qr ? "#ffffff" : raiz.tema.superficie2
                Image {
                    anchors.fill: parent
                    anchors.margins: 6
                    source: caixa.qr
                    smooth: false
                    fillMode: Image.PreserveAspectFit
                }
            }
            Espera { visible: !!caixa.espera; texto: caixa.espera; anchors.horizontalCenter: parent.horizontalCenter }
            Text {
                visible: !!caixa.rodape
                width: parent.width - 36
                anchors.horizontalCenter: parent.horizontalCenter
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: caixa.rodape
                color: raiz.tema.textoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 12
            }
            Column { id: extraCaixa; anchors.horizontalCenter: parent.horizontalCenter }
        }
    }

    // O estado de uma conexão: Conectado (verde), Pronto (azul), Desligado.
    component Etiqueta: Rectangle {
        property string estado: ""
        readonly property color cor: estado === "conectado" ? "#38d39f"
                                   : estado === "pronto" ? raiz.tema.persona : raiz.tema.textoFraco
        width: rotuloEtiqueta.implicitWidth + 16
        height: 20
        radius: 10
        color: estado === "desligado" || estado === "" ? raiz.tema.superficie2 : Qt.rgba(cor.r, cor.g, cor.b, 0.13)
        Text {
            id: rotuloEtiqueta
            anchors.centerIn: parent
            text: parent.estado === "conectado" ? "Conectado" : parent.estado === "pronto" ? "Pronto"
                : parent.estado === "desligado" ? "Desligado" : "…"
            color: parent.cor
            font.family: raiz.tema.familia
            font.pixelSize: 12
            font.weight: Font.Medium
        }
    }

    // -- o painel -----------------------------------------------------------------

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0.016, 0.024, 0.035, 0.62)
        MouseArea { anchors.fill: parent; onClicked: raiz.fechar() }
    }

    Rectangle {
        id: painel
        anchors.centerIn: parent
        width: Math.min(1000, raiz.width - 80)
        height: Math.min(700, raiz.height - 80)
        radius: 18
        color: raiz.tema.lateral
        border.width: 1
        border.color: raiz.tema.tracoForte
        clip: true
        focus: true
        Keys.onEscapePressed: raiz.fechar()
        // O clique dentro do painel não fecha.
        MouseArea { anchors.fill: parent }

        // O topo: "Ajustes" e o X.
        Item {
            id: topo
            width: parent.width
            height: 58
            Text {
                anchors.verticalCenter: parent.verticalCenter
                x: 22
                text: "Ajustes"
                color: raiz.tema.texto
                font.family: raiz.tema.familia
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                anchors.rightMargin: 16
                width: 32; height: 32; radius: 9
                color: botaoX.containsMouse ? raiz.tema.realce : "transparent"
                Icone {
                    anchors.centerIn: parent
                    caminho: raiz.tema.icones.fechar
                    cor: raiz.tema.textoFraco
                    tamanho: 18
                }
                MouseArea {
                    id: botaoX
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: raiz.fechar()
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: raiz.tema.traco }
        }

        // As categorias.
        Column {
            id: categorias
            anchors { top: topo.bottom; left: parent.left; bottom: parent.bottom }
            width: 232
            topPadding: 12
            leftPadding: 12
            rightPadding: 12
            Repeater {
                model: raiz.categorias
                Column {
                    required property var modelData
                    required property int index
                    width: categorias.width - 24
                    Item {
                        width: parent.width
                        height: modelData.grupo ? (index === 0 ? 26 : 40) : 18
                        Text {
                            visible: !!modelData.grupo
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 7
                            x: 10
                            text: modelData.grupo
                            color: raiz.tema.muitoFraco
                            font.family: raiz.tema.familia
                            font.pixelSize: 12
                        }
                    }
                    Repeater {
                        model: modelData.itens
                        Rectangle {
                            required property var modelData
                            readonly property bool aqui: raiz.aba === modelData.id
                            width: parent.width
                            height: 36
                            radius: 9
                            color: aqui ? raiz.tema.realce : botaoCat.containsMouse ? raiz.tema.superficie : "transparent"
                            Icone {
                                anchors.verticalCenter: parent.verticalCenter
                                x: 10
                                caminho: raiz.tema.icones[modelData.icone] || ""
                                cor: aqui ? raiz.tema.persona : raiz.tema.textoMedio
                                tamanho: 18
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                x: 39
                                text: modelData.nome
                                color: aqui ? raiz.tema.texto : raiz.tema.textoMedio
                                font.family: raiz.tema.familia
                                font.pixelSize: 14
                            }
                            MouseArea {
                                id: botaoCat
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: { raiz.aba = modelData.id; rolagem.contentY = 0 }
                            }
                        }
                    }
                }
            }
        }
        Rectangle {
            anchors { top: topo.bottom; bottom: parent.bottom; left: categorias.right }
            width: 1
            color: raiz.tema.traco
        }

        // O conteúdo da categoria escolhida.
        Flickable {
            id: rolagem
            anchors { top: topo.bottom; left: categorias.right; right: parent.right; bottom: parent.bottom; leftMargin: 1 }
            contentHeight: pagina.height + 48
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: rolagem.contentHeight > rolagem.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }
            Loader {
                id: pagina
                x: 28; y: 22
                width: rolagem.width - 56
                sourceComponent: raiz.aba === "voz" ? paginaVoz : raiz.aba === "avisos" ? paginaAvisos
                               : raiz.aba === "uso" ? paginaUso : raiz.aba === "personas" ? paginaPersonas
                               : raiz.aba === "conexoes" ? (raiz.passo ? paginaPasso : paginaConexoes)
                               : raiz.aba === "sobre" ? paginaSobre
                               : paginaGeral
            }
        }
    }

    // -- as páginas -------------------------------------------------------------

    Component {
        id: paginaGeral
        Column {
            width: pagina.width
            Secao {
                titulo: "Você"
                Linha {
                    titulo: "Seu nome"
                    descricao: "Como o Jarvis e a Friday te chamam."
                    ultima: true
                    Rectangle {
                        width: 230; height: 36; radius: 9
                        color: raiz.tema.superficie
                        border.width: 1
                        border.color: campoNome.activeFocus ? raiz.tema.persona : raiz.tema.traco
                        enabled: !!raiz.ajustes
                        TextInput {
                            id: campoNome
                            anchors.fill: parent
                            anchors.leftMargin: 12; anchors.rightMargin: 12
                            verticalAlignment: TextInput.AlignVCenter
                            maximumLength: 30
                            clip: true
                            color: raiz.tema.texto
                            selectionColor: raiz.tema.persona
                            font.family: raiz.tema.familia
                            font.pixelSize: 14
                            text: raiz.ajustes ? (raiz.ajustes.nome || "") : ""
                            // Salva quando sai do campo ou dá Enter.
                            onEditingFinished: if (raiz.ajustes && text.trim() !== (raiz.ajustes.nome || "")) raiz.mudarNome(text.trim())
                            Text {
                                visible: !campoNome.text && !campoNome.activeFocus
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Como ele te chama"
                                color: raiz.tema.muitoFraco
                                font.family: raiz.tema.familia
                                font.pixelSize: 14
                            }
                        }
                    }
                }
            }
            Secao {
                titulo: "Este computador"
                Linha {
                    titulo: "Nome do PC"
                    ultima: true
                    Valor { text: raiz.ajustes && raiz.ajustes.pc ? raiz.ajustes.pc : "—" }
                }
            }
        }
    }

    Component {
        id: paginaVoz
        Column {
            width: pagina.width
            Secao {
                titulo: "Aparelhos de som"
                dica: raiz.som ? "" : (raiz.conectado ? "Procurando os aparelhos de som…" : "Aparece quando a NOVA subir.")
                Repeater {
                    model: raiz.som ? [
                        { tipo: "entrada", nome: "Microfone", lista: "entradas", padrao: "padrao_entrada" },
                        { tipo: "saida", nome: "Saída da voz", lista: "saidas", padrao: "padrao_saida" },
                    ] : []
                    Linha {
                        required property var modelData
                        required property int index
                        titulo: modelData.nome
                        ultima: index === 1
                        z: 2 - index  // o menu de cima abre por cima da linha de baixo
                        Seletor {
                            tema: raiz.tema
                            paraCima: false
                            alinharDireita: true
                            rotulo: modelData.nome
                            opcoes: raiz.opcoesDeSom(raiz.som[modelData.lista], raiz.som[modelData.padrao])
                            valor: raiz.som[modelData.tipo] || ""
                            onEscolhido: (valor) => raiz.escolherSom(modelData.tipo, valor)
                        }
                    }
                }
            }
            Secao {
                titulo: "Voz"
                // O volume da voz no PC. 100% é o de sempre e é o teto: daqui
                // só se abaixa (o volume já machucou o ouvido do Léo).
                Linha {
                    titulo: "Volume da voz"
                    descricao: "O volume do Jarvis e da Friday no PC, separado do resto."
                    ultima: true
                    enabled: !!raiz.ajustes
                    opacity: enabled ? 1 : 0.5
                    Row {
                        spacing: 12
                        Slider {
                            id: deslizador
                            anchors.verticalCenter: parent.verticalCenter
                            width: 220
                            from: 0; to: 100; stepSize: 5
                            value: raiz.ajustes ? raiz.ajustes.volume_voz : 100
                            // Manda só quando solta: arrastando não vira uma enxurrada de pedidos.
                            onPressedChanged: if (!pressed) raiz.mudarVolume(Math.round(value))
                            background: Rectangle {
                                x: deslizador.leftPadding
                                y: deslizador.topPadding + deslizador.availableHeight / 2 - height / 2
                                width: deslizador.availableWidth
                                height: 5
                                radius: 3
                                color: raiz.tema.tracoForte
                                Rectangle {
                                    width: deslizador.visualPosition * parent.width
                                    height: parent.height
                                    radius: 3
                                    color: raiz.tema.persona
                                }
                            }
                            handle: Rectangle {
                                x: deslizador.leftPadding + deslizador.visualPosition * (deslizador.availableWidth - width)
                                y: deslizador.topPadding + deslizador.availableHeight / 2 - height / 2
                                width: 15; height: 15; radius: 8
                                color: deslizador.pressed ? raiz.tema.texto : "#ffffff"
                            }
                        }
                        Valor {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 40
                            horizontalAlignment: Text.AlignRight
                            text: Math.round(deslizador.value) + "%"
                        }
                    }
                }
            }
            Secao {
                titulo: "Quem fala"
                visible: !!raiz.ajustes && raiz.ajustes.reconhece_voz !== undefined
                Linha {
                    titulo: "Reconhecer a tua voz"
                    descricao: raiz.ajustes && raiz.ajustes.reconhece_voz
                        ? "Só a tua voz pode apagar memória, mexer nos teus arquivos e outras coisas importantes."
                        : "Sem o perfil da tua voz: qualquer pessoa que falar perto do PC vale como você."
                    ultima: true
                    Valor { text: raiz.ajustes && raiz.ajustes.reconhece_voz ? "Ligado" : "Desligado" }
                }
            }
            // As vozes dubladas (jarvis/vozes.py): o instalador anota a pasta; se ela
            // mudar de lugar e a NOVA não achar sozinha, escolhe aqui.
            Secao {
                id: secaoVozes
                titulo: "Vozes dubladas"
                visible: !!raiz.ajustes && !!raiz.ajustes.vozes
                readonly property var v: raiz.ajustes && raiz.ajustes.vozes ? raiz.ajustes.vozes : ({})
                dica: v.jarvis || v.friday ? "Ficam em " + v.pasta
                                           : "Não achei as vozes dubladas: o Jarvis e a Friday falam com a voz reserva."
                Linha {
                    titulo: "Jarvis"
                    Valor { text: secaoVozes.v.jarvis ? "Encontrada" : "Voz reserva" }
                }
                Linha {
                    titulo: "Friday"
                    Valor { text: secaoVozes.v.friday ? "Encontrada" : "Voz reserva" }
                }
                Linha {
                    titulo: "Mudou a pasta de lugar?"
                    descricao: raiz.conexao.id === "vozes" && raiz.conexao.detalhe ? raiz.conexao.detalhe
                               : "Mostra onde ela está agora (a que tem o nova-vozes.json)."
                    ultima: true
                    Botao { texto: "Procurar pasta"; onClicado: pastaVozes.open() }
                }
                FolderDialog {
                    id: pastaVozes
                    title: "Onde estão as vozes da NOVA?"
                    onAccepted: {
                        raiz.pedirConexao("vozes", "escolher",
                                          decodeURIComponent(selectedFolder.toString().replace(/^file:\/\//, "")));
                        raiz.pedirAjustes();
                    }
                }
            }
        }
    }

    Component {
        id: paginaAvisos
        Column {
            width: pagina.width
            Secao {
                titulo: "Avisos"
                dica: "Nenhum aviso para ajustar ainda: eles aparecem aqui quando a conexão de cada um estiver ligada."
            }
        }
    }

    Component {
        id: paginaUso
        Column {
            width: pagina.width
            Secao {
                titulo: "Uso da assinatura"
                dica: raiz.usoCinco < 0 && raiz.usoSemana < 0 ? "Aparece depois do primeiro pedido ao Claude."
                                                              : "Quanto do limite do Claude já foi usado."
                Repeater {
                    model: [
                        { nome: "Últimas 5 horas", uso: raiz.usoCinco, volta: raiz.voltaCinco, dia: false },
                        { nome: "Esta semana", uso: raiz.usoSemana, volta: raiz.voltaSemana, dia: true },
                    ]
                    Column {
                        required property var modelData
                        visible: modelData.uso >= 0
                        width: parent.width
                        topPadding: 12
                        bottomPadding: 12
                        spacing: 9
                        readonly property color corDaBarra: modelData.uso >= 0.9 ? "#ff6b6b"
                                                          : modelData.uso >= 0.7 ? "#ffb454" : raiz.tema.persona
                        Item {
                            width: parent.width
                            height: 20
                            Text {
                                text: modelData.nome
                                color: raiz.tema.texto
                                font.family: raiz.tema.familia
                                font.pixelSize: 14
                            }
                            Text {
                                anchors.right: parent.right
                                text: Math.round(modelData.uso * 100) + "%  ·  " + raiz.quandoRenova(modelData.volta, modelData.dia)
                                color: raiz.tema.textoFraco
                                font.family: raiz.tema.familia
                                font.pixelSize: 13
                            }
                        }
                        Rectangle {
                            width: parent.width
                            height: 8
                            radius: 4
                            color: raiz.tema.superficie2
                            Rectangle {
                                width: Math.max(8, parent.width * Math.min(1, modelData.uso))
                                height: parent.height
                                radius: 4
                                color: parent.parent.corDaBarra
                                Behavior on width { NumberAnimation { duration: raiz.tema.lento; easing.type: Easing.OutCubic } }
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: paginaPersonas
        Column {
            width: pagina.width
            Secao {
                titulo: "Personas"
                dica: "Quem responde. As duas dividem a conversa, a memória e as ferramentas; muda o jeito de falar, a voz e a cor."
                Repeater {
                    model: [
                        { id: "jarvis", nome: "Jarvis", cor: "#4da3ff", descricao: "O mordomo de humor seco. Chamado com \"Hey Jarvis\"." },
                        { id: "friday", nome: "Friday", cor: raiz.corFriday || "#ff6fb5", descricao: "Carinhosa e animada. Chamada com \"Hey Friday\"." },
                    ]
                    Linha {
                        required property var modelData
                        required property int index
                        titulo: modelData.nome
                        descricao: modelData.descricao
                        ultima: index === 1
                        Row {
                            spacing: 14
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 22; height: 22; radius: 11
                                color: modelData.cor
                            }
                            Rectangle {
                                readonly property bool ativa: raiz.persona === modelData.id
                                anchors.verticalCenter: parent.verticalCenter
                                width: 96; height: 32; radius: 9
                                color: ativa ? Qt.rgba(0.22, 0.83, 0.62, 0.13) : botaoUsar.containsMouse ? raiz.tema.realce : "transparent"
                                border.width: ativa ? 0 : 1
                                border.color: raiz.tema.tracoForte
                                Text {
                                    anchors.centerIn: parent
                                    text: parent.ativa ? "Ativa" : "Usar"
                                    color: parent.ativa ? "#38d39f" : raiz.tema.textoMedio
                                    font.family: raiz.tema.familia
                                    font.pixelSize: 13
                                    font.weight: parent.ativa ? Font.Medium : Font.Normal
                                }
                                MouseArea {
                                    id: botaoUsar
                                    anchors.fill: parent
                                    enabled: !parent.ativa && raiz.conectado
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: raiz.escolherPersona(modelData.id)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: paginaConexoes
        Column {
            width: pagina.width
            Secao {
                titulo: "Conexões da NOVA"
                dica: raiz.ajustes && raiz.ajustes.conexoes
                      ? "O que o Jarvis e a Friday conseguem usar neste PC. Tudo começa desligado: liga só o que quiser."
                      : "Aparece quando a NOVA subir."
                Grid {
                    id: grade
                    width: parent.width
                    columns: 2
                    columnSpacing: 12
                    rowSpacing: 12
                    Repeater {
                        model: raiz.conexoes
                        Rectangle {
                            required property var modelData
                            readonly property var agora: raiz.estadoDe(modelData.id)
                            readonly property string falta: raiz.faltaPara(modelData.id)
                            width: (grade.width - grade.columnSpacing) / 2
                            height: Math.max(118, conteudoCartao.height + 28)
                            radius: 14
                            color: raiz.tema.superficie
                            border.width: 1
                            border.color: raiz.tema.traco
                            Rectangle {
                                x: 16; y: 14
                                width: 38; height: 38; radius: 11
                                color: raiz.tema.superficie2
                                Icone {
                                    anchors.centerIn: parent
                                    caminho: raiz.tema.icones[modelData.icone] || ""
                                    cor: raiz.tema.textoMedio
                                    tamanho: 18
                                }
                            }
                            Column {
                                id: conteudoCartao
                                x: 67; y: 14
                                width: parent.width - 67 - 16
                                spacing: 4
                                Text {
                                    text: modelData.nome
                                    color: raiz.tema.texto
                                    font.family: raiz.tema.familia
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    width: parent.width
                                    wrapMode: Text.WordWrap
                                    text: modelData.descricao + (agora.detalhe ? " (" + agora.detalhe + ")" : "")
                                    color: raiz.tema.textoFraco
                                    font.family: raiz.tema.familia
                                    font.pixelSize: 13
                                    lineHeight: 1.1
                                }
                                Item {
                                    width: parent.width
                                    height: 38
                                    Etiqueta {
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.verticalCenterOffset: 3
                                        estado: agora.estado
                                    }
                                    Text {
                                        visible: falta !== "" && agora.estado !== "conectado"
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.verticalCenterOffset: 3
                                        text: falta
                                        color: raiz.tema.muitoFraco
                                        font.family: raiz.tema.familia
                                        font.pixelSize: 12
                                    }
                                    Botao {
                                        visible: falta === "" || agora.estado === "conectado"
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.verticalCenterOffset: 3
                                        forte: agora.estado !== "conectado" && agora.estado !== "pronto"
                                        texto: modelData.id === "atalhos" ? "Como usar"
                                             : agora.estado === "conectado" || agora.estado === "pronto" ? "Gerenciar" : "Conectar"
                                        onClicado: raiz.abrirPasso(modelData.id)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            Secao {
                titulo: "Da tua conta do Claude"
                dica: "Gmail, Agenda, Drive e outros: liga no site do Claude e o Jarvis e a Friday já usam, aqui e no celular."
                Rectangle {
                    width: parent.width
                    height: Math.max(62, linhaConta.height + 28)
                    radius: 14
                    color: raiz.tema.superficie
                    border.width: 1
                    border.color: raiz.tema.traco
                    Flow {
                        id: linhaConta
                        x: 16
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 32 - botaoClaude.width - 16
                        spacing: 8
                        Text {
                            visible: !raiz.ajustes || !(raiz.ajustes.conectores || []).length
                            height: 30
                            verticalAlignment: Text.AlignVCenter
                            text: "Nenhum conector ligado na conta ainda."
                            color: raiz.tema.textoFraco
                            font.family: raiz.tema.familia
                            font.pixelSize: 13
                        }
                        Repeater {
                            model: raiz.ajustes ? (raiz.ajustes.conectores || []) : []
                            Rectangle {
                                required property var modelData
                                width: nomeConector.implicitWidth + 36
                                height: 30
                                radius: 15
                                color: raiz.tema.superficie2
                                Rectangle { x: 12; anchors.verticalCenter: parent.verticalCenter; width: 7; height: 7; radius: 4; color: "#38d39f" }
                                Text {
                                    id: nomeConector
                                    x: 25
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData
                                    color: raiz.tema.textoMedio
                                    font.family: raiz.tema.familia
                                    font.pixelSize: 13
                                }
                            }
                        }
                    }
                    Botao {
                        id: botaoClaude
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        texto: "Adicionar no claude.ai ↗"
                        onClicado: Qt.openUrlExternally("https://claude.ai/settings/connectors")
                    }
                }
            }
        }
    }

    // O passo a passo de uma conexão (protótipo aprovado em 28/10/2026). O
    // estado vem do PC (jarvis/conectar.py), pedido de novo a cada 2 s.
    Component {
        id: paginaPasso
        Column {
            id: passoCol
            width: pagina.width
            spacing: 0
            readonly property var info: raiz.infoDe(raiz.passo)

            // ‹ Conexões
            Item {
                width: voltaTxt.implicitWidth + 22
                height: 30
                Icone { anchors.verticalCenter: parent.verticalCenter; caminho: raiz.tema.icones.voltar || ""; cor: raiz.tema.textoFraco; tamanho: 15 }
                Text {
                    id: voltaTxt
                    x: 20
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Conexões"
                    color: raiz.tema.textoFraco
                    font.family: raiz.tema.familia
                    font.pixelSize: 13
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: raiz.fecharPasso() }
            }
            Item { width: 1; height: 10 }
            Row {
                spacing: 14
                Rectangle {
                    width: 46; height: 46; radius: 13
                    color: raiz.tema.superficie2
                    Icone { anchors.centerIn: parent; caminho: raiz.tema.icones[info.icone] || ""; cor: raiz.tema.persona; tamanho: 22 }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: info.nome || ""
                    color: raiz.tema.texto
                    font.family: raiz.tema.familia
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }
                Etiqueta { anchors.verticalCenter: parent.verticalCenter; estado: raiz.estadoPasso }
            }
            Item { width: 1; height: 18 }

            Loader {
                width: parent.width
                sourceComponent: raiz.passo === "whatsapp" ? passoWhatsapp : raiz.passo === "fora" ? passoFora
                               : raiz.passo === "celular" ? passoCelular : raiz.passo === "grupo" ? passoGrupo
                               : raiz.passo === "relogio" ? passoRelogio : raiz.passo === "musica" ? passoMusica
                               : passoAtalhos
            }
        }
    }

    Component {
        id: passoWhatsapp
        Column {
            width: parent ? parent.width : 0
            spacing: 16
            Column {
                visible: raiz.estadoPasso === "conectado"
                width: parent.width
                spacing: 14
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Conectado. O Jarvis e a Friday leem as mensagens deste PC e avisam quem te escreveu."
                    color: raiz.tema.textoMedio; font.family: raiz.tema.familia; font.pixelSize: 14
                }
                BotaoConfirmar { texto: "Desconectar"; onConfirmado: raiz.pedirConexao("whatsapp", "desconectar", "") }
            }
            Text {
                visible: raiz.cp.estado === "falta" || raiz.cp.estado === "erro"
                width: parent.width
                wrapMode: Text.WordWrap
                text: raiz.cp.detalhe || ""
                color: raiz.tema.textoMedio; font.family: raiz.tema.familia; font.pixelSize: 14
            }
            Row {
                visible: raiz.estadoPasso !== "conectado" && raiz.cp.estado !== "falta"
                width: parent.width
                spacing: 26
                Column {
                    width: parent.width - 300 - 26
                    Passo { numero: 1; agora: true; titulo: "No celular, abre o WhatsApp"; dica: "Android: os três pontinhos. iPhone: Configurações." }
                    Passo { numero: 2; titulo: "Toca em <b>Aparelhos conectados</b> → <b>Conectar um aparelho</b>" }
                    Passo { numero: 3; titulo: "Aponta a câmera para o código ao lado"; dica: "Pronto: o cartão vira \"Conectado\" sozinho."; ultimo: true }
                }
                CaixaQr {
                    qr: raiz.cp.qr || ""
                    espera: raiz.cp.estado === "expirou" || raiz.cp.estado === "saiu" ? "" : raiz.cp.qr ? "esperando o celular ler…" : "gerando o código…"
                    rodape: raiz.cp.estado === "expirou" || raiz.cp.estado === "saiu" ? "" : "O código troca a cada 20 segundos."
                    Botao {
                        visible: raiz.cp.estado === "expirou" || raiz.cp.estado === "saiu" || raiz.cp.estado === "desligado"
                        forte: true
                        texto: "Gerar outro código"
                        onClicado: raiz.pedirConexao("whatsapp", "conectar", "")
                    }
                }
            }
            Nota { texto: "As mensagens ficam só neste PC. O Jarvis e a Friday leem e avisam quem escreveu, mas mandar sempre pede o teu \"pode\" falado." }
        }
    }

    Component {
        id: passoFora
        Column {
            width: parent ? parent.width : 0
            spacing: 6
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "O Tailscale é um app grátis que liga o teu celular ao PC, em casa ou na rua, sem abrir nada para a internet."
                color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 13
                bottomPadding: 6
            }
            Passo {
                numero: 1; feito: !!raiz.cp.instalado; agora: !raiz.cp.instalado
                titulo: "Instalar o Tailscale neste PC"
                dica: raiz.cp.instalado ? "Achei ele instalado." : "Copia e roda no terminal (pede a tua senha do PC):"
                Comando { visible: !raiz.cp.instalado; texto: raiz.cp.comando_instalar || "" }
            }
            Passo {
                numero: 2; feito: !!raiz.cp.conta; agora: !!raiz.cp.instalado && !raiz.cp.conta
                titulo: "Entrar com a tua conta"
                dica: raiz.cp.conta ? "Entrou como " + raiz.cp.conta + "." : "Roda isto e entra no navegador que abrir:"
                Comando { visible: !!raiz.cp.instalado && !raiz.cp.conta; texto: raiz.cp.comando_entrar || "" }
            }
            Passo {
                numero: 3; feito: !!raiz.cp.celular; agora: !!raiz.cp.conta && !raiz.cp.celular
                titulo: "No celular, instala o Tailscale (Play Store ou App Store) e entra com a <b>mesma conta</b>"
                dica: raiz.cp.celular ? "Achei: " + raiz.cp.celular + "." : ""
                Espera { visible: !!raiz.cp.conta && !raiz.cp.celular; texto: "esperando o celular aparecer na tua conta…" }
            }
            Passo {
                numero: 4; feito: !!raiz.cp.servindo; agora: !!raiz.cp.celular && !raiz.cp.servindo; ultimo: true
                titulo: "Ligar o acesso do celular"
                dica: raiz.cp.detalhe ? raiz.cp.detalhe : raiz.cp.servindo ? "Ligado." : "A NOVA faz sozinha quando o celular aparecer."
            }
            BotaoConfirmar {
                visible: raiz.estadoPasso === "conectado"
                texto: "Desconectar"
                onConfirmado: raiz.pedirConexao("fora", "desconectar", "")
            }
        }
    }

    Component {
        id: passoCelular
        Column {
            width: parent ? parent.width : 0
            spacing: 16
            Column {
                visible: raiz.cp.estado === "falta"
                width: parent.width
                spacing: 12
                Text {
                    text: raiz.cp.detalhe || ""
                    color: raiz.tema.textoMedio; font.family: raiz.tema.familia; font.pixelSize: 14
                }
                Botao { forte: true; texto: "Ir para Fora de casa"; onClicado: raiz.abrirPasso("fora") }
            }
            Row {
                visible: raiz.cp.estado !== "falta"
                width: parent.width
                spacing: 26
                Column {
                    width: parent.width - 300 - 26
                    Passo { numero: 1; feito: true; titulo: "Fora de casa ligado"; dica: "O celular já alcança o PC." }
                    Passo { numero: 2; agora: raiz.cp.estado !== "conectado"; feito: raiz.cp.estado === "conectado"
                            titulo: "Abre a câmera do celular e aponta para o código"; dica: "Sem o app ainda? A página que abrir baixa ele." }
                    Passo { numero: 3; feito: raiz.cp.estado === "conectado"; ultimo: true
                            titulo: "Toca em <b>Abrir no app NOVA</b>"; dica: "O app abre já ligado a este PC, sem colar nada." }
                }
                CaixaQr {
                    qr: raiz.cp.qr || ""
                    espera: raiz.cp.estado === "conectado" ? "" : "esperando o celular…"
                    rodape: raiz.cp.estado === "conectado" ? "Um celular já está ligado. Outro pode ler o mesmo código."
                                                    : "O código leva a chave deste PC: não mostra para ninguém."
                }
            }
        }
    }

    Component {
        id: passoGrupo
        Column {
            width: parent ? parent.width : 0
            spacing: 16
            Text {
                visible: raiz.cp.estado === "falta"
                text: raiz.cp.detalhe || ""
                color: raiz.tema.textoMedio; font.family: raiz.tema.familia; font.pixelSize: 14
            }
            Row {
                visible: raiz.cp.estado !== "falta"
                width: parent.width
                spacing: 26
                Column {
                    width: parent.width - 300 - 26
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: "Escolhe o grupo onde o Jarvis responde quando alguém escreve \"Jarvis, …\"."
                        color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 13
                        bottomPadding: 8
                    }
                    Repeater {
                        model: raiz.cp.grupos || []
                        Item {
                            required property var modelData
                            required property int index
                            readonly property bool sim: modelData.jid === raiz.cp.escolhido
                            width: parent.width
                            height: 44
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                x: 4; width: 18; height: 18; radius: 9
                                color: "transparent"
                                border.width: 2
                                border.color: sim ? raiz.tema.persona : raiz.tema.tracoForte
                                Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: 4; color: raiz.tema.persona; visible: sim }
                            }
                            Text {
                                x: 34
                                width: parent.width - 34
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
                                text: modelData.nome
                                color: sim ? raiz.tema.texto : raiz.tema.textoMedio
                                font.family: raiz.tema.familia; font.pixelSize: 14
                            }
                            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: raiz.tema.traco }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: raiz.pedirConexao("grupo", "escolher", modelData.jid)
                            }
                        }
                    }
                }
                Rectangle {
                    width: 300
                    height: 76
                    radius: 16
                    color: raiz.tema.superficie
                    border.width: 1
                    border.color: raiz.tema.traco
                    Column {
                        x: 18
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 3
                        Text { text: "Responder no grupo"; color: raiz.tema.texto; font.family: raiz.tema.familia; font.pixelSize: 14 }
                        Text { text: raiz.cp.escolhido ? "Liga e desliga quando quiser." : "Escolhe um grupo primeiro."
                               color: raiz.tema.textoFraco; font.family: raiz.tema.familia; font.pixelSize: 12 }
                    }
                    Interruptor {
                        anchors.right: parent.right
                        anchors.rightMargin: 18
                        anchors.verticalCenter: parent.verticalCenter
                        opacity: raiz.cp.escolhido ? 1 : 0.4
                        ligado: !!raiz.cp.ligado
                        onTrocou: if (raiz.cp.escolhido) { raiz.mudarGrupo(!ligado); raiz.pedirConexao("grupo", "estado", "") }
                    }
                }
            }
            Nota { visible: raiz.cp.estado !== "falta"
                   texto: "No grupo ele conversa, pesquisa e anota recados. O que mexe nas tuas coisas (arquivos, mensagens, o PC) só acontece com o teu Sim no celular." }
        }
    }

    Component {
        id: passoRelogio
        Column {
            width: parent ? parent.width : 0
            spacing: 16
            Column {
                width: parent.width
                Passo { numero: 1; feito: raiz.estadoDe("celular").estado === "conectado"; agora: !feito
                        titulo: "Celular conectado"; dica: feito ? "" : "Liga o Celular primeiro, aqui em Conexões." }
                Passo { numero: 2; agora: raiz.estadoDe("celular").estado === "conectado"
                        titulo: "Instalar o NOVA no relógio"; dica: "Por enquanto é pela depuração sem fio do relógio: o Léo te ajuda nesse passo." }
                Passo { numero: 3; ultimo: true; feito: raiz.estadoPasso === "conectado"
                        titulo: "Abre o NOVA no relógio e toca no átomo"; dica: "O cartão vira \"Conectado\" quando ele aparecer." }
            }
            Nota { texto: "Funciona com relógio Wear OS (Galaxy Watch e parecidos), sempre pelo celular." }
        }
    }

    Component {
        id: passoMusica
        Column {
            width: parent ? parent.width : 0
            Passo {
                numero: 1; feito: raiz.estadoPasso === "conectado"; agora: !feito
                titulo: feito ? "O programa que toca o som (o mpv) está instalado" : "Falta o programa que toca o som (o mpv). Copia e roda no terminal:"
                dica: feito ? "" : "Pede a tua senha do PC. A NOVA não roda nada como administrador sozinha."
                Comando { visible: raiz.estadoPasso !== "conectado"; texto: raiz.cp.comando || "" }
            }
            Passo { numero: 2; ultimo: true; feito: raiz.estadoPasso === "conectado"
                    titulo: "Pede: <b>\"Jarvis, toca uma música\"</b>" }
        }
    }

    Component {
        id: passoAtalhos
        Column {
            width: parent ? parent.width : 0
            spacing: 16
            Column {
                width: parent.width
                Passo { numero: 1; titulo: "Pede: <b>\"Jarvis, cria um atalho pro Discord\"</b>"; dica: "Vale programa, pasta ou site." }
                Passo { numero: 2; ultimo: true; titulo: "Depois é só falar: <b>\"abre o Discord\"</b>" }
            }
            Nota { texto: "Os atalhos ficam neste PC. " + (raiz.estadoDe("atalhos").detalhe ? "Agora: " + raiz.estadoDe("atalhos").detalhe + "." : "Nenhum ainda.") }
        }
    }

    Component {
        id: paginaSobre
        Column {
            width: pagina.width
            Secao {
                titulo: "Sobre a NOVA"
                Repeater {
                    model: [
                        ["Versão", "beta 0.17.0"],
                        ["Conexão", raiz.conectado ? "Ligado" : "Esperando a NOVA subir"],
                    ]
                    Linha {
                        required property var modelData
                        required property int index
                        titulo: modelData[0]
                        ultima: index === 1
                        Valor { text: modelData[1] }
                    }
                }
                Text {
                    width: parent.width
                    topPadding: 16
                    wrapMode: Text.WordWrap
                    textFormat: Text.StyledText
                    lineHeight: 1.45
                    color: raiz.tema.textoMedio
                    font.family: raiz.tema.familia
                    font.pixelSize: 14
                    text: "A NOVA é uma assistente que mora no teu PC e conversa contigo por voz, pela janela, "
                        + "pelo celular e pelo relógio. Ela tem duas personas: o <font color='" + raiz.tema.texto
                        + "'><b>Jarvis</b></font>, mais sério e direto, e a <font color='" + raiz.tema.texto
                        + "'><b>Friday</b></font>, mais carinhosa e animada. Você escolhe com quem quer falar, "
                        + "e os dois conhecem a tua rotina, lembram das tuas coisas e cuidam do que você pedir."
                }
            }
            Secao {
                titulo: "Teclas"
                Repeater {
                    model: [
                        ["Novo chat", "Ctrl + N"],
                        ["Procurar conversa", "Ctrl + K"],
                        ["Voltar pra conversa de agora", "Esc"],
                        ["Enviar / quebrar a linha", "Enter / Shift + Enter"],
                        ["Colar texto, ou anexar imagem e arquivo copiados", "Ctrl + V"],
                    ]
                    Linha {
                        required property var modelData
                        required property int index
                        titulo: modelData[0]
                        ultima: index === 4
                        Tecla { texto: modelData[1] }
                    }
                }
            }
        }
    }
}
