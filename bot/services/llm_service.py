import json
from openai import AsyncOpenAI

from bot.config.settings import settings
from database.models import User, Exercise
from bot.schemas.workout import LLMWorkoutPlan

# Промпт для генерации НЕДЕЛЬНОЙ программы тренировок
WORKOUT_WEEK_JSON_PROMPT = """
Ты - элитный фитнес-тренер и методист, создающий программы на основе научных данных.
Твоя задача - составить детализированный и эффективную ПОЛНУЮ недельную программу тренировок, которая будет соответствовать уровню подготовки и целям пользователя.


ВЫВОДИ СТРОГО ВАЛИДНЫЙ JSON и НИЧЕГО, кроме JSON, по схеме из раздела «ФОРМАТ ВЫВОДА».

# ВХОДНЫЕ ПАРАМЕТРЫ
goal: {goal}                      # одно из: похудение | набор | поддержание
experience: {experience}          # одно из: новичок | средний | продвинутый
weekly_sessions: {weekly_sessions}# одно из: 2 | 3 | 5
equipment: {equipment}            # одно из: gym | bodyweight

# ПУЛ ДОСТУПНЫХ УПРАЖНЕНИЙ (ИСПОЛЬЗОВАТЬ ТОЛЬКО ИХ, названия 1-в-1)
exercise_pool = {exercise_pool_json}

# ЖЁСТКИЕ ПРАВИЛА
1) **Выбор сплита (строгий алгоритм):**
   Сначала определи сплит по количеству дней (`weekly_sessions`), затем по уровню (`experience`).

   а) **Если `weekly_sessions` = 5:**
      - **Всегда** используется 5-дневный сплит (День 1: Грудь; День 2: Спина; День 3: Ноги; День 4: Плечи; День 5: Руки). Уровень `experience` не имеет значения.

   б) **Если `weekly_sessions` = 3:**
      - Если `experience` = "новичок" -> **FullBody**.
      - Если `experience` = "средний" или "продвинутый" -> **PPL (Push/Pull/Legs)**.
         - Push-день: Грудь, Плечи, Трицепс.
         - Pull-день: Спина, Бицепс.
         - Legs-день: Ноги.

   в) **Если `weekly_sessions` = 2:**
      - Если `experience` = "новичок" -> **FullBody**.
      - Если `experience` = "средний" или "продвинутый" -> **Верх/Низ (Upper/Lower)**.
         - День верха: Грудь, Спина, Плечи, Бицепс, Трицепс.
         - День низа: Ноги.
   
2) Недельные коридоры подходов:
   - БОЛЬШИЕ (грудь, спина, ноги):
     новичок 6–8; средний 8–10; продвинутый 10–15 сетов в неделю.
   - МАЛЫЕ (плечи, бицепс, трицепс):
     новичок 4–5; средний 6; продвинутый 6–9 сетов в неделю.
3) Распределение объёма по сессиям:
   - Количество подходов в упражнениях должны быть равномерно разбиты по дням.
4) Ограничения внутри сессии:
   - На ОДНУ крупную группу в день ≤ 12 подходов.
   - У новичка максимум 3 подхода в упражнении.
   - На упражнение от 2 до 4 подхода.
   - **САМОЕ ГЛАВНОЕ ПРАВИЛО:** В любом упражнении должно быть МИНИМУМ 2 подхода. Если при распределении недельного объёма на какой-то день выпадает 1 подход, ОБЯЗАТЕЛЬНО увеличь его до 2, даже если это немного превысит недельный коридор по объёму.
   - Если на малую группу за НЕДЕЛЮ назначено ≥6 подходов — в сумме недели должно быть минимум 2 РАЗНЫХ упражнения на эту группу.
   - Лимит упражнений в день:
       * FullBody / PPL: максимум 6 упражнений;
       * 5-дневка: 3–5 упражнений.
5) Повторы по цели:
   - «похудение»: 10–15 (изоляции допускается 12–20);
   - «набор»: 8–12;
   - «поддержание»: 6–12.
   AMRAP разрешён ТОЛЬКО если equipment = "bodyweight"; иначе — только интервалы повторений.
6) Названия упражнений выбирать СТРОГО из exercise_pool. Новые придумывать запрещено.
7) Все группы должны суммарно за неделю попасть в свой коридор по объёму для данного уровня подготовки.

# ФОРМАТ ВЫВОДА (СТРОГИЙ JSON)
{{
  "sessions": [
    {{
      "session": 1,
      "exercises": [
        {{ "name": "<строго из exercise_pool>", "muscle_group": "<группа мышц из exercise_pool>", "sets": <целое>, "reps": "<интервал вида 8-12 | 10-15 | AMRAP>" }}
      ]
    }}
  ]
}}

# ТОЛЬКО JSON. Никакого текста, комментариев и пояснений.
"""


class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.PROXY_API_KEY, base_url=settings.PROXY_API_URL
        )

    async def generate_workout_plan(
        self, user: User, exercises: list[Exercise]
    ) -> LLMWorkoutPlan:
        """
        Генерирует НЕДЕЛЬНУЮ программу тренировок с помощью LLM.
        """
        user_params = self._prepare_user_data_for_prompt(user)
        exercise_pool_json = self._prepare_exercises_for_prompt(exercises)

        prompt = WORKOUT_WEEK_JSON_PROMPT.format(
            goal=user_params["goal"],
            experience=user_params["experience"],
            weekly_sessions=user_params["weekly_sessions"],
            equipment=user_params["equipment"],
            exercise_pool_json=exercise_pool_json,
        )

        chat_completion = await self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4,
            timeout=180.0,
        )

        response_json = json.loads(chat_completion.choices[0].message.content)
        return LLMWorkoutPlan.model_validate(response_json)

    def _prepare_user_data_for_prompt(self, user: User) -> dict:
        """Конвертирует данные пользователя в формат для промпта."""
        goal_map = {
            "mass_gain": "набор",
            "weight_loss": "похудение",
            "maintenance": "поддержание",
        }
        experience_map = {
            "beginner": "новичок",
            "intermediate": "средний",
            "advanced": "продвинутый",
        }
        return {
            "goal": goal_map.get(user.goal.value, "поддержание"),
            "experience": experience_map.get(user.fitness_level.value, "новичок"),
            "weekly_sessions": user.workout_frequency,
            "equipment": user.equipment_type.value,
        }

    def _prepare_exercises_for_prompt(self, exercises: list[Exercise]) -> str:
        """Группирует упражнения по мышечным группам для промпта."""
        exercise_pool = {}
        for ex in exercises:
            if ex.muscle_groups not in exercise_pool:
                exercise_pool[ex.muscle_groups] = []
            exercise_pool[ex.muscle_groups].append(ex.name)
        return json.dumps(exercise_pool, ensure_ascii=False, indent=2)


llm_service = LLMService()
