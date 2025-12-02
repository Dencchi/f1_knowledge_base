from django.shortcuts import render, get_object_or_404
from django.db.models import Min, Max, Sum, Count, Q, F
from .models import Driver, Constructor, Circuit, Race, Result, SprintResult
from datetime import date
import re
from thefuzz import fuzz

# --- ГЛАВНАЯ ---
def index(request):
    today = date.today()

    # 1. СЛЕДУЮЩАЯ ГОНКА
    # Ищем первую гонку, дата которой >= сегодня
    next_race = Race.objects.filter(date__gte=today).order_by('date').first()

    # 2. ПРОШЛАЯ ГОНКА (Для вывода победителя)
    last_race = Race.objects.filter(date__lt=today).order_by('-date').first()
    last_winner = None
    if last_race:
        # Ищем победителя (позиция 1)
        last_winner = Result.objects.filter(race=last_race, position=1).select_related('driver', 'constructor').first()

    # 3. ТОП-3 ПИЛОТОВ (ТЕКУЩИЙ СЕЗОН)
    # Определяем текущий год по следующей или прошлой гонке
    current_year = next_race.year if next_race else (last_race.year if last_race else 2025)

    top_drivers = []
    # Берем пилотов этого года
    drivers_qs = Driver.objects.filter(
        Q(results__race__year=current_year) | Q(sprint_results__race__year=current_year)
    ).distinct()

    for driver in drivers_qs:
        p_race = Result.objects.filter(driver=driver, race__year=current_year).aggregate(Sum('points'))[
                     'points__sum'] or 0
        p_sprint = SprintResult.objects.filter(driver=driver, race__year=current_year).aggregate(Sum('points'))[
                       'points__sum'] or 0
        total_points = p_race + p_sprint

        # Нам нужно только имя, команда, фото и очки
        # Ищем команду
        last_res = Result.objects.filter(driver=driver, race__year=current_year).order_by('-race__date').first()
        if not last_res:
            last_res = SprintResult.objects.filter(driver=driver, race__year=current_year).order_by(
                '-race__date').first()
        team = last_res.constructor if last_res else None

        top_drivers.append({
            'driver': driver,
            'team': team,
            'points': total_points
        })

    # Сортируем и берем топ-3
    top_drivers.sort(key=lambda x: x['points'], reverse=True)
    top_3 = top_drivers[:3]

    # 4. БАЗОВАЯ СТАТИСТИКА (счетчики)
    counts = {
        'drivers': Driver.objects.count(),
        'teams': Constructor.objects.count(),
        'races': Race.objects.count()
    }

    context = {
        'next_race': next_race,
        'last_race': last_race,
        'last_winner': last_winner,
        'top_3': top_3,
        'counts': counts,
        'current_year': current_year
    }
    return render(request, 'racing/index.html', context)


