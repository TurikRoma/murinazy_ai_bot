from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
    SuccessfulPayment,
)
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from bot.config.settings import settings
from bot.requests.user_requests import get_user_by_telegram_id
from bot.services.subscription_service import subscription_service
from bot.services.workout_service import WorkoutService

router = Router()


@router.callback_query(F.data == "buy_subscription")
async def process_buy_subscription(query: CallbackQuery):
    """Отправляет инвойс на оплату подписки."""
    if not settings.TELEGRAM_PAYMENT_PROVIDER_TOKEN:
        logging.error("TELEGRAM_PAYMENT_PROVIDER_TOKEN is not set!")
        await query.answer("Оплата временно недоступна.", show_alert=True)
        return

    await query.bot.send_invoice(
        chat_id=query.from_user.id,
        title="Подписка на AI-тренера",
        description="Полный доступ ко всем функциям на 1 месяц.",
        payload="monthly_subscription",
        provider_token=settings.TELEGRAM_PAYMENT_PROVIDER_TOKEN,
        currency="XTR",
        prices=[LabeledPrice(label="Подписка на 1 месяц", amount=100)],
        start_parameter="one-month-subscription",
    )
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

    # 1. Активируем подписку
    await subscription_service.activate_subscription(session, user)

    await message.answer(
        "✅ Оплата прошла успешно! Ваша подписка активирована на 30 дней.\n\n"
        "Сейчас я подготовлю для вас план тренировок на оставшуюся часть недели..."
    )

    # 2. Запускаем генерацию тренировок (логика в сервисе сама определит нужные даты)
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

