"""Тесты командной строки: вывод зависимостей и обработка ошибок."""

import contextlib
import io
import pathlib
import unittest

from depgraph.cli import EXIT_ERROR, EXIT_OK, main

INDEX_URL = (pathlib.Path(__file__).parent / "data" / "Packages").as_uri()


def run_main(argv):
    """Запустить main и вернуть (код, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def remote_args(package, version):
    """Собрать аргументы для запроса к тестовому индексу."""
    return ["-p", package, "-r", INDEX_URL, "-V", version]


class CliTest(unittest.TestCase):
    """Проверка поведения main на этапе 2."""

    def test_prints_direct_dependencies(self):
        """Выводится заголовок со счётчиком и список зависимостей."""
        code, out, err = run_main(remote_args("bash", "5.1-6ubuntu1"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertEqual(
            out.splitlines(),
            [
                "Прямые зависимости bash 5.1-6ubuntu1 (4):",
                "  libc6 (>= 2.34)",
                "  libtinfo6 (>= 6)",
                "  base-files (>= 2.1.0)",
                "  debianutils (>= 2.15)",
            ],
        )

    def test_package_without_dependencies(self):
        """Для пакета без зависимостей выводится «нет»."""
        code, out, _ = run_main(remote_args("demo-lib", "1.0-1"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(out, "Прямые зависимости demo-lib 1.0-1: нет\n")

    def test_parameters_are_not_printed(self):
        """Вывод параметров был только на этапе 1."""
        _, out, _ = run_main(remote_args("demo-lib", "1.0-1"))
        self.assertNotIn("max-depth", out)

    def test_unknown_version_is_error(self):
        """Неизвестная версия: сообщение в stderr и код ошибки."""
        code, out, err = run_main(remote_args("bash", "9.9"))
        self.assertEqual(code, EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("доступные версии", err)

    def test_invalid_parameter_is_error(self):
        """Ошибка параметра обрабатывается так же, как на этапе 1."""
        code, _, err = run_main(["-p", "bash"])
        self.assertEqual(code, EXIT_ERROR)
        self.assertTrue(err.startswith("Ошибка:"))

    def test_test_mode_not_supported_yet(self):
        """Режим test пока сообщает, что появится на этапе 3."""
        path = str(pathlib.Path(__file__).parent / "data" / "Packages")
        code, _, err = run_main(["-m", "test", "-p", "A", "-r", path])
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("этапе 3", err)
