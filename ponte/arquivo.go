package main

// Arquiva todo evento do whatsmeow, inclusive revoke e mídia que "some".

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"time"

	_ "modernc.org/sqlite"
)

var arq *sql.DB

func abrirArquivo() error {
	pasta := filepath.Join(os.Getenv("HOME"), ".local/share/jarvis")
	os.MkdirAll(pasta, 0o700)
	var err error
	arq, err = sql.Open("sqlite", filepath.Join(pasta, "memoria_viva.db"))
	if err != nil {
		return err
	}
	_, err = arq.Exec(`CREATE TABLE IF NOT EXISTS arquivo_mensagens (
		id TEXT PRIMARY KEY, chat TEXT, autor TEXT, ts REAL,
		texto TEXT, midia TEXT, apagada INTEGER DEFAULT 0, tipo TEXT)`)
	return err
}

func arquivar(id, chat, autor, texto, midia, tipo string) {
	if arq == nil {
		return
	}
	arq.Exec(`INSERT OR REPLACE INTO arquivo_mensagens
		(id, chat, autor, ts, texto, midia, tipo) VALUES (?,?,?,?,?,?,?)`,
		id, chat, autor, float64(time.Now().Unix()), texto, midia, tipo)
}

func marcarApagada(id string) {
	if arq != nil {
		arq.Exec(`UPDATE arquivo_mensagens SET apagada = 1 WHERE id = ?`, id)
	}
}

// chamar de dentro do handler de eventos, no case de mensagem:
func arquivarEvento(evt map[string]any) {
	info, _ := evt["Info"].(map[string]any)
	if info == nil {
		return
	}
	id, _ := info["ID"].(string)
	chat, _ := info["Chat"].(string)
	autor, _ := info["Sender"].(string)
	tipo, _ := info["Type"].(string)
	switch {
	case tipo == "revoke" || evt["Apagada"] == true:
		marcarApagada(id)
	case tipo == "media":
		arquivar(id, chat, autor, "", extrairMidia(evt), "midia")
	default:
		texto, _ := evt["Texto"].(string)
		arquivar(id, chat, autor, texto, "", "texto")
	}
}

// GET /api/arquivo?chat=...&q=...
func servirArquivo(w http.ResponseWriter, r *http.Request) {
	chat, termo := r.URL.Query().Get("chat"), r.URL.Query().Get("q")
	var linhas *sql.Rows
	var err error
	if termo != "" {
		linhas, err = arq.Query(`SELECT chat, autor, ts, texto, apagada FROM arquivo_mensagens
			WHERE texto LIKE ? ORDER BY ts DESC LIMIT 100`, "%"+termo+"%")
	} else {
		linhas, err = arq.Query(`SELECT autor, ts, texto, apagada FROM arquivo_mensagens
			WHERE chat = ? ORDER BY ts DESC LIMIT 300`, chat)
	}
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	defer linhas.Close()
	saida := []map[string]any{}
	for linhas.Next() {
		linha := map[string]any{}
		if termo != "" {
			var c, a, t string
			var ts float64
			var ap int
			linhas.Scan(&c, &a, &ts, &t, &ap)
			linha = map[string]any{"chat": c, "autor": a, "ts": ts, "texto": t, "apagada": ap}
		} else {
			var a, t string
			var ts float64
			var ap int
			linhas.Scan(&a, &ts, &t, &ap)
			linha = map[string]any{"autor": a, "ts": ts, "texto": t, "apagada": ap}
		}
		saida = append(saida, linha)
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(saida)
}