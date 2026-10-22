import QtQuick

// As falas de uma conversa, com as regras de como elas entram na lista.
//
// Papéis: quem ("voce" | "jarvis" | "painel" | "atividade"), texto, origem
// (voz, texto, celular...), titulo (do painel), quando (segundos desde a
// época), perguntando, passos (as atividades seguidas, uma por linha) e
// animar (fala nova chegando; o histórico entra parado).
ListModel {
    id: raiz

    function _agora() { return Date.now() / 1000; }

    // Só a última fala pode estar perguntando: qualquer fala nova responde
    // ou atropela a pergunta.
    function _fecharPerguntas() {
        for (var i = 0; i < count; i++)
            if (get(i).perguntando) setProperty(i, "perguntando", false);
    }

    function _nova(quem, texto, extra, animar) {
        extra = extra || {};
        return { quem: quem, texto: texto || "", origem: extra.origem || "",
                 titulo: extra.titulo || "", quando: extra.quando || _agora(),
                 perguntando: extra.perguntando === true, passos: "",
                 animar: animar };
    }

    // A resposta formatada (lista, código) chega como painel SEM título e,
    // logo depois, a versão falada dela. Na janela fica só a formatada.
    function _ehAFalaDoPainel(quem) {
        if (quem !== "jarvis" || count === 0)
            return false;
        var ultima = get(count - 1);
        return ultima.quem === "painel" && ultima.titulo === "" && _agora() - ultima.quando < 15;
    }

    function acrescentar(quem, texto, extra) {
        if (_ehAFalaDoPainel(quem)) {
            if (extra && extra.perguntando)
                setProperty(count - 1, "perguntando", true);
            return;
        }
        _fecharPerguntas();
        append(_nova(quem, texto, extra, true));
    }

    function mostrar(titulo, texto) {
        _fecharPerguntas();
        append(_nova("painel", texto, { titulo: titulo }, true));
    }

    // O que ele está fazendo. Atividades seguidas viram UM item, que guarda
    // todos os passos; a conversa não enche de linhas.
    function atividade(texto) {
        var ultima = count - 1;
        if (ultima >= 0 && get(ultima).quem === "atividade") {
            var passos = get(ultima).passos;
            setProperty(ultima, "passos", passos ? passos + "\n" + texto : texto);
            setProperty(ultima, "texto", texto);
        } else {
            var nova = _nova("atividade", texto, {}, true);
            nova.passos = texto;
            append(nova);
        }
    }

    // A conversa que JÁ existia: entra de uma vez e sem animação.
    function preencher(anteriores) {
        clear();
        for (var i = 0; i < anteriores.length; i++) {
            var f = anteriores[i];
            if (f.quem === "atividade") {
                var ultima = count - 1;
                if (ultima >= 0 && get(ultima).quem === "atividade") {
                    setProperty(ultima, "passos", get(ultima).passos + "\n" + f.texto);
                    setProperty(ultima, "texto", f.texto);
                } else {
                    var a = _nova("atividade", f.texto, { quando: f.quando }, false);
                    a.passos = f.texto;
                    append(a);
                }
                continue;
            }
            // Na conversa ao vivo, a fala que repete o painel não entra.
            if (f.quem === "jarvis" && count > 0) {
                var antes = get(count - 1);
                if (antes.quem === "painel" && antes.titulo === ""
                        && Math.abs((f.quando || 0) - antes.quando) < 15)
                    continue;
            }
            append(_nova(f.quem, f.texto, {
                origem: f.origem, titulo: f.titulo, quando: f.quando,
                perguntando: f.perguntando === true && i === anteriores.length - 1
            }, false));
        }
    }
}
