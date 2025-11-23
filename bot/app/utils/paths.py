"""
Утилиты для работы с путями к ассетам.
"""

from pathlib import Path


def get_body_image_path(gender: str, stage: str, variant_id: int) -> str:
    """
    Возвращает относительный путь к изображению типа фигуры.

    Args:
        gender: "male" | "female"
        stage: "now" | "ideal"
        variant_id: номер варианта (1, 2, 3, ...)

    Returns:
        Путь вида "assets/body_types/female/now/female_now_3.jpg"

    Example:
        >>> get_body_image_path("female", "now", 3)
        'assets/body_types/female/now/female_now_3.jpg'
    """
    return f"assets/body_types/{gender}/{stage}/{gender}_{stage}_{variant_id}.jpg"


def get_absolute_body_image_path(gender: str, stage: str, variant_id: int) -> Path:
    """
    Возвращает абсолютный путь к изображению типа фигуры.

    Args:
        gender: "male" | "female"
        stage: "now" | "ideal"
        variant_id: номер варианта (1, 2, 3, ...)

    Returns:
        Абсолютный Path к файлу изображения
    """
    # Получить корневую директорию проекта (1 уровень вверх от текущего файла - из app/utils в app)
    app_root = Path(__file__).resolve().parents[1]
    relative_path = get_body_image_path(gender, stage, variant_id)
    return app_root / relative_path


def ensure_assets_directory_exists() -> None:
    """Создаёт директории для ассетов, если они не существуют."""
    app_root = Path(__file__).resolve().parents[1]
    assets_root = app_root / "assets" / "body_types"

    for gender in ["female", "male"]:
        for stage in ["now", "ideal"]:
            directory = assets_root / gender / stage
            directory.mkdir(parents=True, exist_ok=True)


def validate_image_file_exists(gender: str, stage: str, variant_id: int) -> bool:
    """
    Проверяет, существует ли файл изображения.

    Args:
        gender: "male" | "female"
        stage: "now" | "ideal"
        variant_id: номер варианта

    Returns:
        True если файл существует, иначе False
    """
    path = get_absolute_body_image_path(gender, stage, variant_id)
    return path.exists() and path.is_file()
