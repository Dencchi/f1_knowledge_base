import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from racing.models import Driver


class Command(BaseCommand):
    help = 'Парсинг фото пилотов с Википедии'

    def handle(self, *args, **kwargs):
        # Берем пилотов без фото
        drivers = Driver.objects.filter(photo='')
        self.stdout.write(f"Пилотов без фото: {drivers.count()}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        success_count = 0

        for driver in drivers:
            self.stdout.write(f"[{driver.surname}] ", ending='')

            # 1. Ссылка
            url = driver.url
            if not url:
                # Пробуем угадать (Max_Verstappen)
                url = f"https://en.wikipedia.org/wiki/{driver.forename}_{driver.surname}"

            try:
                response = requests.get(url, headers=headers, timeout=5)
                # Если 404, пробуем добавить "_(racing_driver)" (частая практика на Вики)
                if response.status_code == 404:
                    url = f"{url}_(racing_driver)"
                    response = requests.get(url, headers=headers, timeout=5)

                if response.status_code != 200:
                    self.stdout.write(self.style.WARNING("URL не работает"))
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')
                infobox = soup.find('table', class_='infobox')

                if not infobox:
                    self.stdout.write(self.style.WARNING("Нет инфобокса"))
                    continue

                # 2. Ищем фото
                # Обычно фото пилота - это вторая картинка (первая часто иконка) или самая большая сверху
                images = infobox.find_all('img')
                target_url = None

                for img in images:
                    try:
                        width = int(img.get('width', 0))
                        # Игнорируем флаги и иконки (обычно они < 50px)
                        if width > 120:
                            target_url = img.get('src')
                            break  # Берем первое большое фото
                    except:
                        pass

                if not target_url:
                    self.stdout.write(self.style.WARNING("Фото не найдено"))
                    continue

                # 3. Чистим URL
                if target_url.startswith('//'):
                    target_url = 'https:' + target_url

                # 4. Скачиваем
                img_resp = requests.get(target_url, headers=headers, timeout=5)
                if img_resp.status_code == 200:
                    # Имя файла
                    ext = 'jpg'
                    if '.png' in target_url: ext = 'png'
                    filename = f"{driver.driver_ref}.{ext}"

                    driver.photo.save(filename, ContentFile(img_resp.content), save=True)
                    self.stdout.write(self.style.SUCCESS("OK"))
                    success_count += 1
                else:
                    self.stdout.write(self.style.ERROR("Ошибка скачивания"))

            except Exception:
                self.stdout.write(self.style.ERROR("Ошибка"))

        self.stdout.write(self.style.SUCCESS(f"--- ЗАГРУЖЕНО ФОТО: {success_count} ---"))