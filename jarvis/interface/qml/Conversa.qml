import QtQuick

// O que foi pedido e o que ele respondeu, em ordem. O histórico da lateral
// (passada 4) lê o .jsonl da sessão; isto aqui é só o que aconteceu com a
// janela aberta.
Item {
    id: raiz
    property var tema

    // Só a última fala pode estar perguntando: qualquer fala nova responde ou
    // atropela a pergunta, e a borda dela apaga.
    function _fecharPerguntas() {
        for (var i = 0; i < falas.count; i++)
            if (falas.get(i).perguntando) falas.setProperty(i, "perguntando", false);
    }

    function acrescentar(quem, texto, acao, perguntando) {
        _fecharPerguntas();
        falas.append({ quem: quem, texto: texto, acao: acao || "", titulo: "",
                       perguntando: perguntando === true, animar: true });
    }

    // O que o Claude mandou para a janela: código, lista, passos. Um cartão
    // largo, com markdown e texto que dá para selecionar e copiar.
    function mostrar(titulo, texto) {
        falas.append({ quem: "painel", texto: texto, acao: "", titulo: titulo || "",
                       perguntando: false, animar: true });
    }

    // O que ele está fazendo agora. Uma linha só por sequência: cada
    // atividade nova troca a anterior, em vez de encher a conversa de passos.
    function atividade(texto) {
        var ultima = falas.count - 1;
        if (ultima >= 0 && falas.get(ultima).quem === "atividade")
            falas.setProperty(ultima, "texto", texto);
        else
            falas.append({ quem: "atividade", texto: texto, acao: "", titulo: "",
                           perguntando: false, animar: true });
    }

    // A conversa que JÁ existia, vinda do assistente ao conectar. Entra de uma
    // vez e sem animação: não é fala nova chegando, e animar tudo faria a
    // janela parecer que está recebendo a conversa inteira agora.
    function preencher(anteriores) {
        falas.clear();
        for (var i = 0; i < anteriores.length; i++) {
            var f = anteriores[i];
            falas.append({ quem: f.quem, texto: f.texto || "",
                           acao: f.acao || "", titulo: f.titulo || "",
                           perguntando: f.perguntando === true && i === anteriores.length - 1,
                           animar: false });
        }
        raiz.seguindo = true;
        Qt.callLater(lista.positionViewAtEnd);
    }

    function limpar() { falas.clear(); }

    property string dica: ""
    readonly property bool vazia: falas.count === 0

    // "Estou acompanhando o fim da conversa." Só muda quando o Léo arrasta a
    // lista — e não a cada fala nova.
    //
    // Antes isso era decidido por `atYEnd` na hora da fala nova, e não
    // funcionava: logo depois de preencher o histórico as bolhas ainda não
    // tinham sido medidas, a lista se achava fora do fim, e daí em diante
    // nenhuma fala nova aparecia sem arrastar à mão.
    property bool seguindo: true

    ListModel { id: falas }

    // Conversa vazia é um vão grande no meio da janela. Uma linha só, apagada,
    // dizendo por onde se começa.
    Text {
        anchors.centerIn: parent
        width: parent.width - 80
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        visible: opacity > 0
        opacity: raiz.vazia && raiz.dica !== "" ? 0.45 : 0.0
        text: raiz.dica
        color: raiz.tema.textoFraco
        font.family: raiz.tema.familia
        font.pixelSize: 13
        renderType: Text.NativeRendering
        Behavior on opacity { NumberAnimation { duration: raiz.tema.lento } }
    }

    ListView {
        id: lista
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        clip: true
        spacing: 2
        model: falas
        // A conversa acompanha o fim sozinha: quem está lendo o meio segura a
        // rolagem, e quem está no fim continua vendo o que chega.
        // `Qt.callLater` porque rolar antes de a lista se medir não vai a lugar
        // nenhum: a altura das bolhas ainda não existe.
        onCountChanged: if (raiz.seguindo) Qt.callLater(positionViewAtEnd)
        onMovementEnded: raiz.seguindo = atYEnd
        // Os papéis vêm do `model`, e não de propriedades obrigatórias: o
        // Mensagem já declara essas propriedades, e redeclará-las aqui fazia
        // cada uma ser atribuída a si mesma.
        delegate: Mensagem {
            tema: raiz.tema
            quem: model.quem
            texto: model.texto
            acao: model.acao
            titulo: model.titulo
            perguntando: model.perguntando
            animar: model.animar
        }
    }

    // Um fiapo de sombra no topo, para a conversa parecer passar por baixo da
    // esfera em vez de começar do nada.
    Rectangle {
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: 24
        gradient: Gradient {
            GradientStop { position: 0.0; color: raiz.tema.fundo }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }
}
