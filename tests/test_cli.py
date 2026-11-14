"""Тесты командной строки: вывод параметров и обработка ошибок."""

import contextlib
import io
import unittest

from depgraph.cli import EXIT_ERROR, EXIT_OK, main

REMOTE_URL = "https://mirror.example.org/ubuntu/Packages.gz"


def run_main(argv):
    """Запустить main и вернуть (код, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    """Проверка поведения main."""

    def test_prints_all_parameters(self):
        """Все параметры выводятся как «ключ: значение»."""
        argv = [
            "-p", "bash", "-r", REMOTE_URL, "-V", "5.1-1", "-d", "4",
        ]
        code, out, err = run_main(argv)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertEqual(
            out.splitlines(),
            [
                "package: bash",
                f"repo: {REMOTE_URL}",
                "repo-mode: remote",
                "package-version: 5.1-1",
                "max-depth: 4",
            ],
        )

    def test_error_goes_to_stderr(self):
        """Ошибка параметра печатается в stderr, код завершения ненулевой."""
        code, out, err = run_main(["-p", "bash"])
        self.assertEqual(code, EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("Ошибка:"))
