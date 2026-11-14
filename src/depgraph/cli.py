"""Точка входа командной строки (этап 1: вывод параметров)."""

import sys

from depgraph.config import parse_config
from depgraph.errors import DepGraphError

EXIT_OK = 0
EXIT_ERROR = 1


def print_config(config):
    """Вывести все параметры пользователя в формате «ключ: значение»."""
    for key, value in config.as_pairs():
        print(f"{key}: {value}")


def main(argv=None):
    """Запустить приложение и вернуть код завершения."""
    try:
        config = parse_config(argv)
    except DepGraphError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_ERROR
    print_config(config)
    return EXIT_OK
