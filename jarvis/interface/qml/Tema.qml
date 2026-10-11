import QtQuick

// Cores, raios e durações num lugar só. Mudar a cara da interface é mexer
// aqui, e não caçar número solto espalhado pelos arquivos.
QtObject {
    readonly property color fundo:        "#0a0c10"
    readonly property color superficie:   "#11151c"
    readonly property color traco:        "#1c2431"
    readonly property color texto:        "#e6ebf2"
    readonly property color textoFraco:   "#7e879b"
    readonly property color perigo:       "#ff6b6b"
    // A borda da pergunta que ainda espera resposta. Fixa: se seguisse a cor
    // do estado, a bolha mudaria de cor junto com o átomo.
    readonly property color pergunta:     "#ffb454"

    // Uma cor por estado. É o que permite saber o que ele está fazendo sem ler
    // nada — o pedido do Léo: "quero saber em que estado ele está olhando".
    // Uma cor por estado, e a regra é o contraste entre eles: é assim que o
    // Léo reconhece de olho, sem ler.
    //
    // "escutando" e "falando" se alternam o tempo todo numa conversa, então
    // não podem morar na mesma família — eram os dois verde-água. Agora a SUA
    // voz é fria (verde) e a DELE é quente (âmbar).
    //
    // "dormindo" é acinzentado, mas não apagado: é o estado que ele passa o dia
    // inteiro, e precisa parecer em espera, não desligado. Quem é apagado de
    // verdade é o sem conexão.
    function corDoEstado(estado) {
        switch (estado) {
        case "dormindo":  return "#7387a8";
        case "ouvindo":   return "#4da3ff";
        case "escutando": return "#38d39f";
        case "pensando":  return "#9b7bff";
        case "falando":   return "#ffb454";
        default:          return "#39435a";
        }
    }

    function rotuloDoEstado(estado) {
        switch (estado) {
        case "dormindo":  return "DORMINDO";
        case "ouvindo":   return "OUVINDO";
        case "escutando": return "ESCUTANDO VOCÊ";
        case "pensando":  return "PENSANDO";
        case "falando":   return "FALANDO";
        default:          return "SEM CONEXÃO";
        }
    }

    // Só Noto Sans e DejaVu existem nesta máquina; a primeira é a padrão do
    // sistema. Declarada aqui para o texto não depender do que o Qt escolher.
    //
    // Uma família, e não uma lista: conferido nesta versão do Qt, o `Text` tem
    // `font.family` e NÃO tem `font.families`.
    readonly property string familia: "Noto Sans"

    readonly property int raioJanela: 20
    readonly property int raioBotao: 8

    // Durações. Nada muda num piscar seco: tudo que troca de valor passa por
    // um Behavior com uma destas.
    readonly property int rapido: 160
    readonly property int normal: 320
    readonly property int lento: 640
}
