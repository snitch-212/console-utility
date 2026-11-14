"""Разбор и проверка параметров командной строки."""

import argparse
import os
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from depgraph.errors import ConfigError

MODE_REMOTE = "remote"
MODE_TEST = "test"
REPO_MODES = (MODE_REMOTE, MODE_TEST)
DEFAULT_MODE = MODE_REMOTE
DEFAULT_MAX_DEPTH = 1
MIN_DEPTH = 1
URL_SCHEMES = ("http", "https", "file")
NOT_SET = "(не задана)"

PACKAGE_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]+$")
TEST_PACKAGE_RE = re.compile(r"^[A-Z]+$")
VERSION_RE = re.compile(r"^(?:[0-9]+:)?[0-9][A-Za-z0-9.+~-]*$")

PACKAGE_RULES = {
    MODE_REMOTE: (
        PACKAGE_RE,
        "имя apt-пакета: от 2 символов, строчные латинские буквы, "
        "цифры и знаки + - .",
    ),
    MODE_TEST: (
        TEST_PACKAGE_RE,
        "в тестовом репозитории имена состоят из больших латинских букв",
    ),
}


class ConfigParser(argparse.ArgumentParser):
    """Разборщик аргументов, сообщающий об ошибках через ConfigError."""

    def error(self, message):
        """Вместо вывода справки и выхода сообщить об ошибке исключением."""
        raise ConfigError(f"{message} (подсказка: --help)")


@dataclass(frozen=True)
class Config:
    """Параметры, заданные пользователем."""

    package: str
    repo: str
    repo_mode: str
    package_version: Optional[str]
    max_depth: int

    def as_pairs(self):
        """Вернуть параметры списком пар (ключ, значение)."""
        version = self.package_version or NOT_SET
        return [
            ("package", self.package),
            ("repo", self.repo),
            ("repo-mode", self.repo_mode),
            ("package-version", version),
            ("max-depth", str(self.max_depth)),
        ]


def build_parser():
    """Создать разборщик аргументов командной строки."""
    parser = ConfigParser(
        prog="depgraph",
        description="Инструмент визуализации графа зависимостей apt.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "-p", "--package", help="имя анализируемого пакета"
    )
    parser.add_argument(
        "-r", "--repo",
        help="URL репозитория (режим remote) или путь к файлу "
             "тестового репозитория (режим test)",
    )
    parser.add_argument(
        "-m", "--repo-mode",
        help="режим работы с репозиторием: remote (по умолчанию) или test",
    )
    parser.add_argument(
        "-V", "--package-version",
        help="версия пакета (обязательна в режиме remote)",
    )
    parser.add_argument(
        "-d", "--max-depth",
        help="максимальная глубина анализа, целое >= 1 (по умолчанию 1)",
    )
    return parser


def validate_mode(raw):
    """Проверить режим работы с репозиторием."""
    if raw is None:
        return DEFAULT_MODE
    if raw not in REPO_MODES:
        allowed = ", ".join(REPO_MODES)
        raise ConfigError(
            f"неизвестный режим {raw!r} (--repo-mode), допустимо: {allowed}"
        )
    return raw


def validate_package(raw, mode):
    """Проверить имя пакета с учётом режима работы."""
    if not raw or not raw.strip():
        raise ConfigError("не задано имя пакета (--package)")
    pattern, hint = PACKAGE_RULES[mode]
    if not pattern.match(raw):
        raise ConfigError(f"недопустимое имя пакета {raw!r}: {hint}")
    return raw


def check_url(raw):
    """Проверить, что строка является URL с поддерживаемой схемой."""
    try:
        parsed = urlparse(raw)
    except ValueError as error:
        raise ConfigError(f"некорректный URL репозитория: {error}") from None
    if parsed.scheme not in URL_SCHEMES:
        allowed = ", ".join(URL_SCHEMES)
        raise ConfigError(
            f"неподдерживаемая схема URL {parsed.scheme!r}, "
            f"допустимо: {allowed}"
        )
    location = parsed.path if parsed.scheme == "file" else parsed.netloc
    if not location:
        raise ConfigError(f"в URL не указан адрес: {raw!r}")
    return raw


def check_test_path(raw):
    """Проверить, что путь указывает на читаемый файл."""
    if not os.path.exists(raw):
        raise ConfigError(f"файл тестового репозитория не найден: {raw}")
    if not os.path.isfile(raw):
        raise ConfigError(f"путь не является файлом: {raw}")
    if not os.access(raw, os.R_OK):
        raise ConfigError(f"нет прав на чтение файла: {raw}")
    return raw


def validate_repo(raw, mode):
    """Проверить URL или путь к репозиторию в зависимости от режима."""
    if not raw or not raw.strip():
        raise ConfigError("не задан репозиторий (--repo)")
    if mode == MODE_TEST:
        return check_test_path(raw)
    return check_url(raw)


def validate_version(raw, mode):
    """Проверить версию пакета: в режиме remote она обязательна."""
    if raw is None:
        if mode == MODE_REMOTE:
            raise ConfigError("не задана версия пакета (--package-version)")
        return None
    if not VERSION_RE.match(raw):
        raise ConfigError(f"недопустимая версия пакета {raw!r}")
    return raw


def validate_depth(raw):
    """Проверить максимальную глубину анализа."""
    if raw is None:
        return DEFAULT_MAX_DEPTH
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(
            f"глубина анализа (--max-depth) должна быть целым числом: "
            f"{raw!r}"
        ) from None
    if value < MIN_DEPTH:
        raise ConfigError(
            f"глубина анализа (--max-depth) должна быть не меньше "
            f"{MIN_DEPTH}, получено {value}"
        )
    return value


def parse_config(argv=None):
    """Разобрать аргументы командной строки и вернуть Config."""
    args = build_parser().parse_args(argv)
    mode = validate_mode(args.repo_mode)
    return Config(
        package=validate_package(args.package, mode),
        repo=validate_repo(args.repo, mode),
        repo_mode=mode,
        package_version=validate_version(args.package_version, mode),
        max_depth=validate_depth(args.max_depth),
    )
