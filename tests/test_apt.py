"""Тесты получения прямых зависимостей из индекса Packages."""

import gzip
import lzma
import os
import pathlib
import tempfile
import unittest

from depgraph.apt import (
    Dependency,
    Relation,
    get_direct_dependencies,
    parse_dependencies,
    parse_relation,
)
from depgraph.errors import PackageNotFoundError, RepositoryError

DATA_FILE = pathlib.Path(__file__).parent / "data" / "Packages"
BASH_DEPENDENCIES = [
    "libc6 (>= 2.34)",
    "libtinfo6 (>= 6)",
    "base-files (>= 2.1.0)",
    "debianutils (>= 2.15)",
]


def as_strings(dependencies):
    """Преобразовать список требований в список строк."""
    return [str(item) for item in dependencies]


class ParseTest(unittest.TestCase):
    """Разбор синтаксиса полей Depends."""

    def test_relation_with_version(self):
        """Имя и ограничение версии разбираются отдельно."""
        relation = parse_relation("libc6 (>= 2.34)")
        self.assertEqual(relation, Relation("libc6", None, ">=", "2.34"))

    def test_relation_with_arch(self):
        """Квалификатор архитектуры отделяется от имени."""
        relation = parse_relation("python3:any")
        self.assertEqual(relation, Relation("python3", "any"))

    def test_all_operators(self):
        """Поддерживаются все операторы сравнения версий."""
        for operator in ("<<", "<=", "=", ">=", ">>"):
            with self.subTest(operator=operator):
                relation = parse_relation(f"pkg ({operator} 1.0)")
                self.assertEqual(relation.operator, operator)

    def test_invalid_relation(self):
        """Некорректная запись зависимости вызывает RepositoryError."""
        with self.assertRaises(RepositoryError):
            parse_relation("libc6 (>> )")

    def test_alternatives(self):
        """Альтернативы через « | » образуют одно требование."""
        result = parse_dependencies("a | b (>= 1), c")
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0].alternatives), 2)
        self.assertEqual(as_strings(result), ["a | b (>= 1)", "c"])

    def test_empty_field(self):
        """Пустое значение поля даёт пустой список."""
        self.assertEqual(parse_dependencies(""), [])

    def test_dependency_type(self):
        """Элементы списка являются объектами Dependency."""
        result = parse_dependencies("a")
        self.assertIsInstance(result[0], Dependency)


class RepositoryTest(unittest.TestCase):
    """Получение зависимостей из файла индекса через URL."""

    def fetch(self, name, version, url=None):
        """Получить зависимости из тестового индекса."""
        return get_direct_dependencies(
            url or DATA_FILE.as_uri(), name, version
        )

    def test_pre_depends_and_depends(self):
        """Pre-Depends и Depends объединяются в порядке записи."""
        result = self.fetch("bash", "5.1-6ubuntu1")
        self.assertEqual(as_strings(result), BASH_DEPENDENCIES)

    def test_exact_name_match(self):
        """Пакет bash-completion не путается с пакетом bash."""
        result = self.fetch("bash-completion", "1:2.11-5ubuntu1")
        self.assertEqual(as_strings(result), ["bash (>= 4.1)"])

    def test_alternatives_and_continuation(self):
        """Строки продолжения и альтернативы разбираются верно."""
        result = self.fetch("demo-editor", "1.2-1")
        self.assertEqual(
            as_strings(result),
            [
                "libc6 (>= 2.34)",
                "python3:any",
                "mail-transport-agent | postfix (>= 3.0) | exim4",
            ],
        )

    def test_selects_requested_version(self):
        """Из нескольких версий выбирается именно заданная."""
        self.assertEqual(self.fetch("demo-lib", "1.0-1"), [])
        result = self.fetch("demo-lib", "2.0-1")
        self.assertEqual(as_strings(result), ["libc6 (>= 2.34)"])

    def test_unknown_package(self):
        """Отсутствующий пакет вызывает PackageNotFoundError."""
        with self.assertRaises(PackageNotFoundError) as context:
            self.fetch("no-such-package", "1.0")
        self.assertIn("не найден", str(context.exception))

    def test_unknown_version_lists_available(self):
        """При неизвестной версии перечисляются доступные."""
        with self.assertRaises(PackageNotFoundError) as context:
            self.fetch("bash", "9.9")
        message = str(context.exception)
        self.assertIn("5.1-6ubuntu1, 5.1-6ubuntu1.1", message)

    def test_missing_file(self):
        """Недоступный индекс вызывает RepositoryError."""
        with self.assertRaises(RepositoryError):
            self.fetch("bash", "1", url="file:///no/such/Packages")

    def test_compressed_indexes(self):
        """Индексы .gz и .xz распознаются по сигнатуре."""
        raw = DATA_FILE.read_bytes()
        variants = {
            "Packages.gz": gzip.compress(raw),
            "Packages.xz": lzma.compress(raw),
        }
        with tempfile.TemporaryDirectory() as folder:
            for filename, payload in variants.items():
                path = pathlib.Path(folder, filename)
                path.write_bytes(payload)
                with self.subTest(filename=filename):
                    result = self.fetch("bash", "5.1-6ubuntu1", path.as_uri())
                    self.assertEqual(as_strings(result), BASH_DEPENDENCIES)

    def test_corrupted_archive(self):
        """Повреждённый архив вызывает RepositoryError."""
        broken = b"\x1f\x8b" + os.urandom(8)
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder, "Packages.gz")
            path.write_bytes(broken)
            with self.assertRaises(RepositoryError):
                self.fetch("bash", "1", path.as_uri())
