from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from bot.requests.user_requests import get_user_by_telegram_id, add_score_to_user
from bot.requests.workout_requests import (
    get_workout_with_exercises,
    update_workout_status,
    get_next_workout_for_user,
    get_workout_exercise_details,
)
from bot.services.workout_service import WorkoutService
from bot.services.llm_service import llm_service
from database.models import Workout, WorkoutStatusEnum
from bot.scheduler import scheduler
from bot.states.workout import WorkoutState
from bot.services.subscription_service import subscription_service
from bot.requests import subscription_requests
from database.models import User
from bot.utils.profile_helpers import get_training_week_description

from bot.keyboards.workout import (
    get_start_workout_keyboard,
    get_exercise_navigation_keyboard,
)
from bot.keyboards.payment import get_payment_keyboard

router = Router()


async def _check_and_notify_for_subscription(
    query: CallbackQuery, session: AsyncSession, user: User
) -> bool:
    """
    Проверяет, может ли пользователь получить следующую тренировку.
    Если нет, отправляет уведомление о необходимости продлить подписку.
    Возвращает True, если уведомление было отправлено, иначе False.
    """
    can_get_next = await subscription_service.can_receive_workout(session, user)
    if not can_get_next:
        subscription = await subscription_requests.get_subscription_by_user_id(
            session, user.id
        )
        
        message_text = (
            "🔥 Ваша подписка закончилась, и это была последняя доступная тренировка.\n\n"
            "Чтобы продолжать тренировки и получить новый план, "
            "пожалуйста, оформите подписку."
        )

        if subscription and subscription.status == "trial":
            message_text = (
                "🏆 Ваш пробный период завершен.\n\n"
                "Чтобы разблокировать полный доступ и получить доступ к следующим тренировкам, "
                "оформите подписку."
            )
            # Меняем статус, чтобы не отправлять это сообщение повторно
            await subscription_service.expire_trial_subscription(session, user.id)

        await query.message.answer(message_text, reply_markup=get_payment_keyboard())
        return True

    return False


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
        f"Нажмите 'Начать выполнение', когда будете готовы."
    )
    return message


async def send_current_exercise(
    message: Message, state: FSMContext, session: AsyncSession
):
    """
    Получает текущее состояние FSM и отправляет сообщение
    с видео, описанием и кнопками для текущего упражнения.
    """
    data = await state.get_data()
    current_index = data.get("current_index", 0)
    exercise_ids = data.get("exercise_ids", [])
    workout_id = data.get("workout_id")
    total_exercises = data.get("total_exercises")

    if not exercise_ids or current_index >= len(exercise_ids):
        # Если что-то пошло не так или упражнения закончились
        await state.clear()
        return

    workout_exercise_id = exercise_ids[current_index]

    # Получаем детали упражнения из БД
    workout_exercise = await get_workout_exercise_details(session, workout_exercise_id)
    if not workout_exercise or not workout_exercise.exercise:
        # Обработка ошибки, если упражнение не найдено
        await message.answer("Не удалось загрузить упражнение. Тренировка прервана.")
        await state.clear()
        return

    exercise = workout_exercise.exercise

    # Формируем сообщение
    caption = (
        f"Упражнение {current_index + 1}/{total_exercises}\n\n"
        f"<b>{exercise.name.upper()}</b>\n"
        f"Подходы: {workout_exercise.sets}\n"
        f"Повторения: {workout_exercise.reps}\n\n"
    )
    if exercise.instructions:
        caption += f"<i>{exercise.instructions}</i>"

    # Отправляем видео или гифку с подписью и клавиатурой
    media_id = exercise.video_id or exercise.gif_id
    
    if exercise.video_id:
        sent_message = await message.answer_video(
            video=exercise.video_id,
            caption=caption,
            reply_markup=get_exercise_navigation_keyboard(
                workout_id, current_index, total_exercises
            ),
            parse_mode="HTML",
        )
    elif exercise.gif_id:
        sent_message = await message.answer_animation(
            animation=exercise.gif_id,
            caption=caption,
            reply_markup=get_exercise_navigation_keyboard(
                workout_id, current_index, total_exercises
            ),
            parse_mode="HTML",
        )
    else:
        # Если нет ни видео, ни гифки
        sent_message = await message.answer(
            caption,
            reply_markup=get_exercise_navigation_keyboard(
                workout_id, current_index, total_exercises
            ),
            parse_mode="HTML",
        )

    # Сохраняем ID сообщения, чтобы его можно было удалить
    await state.update_data(last_exercise_message_id=sent_message.message_id)


