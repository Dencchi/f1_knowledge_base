import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from racing.models import Constructor


class Command(BaseCommand):
    help = 'Агрессивный поиск логотипов команд V3'

    def handle(self, *args, **kwargs):
        all_teams = Constructor.objects.all()
        self.stdout.write(f"Всего команд: {all_teams.count()}")
        self.stdout.write("--- НАЧИНАЕМ ПОИСК ЛОГОТИПОВ ---")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        success_count = 0

        for team in all_teams:
            # Проверка: если логотип уже есть и у него есть имя файла - пропускаем
            if team.logo and team.logo.name:
                continue

            self.stdout.write(f"Поиск для: {team.name}...", ending='')

            # 1. Формируем URL
            target_url = team.url
            if not target_url:
                # Генерируем варианты ссылок
                # Для Ferrari -> Scuderia_Ferrari, для McLaren -> McLaren_(racing_team)
                search_query = team.name.replace(' ', '_')
                target_url = f"https://en.wikipedia.org/wiki/{search_query}"

            try:
                response = requests.get(target_url, headers=headers, timeout=5)

                # Если 404, пробуем добавить "_(Formula_One)" или "_(racing_team)"
                if response.status_code == 404:
                    response = requests.get(f"{target_url}_(Formula_One)", headers=headers, timeout=5)

                if response.status_code != 200:
                    self.stdout.write(self.style.WARNING(" URL не работает"))
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')

                # 2. Ищем Инфобокс
                infobox = soup.find('table', class_='infobox')
                if not infobox:
                    self.stdout.write(self.style.WARNING(" Нет инфобокса"))
                    continue

                # 3. Ищем картинку
                # Логотип почти всегда ПЕРВАЯ картинка в инфобоксе
                images = infobox.find_all('img')
                best_image_url = None

                for img in images:
                    src = img.get('src', '')
                    try:
                        width = int(img.get('width', 0))
                        # Логотипы обычно от 100 до 300px. Флаги < 50px.
                        if width > 50:
                            best_image_url = src
                            break  # Берем первую нормальную картинку
                    except:
                        pass

                if not best_image_url:
                    self.stdout.write(self.style.WARNING(" Картинка не найдена"))
                    continue

                # 4. Обработка URL (Википедия часто дает //upload...)
                if best_image_url.startswith('//'):
                    best_image_url = 'https:' + best_image_url

                # Если это SVG, Википедия дает превью в .png в папке /thumb/
                # Мы скачаем именно это PNG превью, чтобы Django не ругался

                # 5. Скачиваем
                img_resp = requests.get(best_image_url, headers=headers, timeout=10)

                if img_resp.status_code == 200:
                    # Определяем расширение
                    ext = 'jpg'
                    if '.png' in best_image_url:
                        ext = 'png'
                    elif '.svg' in best_image_url:
                        ext = 'svg'  # На всякий случай

                    filename = f"{team.constructor_ref}.{ext}"

                    team.logo.save(filename, ContentFile(img_resp.content), save=True)
                    self.stdout.write(self.style.SUCCESS(" OK!"))
                    success_count += 1
                else:
                    self.stdout.write(self.style.ERROR(" Ошибка скачивания"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f" Ошибка: {e}"))

        self.stdout.write(self.style.SUCCESS(f"--- ИТОГ: Загружено {success_count} новых лого ---"))