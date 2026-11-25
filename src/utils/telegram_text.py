MAX_MESSAGE_UNITS = 3500


def split_telegram_text(text: str, max_units: int = MAX_MESSAGE_UNITS):
    """Делит текст на сообщения, учитывая длину эмодзи в UTF-16."""
    if max_units < 2:
        raise ValueError("Размер сообщения должен быть не меньше двух символов")

    offset = 0
    while offset < len(text):
        end = offset
        units = 0
        while end < len(text):
            char_units = 2 if ord(text[end]) > 0xFFFF else 1
            if units + char_units > max_units:
                break
            units += char_units
            end += 1

        if end < len(text):
            newline = text.rfind("\n", offset, end)
            if newline > offset:
                end = newline + 1

        yield text[offset:end]
        offset = end


async def send_text_in_parts(message, text: str) -> None:
    for part in split_telegram_text(text):
        await message.answer(part)
