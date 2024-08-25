# The code from this repository is taken as a basis: https://github.com/flymedllva/Telebot-Calendar/
# Only some changes have been made to the names of the buttons and the behavior of the functions.

import datetime
import calendar

from telebot import TeleBot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telebot_calendar import Calendar as CalendarBase, CallbackData, RUSSIAN_LANGUAGE


class Calendar(CalendarBase):
    def create_calendar(
        self,
        name: str = "calendar",
        year: int = None,
        month: int = None,
        start_func: int = None,
        redis_data_key: str = None,
    ) -> InlineKeyboardMarkup:
        """
        Create a built in inline keyboard with calendar

        :param name:
        :param year: Year to use in the calendar if you are not using the current year.
        :param month: Month to use in the calendar if you are not using the current month.
        :return: Returns an InlineKeyboardMarkup object with a calendar.
        """

        now_day = datetime.datetime.now()

        if year is None:
            year = now_day.year
        if month is None:
            month = now_day.month

        calendar_callback = CallbackData(name, "action", "year", "month", "day", "start_func", "redis_data_key")
        data_ignore = calendar_callback.new("IGNORE", year, month, "!", start_func, redis_data_key)
        data_months = calendar_callback.new("MONTHS", year, month, "!", start_func, redis_data_key)

        keyboard = InlineKeyboardMarkup(row_width=7)

        keyboard.add(
            InlineKeyboardButton(
                self.__lang.months[month - 1] + " " + str(year),
                callback_data=data_months,
            )
        )

        keyboard.add(
            *[
                InlineKeyboardButton(day, callback_data=data_ignore)
                for day in self.__lang.days
            ]
        )

        for week in calendar.monthcalendar(year, month):
            row = list()
            for day in week:
                if day == 0:
                    row.append(InlineKeyboardButton(" ", callback_data=data_ignore))
                elif (
                    f"{now_day.day}.{now_day.month}.{now_day.year}"
                    == f"{day}.{month}.{year}"
                ):
                    row.append(
                        InlineKeyboardButton(
                            f"({day})",
                            callback_data=calendar_callback.new(
                                "DAY", year, month, day, start_func, redis_data_key,
                            ),
                        )
                    )
                else:
                    row.append(
                        InlineKeyboardButton(
                            str(day),
                            callback_data=calendar_callback.new(
                                "DAY", year, month, day, start_func, redis_data_key,
                            ),
                        )
                    )
            keyboard.add(*row)

        keyboard.add(
            InlineKeyboardButton(
                "◀️",
                callback_data=calendar_callback.new("PREVIOUS-MONTH", year, month, "!", start_func, redis_data_key),
            ),
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=calendar_callback.new("CANCEL", year, month, "!", start_func, redis_data_key),
            ),
            InlineKeyboardButton(
                "▶️", callback_data=calendar_callback.new("NEXT-MONTH", year, month, "!", start_func, redis_data_key)
            ),
        )

        return keyboard

    def calendar_query_handler(
        self,
        bot: TeleBot,
        call: CallbackQuery,
        name: str,
        action: str,
        year: int,
        month: int,
        day: int,
        start_func: int = None,
        redis_data_key: str = None,
    ) -> None or datetime.datetime:
        """
        The method creates a new calendar if the forward or backward button is pressed
        This method should be called inside CallbackQueryHandler.


        :param bot: The object of the bot CallbackQueryHandler
        :param call: CallbackQueryHandler data
        :param day:
        :param month:
        :param year:
        :param action:
        :param name:
        :return: Returns a tuple
        """

        current = datetime.datetime(int(year), int(month), 1)
        if action == "IGNORE":
            bot.answer_callback_query(callback_query_id=call.id)
            return False, None
        elif action == "DAY":
            bot.delete_message(
                chat_id=call.message.chat.id, message_id=call.message.message_id
            )
            return datetime.datetime(int(year), int(month), int(day))
        elif action == "PREVIOUS-MONTH":
            preview_month = current - datetime.timedelta(days=1)
            bot.edit_message_text(
                text=call.message.text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=self.create_calendar(
                    name=name,
                    year=int(preview_month.year),
                    month=int(preview_month.month),
                    start_func=start_func,
                    redis_data_key=redis_data_key,
                ),
            )
            return None
        elif action == "NEXT-MONTH":
            next_month = current + datetime.timedelta(days=31)
            bot.edit_message_text(
                text=call.message.text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=self.create_calendar(
                    name=name, year=int(next_month.year), month=int(next_month.month),
                    start_func=start_func, redis_data_key=redis_data_key,
                ),
            )
            return None
        elif action == "MONTHS": pass
        elif action == "MONTH":
            bot.edit_message_text(
                text=call.message.text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=self.create_calendar(
                    name=name, year=int(year), month=int(month), 
                    start_func=start_func, redis_data_key=redis_data_key,
                ),
            )
            return None
        elif action == "CANCEL":
            bot.delete_message(
                chat_id=call.message.chat.id, message_id=call.message.message_id
            )
            return "CANCEL", None
        else:
            bot.answer_callback_query(callback_query_id=call.id, text="ERROR!")
            bot.delete_message(
                chat_id=call.message.chat.id, message_id=call.message.message_id
            )
            return None