# --- СПИСОК ПИЛОТОВ ---
def driver_list(request):
    years = Race.objects.values_list('year', flat=True).distinct().order_by('-year')

    # 1. Получаем параметры
    if not years:
        selected_year = 2025
    else:
        selected_year_param = request.GET.get('year')
        try:
            selected_year = int(selected_year_param) if selected_year_param else years[0]
        except ValueError:
            selected_year = years[0]

    sort_param = request.GET.get('sort', 'name')

    # 2. ЛОГИКА "АКТУАЛЬНОГО СОСТАВА" (ПО ДАТЕ)
    today = date.today()

    # Ищем гонку в выбранном году, которая:
    # а) Уже прошла (date <= today)
    # б) Имеет загруженные результаты (чтобы не показать пустой экран, если ты забыл запустить импорт)
    last_race = Race.objects.filter(
        year=selected_year,
        date__lte=today,  # Дата гонки меньше или равна сегодня
        results__isnull=False  # И результаты загружены
    ).order_by('-date').first()  # Берем самую свежую из прошедших

    drivers_data = []

    # Если такая гонка найдена (сезон идет или прошел)
    if last_race:
        # Берем тех, кто участвовал именно в этом Гран-при
        drivers_qs = Driver.objects.filter(
            Q(results__race=last_race) | Q(sprint_results__race=last_race)
        ).distinct()
    else:
        # ФОЛЛБЭК: Если сезон еще не начался (по дате), или мы смотрим будущий год,
        # или скрипт еще не прогнали - показываем всех, у кого есть хоть какие-то результаты в этом году.
        drivers_qs = Driver.objects.filter(
            Q(results__race__year=selected_year) | Q(sprint_results__race__year=selected_year)
        ).distinct()

    # Собираем данные (Фото, Команда)
    for driver in drivers_qs:
        # Ищем команду в ТОЙ ЖЕ гонке, которую мы определили как "последнюю"
        # Если last_race есть, ищем именно в ней. Если нет - ищем в последней доступной.
        target_race = last_race

        last_result = None
        if target_race:
            last_result = Result.objects.filter(driver=driver, race=target_race).first()
            if not last_result:
                last_result = SprintResult.objects.filter(driver=driver, race=target_race).first()

        # Если вдруг в конкретной гонке не нашли (редкий баг), ищем просто последнюю в сезоне
        if not last_result:
            last_result = Result.objects.filter(driver=driver, race__year=selected_year).order_by('-race__date').first()

        team = last_result.constructor if last_result else None

        drivers_data.append({
            'driver': driver,
            'team': team
        })

    # 3. СОРТИРОВКА
    if sort_param == 'team':
        drivers_data.sort(key=lambda x: x['team'].name if x['team'] else 'zzz')
    elif sort_param == 'number':
        drivers_data.sort(key=lambda x: x['driver'].number if x['driver'].number else 999)
    else:  # name
        drivers_data.sort(key=lambda x: x['driver'].surname)

    context = {
        'drivers_data': drivers_data,
        'years': years,
        'selected_year': selected_year,
        'sort_param': sort_param,
    }
    return render(request, 'racing/driver_list.html', context)


# --- ДЕТАЛЬНАЯ ПИЛОТА ---
def driver_detail(request, driver_ref):
    driver = get_object_or_404(Driver, pk=driver_ref)
    available_years = Race.objects.filter(results__driver=driver).values_list('year', flat=True).distinct().order_by(
        '-year')
    selected_year = int(request.GET.get('year', available_years[0] if available_years else 0))
    sort_order = request.GET.get('sort', 'asc')

    def get_stats(main_qs, sprint_qs=None):
        stats = {
            'races': main_qs.count(),
            'wins': main_qs.filter(position=1).count(),
            'podiums': main_qs.filter(position__lte=3).count(),
            'poles': main_qs.filter(grid=1).count(),
            'dnfs': main_qs.exclude(position_text__regex=r'^\d+$').exclude(position_text='D').count(),
            'points': (main_qs.aggregate(Sum('points'))['points__sum'] or 0),
            'top10s': main_qs.filter(position__lte=10).count()
        }
        if sprint_qs:
            stats['points'] += (sprint_qs.aggregate(Sum('points'))['points__sum'] or 0)
        return stats

    career_stats = get_stats(driver.results.all(), driver.sprint_results.all())

    season_main = Result.objects.filter(driver=driver, race__year=selected_year)
    season_sprint = SprintResult.objects.filter(driver=driver, race__year=selected_year)

    table_data = []
    if selected_year:
        order_by = 'round' if sort_order == 'asc' else '-round'
        races = Race.objects.filter(year=selected_year).order_by(order_by)
        for race in races:
            main_res = season_main.filter(race=race).first()
            sprint_res = season_sprint.filter(race=race).first()
            if main_res or sprint_res:
                table_data.append({'race': race, 'main': main_res, 'sprint': sprint_res})

    season_gp_stats = get_stats(season_main)
    season_sprint_stats = get_stats(season_sprint)
    season_total_stats = get_stats(season_main, season_sprint)

    teams_data = []
    constructors = Constructor.objects.filter(result__driver=driver).distinct()

    for team in constructors:
        years = Race.objects.filter(results__driver=driver, results__constructor=team) \
            .aggregate(start=Min('year'), end=Max('year'))
        start = years['start']
        end = years['end']

        if start and end:
            period = f"{start}" if start == end else f"{start}–{end}"
            teams_data.append({
                'team': team,  # <--- ТЕПЕРЬ ПЕРЕДАЕМ ВЕСЬ ОБЪЕКТ, А НЕ ТОЛЬКО ИМЯ
                'period': period,
                'end_year': end
            })
    teams_data.sort(key=lambda x: x['end_year'], reverse=True)

    context = {
        'driver': driver, 'career_stats': career_stats,
        'season_gp_stats': season_gp_stats, 'season_sprint_stats': season_sprint_stats,
        'season_total_stats': season_total_stats, 'teams_history': teams_data,
        'table_data': table_data, 'available_years': available_years, 'selected_year': selected_year,
        'sort_order': sort_order
    }
    return render(request, 'racing/driver_detail.html', context)


