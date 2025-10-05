# Техническое видение AI-тренера для тренажёрного зала

## Технологии

**Backend:**

- Python 3.11+
- aiogram 3.x (для Telegram бота)
- PostgreSQL (пользователи, упражнения, тренировки)
- Redis (кэширование и сессии бота)

**LLM:**

- OpenAI GPT-4o-mini (основной выбор)

**Деплой:**

- Docker + Docker Compose
- VPS (DigitalOcean, Hetzner и т.п.)

**Дополнительно:**

- Pydantic (валидация данных)
- SQLAlchemy + asyncpg (асинхронная работа с БД)
- Alembic (миграции БД)
- python-dotenv (конфигурация)

## Принципы разработки

**Основной принцип:** KISS (Keep It Simple, Stupid)

- Никакого оверинжиниринга
- Простые и понятные решения
- MVP-подход для быстрой проверки идеи

**Конкретные принципы:**

- Монолитная архитектура (один бот-сервис)
- Использование ProxyAPI для доступа к LLM (вместо прямого OpenAI API)
- Простые SQL-запросы через SQLAlchemy
- Минимальное количество абстракций
- Использование готовых решений где возможно
- Сначала работающий код, потом оптимизация

**Разработка:**

- Feature-first подход (от функциональности к коду)
- Быстрые итерации и тестирование на реальных пользователях
- Git flow: main ветка + feature branches
- Документация только необходимого минимума

## Структура проекта

```
murinazy_ai_bot/
├── bot/                    # Основной код бота
│   ├── __init__.py
│   ├── main.py            # Точка входа
│   ├── handlers/          # Обработчики команд и сообщений
│   │   ├── __init__.py
│   │   ├── start.py       # /start, регистрация
│   │   ├── workout.py     # Работа с тренировками
│   │   └── profile.py     # Профиль пользователя
│   ├── states/            # FSM состояния для aiogram
│   │   ├── __init__.py
│   │   ├── registration.py # Состояния регистрации
│   │   └── workout.py     # Состояния работы с тренировками
│   ├── keyboards/         # Клавиатуры
│   │   ├── __init__.py
│   │   └── registration.py
│   ├── services/          # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── llm_service.py # Работа с ProxyAPI
│   │   ├── workout_service.py
│   │   └── user_service.py
│   ├── requests/          # Запросы к БД
│   │   ├── __init__.py
│   │   ├── user_requests.py
│   │   ├── exercise_requests.py
│   │   └── workout_requests.py
│   └── @schemas/          # Pydantic модели
│       ├── __init__.py
│       ├── user.py
│       ├── exercise.py
│       └── workout.py
├── database/
│   ├── models.py          # SQLAlchemy модели
│   └── migrations/        # Alembic миграции
├── config/
│   └── settings.py        # Конфигурация
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env
```

## Архитектура проекта

**Общая схема:**

```
Telegram Bot API ←→ aiogram ←→ Handlers ←→ Services ←→ Requests ←→ PostgreSQL
                                     ↓
                                LLM Service ←→ ProxyAPI ←→ OpenAI
                                     ↓
                                   Redis (кэш/сессии)
```

**Слои архитектуры:**

1. **Handlers** - обработчики Telegram команд и сообщений
2. **Services** - бизнес-логика (генерация тренировок, работа с LLM)
3. **Requests** - слой работы с БД (CRUD операции)
4. **Models** - SQLAlchemy модели для БД
5. **Schemas** - Pydantic модели для валидации

**Принцип работы:**

- Пользователь отправляет сообщение в Telegram
- aiogram передает в соответствующий Handler
- Handler вызывает нужный Service
- Service использует Requests для работы с БД и LLM Service для AI
- Результат возвращается пользователю

## Модель данных

**Основные таблицы:**

1. **Users** - пользователи бота

   - id, telegram_id
   - created_at, updated_at
   - Базовые данные: gender (male/female), age (10-100), height (100-250 см), current_weight (30-300 кг)
   - Цели: goal (mass_gain/weight_loss/maintenance), target_weight (30-300 кг)
   - Уровень: fitness_level (beginner/intermediate/advanced) - где intermediate = 1-3 года, advanced = >3 лет
   - Тренировки: workout_frequency (2/3/5 раз в неделю)
   - Оборудование: equipment_type (gym/bodyweight)

2. **Exercises** - база упражнений

   - id, name, description
   - muscle_groups (str)
   - video_url, image_url
   - instructions (текст)

3. **Workouts** - тренировки пользователей

   - id, user_id
   - created_at, planned_date
   - status (planned/completed/skipped)

4. **WorkoutExercises** - упражнения в тренировке
   - id, workout_id, exercise_id
   - sets, reps, weight
   - rest_time, notes
   - order (порядок выполнения)

## Работа с LLM

**Подключение:**

- ProxyAPI для доступа к OpenAI GPT-4o-mini
- Простой HTTP клиент (httpx)
- Без дополнительных библиотек

**Основные задачи для LLM:**

1. **Генерация тренировочных программ** - на основе профиля пользователя
2. **Персонализация программ** - учет целей, уровня, оборудования
3. ~~Консультации~~ - на будущее

