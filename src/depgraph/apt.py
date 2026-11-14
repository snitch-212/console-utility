"""Получение прямых зависимостей пакета из индекса Packages (apt).

Индекс Packages репозитория Ubuntu состоит из абзацев, разделённых пустыми
строками. Каждый абзац описывает одну версию пакета полями «Имя: значение».
Менеджеры пакетов и сторонние библиотеки не используются.
"""

import gzip
import lzma
import re
import urllib.error
import zlib
from dataclasses import dataclass
from typing import Optional
from urllib.request import Request, urlopen

from depgraph.errors import PackageNotFoundError, RepositoryError

REQUEST_TIMEOUT = 60
USER_AGENT = "depgraph/0.2"
GZIP_MAGIC = b"\x1f\x8b"
XZ_MAGIC = b"\xfd7zXZ\x00"
DEPENDENCY_FIELDS = ("Pre-Depends", "Depends")
KEPT_FIELDS = frozenset(("Package", "Version", *DEPENDENCY_FIELDS))
BLOCK_SEPARATOR = re.compile(r"\n[ \t]*\n")
RELATION_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9+.-]*)"
    r"(?::(?P<arch>[A-Za-z0-9-]+))?"
    r"(?:\s*\(\s*(?P<operator><<|<=|=|>=|>>|<|>)\s*"
    r"(?P<version>[A-Za-z0-9][^)\s]*)\s*\))?"
    r"$"
)


@dataclass(frozen=True)
class Relation:
    """Ссылка на пакет: имя и необязательное ограничение версии."""

    name: str
    arch: Optional[str] = None
    operator: Optional[str] = None
    version: Optional[str] = None

    def __str__(self):
        """Вернуть запись в синтаксисе Debian: имя[:арх] [(опер версия)]."""
        text = self.name
        if self.arch:
            text += f":{self.arch}"
        if self.operator:
            text += f" ({self.operator} {self.version})"
        return text


@dataclass(frozen=True)
class Dependency:
    """Одно требование из поля Depends: одна или несколько альтернатив."""

    alternatives: tuple

    def __str__(self):
        """Вернуть альтернативы через « | »."""
        return " | ".join(str(item) for item in self.alternatives)


def download(url):
    """Скачать содержимое по URL (http, https или file) и вернуть байты."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise RepositoryError(
            f"сервер ответил {error.code} {error.reason}: {url}"
        ) from error
    except OSError as error:
        raise RepositoryError(
            f"не удалось получить индекс {url}: {error}"
        ) from error


def decompress(data, url):
    """Распаковать индекс по сигнатуре: gzip, xz или обычный текст."""
    try:
        if data.startswith(GZIP_MAGIC):
            return gzip.decompress(data)
        if data.startswith(XZ_MAGIC):
            return lzma.decompress(data)
    except (OSError, EOFError, zlib.error, lzma.LZMAError) as error:
        raise RepositoryError(
            f"повреждённый архив индекса {url}: {error}"
        ) from error
    return data


def parse_block(block):
    """Разобрать абзац индекса в словарь нужных полей."""
    fields = {}
    current = None
    for line in block.splitlines():
        if line.startswith((" ", "\t")):
            if current:
                fields[current] += " " + line.strip()
            continue
        name, _, value = line.partition(":")
        current = name if name in KEPT_FIELDS else None
        if current:
            fields[current] = value.strip()
    return fields


def find_entries(text, name):
    """Вернуть записи пакета с точным именем name (все его версии)."""
    marker = f"Package: {name}"
    entries = []
    for block in BLOCK_SEPARATOR.split(text):
        if marker not in block:
            continue
        fields = parse_block(block)
        if fields.get("Package") == name:
            entries.append(fields)
    return entries


def select_version(entries, name, version):
    """Выбрать запись нужной версии или объяснить, чего не хватает."""
    for fields in entries:
        if fields.get("Version") == version:
            return fields
    if not entries:
        raise PackageNotFoundError(f"пакет {name!r} не найден в индексе")
    available = ", ".join(item.get("Version", "?") for item in entries)
    raise PackageNotFoundError(
        f"версия {version!r} пакета {name!r} не найдена; "
        f"доступные версии: {available}"
    )


def parse_relation(text):
    """Разобрать одну ссылку на пакет, например «libc6 (>= 2.34)»."""
    match = RELATION_RE.match(text.strip())
    if match is None:
        raise RepositoryError(f"не удалось разобрать зависимость {text!r}")
    return Relation(**match.groupdict())


def parse_dependency(entry):
    """Разобрать требование с альтернативами, разделёнными «|»."""
    parts = entry.split("|")
    return Dependency(tuple(parse_relation(part) for part in parts))


def parse_dependencies(text):
    """Разобрать значение поля Depends в список требований."""
    entries = (part.strip() for part in text.split(","))
    return [parse_dependency(entry) for entry in entries if entry]


def join_dependency_fields(fields):
    """Объединить поля Pre-Depends и Depends в одну строку."""
    values = (fields.get(key, "") for key in DEPENDENCY_FIELDS)
    return ", ".join(value for value in values if value)


def get_direct_dependencies(url, name, version):
    """Вернуть прямые зависимости пакета name версии version.

    Индекс Packages (обычный, .gz или .xz) загружается по url.
    """
    data = decompress(download(url), url)
    text = data.decode("utf-8", errors="replace")
    entries = find_entries(text, name)
    fields = select_version(entries, name, version)
    return parse_dependencies(join_dependency_fields(fields))