# --- СПИСОК КОМАНД ---
def constructor_list(request):
    last_year = Race.objects.aggregate(Max('year'))['year__max'] or 2025
    active_teams = Constructor.objects.filter(result__race__year=last_year).distinct().order_by('name')
    historic_teams = Constructor.objects.exclude(pk__in=active_teams.values('pk')).order_by('name')
    return render(request, 'racing/constructor_list.html',
                  {'active_teams': active_teams, 'historic_teams': historic_teams, 'current_season': last_year})


# --- ДЕТАЛЬНАЯ КОМАНДЫ (ИСПРАВЛЕННАЯ) ---
def constructor_detail(request, constructor_ref):
    team = get_object_or_404(Constructor, pk=constructor_ref)

    last_year_agg = Result.objects.filter(constructor=team).aggregate(Max('race__year'))
    last_year = last_year_agg['race__year__max'] or 2025
    first_entry = Result.objects.filter(constructor=team).aggregate(Min('race__year'))['race__year__min']

    # Год: берем из GET или последний активный
    available_years = Race.objects.filter(results__constructor=team).values_list('year', flat=True).distinct().order_by(
        '-year')
    last_active_year = available_years[0] if available_years else 2025

    selected_year = request.GET.get('year')
    if selected_year:
        try:
            selected_year = int(selected_year)
        except ValueError:
            selected_year = last_active_year
    else:
        selected_year = last_active_year

    # 1. ОБЩАЯ ИСТОРИЯ
    main_qs_all = Result.objects.filter(constructor=team)
    sprint_qs_all = SprintResult.objects.filter(constructor=team)
    total_stats = {
        'races': main_qs_all.values('race').distinct().count(),
        'wins': main_qs_all.filter(position=1).count(),
        'podiums': main_qs_all.filter(position__lte=3).count(),
        'poles': main_qs_all.filter(grid=1).count(),
        'points': (main_qs_all.aggregate(Sum('points'))['points__sum'] or 0) + (
                    sprint_qs_all.aggregate(Sum('points'))['points__sum'] or 0)
    }

    # 2. ПОДРОБНАЯ СТАТИСТИКА СЕЗОНА (GP / Sprint / Total)
    season_main = Result.objects.filter(constructor=team, race__year=selected_year)
    season_sprint = SprintResult.objects.filter(constructor=team, race__year=selected_year)

    def get_team_stats_block(m_qs, s_qs=None):
        stats = {
            'races': m_qs.values('race').distinct().count(),
            'wins': m_qs.filter(position=1).count(),
            'podiums': m_qs.filter(position__lte=3).count(),
            'poles': m_qs.filter(grid=1).count(),
            'top10s': m_qs.filter(position__lte=10).count(),
            'dnfs': m_qs.exclude(position_text__regex=r'^\d+$').exclude(position_text='D').count(),
            'points': (m_qs.aggregate(Sum('points'))['points__sum'] or 0)
        }
        if s_qs:
            stats['points'] += (s_qs.aggregate(Sum('points'))['points__sum'] or 0)
        return stats

    season_gp_stats = get_team_stats_block(season_main)
    season_sprint_stats = get_team_stats_block(season_sprint)  # wins тут = победы в спринтах
    season_total_stats = get_team_stats_block(season_main, season_sprint)

    # 3. АКТИВНЫЕ ПИЛОТЫ И СРАВНЕНИЕ (HEAD-TO-HEAD)
    drivers_this_year = Driver.objects.filter(results__constructor=team, results__race__year=selected_year).distinct()

    drivers_detailed = []
    for driver in drivers_this_year:
        d_main = season_main.filter(driver=driver)
        d_sprint = season_sprint.filter(driver=driver)

        # Считаем детальную стату для сравнения
        races_count = d_main.count()
        points = (d_main.aggregate(Sum('points'))['points__sum'] or 0) + (
                    d_sprint.aggregate(Sum('points'))['points__sum'] or 0)

        # Лучший финиш
        best_pos = d_main.aggregate(Min('position'))['position__min']

        drivers_detailed.append({
            'obj': driver,
            'races': races_count,
            'points': points,
            'wins': d_main.filter(position=1).count(),
            'podiums': d_main.filter(position__lte=3).count(),
            'poles': d_main.filter(grid=1).count(),
            'dnfs': d_main.exclude(position_text__regex=r'^\d+$').exclude(position_text='D').count(),
            'best_pos': best_pos if best_pos else '-',
        })

    # Сортируем по очкам
    drivers_detailed.sort(key=lambda x: x['points'], reverse=True)

    # Определяем запасных (меньше 50% гонок лидера)
    if drivers_detailed:
        max_races = drivers_detailed[0]['races']
        for d in drivers_detailed:
            # Если лидер проехал > 4 гонок, а этот < половины, то он запасной/замена
            d['is_reserve'] = (max_races > 4 and d['races'] < (max_races * 0.5))

    # Для сравнения берем ТОЛЬКО топ-2 основных пилота
    comparison_drivers = [d for d in drivers_detailed if not d.get('is_reserve')][:2]

    # 4. ИСТОРИЯ ВСЕХ ПИЛОТОВ
    all_drivers_data = []
    d_stats = Result.objects.filter(constructor=team).values('driver').annotate(start=Min('race__year'),
                                                                                end=Max('race__year')).order_by('-end',
                                                                                                                'driver__surname')
    for item in d_stats:
        driver = Driver.objects.get(pk=item['driver'])
        period = f"{item['start']}" if item['start'] == item['end'] else f"{item['start']}-{item['end']}"
        all_drivers_data.append({'driver': driver, 'period': period})

    # 5. ТАБЛИЦА ГОНОК (ГРУППИРОВКА)
    season_race_data = []
    races = Race.objects.filter(year=selected_year).order_by('round')

    for race in races:
        # Для этой гонки берем результаты
        race_results = Result.objects.filter(race=race, constructor=team).select_related('driver').order_by('position')
        sprint_results = SprintResult.objects.filter(race=race, constructor=team).select_related('driver').order_by(
            'position')

        if race_results.exists() or sprint_results.exists():
            season_race_data.append({
                'race': race,
                'results': race_results,
                'sprints': sprint_results
            })

    context = {
        'team': team, 'total_stats': total_stats,
        'first_entry': first_entry,
        'season_gp_stats': season_gp_stats, 'season_sprint_stats': season_sprint_stats,
        'season_total_stats': season_total_stats,
        'drivers_detailed': drivers_detailed,  # ТЕКУЩИЕ ПИЛОТЫ
        'comparison_drivers': comparison_drivers,
        'all_drivers': all_drivers_data,
        'season_race_data': season_race_data,
        'selected_year': selected_year, 'available_years': available_years
    }
    return render(request, 'racing/constructor_detail.html', context)


