package main

// Jarvis (09/11/2026, feito pelo Léo, ajustado para a ponte): arquiva toda
// mensagem que chega, inclusive as que depois são apagadas para todos
// (revoke). O banco é o memoria_viva.db do Jarvis, tabela arquivo_mensagens
// (a mesma do jarvis/nucleo/whatsapp_arquivo.py).
//
//	GET /api/arquivo?chat=<jid>   -> as últimas 300 do chat
//	GET /api/arquivo?q=<termo>    -> procura em todos

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"

	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/types/events"
)

var arq *sql.DB

func abrirArquivo() error {
	pasta := filepath.Join(os.Getenv("HOME"), ".local/share/jarvis")
	os.MkdirAll(pasta, 0o700)
	var err error
	arq, err = sql.Open("sqlite3", "file:"+filepath.Join(pasta, "memoria_viva.db")+"?_journal_mode=WAL&_busy_timeout=5000")
	if err != nil {
		return err
	}
	_, err = arq.Exec(`CREATE TABLE IF NOT EXISTS arquivo_mensagens (
		id TEXT PRIMARY KEY, chat TEXT, autor TEXT, ts REAL,
		texto TEXT, midia TEXT, apagada INTEGER DEFAULT 0, tipo TEXT)`)
	return err
}

// arquivarMensagem: chamada no começo do handleMessage, para toda mensagem.
func arquivarMensagem(msg *events.Message) {
	if arq == nil || msg.Message == nil {
		return
	}
	// Apagada para todos: o celular manda um "revoke" com o id da original.
	if p := msg.Message.GetProtocolMessage(); p != nil {
		if p.GetType() == waE2E.ProtocolMessage_REVOKE && p.GetKey() != nil {
			arq.Exec(`UPDATE arquivo_mensagens SET apagada = 1 WHERE id = ?`, p.GetKey().GetID())
		}
		return
	}
	texto := extractTextContent(msg.Message)
	midia, nome, _, _, _, _, _ := extractMediaInfo(msg.Message)
	if texto == "" && midia == "" {
		return
	}
	tipo := "texto"
	if midia != "" {
		tipo = "midia"
		if nome != "" {
			midia += ": " + nome
		}
	}
	ts := float64(msg.Info.Timestamp.Unix())
	// Mantém o "apagada" se ela já tinha sido marcada (a original chega uma vez só).
	arq.Exec(`INSERT INTO arquivo_mensagens (id, chat, autor, ts, texto, midia, tipo) VALUES (?,?,?,?,?,?,?)
		ON CONFLICT(id) DO UPDATE SET texto = excluded.texto, midia = excluded.midia`,
		msg.Info.ID, msg.Info.Chat.String(), msg.Info.Sender.User, ts, texto, midia, tipo)
}

func servirArquivo(w http.ResponseWriter, r *http.Request) {
	if arq == nil {
		http.Error(w, "arquivo fechado", 503)
		return
	}
	chat, termo := r.URL.Query().Get("chat"), r.URL.Query().Get("q")
	var linhas *sql.Rows
	var err error
	if termo != "" {
		linhas, err = arq.Query(`SELECT chat, autor, ts, texto, apagada FROM arquivo_mensagens
			WHERE texto LIKE ? ORDER BY ts DESC LIMIT 100`, "%"+termo+"%")
	} else {
		linhas, err = arq.Query(`SELECT chat, autor, ts, texto, apagada FROM arquivo_mensagens
			WHERE chat = ? ORDER BY ts DESC LIMIT 300`, chat)
	}
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	defer linhas.Close()
	saida := []map[string]any{}
	for linhas.Next() {
		var c, a string
		var t sql.NullString
		var ts float64
		var ap int
		if linhas.Scan(&c, &a, &ts, &t, &ap) != nil {
			continue
		}
		saida = append(saida, map[string]any{"chat": c, "autor": a, "ts": ts, "texto": t.String, "apagada": ap})
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(saida)
}