@router.callback_query(F.data == "get_workout")
async def get_workout_handler_callback(query: CallbackQuery, session: AsyncSession):
    """
    Находит ближайшую запланированную тренировку и показывает ее.
    """
    user = await get_user_by_telegram_id(session, query.from_user.id)
    if not user:
        await query.answer(
            "Не удалось найти ваш профиль. Пожалуйста, пройдите регистрацию /start.",
            show_alert=True,
        )
        return

    # Проверка подписки
    can_get_workout = await subscription_service.can_receive_workout(session, user)
    if not can_get_workout:
        await query.message.answer(
            "🔥 Ваш пробный период завершен или подписка истекла.\n\n"
            "Чтобы продолжать тренировки, пожалуйста, оформите подписку.",
            reply_markup=get_payment_keyboard()
        )
        await query.answer()
        return

    workout = await get_next_workout_for_user(session, user.id)

    if workout:
        workout_with_exercises = await get_workout_with_exercises(
            session, workout.id
        )
        if workout_with_exercises:
            message_text = format_workout_message(workout_with_exercises)
            await query.message.answer(
                message_text,
                reply_markup=get_start_workout_keyboard(workout.id),
                parse_mode="HTML",
            )
            await query.message.edit_reply_markup(reply_markup=None)
            
            # Фиксируем отправку тренировки для триала
            await subscription_service.record_workout_sent(session, user)

            try:
                scheduler.remove_job(f"workout_{workout.id}")
            except Exception as e:
                logging.warning(f"Could not remove job workout_{workout.id}. Maybe it was already triggered. Error: {e}")
        else:
            await query.message.answer("Не удалось загрузить детали тренировки.")
    else:
        await query.message.answer(
            "На данный момент у вас нет запланированных тренировок."
        )

    await query.answer()


@router.callback_query(F.data.startswith("get_workout_now_"))
async def get_workout_now_handler(query: CallbackQuery, session: AsyncSession):
    """
    Обработчик кнопки "Получить тренировку сейчас".
    """
    user = await get_user_by_telegram_id(session, query.from_user.id)
    if not user:
        await query.answer("Не удалось найти ваш профиль. Пожалуйста, перезапустите бота /start.", show_alert=True)
        return

    # Проверка подписки
    can_get_workout = await subscription_service.can_receive_workout(session, user)
    if not can_get_workout:
        await query.message.answer(
            "🔥 Ваш пробный период завершен или подписка истекла.\n\n"
            "Чтобы продолжать тренировки, пожалуйста, оформите подписку.",
            reply_markup=get_payment_keyboard()
        )
        await query.answer()
        return
        
    workout_id = int(query.data.split("_")[-1])
    workout = await get_workout_with_exercises(session, workout_id)

    if workout:
        message_text = format_workout_message(workout)
        await query.message.answer(
            message_text,
            reply_markup=get_start_workout_keyboard(workout.id),
            parse_mode="HTML",
        )
        # Фиксируем отправку тренировки для триала
        await subscription_service.record_workout_sent(session, user)

        try:
            scheduler.remove_job(f"workout_{workout_id}")
        except Exception as e:
            logging.warning(f"Could not remove job workout_{workout_id}. Maybe it was already triggered. Error: {e}")
    else:
        await query.message.answer(
            "Не удалось найти эту тренировку. Возможно, она была удалена."
        )

    await query.answer()