# ЗАГЛУШКИ
def circuit_list(request):
    # 1. Находим текущий сезон
    last_year = Race.objects.aggregate(Max('year'))['year__max'] or 2025

    # 2. Находим трассы, на которых были гонки в этом году (Активные)
    active_circuit_ids = Race.objects.filter(year=last_year).values_list('circuit', flat=True)

    active_circuits = Circuit.objects.filter(pk__in=active_circuit_ids).order_by('country')
    historic_circuits = Circuit.objects.exclude(pk__in=active_circuit_ids).order_by('name')

    context = {
        'active_circuits': active_circuits,
        'historic_circuits': historic_circuits,
        'current_season': last_year
    }
    return render(request, 'racing/circuit_list.html', context)


def circuit_detail(request, circuit_ref):
    circuit = get_object_or_404(Circuit, pk=circuit_ref)

    # 1. ИСТОРИЯ ГОНОК НА ЭТОЙ ТРАССЕ
    # Нам нужно найти победителя каждой гонки
    # Используем сложный запрос, чтобы сразу вытащить победителя (position=1)
    races_qs = Race.objects.filter(circuit=circuit).order_by('-year')

    races_data = []
    for race in races_qs:
        # Ищем победителя (Position 1)
        winner_res = Result.objects.filter(race=race, position=1).select_related('driver', 'constructor').first()
        races_data.append({
            'race': race,
            'winner': winner_res
        })

    # 2. СТАТИСТИКА (КОРОЛЬ ТРАССЫ)
    # Считаем, какой пилот побеждал чаще всего
    top_driver = Result.objects.filter(race__circuit=circuit, position=1) \
        .values('driver__forename', 'driver__surname', 'driver__driver_ref') \
        .annotate(wins=Count('id')) \
        .order_by('-wins').first()

    # Считаем, какая команда побеждала чаще всего
    top_team = Result.objects.filter(race__circuit=circuit, position=1) \
        .values('constructor__name', 'constructor__constructor_ref') \
        .annotate(wins=Count('id')) \
        .order_by('-wins').first()

    stats = {
        'count': races_qs.count(),  # Всего гонок
        'first_year': races_qs.last().year if races_qs else '-',
        'last_year': races_qs.first().year if races_qs else '-',
    }

    context = {
        'circuit': circuit,
        'races_data': races_data,
        'top_driver': top_driver,
        'top_team': top_team,
        'stats': stats
    }
    return render(request, 'racing/circuit_detail.html', context)

