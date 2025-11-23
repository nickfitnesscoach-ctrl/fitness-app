"""
Сервис для отправки изображений типов фигуры.
"""

import asyncio
from typing import List, Optional
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, Message
from aiogram.exceptions import TelegramBadRequest

from app.constants import BODY_LABELS, BODY_COUNTS
from app.utils.paths import get_absolute_body_image_path
from app.keyboards import get_body_type_keyboard
from app.utils.logger import logger


class ImageSender:
    """Сервис для отправки изображений типов фигуры."""

    MAX_RETRIES = 3
    RETRY_DELAY = 2  # секунды

    @staticmethod
    async def send_body_type_options(
        bot: Bot,
        chat_id: int,
        gender: str,
        stage: str,
        header_message: str
    ) -> List[int]:
        """
        Отправляет варианты типов фигуры отдельными сообщениями.

        Args:
            bot: Экземпляр бота
            chat_id: ID чата
            gender: "male" или "female"
            stage: "now" или "ideal"
            header_message: Заголовочное сообщение

        Returns:
            Список message_id отправленных сообщений (для последующего удаления)
        """
        message_ids: List[int] = []

        # Отправить заголовок
        try:
            header_msg = await bot.send_message(chat_id, header_message, parse_mode="HTML", disable_notification=True)
            message_ids.append(header_msg.message_id)
        except Exception as e:
            logger.error(f"Failed to send header message: {e}")

        # Получить количество вариантов для данного пола и стадии
        variant_count = BODY_COUNTS.get(gender, {}).get(stage, 3)

        # Отправить изображения по одному
        for variant_id in range(1, variant_count + 1):
            message_id = await ImageSender._send_single_body_image(
                bot=bot,
                chat_id=chat_id,
                gender=gender,
                stage=stage,
                variant_id=variant_id
            )
            if message_id:
                message_ids.append(message_id)

        return message_ids

    @staticmethod
    async def _send_single_body_image(
        bot: Bot,
        chat_id: int,
        gender: str,
        stage: str,
        variant_id: int
    ) -> Optional[int]:
        """
        Отправляет одно изображение типа фигуры с retry логикой.

        Args:
            bot: Экземпляр бота
            chat_id: ID чата
            gender: "male" или "female"
            stage: "now" или "ideal"
            variant_id: Номер варианта

        Returns:
            message_id отправленного сообщения или None при ошибке
        """
        image_path = get_absolute_body_image_path(gender, stage, variant_id)
        label = BODY_LABELS.get(gender, {}).get(stage, {}).get(variant_id, f"Вариант {variant_id}")

        caption = f"<b>Вариант {variant_id}</b>\n{label}"
        keyboard = get_body_type_keyboard(variant_id)

        # Попытки отправки с retry
        for attempt in range(1, ImageSender.MAX_RETRIES + 1):
            try:
                if not image_path.exists():
                    logger.error(f"Image file not found: {image_path}")
                    return None

                photo = FSInputFile(image_path)
                message = await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_notification=True
                )
                logger.debug(f"Sent body image: {gender}/{stage}/{variant_id} (msg_id: {message.message_id})")
                return message.message_id

            except FileNotFoundError as e:
                logger.error(f"File not found: {image_path} - {e}")
                return None

            except TelegramBadRequest as e:
                logger.error(f"Telegram API error on attempt {attempt}/{ImageSender.MAX_RETRIES}: {e}")
                if attempt < ImageSender.MAX_RETRIES:
                    await asyncio.sleep(ImageSender.RETRY_DELAY)
                else:
                    # Отправить fallback сообщение
                    await ImageSender._send_fallback_message(bot, chat_id, variant_id, label)
                    return None

            except Exception as e:
                logger.error(f"Unexpected error sending image {variant_id}: {e}")
                if attempt < ImageSender.MAX_RETRIES:
                    await asyncio.sleep(ImageSender.RETRY_DELAY)
                else:
                    return None

        return None

    @staticmethod
    async def _send_fallback_message(
        bot: Bot,
        chat_id: int,
        variant_id: int,
        label: str
    ) -> None:
        """
        Отправляет fallback-сообщение, если изображение недоступно.

        Args:
            bot: Экземпляр бота
            chat_id: ID чата
            variant_id: Номер варианта
            label: Описание варианта
        """
        try:
            fallback_text = (
                f"⚠️ <b>Вариант {variant_id}</b>\n"
                f"{label}\n\n"
                f"<i>Изображение временно недоступно</i>"
            )
            keyboard = get_body_type_keyboard(variant_id)
            await bot.send_message(
                chat_id=chat_id,
                text=fallback_text,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_notification=True
            )
        except Exception as e:
            logger.error(f"Failed to send fallback message: {e}")

    @staticmethod
    async def delete_messages(bot: Bot, chat_id: int, message_ids: List[int]) -> None:
        """
        Удаляет несколько сообщений.

        Args:
            bot: Экземпляр бота
            chat_id: ID чата
            message_ids: Список message_id для удаления
        """
        for msg_id in message_ids:
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception as e:
                logger.debug(f"Failed to delete message {msg_id}: {e}")


# Глобальный экземпляр
image_sender = ImageSender()