**Подход:**

- Системный промпт для генерации тренировок
- Шаблон запроса с данными пользователя и списком доступных упражнений
- Простая обработка ответа - парсинг JSON с тренировкой

**Обработка ошибок:**

- Базовые try/except блоки
- Retry при временных сбоях (1-2 попытки)
- Fallback на базовую тренировку если LLM недоступен

**Без кэширования** - каждая тренировка персонализирована и уникальна

## Мониторинг LLM

**Просто логи для отладки:**

**Что логируем:**

- Запросы к ProxyAPI (user_id, время)
- Ошибки при вызовах LLM
- Время ответа для отладки производительности

**Как:**

- Python logging в файл и консоль
- Базовые уровни: INFO для запросов, ERROR для ошибок

**Примеры логов:**

```python
logger.info(f"LLM request: user_id={user_id}")
logger.error(f"LLM failed: {error}")
```

**Все остальное - на будущее.**

## Сценарии работы

**1. Первое знакомство (регистрация):**

- /start - приветственный кружок (video_note) с приветствием от AI-тренера
- Кнопка "Начать" для старта регистрации
- Сбор пола: мужской/женский (inline кнопки)
- Сбор возраста: ввод числа (с валидацией 10-100 лет)
- Сбор роста: ввод в см (с валидацией 100-250 см)
- Сбор текущего веса: ввод в кг (с валидацией 30-300 кг)
- Определение уровня подготовки: начинающий/1-3 года/>3 лет (inline кнопки)
- Выбор цели: набор массы/похудение/поддержание формы (inline кнопки)
- Сбор целевого веса: ввод в кг (с валидацией 30-300 кг)
- Выбор частоты тренировок: 2/3/5 раз в неделю (inline кнопки)
- Выбор типа оборудования: зал/свой вес (inline кнопки)
- Сохранение профиля в БД

**2. Получение тренировки:**

- Команда "Получить тренировку"
- Проверка: прошло ли 12+ часов с последней полученной тренировки
- LLM генерирует одну тренировку на основе профиля
- Отображение списка упражнений с описаниями и видео
- Кнопка "Завершить тренировку"
- Сохранение тренировки в БД со статусом "planned"

**3. Завершение тренировки:**

- Нажатие кнопки "Завершить тренировку"
- Обновление статуса на "completed"
- Новую тренировку можно будет получить через 12 часов с момента получения предыдущей

**MVP-версия:** все 3 сценария для полного цикла тренировок.

## Деплой

**Где разворачиваем:**

- Простой VPS (DigitalOcean, Hetzner, Selectel)
- 1-2 CPU, 2-4GB RAM для начала
- Ubuntu 22.04 LTS

**Как разворачиваем:**

- Docker + Docker Compose (простота и изоляция)
- Один docker-compose.yml с:
  - Telegram бот (Python)
  - PostgreSQL
  - Redis

**Процесс деплоя:**

1. git clone на VPS
2. Настройка .env файла
3. docker-compose up -d
4. Миграции БД через alembic

**Управление:**

- Systemd для автостарта docker-compose
- Простые bash скрипты для обновления
- Логи через docker logs

**Без:**

- CI/CD пайплайнов (пока рано)
- Kubernetes (оверкилл)
- Load balancer'ов

## Подход к конфигурированию

**Простой .env файл:**

```env
# Telegram Bot
BOT_TOKEN=your_bot_token

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/murinazy_bot
REDIS_URL=redis://localhost:6379

# LLM
PROXY_API_URL=https://your-proxy-api.com
PROXY_API_KEY=your_proxy_key

# App Settings
WORKOUT_COOLDOWN_HOURS=12
LOG_LEVEL=INFO
```

**Загрузка конфигурации:**

- python-dotenv для загрузки .env
- Pydantic Settings для валидации
- Один класс Settings с типизацией

**Структура:**

```python
class Settings(BaseSettings):
    bot_token: str
    database_url: str
    redis_url: str
    proxy_api_url: str
    proxy_api_key: str
    workout_cooldown_hours: int = 12
    log_level: str = "INFO"
```

**Без:**

- Разных окружений (dev/prod) пока не нужно
- Сложных конфигов в YAML/TOML

## Подход к логгированию

**Простое Python logging:**

- Стандартная библиотека logging
- Два вывода: консоль + файл
- Конфигурируемый уровень через .env

**Структура логов:**

```python
# Формат: время - уровень - модуль - сообщение
2024-10-05 15:30:15 - INFO - bot.handlers.start - User 12345 started registration
2024-10-05 15:30:20 - INFO - bot.services.llm_service - LLM request: user_id=12345
2024-10-05 15:30:22 - ERROR - bot.services.llm_service - LLM failed: Connection timeout
```

**Что логируем:**

- Основные действия пользователей (start, get workout, complete)
- Запросы к LLM и их результаты
- Ошибки и исключения
- Время выполнения критических операций

**Настройка:**

- Один logger на модуль
- Уровень из конфига (INFO/DEBUG/ERROR)
- Ротация файлов по размеру

**Без:**

- Структурированных логов (JSON) пока не нужно
- Централизованного сбора логов
- ELK stack'а
