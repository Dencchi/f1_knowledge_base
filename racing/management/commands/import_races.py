import requests
import time
from django.core.management.base import BaseCommand
from racing.models import Circuit, Constructor, Driver, Race, Result, SprintResult
from django.utils.dateparse import parse_date


class Command(BaseCommand):
    help = 'Импорт ТОЛЬКО гонок и результатов (для обновлений)'

    BASE_URL = "http://api.jolpi.ca/ergast/f1"

    def add_arguments(self, parser):
        # Добавляем возможность указать год через консоль: --year 2024
        parser.add_argument(
            '--year',
            type=int,
            help='Укажите конкретный год для импорта (например, 2024)',
        )

    def handle(self, *args, **options):
        # Если год указан в консоли - берем его. Если нет - берем диапазон по умолчанию.
        if options['year']:
            years = [options['year']]
            self.stdout.write(f"--- ОБНОВЛЕНИЕ РЕЗУЛЬТАТОВ ЗА {options['year']} ГОД ---")
        else:
            years = range(2021, 2026)  # 2025 включительно
            self.stdout.write("--- ОБНОВЛЕНИЕ РЕЗУЛЬТАТОВ (2021-2025) ---")

        for year in years:
            self.import_season(year)

        self.stdout.write(self.style.SUCCESS("--- ГОТОВО ---"))

    def get_json(self, endpoint, params=None):
        url = f"{self.BASE_URL}/{endpoint}.json"
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка соединения: {e}"))
            return None

    def import_season(self, year):
        self.stdout.write(f"\nЗагрузка сезона {year}...")

        # 1. Получаем календарь
        schedule_data = self.get_json(f"{year}", params={'limit': 100})
        if not schedule_data: return

        races = schedule_data['MRData']['RaceTable']['Races']

        for race_info in races:
            round_num = race_info['round']
            race_name = race_info['raceName']

            # --- А. СОХРАНЯЕМ ГОНКУ ---
            circuit_ref = race_info['Circuit']['circuitId']
            try:
                circuit_obj = Circuit.objects.get(pk=circuit_ref)
            except Circuit.DoesNotExist:
                continue

            race_obj, _ = Race.objects.update_or_create(
                year=int(race_info['season']),
                round=int(round_num),
                defaults={
                    'name': race_name,
                    'date': parse_date(race_info['date']),
                    'circuit': circuit_obj,
                    'url': race_info.get('url', '')
                }
            )

            # --- Б. ОСНОВНАЯ ГОНКА (Results) ---
            res_data = self.get_json(f"{year}/{round_num}/results", params={'limit': 1000})
            if res_data and res_data['MRData']['RaceTable']['Races']:
                results_list = res_data['MRData']['RaceTable']['Races'][0]['Results']
                for res in results_list:
                    self.save_result(res, race_obj, Result)

            # --- В. СПРИНТ (SprintResults) - НОВОЕ! ---
            # API endpoint: /2024/5/sprint.json
            sprint_data = self.get_json(f"{year}/{round_num}/sprint", params={'limit': 1000})

            # Проверяем, был ли спринт (если нет, API вернет пустой список Races)
            if sprint_data and sprint_data['MRData']['RaceTable']['Races']:
                # Иногда структура чуть отличается, но обычно SprintResults внутри Races[0]
                sprint_list = sprint_data['MRData']['RaceTable']['Races'][0].get('SprintResults', [])

                if sprint_list:
                    self.stdout.write(f"   Этап {round_num}: {race_name} + СПРИНТ")
                    for res in sprint_list:
                        self.save_result(res, race_obj, SprintResult)
                else:
                    self.stdout.write(f"   Этап {round_num}: {race_name}")
            else:
                self.stdout.write(f"   Этап {round_num}: {race_name}")

            time.sleep(0.2)

        # Вспомогательная функция, чтобы не дублировать код сохранения

    def save_result(self, res, race_obj, model_class):
        try:
            driver_ref = res['Driver']['driverId']
            constructor_ref = res['Constructor']['constructorId']
            driver_obj = Driver.objects.get(pk=driver_ref)
            constructor_obj = Constructor.objects.get(pk=constructor_ref)

            try:
                pos_int = int(res['position'])
            except ValueError:
                pos_int = None

            model_class.objects.update_or_create(
                race=race_obj,
                driver=driver_obj,
                constructor=constructor_obj,
                defaults={
                    'grid': int(res['grid']),
                    'position': pos_int,
                    'position_text': res['positionText'],
                    'points': float(res['points']),
                    'status': res['status']
                }
            )
        except Exception:
            pass