"""Исключения приложения depgraph."""


class DepGraphError(Exception):
    """Базовое исключение: текст предназначен для пользователя."""


class ConfigError(DepGraphError):
    """Некорректные параметры командной строки."""


class RepositoryError(DepGraphError):
    """Не удалось получить или разобрать данные репозитория."""


class PackageNotFoundError(RepositoryError):
    """Пакет или его версия отсутствует в индексе репозитория."""


class NotSupportedError(DepGraphError):
    """Запрошенный режим работы пока не реализован."""
