import QtQuick

// Cores, fontes, raios e durações num lugar só. Mudar a cara da interface é
// mexer aqui, e não caçar número solto espalhado pelos arquivos.
//
// A janela grande (22/10/2026) segue o protótipo que o Léo aprovou: fundo
// quase preto, barra lateral um tom acima, cartões mais um tom, e as cores
// dos estados do átomo de sempre.
QtObject {
    readonly property color fundo:        "#0a0c10"
    readonly property color lateral:      "#0d1016"
    readonly property color superficie:   "#131821"
    readonly property color superficie2:  "#181e29"
    readonly property color realce:       "#1f2738"   // item escolhido, hover forte
    readonly property color traco:        "#1f2734"
    readonly property color tracoForte:   "#2a3446"
    readonly property color texto:        "#e6ebf2"
    readonly property color textoMedio:   "#b9c1cf"
    readonly property color textoFraco:   "#7e879b"
    readonly property color muitoFraco:   "#4d5568"
    readonly property color perigo:       "#ff6b6b"
    readonly property color codigo:       "#0c0f15"
    // A borda da pergunta que ainda espera resposta. Fixa: se seguisse a cor
    // do estado, a bolha mudaria de cor junto com o átomo.
    readonly property color pergunta:     "#ffb454"
    // A cor da persona (o Jarvis é azul; a segunda persona terá a dela). A
    // janela troca pela escolhida nos Ajustes (beta 0.7.0).
    property color persona:               "#4da3ff"

    // Uma cor por estado, e a regra é o contraste entre eles: é assim que o
    // Léo reconhece de olho, sem ler. A voz DELE é fria (verde), a do Jarvis
    // é quente (âmbar); dormindo é acinzentado mas vivo; sem conexão, apagado.
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

    function dicaDoEstado(estado) {
        switch (estado) {
        case "dormindo":  return "Fala \"Hey Jarvis\" pra acordar";
        case "ouvindo":   return "Pode falar, ou escreve";
        case "escutando": return "Tô te ouvindo…";
        case "pensando":  return "Trabalhando no pedido";
        case "falando":   return "Respondendo";
        default:          return "Esperando o Jarvis subir";
        }
    }

    // A Inter vem junto do projeto (jarvis/interface/fontes, licença OFL); o
    // interface.py a carrega antes da janela. É variável: o peso funciona.
    readonly property string familia: "Inter Variable"
    readonly property string mono: "DejaVu Sans Mono"

    readonly property int raioBotao: 8

    // Durações. Nada muda num piscar seco: tudo que troca de valor passa por
    // um Behavior com uma destas.
    readonly property int rapido: 140
    readonly property int normal: 280
    readonly property int lento: 560

    // Ícones: caminhos SVG numa caixa de 24×24 (o componente Icone desenha).
    readonly property var icones: ({
        mais: "M12 5v14M5 12h14",
        lupa: "M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14M20 20l-3.5-3.5",
        voz: "M9 6a3 3 0 0 1 6 0v5a3 3 0 0 1-6 0zM5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21",
        relogio: "M10 6h4a4 4 0 0 1 4 4v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4v-4a4 4 0 0 1 4-4zM9 6l1-3h4l1 3M9 18l1 3h4l1-3",
        celular: "M9.5 2.5h5a2.5 2.5 0 0 1 2.5 2.5v14a2.5 2.5 0 0 1-2.5 2.5h-5A2.5 2.5 0 0 1 7 19V5a2.5 2.5 0 0 1 2.5-2.5zM11 18.5h2",
        teclado: "M5 6h14a2.5 2.5 0 0 1 2.5 2.5v7A2.5 2.5 0 0 1 19 18H5a2.5 2.5 0 0 1-2.5-2.5v-7A2.5 2.5 0 0 1 5 6zM7.5 14.5h9M6.5 10.5h1M10 10.5h1M13.5 10.5h1M17 10.5h1",
        memoria: "M9 4a3 3 0 0 0-3 3v.2A3 3 0 0 0 4 10a3 3 0 0 0 1 2.2A3 3 0 0 0 6 17a3 3 0 0 0 3 3V4zM15 4a3 3 0 0 1 3 3v.2A3 3 0 0 1 20 10a3 3 0 0 1-1 2.2A3 3 0 0 1 18 17a3 3 0 0 1-3 3V4z",
        ajustes: "M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4",
        clipe: "M16.8 7.2L9 15a2.4 2.4 0 0 0 3.4 3.4L20 10.8a4.2 4.2 0 0 0-6-6L5.6 13.2a6.2 6.2 0 0 0 8.8 8.8L21 15.4",
        enviar: "M12 19V5M5.5 11.5L12 5l6.5 6.5",
        raio: "M13 2.5L5 13.5h6l-1 8 8-11h-6z",
        copiar: "M9 9h10a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-8a2 2 0 0 1-2-2zM5 15V5a2 2 0 0 1 2-2h8",
        certo: "M5 12.5l4.5 4.5L19 7",
        seta: "M7 10l5 5 5-5",
        direita: "M10 7l5 5-5 5",
        minimizar: "M6 12h12",
        maximizar: "M7 7h10v10H7z",
        restaurar: "M9 9h8v8H9zM7 15V7h8",
        fechar: "M7 7l10 10M17 7L7 17",
        voltar: "M15 6l-6 6 6 6",
        pessoa: "M12 4a4 4 0 1 1 0 8a4 4 0 1 1 0-8M4.5 20a7.5 7.5 0 0 1 15 0"
    })
}
