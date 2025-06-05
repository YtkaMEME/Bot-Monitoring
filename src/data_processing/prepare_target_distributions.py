import math
from scipy.stats import norm

def calculate_sample_size(confidence_level, p, E, N=None):
    alpha = 1 - confidence_level
    Z = norm.ppf(1 - alpha / 2)
    numerator = (Z * math.sqrt(p * (1 - p))) ** 2
    denominator = E ** 2
    n = numerator / denominator

    if N:  # если передали конечную генеральную совокупность
        n = (n * N) / (n + (N - 1))

    return math.ceil(n)

def prepare_target_distributions(male_count, female_count, 
                                  age_group_distribution, age_group_labels,
                                  art_school_distribution, art_school_labels,
                                  confidence_level, p, E):
    """
    На вход подаются:
    - male_count: кол-во мужчин
    - female_count: кол-во женщин
    - age_group_distribution: список количеств по возрастным группам
    - age_group_labels: список названий возрастных групп
    - art_school_distribution: список количеств по арт-школам
    - art_school_labels: список названий арт-школ

    На выходе: словари target-долей + N
    """

    # Считаем общее количество
    N = calculate_sample_size(confidence_level, p, E, male_count + female_count)

    # Доли по полу
    target_pol = {
        'Мужчина': male_count / (male_count + female_count),
        'Женщина': female_count / (male_count + female_count)
    }

    # Доли по возрасту
    total_age = sum(age_group_distribution)
    target_vozrast = {
        label: count / total_age
        for label, count in zip(age_group_labels, age_group_distribution)
    }

    # Доли по арт-школам
    total_art = sum(art_school_distribution)
    target_art = {
        label: count / total_art
        for label, count in zip(art_school_labels, art_school_distribution)
    }

    return target_pol, target_vozrast, target_art, N