@router.callback_query(F.data.startswith("start_workout_"))
async def start_workout_handler(
    query: CallbackQuery, state: FSMContext, session: AsyncSession
):
    """
    Обрабатывает начало выполнения тренировки, запускает FSM
    и отправляет первое упражнение.
    """
    workout_id = int(query.data.split("_")[-1])

    workout = await get_workout_with_exercises(session, workout_id)
    if not workout or not workout.workout_exercises:
        await query.answer("Тренировка не найдена.", show_alert=True)
        return

    sorted_exercises = sorted(workout.workout_exercises, key=lambda x: x.order)
    exercise_ids = [we.id for we in sorted_exercises]

    await state.set_state(WorkoutState.in_progress)
    await state.update_data(
        workout_id=workout_id,
        exercise_ids=exercise_ids,
        current_index=0,
        total_exercises=len(exercise_ids),
        telegram_id=query.from_user.id
    )

    await query.message.edit_reply_markup(reply_markup=None)

    await send_current_exercise(query.message, state, session)
    await query.answer()


@router.callback_query(F.data == "next_exercise", WorkoutState.in_progress)
async def next_exercise_handler(
    query: CallbackQuery, state: FSMContext, session: AsyncSession
):
    """
    Обрабатывает переход к следующему упражнению.
    """
    data = await state.get_data()
    current_index = data.get("current_index", 0)
    
    # Убираем удаление предыдущего сообщения, чтобы сохранить историю

    await state.update_data(current_index=current_index + 1)
    await send_current_exercise(query.message, state, session)
    await query.answer()


@router.callback_query(F.data.startswith("finish_workout_"), WorkoutState.in_progress)
async def finish_workout_handler(
    query: CallbackQuery, state: FSMContext, session: AsyncSession
):
    """
    Обрабатывает завершение тренировки (досрочное или полное).
    """
    data = await state.get_data()
    workout_id = int(query.data.split("_")[-1])
    current_index = data.get("current_index", 0)
    total_exercises = data.get("total_exercises", 0)
    
    # Убираем удаление последнего сообщения с упражнением

    # Проверяем, была ли тренировка завершена полностью
    is_completed_fully = current_index == total_exercises - 1

    if is_completed_fully:
        await update_workout_status(session, workout_id, WorkoutStatusEnum.completed)
        await query.answer("✅ Отлично, тренировка завершена!", show_alert=True)

        user = await get_user_by_telegram_id(session, query.from_user.id)
        if user:
            await add_score_to_user(session, user.id, points=1)

            # Проверяем подписку и отправляем уведомление, если нужно
            if await _check_and_notify_for_subscription(query, session, user):
                pass  # Уведомление отправлено, ничего больше не делаем
            else:
                congrats_message = (
                    "Красава! Ты полностью выполнил тренировку и заработал +1 очко. 🏆\n\n"
                )
                
                # Добавляем информацию о текущем цикле
                training_week_info = get_training_week_description(user)
                if training_week_info:
                    congrats_message += (
                        f"Ты сейчас на: <b>{training_week_info}</b>.\n"
                        "Продолжай в том же духе!\n\n"
                    )

                next_workout = await get_next_workout_for_user(session, user.id)
                if next_workout:
                    days_ru = {
                        0: "понедельник", 1: "вторник", 2: "среду", 3: "четверг",
                        4: "пятницу", 5: "субботу", 6: "воскресенье"
                    }
                    day_of_week = days_ru.get(next_workout.planned_date.weekday(), "")
                    date_str = next_workout.planned_date.strftime('%d.%m.%Y')
                    message_text = (
                        f"Следующее испытание ждет тебя в <b>{day_of_week}</b>, "
                        f"<b>{date_str}</b>. Не пропусти!"
                    )
                    await query.message.answer(
                        congrats_message + message_text, parse_mode="HTML"
                    )
                else:
                    await query.message.answer(
                        congrats_message
                        + "Отличная работа! Это была последняя запланированная на неделе тренировка. "
                        "Скоро я подготовлю для тебя новый план.",
                        parse_mode="HTML",
                    )
    else:
        # Досрочное завершение
        await update_workout_status(session, workout_id, WorkoutStatusEnum.skipped)
        await query.message.answer(
            f"Тренировка завершена досрочно. Выполнено упражнений: {current_index} из {total_exercises}.\n\n"
            "В следующий раз постарайся дойти до конца! 💪"
        )
        
        user = await get_user_by_telegram_id(session, query.from_user.id)
        if user:
            # Проверяем подписку и здесь, на случай если это была последняя треня
            await _check_and_notify_for_subscription(query, session, user)

    await state.clear()


