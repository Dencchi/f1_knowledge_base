import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime, parse_time, parse_date
from racing.models import Race, Circuit


class Command(BaseCommand):
    help = 'Импорт расписания (Практики, Квалификации) без результатов'

    BASE_URL = "http://api.jolpi.ca/ergast/f1"

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Конкретный год')

    def handle(self, *args, **options):
        # Если год не указан, берем текущий и следующий (на всякий случай)
        if options['year']:
            years = [options['year']]
        else:
            years = [2024, 2025]

        self.stdout.write(f"--- ИМПОРТ РАСПИСАНИЯ ДЛЯ: {years} ---")

        for year in years:
            self.import_year_schedule(year)

        self.stdout.write(self.style.SUCCESS("--- ГОТОВО ---"))

    def get_json(self, endpoint):
        try:
            r = requests.get(f"{self.BASE_URL}/{endpoint}", timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка API: {e}"))
            return None

    def combine_date_time(self, session_data):
        """Склеивает дату и время из API в формат datetime для Django"""
        if not session_data: return None
        d = session_data.get('date')
        t = session_data.get('time')
        if d and t:
            return parse_datetime(f"{d}T{t}")
        return None

    def import_year_schedule(self, year):
        self.stdout.write(f"Запрос календаря на {year} год...")

        # Делаем всего ОДИН запрос на весь год!
        data = self.get_json(f"{year}.json")

        if not data or not data['MRData']['RaceTable']['Races']:
            self.stdout.write(self.style.WARNING(f"Данных за {year} год нет."))
            return

        races = data['MRData']['RaceTable']['Races']
        count = 0

        for info in races:
            round_num = info['round']
            race_name = info['raceName']

            # --- Парсинг времени сессий ---
            fp1 = self.combine_date_time(info.get('FirstPractice'))
            fp2 = self.combine_date_time(info.get('SecondPractice'))
            fp3 = self.combine_date_time(info.get('ThirdPractice'))
            quali = self.combine_date_time(info.get('Qualifying'))
            sprint_quali = self.combine_date_time(info.get('SprintQualifying'))

            # Парсинг времени гонки
            race_time_obj = None
            if info.get('time'):
                race_time_obj = parse_time(info.get('time'))

            # Парсинг даты спринта
            sprint_date_obj = None
            if info.get('Sprint'):
                sprint_date_obj = parse_date(info.get('Sprint', {}).get('date'))

            # --- Обновление в БД ---
            # Мы используем update_or_create, чтобы не дублировать гонки

            # Сначала находим трассу (если её нет - пропускаем, или создаем заглушку)
            # Но по идее трассы у тебя уже загружены первым скриптом
            circuit_ref = info['Circuit']['circuitId']
            try:
                circuit_obj = Circuit.objects.get(pk=circuit_ref)
            except Circuit.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Трасса {circuit_ref} не найдена, пропускаем {race_name}"))
                continue

            Race.objects.update_or_create(
                year=year,
                round=round_num,
                defaults={
                    'name': race_name,
                    'date': parse_date(info['date']),
                    'circuit': circuit_obj,
                    'url': info.get('url', ''),

                    # Расписание
                    'fp1_time': fp1,
                    'fp2_time': fp2,
                    'fp3_time': fp3,
                    'qualifying_time': quali,
                    'sprint_quali_time': sprint_quali,
                    'race_time': race_time_obj,
                    'sprint_date': sprint_date_obj
                }
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Обновлено расписание для {count} этапов."))