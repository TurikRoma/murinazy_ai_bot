from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.requests.user_requests import get_user_by_telegram_id
from bot.requests.workout_requests import get_workout_with_exercises, update_workout_status, get_next_workout_for_user
from bot.services.workout_service import WorkoutService
from bot.services.llm_service import llm_service
from database.models import User, Workout, WorkoutStatusEnum
from bot.requests.workout_requests import update_workout_status
from bot.scheduler import scheduler
import logging

from bot.keyboards.workout import get_workout_actions_keyboard

router = Router()


def format_workout_message(workout: Workout) -> str:
    """Форматирует красивый текстовый ответ с программой тренировок."""
    exercises_text = "\n".join(
        [
            f"  - {we.exercise.name}: {we.sets} подхода по {we.reps} повторений"
            for we in sorted(workout.workout_exercises, key=lambda x: x.order)
        ]
    )
    message = (
        f"🔥 <b>Тренировка на {workout.planned_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"<b>Разминка:</b> {workout.warm_up}\n\n"
        f"<b>План упражнений:</b>\n{exercises_text}\n\n"
        f"<b>Заминка:</b> {workout.cool_down}\n\n"
        f"Не забудьте сделать отметку о завершении после."
    )
    return message


@router.callback_query(F.data == "get_workout")
async def get_workout_handler_callback(query: CallbackQuery, session: AsyncSession):
    """
    Обработчик кнопки "Получить тренировку" после регистрации.
    Находит ближайшую запланированную тренировку и показывает ее.
    """
    user = await get_user_by_telegram_id(session, query.from_user.id)
    if not user:
        await query.answer("Не удалось найти ваш профиль. Пожалуйста, пройдите регистрацию /start.", show_alert=True)
        return

    workout = await get_next_workout_for_user(session, user.id)

    if workout:
        # Загружаем упражнения для отображения
        workout_with_exercises = await get_workout_with_exercises(session, workout.id)
        if workout_with_exercises:
            message_text = format_workout_message(workout_with_exercises)
            await query.message.answer(
                message_text,
                reply_markup=get_workout_actions_keyboard(workout.id),
                parse_mode="HTML"
            )
            # Убираем клавиатуру с исходного сообщения
            await query.message.edit_reply_markup(reply_markup=None)
            scheduler.remove_job(f"workout_{workout.id}")
            
        else:
             await query.message.answer("Не удалось загрузить детали тренировки.")
    else:
        await query.message.answer("На данный момент у вас нет запланированных тренировок.")

    await query.answer()


@router.callback_query(F.data.startswith("get_workout_now_"))
async def get_workout_now_handler(query: CallbackQuery, session: AsyncSession):
    """
    Обработчик кнопки "Получить тренировку сейчас".
    """
    workout_id = int(query.data.split("_")[-1])
    workout = await get_workout_with_exercises(session, workout_id)

    if workout:
        message_text = format_workout_message(workout)
        await query.message.answer(
            message_text,
            reply_markup=get_workout_actions_keyboard(workout.id),
            parse_mode="HTML"
        )
        scheduler.remove_job(f"workout_{workout_id}")
    else:
        await query.message.answer("Не удалось найти эту тренировку. Возможно, она была удалена.")
    
    await query.answer()


@router.callback_query(F.data.startswith("workout_completed_"))
async def workout_completed_handler(query: CallbackQuery, session: AsyncSession):
    """Обрабатывает нажатие кнопки 'Завершил'."""
    workout_id = int(query.data.split("_")[-1])
    await update_workout_status(session, workout_id, WorkoutStatusEnum.completed)
    await query.message.edit_reply_markup(reply_markup=None)
    await query.answer(
        "✅ Отлично, тренировка отмечена как завершенная!", show_alert=True
    )

    # Ищем следующую тренировку, чтобы анонсировать ее
    user = await get_user_by_telegram_id(session, query.from_user.id)
    if user:
        next_workout = await get_next_workout_for_user(session, user.id)
        if next_workout:
            # Словарь для корректного склонения дней недели
            days_ru_accusative = {
                0: "понедельник", 1: "вторник", 2: "среду", 3: "четверг",
                4: "пятницу", 5: "субботу", 6: "воскресенье"
            }
            day_of_week = days_ru_accusative.get(next_workout.planned_date.weekday(), "")
            date_str = next_workout.planned_date.strftime('%d.%m.%Y')
            
            message_text = (
                f"Так держать! 🚀\n\n"
                f"Следующее испытание ждет тебя уже в этот <b>{day_of_week}</b>, "
                f"<b>{date_str}</b>. Не пропусти!"
            )
            await query.message.answer(message_text, parse_mode="HTML")
        else:
            await query.message.answer(
                "Отличная работа! Это была последняя запланированная тренировка. "
                "Скоро я подготовлю для тебя новый план."
            )


