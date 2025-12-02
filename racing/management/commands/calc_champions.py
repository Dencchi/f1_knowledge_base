import requests
import datetime
from django.core.management.base import BaseCommand
from racing.models import Driver


class Command(BaseCommand):
    help = 'Автоматический подсчет титулов чемпионов мира (Пилоты)'

    BASE_URL = "http://api.jolpi.ca/ergast/f1"

    def handle(self, *args, **kwargs):
        self.stdout.write("--- НАЧИНАЕМ ПОДСЧЕТ ТИТУЛОВ ПИЛОТОВ ---")

        # 1. Сброс
        self.stdout.write("Сброс старых данных...")
        try:
            Driver.objects.update(championships=0)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка сброса (возможно, нет поля в БД?): {e}"))
            return

        # 2. Цикл по годам
        current_year = datetime.date.today().year
        # С 1950 по прошлый год
        years = range(1950, current_year)

        for year in years:
            # Пишем в консоль, чтобы видеть прогресс
            self.stdout.write(f"Обработка {year} года...", ending='')

            url = f"{self.BASE_URL}/{year}/driverStandings.json?limit=1"

            try:
                r = requests.get(url, timeout=10)
                data = r.json()

                standings_list = data['MRData']['StandingsTable']['StandingsLists']

                if not standings_list:
                    self.stdout.write(self.style.WARNING(" Нет данных"))
                    continue

                # Берем данные победителя
                champion_data = standings_list[0]['DriverStandings'][0]
                driver_ref = champion_data['Driver']['driverId']

                # Находим и обновляем
                try:
                    driver = Driver.objects.get(pk=driver_ref)
                    driver.championships += 1
                    driver.save()
                    self.stdout.write(self.style.SUCCESS(f" OK -> {driver.surname}"))
                except Driver.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f" Пилот {driver_ref} не найден в базе!"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f" Ошибка запроса: {e}"))

        self.stdout.write(self.style.SUCCESS(f"--- ГОТОВО ---"))