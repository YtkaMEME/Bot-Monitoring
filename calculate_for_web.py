from src.data_processing.calculate_targets import fetch_form_data, save_calculation_results
from src.data_processing.prepare_target_distributions import prepare_target_distributions


def calculate_for_web():
    form_data = fetch_form_data()
    if form_data is None:
        raise RuntimeError("Нет сохраненных данных формы для расчета.")

    (male_count, female_count, art_school_labels, art_school_distribution,
     age_group_labels, age_group_distribution) = form_data

    # Параметры дисперсионного расчёта
    confidence_level = 0.95
    p = 0.5
    E = 0.05

    # Получаем таргетные распределения
    target_pol, target_age, target_art, sample_size = prepare_target_distributions(
        male_count, female_count,
        age_group_distribution, age_group_labels,
        art_school_distribution, art_school_labels,
        confidence_level, p, E)
    save_calculation_results(sample_size, target_pol, target_age, target_art)
    return sample_size, target_pol, target_age, target_art


if __name__ == "__main__":
    sample_size, target_pol, target_age, target_art = calculate_for_web()
    print({
        "sampleSize": sample_size,
        "targetPol": target_pol,
        "targetAge": target_age,
        "targetArt": target_art,
    })
