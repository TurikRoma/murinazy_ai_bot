from database.models import User


def get_training_week_description(user: User) -> str | None:
    """
    Возвращает описание текущей тренировочной недели пользователя.
    """
    if not user.current_training_week or user.current_training_week == 0:
        return None

    fitness_level = user.fitness_level.value
    training_week = user.current_training_week

    if fitness_level == "beginner":
        # Линейная периодизация для 6 недель
        effective_week = (training_week - 1) % 6 + 1
        descriptions = {
            1: "Адаптация, отработка техники",
            2: "Мышечная выносливость",
            3: "Гипертрофия/набор массы",
            4: "Гипертрофия и сила",
            5: "Развитие силы",
            6: "Разгрузка, активное восстановление",
        }
        description = descriptions.get(effective_week, "Неизвестная неделя")
        return f"Неделя {effective_week}/6 ({description})"

    elif fitness_level in ["intermediate", "advanced"]:
        # Волновая периодизация для 3 недель
        effective_week = (training_week - 1) % 3 + 1
        descriptions = {
            1: "Силовая неделя",
            2: "Неделя гипертрофии",
            3: "Неделя выносливости",
        }
        description = descriptions.get(effective_week, "Неизвестная неделя")
        return f"Неделя {effective_week}/3 ({description})"

    return None