def season_detail(request, year):
    # 1. Список доступных лет для меню
    available_years = Race.objects.values_list('year', flat=True).distinct().order_by('-year')

    # Проверка, есть ли данные за этот год
    if year not in available_years and available_years:
        year = available_years[0]  # Если ввели 1900 год, кидаем на последний доступный

    # --- 1. ЛИЧНЫЙ ЗАЧЕТ (DRIVERS) ---
    driver_standings = []

    # Берем всех пилотов, у которых были результаты в этом году
    drivers = Driver.objects.filter(
        Q(results__race__year=year) | Q(sprint_results__race__year=year)
    ).distinct()

    for driver in drivers:
        # Считаем очки (Гонки + Спринты)
        p_race = Result.objects.filter(driver=driver, race__year=year).aggregate(Sum('points'))['points__sum'] or 0
        p_sprint = SprintResult.objects.filter(driver=driver, race__year=year).aggregate(Sum('points'))[
                       'points__sum'] or 0
        total_points = p_race + p_sprint

        # Считаем победы и подиумы (для статистики и тай-брейков)
        # Победы в спринтах обычно не считаются в официальную статистику "Wins", только Гран-при
        wins = Result.objects.filter(driver=driver, race__year=year, position=1).count()
        podiums = Result.objects.filter(driver=driver, race__year=year, position__lte=3).count()

        # Находим команду (последнюю в сезоне)
        last_res = Result.objects.filter(driver=driver, race__year=year).order_by('-race__date').first()
        team = last_res.constructor if last_res else None

        driver_standings.append({
            'driver': driver,
            'team': team,
            'points': total_points,
            'wins': wins,
            'podiums': podiums
        })

    # Сортируем: сначала по Очкам, потом по Победам (правила Ф1)
    driver_standings.sort(key=lambda x: (x['points'], x['wins']), reverse=True)

    # --- 2. КУБОК КОНСТРУКТОРОВ (CONSTRUCTORS) ---
    team_standings = []

    teams = Constructor.objects.filter(
        Q(result__race__year=year) | Q(sprintresult__race__year=year)
    ).distinct()

    for team in teams:
        # Очки пилотов суммируются для команды
        p_race = Result.objects.filter(constructor=team, race__year=year).aggregate(Sum('points'))['points__sum'] or 0
        p_sprint = SprintResult.objects.filter(constructor=team, race__year=year).aggregate(Sum('points'))[
                       'points__sum'] or 0
        total_points = p_race + p_sprint

        wins = Result.objects.filter(constructor=team, race__year=year, position=1).count()
        podiums = Result.objects.filter(constructor=team, race__year=year, position__lte=3).count()

        team_standings.append({
            'team': team,
            'points': total_points,
            'wins': wins,
            'podiums': podiums
        })

    # Сортировка
    team_standings.sort(key=lambda x: (x['points'], x['wins']), reverse=True)

    context = {
        'year': year,
        'available_years': available_years,
        'driver_standings': driver_standings,
        'team_standings': team_standings,
    }
    return render(request, 'racing/season_detail.html', context)


