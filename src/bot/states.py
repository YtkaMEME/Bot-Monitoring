from aiogram.fsm.state import State, StatesGroup


class MainState(StatesGroup):
    """
    Состояния для основного диалога с ботом
    """
    file = State()
    mood = State()
    mood_number = State()
    nps = State()
    nps_number = State()
    csi = State()
    csi_number = State()
    start_process = State()
    num_person = State()
    type_analyze = State()
    gender = State()
    age = State()
    art_school = State()
    division = State()
    division_number = State()
    

class AdminState(StatesGroup):
    """
    Состояния для административных функций
    """
    change_del_list = State()
    add_del_list = State()
    put_away_del_list = State()
    change_users_list = State()
    add_users_list = State()
    put_away_users_list = State() 