"""Точка входа командной строки (этап 2: прямые зависимости пакета)."""

import sys

from depgraph.apt import get_direct_dependencies
from depgraph.config import MODE_TEST, parse_config
from depgraph.errors import DepGraphError, NotSupportedError

EXIT_OK = 0
EXIT_ERROR = 1


def print_dependencies(config, dependencies):
    """Вывести прямые зависимости пакета, по одной на строку."""
    title = f"Прямые зависимости {config.package} {config.package_version}"
    if not dependencies:
        print(f"{title}: нет")
        return
    print(f"{title} ({len(dependencies)}):")
    for dependency in dependencies:
        print(f"  {dependency}")


def run(config):
    """Выполнить этап 2: получить и вывести прямые зависимости."""
    if config.repo_mode == MODE_TEST:
        raise NotSupportedError(
            "режим test будет реализован на этапе 3, "
            "пока используйте --repo-mode remote"
        )
    dependencies = get_direct_dependencies(
        config.repo, config.package, config.package_version
    )
    print_dependencies(config, dependencies)


def main(argv=None):
    """Запустить приложение и вернуть код завершения."""
    try:
        run(parse_config(argv))
    except DepGraphError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK
