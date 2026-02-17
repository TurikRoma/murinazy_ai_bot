def validate_age(age_str: str) -> int | None:
    """Валидация возраста (от 10 до 100 лет)."""
    try:
        age = int(age_str)
        if 10 <= age <= 100:
            return age
    except (ValueError, TypeError):
        return None
    return None

def validate_height(height_str: str) -> int | None:
    """Валидация роста (от 100 до 250 см)."""
    try:
        height = int(height_str)
        if 100 <= height <= 250:
            return height
    except (ValueError, TypeError):
        return None
    return None

def validate_weight(weight_str: str) -> float | None:
    """Валидация веса (от 30 до 300 кг)."""
    try:
        # Заменяем запятую на точку для поддержки обоих разделителей
        weight = float(weight_str.replace(",", "."))
        if 30 <= weight <= 300:
            return weight
    except (ValueError, TypeError):
        return None
    return None

def validate_time(time_str: str) -> str | None:
    """
    Валидирует время.
    Принимает форматы "HH", "HH:MM".
    Возвращает строку "HH:MM" или None.
    """
    try:
        if ":" in time_str:
            hours, minutes = map(int, time_str.split(":"))
        else:
            hours, minutes = int(time_str), 0
        
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return f"{hours:02d}:{minutes:02d}"
            
    except (ValueError, TypeError):
        return None
        
    return None