def race_detail(request, year, round):
    # Получаем саму гонку
    race = get_object_or_404(Race, year=year, round=round)

    # 1. Основные результаты (Main Race)
    # Сортируем по позиции. Те, кто сошел (position=None), пойдут в конец
    results = Result.objects.filter(race=race).select_related('driver', 'constructor').order_by(
        F('position').asc(nulls_last=True)
    )

    # Выделяем подиум (Топ-3) для красивого отображения сверху
    podium = []
    if results.exists():
        # Берем первые 3 финишировавших (исключая сходы)
        podium = [r for r in results[:3] if r.position]

    # 2. Результаты спринта (если был)
    sprint_results = SprintResult.objects.filter(race=race).select_related('driver', 'constructor').order_by(
        F('position').asc(nulls_last=True)
    )

    context = {
        'race': race,
        'results': results,
        'sprint_results': sprint_results,
        'podium': podium,
    }
    return render(request, 'racing/race_detail.html', context)


def calendar_view(request, year):
    # Доступные годы
    available_years = Race.objects.values_list('year', flat=True).distinct().order_by('-year')
    if year not in available_years and available_years:
        year = available_years[0]

    # Берем все гонки года по порядку
    races_qs = Race.objects.filter(year=year).order_by('round').select_related('circuit')

    calendar_data = []

    for race in races_qs:
        # Проверяем, есть ли результаты (значит гонка прошла)
        results = Result.objects.filter(race=race).select_related('driver', 'constructor').order_by('position')

        is_finished = results.exists()
        podium = []

        if is_finished:
            # Собираем подиум: [1 место, 2 место, 3 место]
            # Нам нужно именно в таком порядке для данных, а в шаблоне мы их переставим визуально (2-1-3)
            podium = list(results[:3])

        calendar_data.append({
            'race': race,
            'is_finished': is_finished,
            'podium': podium
        })

    context = {
        'calendar_data': calendar_data,
        'year': year,
        'available_years': available_years
    }
    return render(request, 'racing/calendar.html', context)


