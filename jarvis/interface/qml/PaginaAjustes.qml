import QtQuick
import QtQuick.Controls.Basic

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
    signal mudarNotificar(bool ligado)
    signal mudarNome(string nome)
    signal mudarGrupo(bool ligado)

    property string aba: "geral"

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
    readonly property var conexoes: [
        { id: "whatsapp", nome: "WhatsApp", icone: "whats", descricao: "Ler e mandar mensagens, e avisar quem te escreveu." },
        { id: "grupo", nome: "Grupo do WhatsApp", icone: "grupo", descricao: "Responde no grupo da família quando chamam o Jarvis." },
        { id: "celular", nome: "Celular", icone: "celular", descricao: "O app NOVA: conversar e receber avisos pelo celular." },
        { id: "relogio", nome: "Relógio", icone: "relogio", descricao: "Falar pelo relógio. Precisa do celular conectado." },
        { id: "fora", nome: "Fora de casa", icone: "globo", descricao: "Usar o celular longe do Wi-Fi de casa (Tailscale)." },
        { id: "escola", nome: "Escola", icone: "escola", descricao: "Notas, tarefas e recados do Estudante Online (SC)." },
        { id: "musica", nome: "Música", icone: "musica", descricao: "Tocar música e vídeo do YouTube pelo PC." },
        { id: "atalhos", nome: "Atalhos", icone: "raio", descricao: "Programas e pastas que ele abre pelo nome." },
    ]
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
    onAbertoChanged: if (aberto) painel.forceActiveFocus()

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
                               : raiz.aba === "conexoes" ? paginaConexoes : raiz.aba === "sobre" ? paginaSobre
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
        }
    }

    Component {
        id: paginaAvisos
        Column {
            width: pagina.width
            Secao {
                titulo: "Avisos"
                dica: raiz.ajustes && raiz.ajustes.tem_escola ? "" : "Nenhum aviso para ajustar ainda: eles aparecem aqui quando a conexão de cada um estiver ligada."
                Linha {
                    visible: !!raiz.ajustes && !!raiz.ajustes.tem_escola
                    titulo: "Notificações da escola"
                    descricao: "Avisa quando aparecer nota, tarefa ou recado novo."
                    ultima: true
                    Interruptor {
                        ligado: raiz.ajustes ? raiz.ajustes.notificar_escola : true
                        onTrocou: raiz.mudarNotificar(!ligado)
                    }
                }
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
                titulo: "Conexões"
                dica: raiz.ajustes && raiz.ajustes.conexoes ? "O que o Jarvis e a Friday conseguem usar neste PC."
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
                                    height: 34
                                    Etiqueta {
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.verticalCenterOffset: 3
                                        estado: agora.estado
                                    }
                                    // O grupo liga e desliga daqui (o mesmo interruptor de antes).
                                    Interruptor {
                                        visible: modelData.id === "grupo" && !!raiz.ajustes && !!raiz.ajustes.grupo_jid
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.verticalCenterOffset: 3
                                        ligado: raiz.ajustes ? !!raiz.ajustes.grupo_ligado : false
                                        onTrocou: raiz.mudarGrupo(!ligado)
                                    }
                                }
                            }
                        }
                    }
                }
            }
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