@router.callback_query(F.data.startswith("workout_skipped_"))
async def workout_skipped_handler(query: CallbackQuery, session: AsyncSession):
    """Обрабатывает нажатие кнопки 'Пропустил'."""
    workout_id = int(query.data.split("_")[-1])
    await update_workout_status(session, workout_id, WorkoutStatusEnum.skipped)
    await query.message.edit_reply_markup(reply_markup=None)
    await query.answer("Тренировка отмечена как пропущенная.", show_alert=True)

    user = await get_user_by_telegram_id(session, query.from_user.id)
    if user:
        # Проверяем подписку и отправляем уведомление, если нужно
        if await _check_and_notify_for_subscription(query, session, user):
            return  # Уведомление отправлено, выходим

        next_workout = await get_next_workout_for_user(session, user.id)
        if next_workout:
            days_ru = {
                0: "понедельник", 1: "вторник", 2: "среду", 3: "четверг",
                4: "пятницу", 5: "субботу", 6: "воскресенье"
            }
            day_of_week = days_ru.get(next_workout.planned_date.weekday(), "")
            date_str = next_workout.planned_date.strftime('%d.%m.%Y')
            message_text = (
                f"Ничего страшного, у всех бывают сбои. Главное — вернуться в строй! 💪\n\n"
                f"Следующая тренировка ждет тебя в <b>{day_of_week}</b>, "
                f"<b>{date_str}</b>. Постарайся не пропустить!"
            )
            await query.message.answer(message_text, parse_mode="HTML")
        else:
            await query.message.answer(
                "Это была последняя запланированная на неделе тренировка. "
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
        new_workout = await workout_service.create_new_workout_plan(session, user)
        response_text = format_workout_message(new_workout)
        # Для разовой тренировки сразу предлагаем начать
        await loading_message.edit_text(
            response_text,
            parse_mode="HTML",
            reply_markup=get_start_workout_keyboard(new_workout.id),
        )

    except Exception as e:
        await loading_message.edit_text(
            "❌ Произошла ошибка при генерации тренировки. "
            "Попробуйте еще раз или свяжитесь с поддержкой."
        )
        logging.error(f"Error generating workout: {e}", exc_info=True)


@router.message(F.text)
async def ai_coach_text_handler(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик всех текстовых сообщений, которые не были перехвачены другими handlers.
    """
    current_state = await state.get_state()
    if current_state is not None:
        if current_state == WorkoutState.in_progress:
            await message.answer("Пожалуйста, сначала завершите текущую тренировку.")
        return

    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer(
            "Пожалуйста, сначала пройдите регистрацию с помощью команды /start."
        )
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        response = await llm_service.generate_ai_coach_response(
            message.text,
        )
        await message.answer(response, parse_mode="HTML")
    except Exception as e:
        logging.exception("Error in AI coach response generation")
        await message.answer(
            "❌ Извините, произошла ошибка при обработке вашего вопроса. "
            "Попробуйте задать вопрос еще раз."
        )

