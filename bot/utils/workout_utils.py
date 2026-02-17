def calculate_effective_training_week(
    current_week: int, fitness_level: str
) -> int:
    """
    Вычисляет номер недели для промпта с учетом цикличности.
    Например, 7-я неделя для новичка снова станет 1-й.
    """
    if fitness_level == "beginner":
        # Цикл 6 недель (1-6)
        return ((current_week - 1) % 6) + 1
    else:  # advanced
        # Цикл 3 недели (1-3)
        return ((current_week - 1) % 3) + 1

