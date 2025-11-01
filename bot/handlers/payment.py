from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
    SuccessfulPayment,
)
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime

from bot.config.settings import settings
from bot.requests.user_requests import get_user_by_telegram_id
from bot.requests.workout_requests import get_next_workout_for_user
from bot.requests import subscription_requests
from bot.services.subscription_service import subscription_service
from bot.services.workout_service import WorkoutService
from bot.keyboards.payment import get_payment_keyboard
from bot.keyboards.registration import get_main_menu_keyboard

router = Router()


@router.message(F.text == "💳 Подписка")
async def subscription_info_handler(message: Message, state: FSMContext):
    """
    Отправляет информацию о подписке и сбрасывает состояние.
    """
    await state.clear()
    await message.answer(
        "Выберите действие:",
        reply_markup=get_payment_keyboard()
    )


@router.callback_query(F.data == "buy_subscription")
async def process_buy_subscription(query: CallbackQuery):
    """Отправляет инвойс на оплату подписки."""
    logging.info(f"User {query.from_user.id} initiated star payment.")
    await query.message.answer("⏳ Генерирую ссылку на оплату...")
    try:
        await query.bot.send_invoice(
            chat_id=query.from_user.id,
            provider_token="",
            title="Подписка на AI-тренера",
            description="Полный доступ ко всем функциям на 1 месяц.",
            payload="monthly_subscription",
            currency="XTR",
            prices=[LabeledPrice(label="Подписка на 1 месяц", amount=50)],
            start_parameter="one-month-subscription",
        )
    except Exception as e:
        logging.error(f"Failed to send invoice to user {query.from_user.id}: {e}", exc_info=True)
        await query.message.answer(
            "❌ Произошла ошибка при создании счета. Пожалуйста, попробуйте еще раз.\n"
            "Если проблема повторится, свяжитесь с поддержкой."
        )
    finally:
        await query.answer()


@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    """Подтверждает готовность к обработке платежа."""
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(
    message: Message, session: AsyncSession, workout_service: WorkoutService
):
    """Обрабатывает успешный платеж."""
    telegram_id = message.from_user.id
    logging.info(
        f"Successful payment from user {telegram_id}. "
        f"Payload: {message.successful_payment.invoice_payload}"
    )

    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        logging.error(
            f"User not found for successful payment. Telegram ID: {telegram_id}"
        )
        return

    # 1. Проверим статус подписки ДО активации, чтобы выбрать правильный текст
    was_active = False
    subscription = await subscription_requests.get_subscription_by_user_id(session, user.id)
    if subscription and subscription.status == "active" and subscription.expires_at and subscription.expires_at > datetime.utcnow():
        was_active = True

    # 2. Активируем/продлеваем подписку
    await subscription_service.activate_subscription(session, user)
    
    # 3. Формируем правильное сообщение
    if was_active:
        confirmation_message = "✅ Оплата прошла успешно! Ваша подписка продлена на 30 дней."
    else:
        confirmation_message = "✅ Оплата прошла успешно! Ваша подписка активирована на 30 дней."

    # 4. Проверяем, есть ли у пользователя уже запланированные тренировки
    next_workout = await get_next_workout_for_user(session, user.id)

    if next_workout:
        # Если план уже есть, просто отправляем итоговое сообщение и выходим
        await message.answer(confirmation_message)
        return

    # 5. Если плана нет, добавляем текст про генерацию и запускаем ее
    await message.answer(
        f"{confirmation_message}\n\n"
        "Сейчас я подготовлю для вас план тренировок на оставшуюся часть недели..."
    )

    try:
        result = await workout_service.create_and_schedule_weekly_workout(
            session, user.telegram_id
        )
        if result:
            plan_summary, next_workout_datetime = result
            if next_workout_datetime:
                await message.answer(
                    f"🚀 Ваш план готов! Первая тренировка запланирована на "
                    f"{next_workout_datetime.strftime('%d.%m.%Y в %H:%M')}. "
                    "Я пришлю уведомление в нужное время."
                )
            else:
                await message.answer(
                    "✅ План на эту неделю сгенерирован, но на оставшиеся дни "
                    "тренировок нет. Новый план будет создан в начале следующей недели."
                )
        else:
            await message.answer(
                "Не удалось создать план тренировок. Пожалуйста, свяжитесь с поддержкой."
            )
    except Exception as e:
        logging.exception(
            f"Error generating workout plan after payment for user {user.id}"
        )
        await message.answer(
            "Произошла ошибка при создании вашего плана тренировок. "
            "Пожалуйста, свяжитесь с поддержкой."
        )

