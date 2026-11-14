"""Исключения приложения depgraph."""


class DepGraphError(Exception):
    """Базовое исключение: текст предназначен для пользователя."""


class ConfigError(DepGraphError):
    """Некорректные параметры командной строки."""
