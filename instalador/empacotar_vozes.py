#!/usr/bin/env python3
"""Monta o pacote de vozes dubladas da NOVA (um .zip) para o Léo subir no Drive.

Vai só o que é voz (os programas que tocam elas o instalador instala à parte):
    nova-vozes.json                       a etiqueta (jarvis/vozes.py)
    jarvis/rvc/jarvis-dublado.pth, .index o timbre do JARVIS (servidor_rvc.py)
    friday/modelo/friday-emilia-v1.safetensors, vocab.txt
    friday/ref/, friday/pronuncia.txt     (servidor_friday.py --pasta)

O .zip vai sem compressão (os modelos não encolhem) para o HD, e o fim mostra
o tamanho e o sha256 que o instalador confere depois de baixar.

    .venv/bin/python instalador/empacotar_vozes.py [pasta de saída]
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ORIGEM = Path.home() / ".local/share/jarvis"
SAIDA = Path("/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Arquivo/NOVA - Pacote de vozes")
VERSAO = 1

ARQUIVOS = {
    "jarvis/rvc/jarvis-dublado.pth": ORIGEM / "voz-jarvis/rvc/jarvis-dublado.pth",
    "jarvis/rvc/jarvis-dublado.index": ORIGEM / "voz-jarvis/rvc/jarvis-dublado.index",
    "friday/modelo/friday-emilia-v1.safetensors": ORIGEM / "voz-friday/modelo/friday-emilia-v1.safetensors",
    "friday/modelo/vocab.txt": ORIGEM / "voz-friday/modelo/vocab.txt",
    "friday/pronuncia.txt": ORIGEM / "voz-friday/pronuncia.txt",
    **{f"friday/ref/{a.name}": a for a in sorted((ORIGEM / "voz-friday/ref").iterdir()) if a.is_file()},
}


def main() -> int:
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else SAIDA
    faltando = [str(o) for o in ARQUIVOS.values() if not o.is_file()]
    if faltando:
        print("Faltam:", *faltando, sep="\n  ")
        return 1
    saida.mkdir(parents=True, exist_ok=True)
    pacote = saida / f"nova-vozes-{VERSAO}.zip"
    etiqueta = {"nova_vozes": VERSAO, "vozes": ["jarvis", "friday"]}
    with zipfile.ZipFile(pacote, "w", zipfile.ZIP_STORED) as z:
        z.writestr("nova-vozes.json", json.dumps(etiqueta, ensure_ascii=False, indent=1))
        for dentro, origem in ARQUIVOS.items():
            z.write(origem, dentro)
    soma = hashlib.sha256()
    with open(pacote, "rb") as f:
        while bloco := f.read(1 << 20):
            soma.update(bloco)
    print(f"{pacote}\n  {pacote.stat().st_size / 1e9:.2f} GB, {len(ARQUIVOS) + 1} arquivos\n  sha256 {soma.hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
