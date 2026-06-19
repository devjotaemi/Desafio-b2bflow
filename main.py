"""Entrypoint fino do motor de disparo.

Garante que ``python main.py`` execute o fluxo de disparo de ponta a ponta:

    python main.py             # dispara
    python main.py --dry-run   # simula, sem chamar a Z-API
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite rodar `python main.py`sem instalar o pacote (adiciona src/ ao path).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import typer

from dispatch.cli import dispatch

if __name__ == "__main__":
    typer.run(dispatch)
