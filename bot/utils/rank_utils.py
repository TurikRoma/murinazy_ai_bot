"""
Утилиты для работы с системой званий пользователей.
"""

# Словарь порогов очков для получения званий
# Формат: {минимальное_количество_очков: "Название звания"}
RANK_THRESHOLDS = {
    1: "Новобранец",
    3: "Молокосос",
    5: "Первопроходец",
    10: "Турникмен",
    15: "Середняк",
    20: "Кабан",
    30: "Машина",
    40: "Качок",
    50: "Белковый монстр",
    60: "Мини пекка",
    75: "Титан",
    100: "Сын Арнольда",
    150: "Папа железа",
    200: "Легенда качалки",
}


def get_rank_by_score(score: int) -> str:
    """
    Определяет звание пользователя по количеству очков.
    
    Args:
        score: Количество очков пользователя
        
    Returns:
        str: Название звания пользователя
    """
    if score < 1:
        return "Без звания"
    
    # Сортируем пороги по убыванию и находим первое звание, которое пользователь достиг
    sorted_thresholds = sorted(RANK_THRESHOLDS.keys(), reverse=True)
    
    for threshold in sorted_thresholds:
        if score >= threshold:
            return RANK_THRESHOLDS[threshold]
    
    # Если очков меньше минимального порога, возвращаем самое первое звание
    return RANK_THRESHOLDS[min(RANK_THRESHOLDS.keys())]


def get_next_rank_threshold(score: int) -> tuple[int, str] | None:
    """
    Возвращает следующий порог и название звания, к которому стремится пользователь.
    
    Args:
        score: Текущее количество очков пользователя
        
    Returns:
        tuple[int, str] | None: Кортеж (порог_очков, название_звания) или None, если уже достигнут максимум
    """
    sorted_thresholds = sorted(RANK_THRESHOLDS.keys())
    
    for threshold in sorted_thresholds:
        if score < threshold:
            return (threshold, RANK_THRESHOLDS[threshold])
    
    # Если пользователь уже достиг максимального звания
    return None


