"""Arquivos do jogador (recordes, configurações) na pasta de dados do usuário. Não depende do pygame."""
import json
import os
import sys

APP_DIR = 'cobra-presentes'


def data_dir():
    """Pasta de dados do usuário (fica fora do projeto, então sobrevive a mudanças no código)."""
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return os.path.join(base, APP_DIR)


def read_json(path):
    """Conteúdo do arquivo, ou None se ele não existe ou está estragado."""
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_json(path, data):
    """Grava num arquivo temporário e troca de uma vez, para não corromper se o jogo fechar no meio."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