def search(request):
    query = request.GET.get('q', '').strip()

    drivers_results = []
    teams_results = []
    circuits_results = []
    races_results = []

    smart_answer = None

    if query:
        query_lower = query.lower()

        # --- 0. ПОИСК ГОДА В ЗАПРОСЕ ---
        year_match = re.search(r'\b(19|20)\d{2}\b', query)
        search_year = int(year_match.group(0)) if year_match else None

        # --- 1. ЛОГИКА "УМНОГО ОТВЕТА" (ЧЕМПИОН) ---
        if search_year:
            keywords_champion = ['чемпион', 'победил', 'выиграл', 'champion', 'winner', 'won']
            if any(k in query_lower for k in keywords_champion):
                # ... (ТУТ ТОТ ЖЕ КОД ПОДСЧЕТА ЧЕМПИОНА, ЧТО БЫЛ РАНЬШЕ) ...
                # (Я его сокращу здесь, но оставь его как был)
                drivers = Driver.objects.filter(results__race__year=search_year).distinct()
                best_driver = None
                max_points = -1
                for d in drivers:
                    p1 = Result.objects.filter(driver=d, race__year=search_year).aggregate(Sum('points'))[
                             'points__sum'] or 0
                    p2 = SprintResult.objects.filter(driver=d, race__year=search_year).aggregate(Sum('points'))[
                             'points__sum'] or 0
                    if (p1 + p2) > max_points:
                        max_points = (p1 + p2)
                        best_driver = d
                if best_driver:
                    smart_answer = {'title': f"Чемпион {search_year}", 'obj': best_driver,
                                    'description': f"Набрал {int(max_points)} очков."}

        # === ПОИСК ПО БАЗЕ (БЕЗ ЛИМИТОВ) ===

        # А. ПИЛОТЫ (Fuzzy)
        all_drivers = Driver.objects.all()
        # Если введен год - ищем пилотов, выступавших в этом году
        if search_year and 'пилот' in query_lower:
            all_drivers = all_drivers.filter(results__race__year=search_year).distinct()

        for d in all_drivers:
            # Сравниваем с фамилией и полным именем
            if fuzz.partial_ratio(query_lower, d.surname.lower()) > 80 or \
                    fuzz.partial_ratio(query_lower, f"{d.forename} {d.surname}".lower()) > 80:
                drivers_results.append(d)

        # Б. КОМАНДЫ (Fuzzy)
        for t in Constructor.objects.all():
            if fuzz.partial_ratio(query_lower, t.name.lower()) > 80:
                teams_results.append(t)

        # В. ТРАССЫ (Fuzzy)
        for c in Circuit.objects.all():
            # Ищем по названию, городу или стране
            full_str = f"{c.name} {c.location} {c.country}"
            if fuzz.partial_ratio(query_lower, full_str.lower()) > 75:
                circuits_results.append(c)

        # Г. ГОНКИ (Улучшенный поиск)
        # 1. Если есть год в запросе -> берем ВСЕ гонки этого года
        if search_year:
            # Если запрос просто "2019" или "Гран при 2019"
            year_races = Race.objects.filter(year=search_year).order_by('date')
            # Если есть еще слова кроме года (например "Bahrain 2019"), фильтруем
            clean_query = query.replace(str(search_year), '').strip()

            if len(clean_query) > 2:
                for r in year_races:
                    if fuzz.partial_ratio(clean_query.lower(), r.name.lower()) > 70:
                        races_results.append(r)
            else:
                # Если просто год - отдаем все гонки года
                races_results = list(year_races)

        # 2. Если года нет -> ищем по названию (fuzzy)
        else:
            all_races = Race.objects.all().order_by('-date')
            # Оптимизация: сначала пробуем строгий поиск
            strict_matches = all_races.filter(name__icontains=query)
            races_results.extend(list(strict_matches))

            # Если мало нашли, подключаем Fuzzy (но осторожно, это долго на 1000 гонках)
            if len(races_results) < 5:
                # Берем последние 5 сезонов для скорости или ищем везде
                for r in all_races[:100]:  # Ищем только в последних 100 гонках, чтобы не вис сайт
                    if r not in races_results and fuzz.partial_ratio(query_lower, r.name.lower()) > 80:
                        races_results.append(r)

    context = {
        'query': query,
        'smart_answer': smart_answer,
        'drivers': list(set(drivers_results)),  # Убираем дубликаты
        'teams': list(set(teams_results)),
        'circuits': list(set(circuits_results)),
        'races': list(set(races_results)),
        'total_results': len(drivers_results) + len(teams_results) + len(circuits_results) + len(races_results)
    }
    return render(request, 'racing/search_results.html', context)