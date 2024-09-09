import asyncio
import os

from data_analysis import questions_validation, AnalysisError
from reading_files import read_file, table_validation, create_questions_list
import pandas as pd


async def main_data_analytics(path, number_mood_quest, number_nps_quest, numbers_csi_quest, message, num_person):
    name = path.split("/")[-1].split(".")[0]
    excel_path = f'./{name}_modified.xlsx'
    csv_path = f'./{name}_modified.csv'

    df = read_file(path)
    df = table_validation(df)

    original_questions_list = create_questions_list(df)

    try:
        (final_data_list, nps, csi, free_answers, answer_for_user) = questions_validation(original_questions_list,
                                                                                          number_mood_quest,
                                                                                          number_nps_quest,
                                                                                          numbers_csi_quest,
                                                                                          num_person)
    except AnalysisError as e:
        await message.answer(f"{e}")
        os.remove(path)
    except:
        await message.answer(f"Произошла какая-то ошибка \U0001F63F\nНо ведь у меня лапки\U0001F43E")
        os.remove(path)

    if final_data_list:
        final_frame = pd.concat(final_data_list, ignore_index=True)
    else:
        final_frame = pd.DataFrame()

    final_frame.to_excel(excel_path, index=False)

    if not answer_for_user == "":
        await message.answer(f"Были пропущены следующие вопросы{answer_for_user}")

    if final_data_list:
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
            workbook = writer.book
            worksheet = workbook['Sheet1']

            new_num = 1

            previous_num = int(worksheet['A2'].value.split("_")[1])

            for i in range(2, worksheet.max_row + 1):
                current_cell = worksheet[f'A{i}']
                current_num = int(current_cell.value.split("_")[1])
                if previous_num == current_num:
                    current_cell.value = f"D1_{new_num}"
                else:
                    previous_num = current_num
                    new_num += 1
                    current_cell.value = f"D1_{new_num}"

    df = pd.read_excel(excel_path, engine="openpyxl")
    df.to_csv(csv_path, index=False, encoding='utf-8')

    if not nps.empty:
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
            nps.to_excel(writer, sheet_name='NPS', index=False)

        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
            workbook = writer.book
            worksheet = workbook['NPS']

            # Применение процентного форматирования ко всему столбцу "Процент"
            for cell in worksheet['C']:  # Предполагается, что 'Процент' в столбце B
                if cell.row > 1:  # Пропустить заголовок
                    if cell.value is not None and isinstance(cell.value, (int, float)):
                        cell.number_format = '0.00%'

    if not csi.empty:
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
            csi.to_excel(writer, sheet_name='CSI', index=False)

    if not free_answers.empty:
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
            free_answers.to_excel(writer, sheet_name='Открытые комментарие', index=False)

    # Использование контекстного менеджера для изменения формата ячеек
    with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
        workbook = writer.book
        worksheet = workbook['Sheet1']

        # Применение процентного форматирования ко всему столбцу "Процент"
        for cell in worksheet['F']:
            if cell.row > 1:
                if cell.value is not None and isinstance(cell.value, (int, float)):
                    cell.number_format = '0%'

    return excel_path, csv_path
