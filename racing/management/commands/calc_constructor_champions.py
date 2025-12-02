import requests
import datetime
from django.core.management.base import BaseCommand
from racing.models import Constructor


class Command(BaseCommand):
    help = 'Автоматический подсчет Кубков Конструкторов через API'

    BASE_URL = "http://api.jolpi.ca/ergast/f1"

    def handle(self, *args, **kwargs):
        self.stdout.write("--- НАЧИНАЕМ ПОДСЧЕТ КУБКОВ КОНСТРУКТОРОВ ---")

        # 1. Сбрасываем счетчик всем командам (чтобы избежать дублей при повторном запуске)
        # Убедись, что в модели Constructor есть поле championships!
        Constructor.objects.update(championships=0)
        self.stdout.write("Счетчики кубков сброшены.")

        # 2. Определяем диапазон лет
        current_year = datetime.date.today().year

        # ВАЖНО: Кубок конструкторов вручается с 1958 года.
        # До 2025 (не включительно), то есть закончит на 2024.
        years = range(1958, current_year)

        for year in years:
            # Запрашиваем таблицу конструкторов, нам нужен только победитель (limit=1)
            # URL: /api/f1/1990/constructorStandings.json
            url = f"{self.BASE_URL}/{year}/constructorStandings.json?limit=1"

            try:
                r = requests.get(url, timeout=10)
                data = r.json()

                # Проверяем, есть ли данные
                standings_list = data['MRData']['StandingsTable']['StandingsLists']
                if not standings_list:
                    self.stdout.write(self.style.WARNING(f"Нет данных за {year} год"))
                    continue

                # Берем данные победителя. Структура JSON отличается от Drivers!
                # Здесь ключ 'ConstructorStandings'
                champion_data = standings_list[0]['ConstructorStandings'][0]

                # Получаем ID команды (например, "mclaren", "ferrari")
                constructor_ref = champion_data['Constructor']['constructorId']

                # Находим команду в базе и обновляем
                try:
                    team = Constructor.objects.get(pk=constructor_ref)
                    team.championships += 1
                    team.save()
                    # Можно вывести лог для проверки
                    # self.stdout.write(f"{year}: {team.name} (+1)")
                except Constructor.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f"Ошибка: Команда {constructor_ref} ({year}) не найдена в базе!"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Ошибка запроса {year}: {e}"))

        self.stdout.write(
            self.style.SUCCESS(f"--- ГОТОВО. Данные о конструкторах обновлены до {current_year - 1} года ---"))