@router.callback_query(F.data.startswith("workout_skipped_"))
async def workout_skipped_handler(query: CallbackQuery, session: AsyncSession):
    """Обрабатывает нажатие кнопки 'Пропустил'."""
    workout_id = int(query.data.split("_")[-1])
    await update_workout_status(session, workout_id, WorkoutStatusEnum.skipped)
    await query.message.edit_reply_markup(reply_markup=None)
    await query.answer(
        "Тренировка отмечена как пропущенная.", show_alert=True
    )

    # Ищем следующую тренировку, чтобы напомнить о ней
    user = await get_user_by_telegram_id(session, query.from_user.id)
    if user:
        next_workout = await get_next_workout_for_user(session, user.id)
        if next_workout:
            days_ru_accusative = {
                0: "понедельник", 1: "вторник", 2: "среду", 3: "четверг",
                4: "пятницу", 5: "субботу", 6: "воскресенье"
            }
            day_of_week = days_ru_accusative.get(next_workout.planned_date.weekday(), "")
            date_str = next_workout.planned_date.strftime('%d.%m.%Y')
            
            message_text = (
                f"Ничего страшного, у всех бывают сбои. Главное — вернуться в строй! 💪\n\n"
                f"Следующая тренировка ждет тебя в <b>{day_of_week}</b>, "
                f"<b>{date_str}</b>. Постарайся не пропустить!"
            )
            await query.message.answer(message_text, parse_mode="HTML")
        else:
            await query.message.answer(
                "Это была последняя запланированная тренировка. "
                "Я скоро подготовлю новый план, чтобы ты мог вернуться к занятиям."
            )


@router.message(Command("workout"))
async def get_workout_handler(
    message: Message, session: AsyncSession, workout_service: WorkoutService
):
    """
    Обработчик команды /workout для генерации новой разовой тренировки.
    """
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer(
            "Пожалуйста, сначала пройдите регистрацию с помощью команды /start."
        )
        return

    loading_message = await message.answer("🏋️‍♂️ Генерирую вашу персональную тренировку...")

    try:
        # Эта логика теперь внутри WorkoutService, но для разовой генерации можно оставить так
        # или вынести в отдельный метод сервиса. Пока оставляем для обратной совместимости.
        new_workout = await workout_service.create_new_workout_plan(session, user)
        response_text = format_workout_message(new_workout)
        await loading_message.edit_text(response_text, parse_mode="HTML")

    except Exception as e:
        await loading_message.edit_text(
            "❌ Произошла ошибка при генерации тренировки. "
            "Попробуйте еще раз или свяжитесь с поддержкой."
        )
        # TODO: Добавить логирование ошибки
        print(f"Error generating workout: {e}")


@router.message(F.text)
async def ai_coach_text_handler(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик всех текстовых сообщений, которые не были перехвачены другими handlers.
    Используется для общения с AI-тренером через generate_ai_coach_response.
    Срабатывает только если пользователь не находится в состоянии FSM (например, не в процессе регистрации).
    
    Этот handler регистрируется последним в роутере workout, который регистрируется последним в main_router,
    что гарантирует его выполнение только если ни один другой handler не обработал сообщение.
    """
    # Проверяем, что пользователь не находится в процессе регистрации или другой FSM-процедуре
    # Если есть активное состояние, значит другой handler должен был его обработать
    # Но на всякий случай проверяем здесь тоже
    current_state = await state.get_state()
    if current_state is not None:
        # Если есть активное состояние, пропускаем обработку
        # В этом случае должен сработать handler с соответствующим состоянием из registration.py
        return
    
    # Проверяем, что пользователь зарегистрирован
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer(
            "Пожалуйста, сначала пройдите регистрацию с помощью команды /start."
        )
        return
    
    # Показываем индикатор набора текста
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Генерируем ответ через AI-тренера
        response = await llm_service.generate_ai_coach_response(message.text,)
        await message.answer(response, parse_mode="HTML")
    except Exception as e:
        logging.exception("Error in AI coach response generation")
        await message.answer(
            "❌ Извините, произошла ошибка при обработке вашего вопроса. "
            "Попробуйте задать вопрос еще раз."
        )

