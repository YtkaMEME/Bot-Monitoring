import json

from aiogram import Bot

from TOKEN import TOKEN

bot = Bot(token=TOKEN)


def get_allowed_user_ids():
    with open('allowed_user_ids.json', 'r', encoding='utf-8') as file:
        allowed_user_ids = json.load(file)

    return allowed_user_ids


def get_trash_list():
    with open('list_to_del.json', 'r', encoding='utf-8') as file:
        list_to_del_list = json.load(file)

    return list_to_del_list
