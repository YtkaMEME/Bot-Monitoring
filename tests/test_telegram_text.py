import asyncio
import unittest

from src.utils.telegram_text import MAX_MESSAGE_UNITS, send_text_in_parts, split_telegram_text


class FakeMessage:
    def __init__(self):
        self.sent = []

    async def answer(self, text):
        self.sent.append(text)


class TelegramTextTest(unittest.TestCase):
    def test_long_summary_is_sent_in_parts(self):
        summary = "\n".join(f"NPS группа {number}: 12,5%" for number in range(400))
        message = FakeMessage()

        asyncio.run(send_text_in_parts(message, summary))

        self.assertGreater(len(message.sent), 1)
        self.assertEqual("".join(message.sent), summary)
        self.assertTrue(all(len(part) <= MAX_MESSAGE_UNITS for part in message.sent))

    def test_long_line_and_emoji_fit_limit(self):
        text = "😀" * 3000 + "А" * 4000
        parts = list(split_telegram_text(text))

        self.assertEqual("".join(parts), text)
        self.assertTrue(all(len(part.encode("utf-16-le")) // 2 <= MAX_MESSAGE_UNITS for part in parts))

    def test_single_divider_summary_stays_one_message(self):
        self.assertEqual(list(split_telegram_text("NPS Общее: 25%")), ["NPS Общее: 25%"])


if __name__ == "__main__":
    unittest.main()
