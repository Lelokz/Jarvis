CREATE TABLE IF NOT EXISTS fatos (
  id INTEGER PRIMARY KEY, tipo TEXT NOT NULL, ts REAL NOT NULL,
  fonte TEXT, texto TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS fatos_fts USING fts5(
  texto, content='fatos', content_rowid='id', tokenize="unicode61 remove_diacritics 2"
);
CREATE TRIGGER IF NOT EXISTS fatos_ai AFTER INSERT ON fatos BEGIN
  INSERT INTO fatos_fts(rowid, texto) VALUES (new.id, new.texto);
END;
CREATE TABLE IF NOT EXISTS vetores (id INTEGER PRIMARY KEY, vetor BLOB NOT NULL);

CREATE TABLE IF NOT EXISTS rostos (
  id INTEGER PRIMARY KEY, nome TEXT NOT NULL, vetor BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS encontros (
  id INTEGER PRIMARY KEY, rosto_id INTEGER, ts REAL, lugar TEXT
);

CREATE TABLE IF NOT EXISTS arquivo_mensagens (
  id TEXT PRIMARY KEY, chat TEXT, autor TEXT, ts REAL,
  texto TEXT, midia TEXT, apagada INTEGER DEFAULT 0, tipo TEXT
);