import requests
import time
from django.core.management.base import BaseCommand
from racing.models import Circuit, Constructor, Driver, Race, Result
from django.utils.dateparse import parse_date


class Command(BaseCommand):
    help = 'Импорт данных из Jolpica (Ergast) API с Пагинацией'

    # Года для результатов
    START_YEAR = 2021
    END_YEAR = 2026

    BASE_URL = "http://api.jolpi.ca/ergast/f1"

    def handle(self, *args, **kwargs):
        self.stdout.write("--- ЗАПУСК ИМПОРТА (РЕЖИМ ПАГИНАЦИИ) ---")

        # 1. Сначала ГАРАНТИРОВАННО скачиваем все справочники целиком
        self.import_all_items_paginated("circuits", self.save_circuit, "CircuitTable", "Circuits")
        self.import_all_items_paginated("constructors", self.save_constructor, "ConstructorTable", "Constructors")
        self.import_all_items_paginated("drivers", self.save_driver, "DriverTable", "Drivers")

        # 2. Только когда все пилоты в базе, качаем результаты
        self.import_seasons_detailed()

        self.stdout.write(self.style.SUCCESS("--- ВСЕ ДАННЫЕ УСПЕШНО ЗАГРУЖЕНЫ ---"))

    def get_json(self, endpoint, params=None):
        url = f"{self.BASE_URL}/{endpoint}.json"
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка: {e}"))
            return None

    # --- УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДЛЯ СКАЧИВАНИЯ СПИСКОВ ЧАСТЯМИ ---
    def import_all_items_paginated(self, endpoint, save_func, table_key, list_key):
        self.stdout.write(f"Скачивание {endpoint}...")
        offset = 0
        limit = 100  # Качаем по 100 штук за раз
        total_saved = 0

        while True:
            params = {'limit': limit, 'offset': offset}
            data = self.get_json(endpoint, params)

            if not data: break

            items = data['MRData'][table_key][list_key]

            if not items:
                break  # Если список пуст, значит мы скачали всё

            # Сохраняем полученную пачку
            for item in items:
                save_func(item)

            count = len(items)
            total_saved += count
            self.stdout.write(f"   ...загружено {count} шт. (всего {total_saved})")

            if count < limit:
                break  # Если вернулось меньше лимита, это была последняя страница

            offset += limit  # Сдвигаем курсор
            time.sleep(0.1)  # Небольшая пауза

        self.stdout.write(self.style.SUCCESS(f"-> ИТОГО {endpoint}: {total_saved} записей."))

    # --- ФУНКЦИИ СОХРАНЕНИЯ (То же самое, что и раньше) ---
    def save_circuit(self, item):
        Circuit.objects.update_or_create(
            circuit_ref=item['circuitId'],
            defaults={
                'name': item['circuitName'],
                'location': item['Location']['locality'],
                'country': item['Location']['country'],
                'lat': float(item['Location']['lat']),
                'lng': float(item['Location']['long']),
                'url': item.get('url', ''),
            }
        )

    def save_constructor(self, item):
        Constructor.objects.update_or_create(
            constructor_ref=item['constructorId'],
            defaults={
                'name': item['name'],
                'nationality': item['nationality'],
                'url': item.get('url', ''),
            }
        )

    def save_driver(self, item):
        Driver.objects.update_or_create(
            driver_ref=item['driverId'],
            defaults={
                'code': item.get('code', ''),
                'number': int(item['permanentNumber']) if item.get('permanentNumber') else None,
                'forename': item['givenName'],
                'surname': item['familyName'],
                'dob': parse_date(item['dateOfBirth']) if item.get('dateOfBirth') else None,
                'nationality': item['nationality'],
                'url': item.get('url', ''),
            }
        )

    # --- ИМПОРТ ГОНОК (Оставили детальный проход) ---
    def import_seasons_detailed(self):
        self.stdout.write("\nЗагрузка результатов гонок...")

        for year in range(self.START_YEAR, self.END_YEAR):
            self.stdout.write(f"Сезон {year}...")

            # 1. Качаем календарь
            schedule_data = self.get_json(f"{year}", params={'limit': 100})
            if not schedule_data: continue

            races = schedule_data['MRData']['RaceTable']['Races']

            for race_info in races:
                round_num = race_info['round']
                race_name = race_info['raceName']

                # Сохраняем гонку
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

                # 2. Качаем результаты (Тут обычно <30 записей, пагинация редко нужна, но лимит 1000 ставим на всякий)
                res_data = self.get_json(f"{year}/{round_num}/results", params={'limit': 1000})

                if not res_data or not res_data['MRData']['RaceTable']['Races']:
                    continue

                results_list = res_data['MRData']['RaceTable']['Races'][0]['Results']

                for res in results_list:
                    driver_ref = res['Driver']['driverId']
                    constructor_ref = res['Constructor']['constructorId']

                    try:
                        # ТЕПЕРЬ ЭТО СРАБОТАЕТ, так как все пилоты точно загружены выше
                        driver_obj = Driver.objects.get(pk=driver_ref)
                        constructor_obj = Constructor.objects.get(pk=constructor_ref)

                        try:
                            pos_int = int(res['position'])
                        except ValueError:
                            pos_int = None

                        Result.objects.update_or_create(
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
                    except Exception as e:
                        # Если вдруг ошибка - выведем её, чтобы знать
                        self.stdout.write(f"Ошибка результата: {driver_ref} в {race_name}")

                self.stdout.write(f"   -> {race_name}: OK ({len(results_list)} пилотов)")
                time.sleep(0.2)