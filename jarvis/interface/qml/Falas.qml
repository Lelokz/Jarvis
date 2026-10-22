import QtQuick

// As falas de uma conversa, com as regras de como elas entram na lista.
//
// Papéis: quem ("voce" | "jarvis" | "painel" | "atividade"), texto, origem
// (voz, texto, celular...), titulo (do painel), quando (segundos desde a
// época), perguntando, opcoes (as da pergunta, uma por linha: viram botões),
// passos (as atividades seguidas, uma por linha), escrevendo + bloco (a
// fala dele chegando em pedaços; beta 0.5) e animar (fala nova chegando; o
// histórico entra parado).
ListModel {
    id: raiz

    // Quantas falas estão sendo escritas agora (a conversa esconde o
    // "Pensando…" enquanto o texto aparece).
    property int abertas: 0
    // A resposta formatada chega como painel sem título e, logo depois, a
    // versão FALADA dela (jarvis_disse): essa não entra. Marca até quando.
    property real _pularFalaAte: 0

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
                 perguntando: extra.perguntando === true,
                 opcoes: (extra.opcoes || []).join("\n"), passos: "",
                 escrevendo: false, bloco: 0, animar: animar };
    }

    // -- o texto chegando em pedaços ------------------------------------------
    function escrever(bloco, delta) {
        for (var i = count - 1; i >= 0 && i >= count - 12; i--) {
            var f = get(i);
            if (f.escrevendo && f.bloco === bloco) {
                setProperty(i, "texto", f.texto + delta);
                return;
            }
        }
        var nova = _nova("jarvis", delta, {}, true);
        nova.escrevendo = true;
        nova.bloco = bloco;
        append(nova);
        abertas += 1;
    }

    // O texto inteiro chegou: troca a fala que estava sendo escrita (a mais
    // antiga aberta, porque os textos inteiros chegam na mesma ordem).
    function _fecharEscrita(quem, texto, extra) {
        for (var i = 0; i < count; i++) {
            if (get(i).escrevendo) {
                setProperty(i, "quem", quem);
                setProperty(i, "texto", texto);
                setProperty(i, "escrevendo", false);
                setProperty(i, "perguntando", !!(extra && extra.perguntando));
                setProperty(i, "opcoes", ((extra && extra.opcoes) || []).join("\n"));
                abertas = Math.max(0, abertas - 1);
                return true;
            }
        }
        return false;
    }

    // Acabou o turno: o que sobrou aberto vira texto normal (interrompido),
    // ou some (descartar: o rápido passou o pedido para o Opus).
    function encerrarEscrita(descartar) {
        for (var i = count - 1; i >= 0; i--) {
            if (!get(i).escrevendo) continue;
            if (descartar) remove(i);
            else setProperty(i, "escrevendo", false);
        }
        abertas = 0;
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
        if (quem === "jarvis" && _agora() < _pularFalaAte) {
            // A versão falada do painel que acabou de chegar.
            _pularFalaAte = 0;
            if (extra && extra.perguntando)
                for (var j = count - 1; j >= 0; j--)
                    if (get(j).quem === "painel") {
                        setProperty(j, "perguntando", true);
                        setProperty(j, "opcoes", (extra.opcoes || []).join("\n"));
                        break;
                    }
            return;
        }
        if (quem === "jarvis") {
            _fecharPerguntas();
            if (_fecharEscrita("jarvis", texto, extra))
                return;
        }
        if (_ehAFalaDoPainel(quem)) {
            if (extra && extra.perguntando) {
                setProperty(count - 1, "perguntando", true);
                setProperty(count - 1, "opcoes", (extra.opcoes || []).join("\n"));
            }
            return;
        }
        _fecharPerguntas();
        append(_nova(quem, texto, extra, true));
    }

    function mostrar(titulo, texto) {
        _fecharPerguntas();
        if (!titulo) {
            _pularFalaAte = _agora() + 15;
            if (_fecharEscrita("painel", texto, {}))
                return;
        }
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
        abertas = 0;
        _pularFalaAte = 0;
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
                origem: f.origem, titulo: f.titulo, quando: f.quando, opcoes: f.opcoes,
                perguntando: f.perguntando === true && i === anteriores.length - 1
            }, false));
        }
    }
}
