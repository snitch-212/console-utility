"""Тесты разбора и проверки параметров командной строки."""

import os
import tempfile
import unittest

from depgraph.config import (
    DEFAULT_MAX_DEPTH,
    MODE_REMOTE,
    MODE_TEST,
    parse_config,
)
from depgraph.errors import ConfigError

REMOTE_URL = (
    "http://archive.ubuntu.com/ubuntu/dists/jammy/"
    "main/binary-amd64/Packages.gz"
)
DEFAULTS = {
    "package": "bash",
    "repo": REMOTE_URL,
    "package-version": "5.1-6ubuntu1",
    "max-depth": "2",
}


def build_args(**overrides):
    """Собрать аргументы командной строки; значение None убирает опцию."""
    options = dict(DEFAULTS)
    for key, value in overrides.items():
        options[key.replace("_", "-")] = value
    args = []
    for key, value in options.items():
        if value is not None:
            args.append(f"--{key}={value}")
    return args


class RemoteModeTest(unittest.TestCase):
    """Проверка параметров в режиме remote."""

    def assert_error(self, fragment, **overrides):
        """Убедиться, что разбор падает с ConfigError и нужным текстом."""
        with self.assertRaises(ConfigError) as context:
            parse_config(build_args(**overrides))
        self.assertIn(fragment, str(context.exception))

    def test_valid_config(self):
        """Корректные параметры разбираются без ошибок."""
        config = parse_config(build_args())
        self.assertEqual(config.package, "bash")
        self.assertEqual(config.repo, REMOTE_URL)
        self.assertEqual(config.repo_mode, MODE_REMOTE)
        self.assertEqual(config.package_version, "5.1-6ubuntu1")
        self.assertEqual(config.max_depth, 2)

    def test_defaults(self):
        """Режим и глубина имеют значения по умолчанию."""
        config = parse_config(build_args(max_depth=None))
        self.assertEqual(config.repo_mode, MODE_REMOTE)
        self.assertEqual(config.max_depth, DEFAULT_MAX_DEPTH)

    def test_short_options(self):
        """Короткие формы опций работают так же, как длинные."""
        argv = ["-p", "bash", "-r", REMOTE_URL, "-V", "1.0", "-d", "3"]
        config = parse_config(argv)
        self.assertEqual(config.max_depth, 3)
        self.assertEqual(config.package_version, "1.0")

    def test_unknown_option(self):
        """Неизвестная опция сообщается как ConfigError, а не выходом."""
        with self.assertRaises(ConfigError):
            parse_config(build_args() + ["--unknown=1"])

    def test_option_without_value(self):
        """Опция без значения сообщается как ConfigError."""
        with self.assertRaises(ConfigError):
            parse_config(["--package"])

    def test_missing_package(self):
        """Имя пакета обязательно."""
        self.assert_error("--package", package=None)

    def test_blank_package(self):
        """Пустое имя пакета недопустимо."""
        self.assert_error("--package", package="  ")

    def test_invalid_package_names(self):
        """Имена не по правилам Debian отклоняются."""
        for name in ("Bad_Name", "a", "bash!", "-bash", "BASH"):
            with self.subTest(name=name):
                self.assert_error("недопустимое имя пакета", package=name)

    def test_missing_repo(self):
        """URL репозитория обязателен."""
        self.assert_error("--repo", repo=None)

    def test_unsupported_scheme(self):
        """Схема URL, кроме http, https и file, отклоняется."""
        self.assert_error("неподдерживаемая схема", repo="ftp://host/x")

    def test_path_instead_of_url(self):
        """Обычный путь в режиме remote не является URL."""
        self.assert_error("неподдерживаемая схема", repo="/tmp/Packages")

    def test_url_without_host(self):
        """URL без адреса сервера отклоняется."""
        self.assert_error("не указан адрес", repo="http://")

    def test_malformed_url(self):
        """Синтаксически неверный URL отклоняется."""
        self.assert_error("некорректный URL", repo="http://[::1")

    def test_unknown_mode(self):
        """Неизвестный режим отклоняется."""
        self.assert_error("неизвестный режим", repo_mode="local")

    def test_missing_version(self):
        """В режиме remote версия пакета обязательна."""
        self.assert_error("--package-version", package_version=None)

    def test_invalid_versions(self):
        """Версии с недопустимым синтаксисом отклоняются."""
        for version in ("", "v1.0", "1.0 beta", "1:2:3", "!"):
            with self.subTest(version=version):
                self.assert_error(
                    "недопустимая версия", package_version=version
                )

    def test_epoch_version(self):
        """Версия с эпохой и ревизией Debian допустима."""
        config = parse_config(build_args(package_version="1:2.5-1ubuntu1"))
        self.assertEqual(config.package_version, "1:2.5-1ubuntu1")

    def test_depth_not_integer(self):
        """Глубина должна быть целым числом."""
        for depth in ("abc", "2.5", ""):
            with self.subTest(depth=depth):
                self.assert_error("целым числом", max_depth=depth)

    def test_depth_too_small(self):
        """Глубина меньше минимальной отклоняется."""
        for depth in ("0", "-3"):
            with self.subTest(depth=depth):
                self.assert_error("не меньше", max_depth=depth)


class TestModeTest(unittest.TestCase):
    """Проверка параметров в режиме test."""

    def parse_with_file(self, **overrides):
        """Разобрать аргументы режима test с существующим файлом."""
        options = {"package": "A", "package_version": None}
        options.update(overrides)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "graph.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("A: B\n")
            args = build_args(repo_mode=MODE_TEST, repo=path, **options)
            return parse_config(args)

    def test_valid_test_config(self):
        """Файл, имя из заглавных букв и отсутствие версии допустимы."""
        config = self.parse_with_file()
        self.assertEqual(config.repo_mode, MODE_TEST)
        self.assertEqual(config.package, "A")
        self.assertIsNone(config.package_version)

    def test_missing_file(self):
        """Несуществующий файл тестового репозитория отклоняется."""
        args = build_args(
            repo_mode=MODE_TEST, repo="/no/such/file.txt", package="A"
        )
        with self.assertRaises(ConfigError) as context:
            parse_config(args)
        self.assertIn("не найден", str(context.exception))

    def test_directory_instead_of_file(self):
        """Каталог вместо файла отклоняется."""
        with tempfile.TemporaryDirectory() as folder:
            args = build_args(repo_mode=MODE_TEST, repo=folder, package="A")
            with self.assertRaises(ConfigError) as context:
                parse_config(args)
        self.assertIn("не является файлом", str(context.exception))

    def test_lowercase_name_rejected(self):
        """В режиме test имена пакетов только из больших латинских букв."""
        with self.assertRaises(ConfigError) as context:
            self.parse_with_file(package="bash")
        self.assertIn("больших латинских", str(context.exception))
