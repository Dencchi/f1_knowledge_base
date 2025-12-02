import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from racing.models import Circuit


class Command(BaseCommand):
    help = 'Парсинг схем трасс (Проверка всех записей)'

    def handle(self, *args, **kwargs):
        all_circuits = Circuit.objects.all()
        self.stdout.write(f"Всего трасс в базе: {all_circuits.count()}")
        self.stdout.write("--- НАЧИНАЕМ ПРОВЕРКУ ---")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        count_success = 0

        for circuit in all_circuits:
            # ПРОВЕРКА: Если картинка уже есть, пропускаем
            # Проверяем и само поле, и атрибут name
            if circuit.layout_image and circuit.layout_image.name:
                # self.stdout.write(f"[{circuit.name}] Схема есть, пропускаем.")
                continue

            self.stdout.write(f"Поиск для: {circuit.name}...", ending='')

            # --- 1. ОПРЕДЕЛЕНИЕ URL ---
            target_url = circuit.url
            if not target_url:
                # Генерируем ссылку, если её нет
                possible_names = [
                    circuit.name.replace(' ', '_'),
                    f"{circuit.name}_Circuit".replace(' ', '_'),
                    f"Autodromo_{circuit.name}".replace(' ', '_')
                ]
                target_url = f"https://en.wikipedia.org/wiki/{possible_names[0]}"

            try:
                response = requests.get(target_url, headers=headers, timeout=5)
                if response.status_code == 404:
                    self.stdout.write(self.style.WARNING(" URL не работает."))
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')

                # --- 2. ПОИСК КАРТИНКИ ---
                infobox = soup.find('table', class_='infobox')
                if not infobox: infobox = soup.find('table', class_='vcard')

                if not infobox:
                    self.stdout.write(self.style.WARNING(" Нет инфобокса."))
                    continue

                images = infobox.find_all('img')
                best_image_url = None

                for img in images:
                    src = img.get('src', '')
                    if not src: continue

                    # Фильтр по размеру (чтобы не качать флаги)
                    try:
                        width = int(img.get('width', 0))
                    except:
                        width = 0
                    if width < 180: continue

                    filename = src.lower()
                    # Ищем слова "схема", "трасса" и т.д. в названии файла
                    keywords = ['circuit', 'layout', 'track', 'karte', 'strecke', 'ring', 'course', 'map']
                    if any(k in filename for k in keywords):
                        best_image_url = src
                        break

                        # Запасной вариант: берем просто большую картинку, если ключевые слова не сработали
                if not best_image_url and len(images) > 0:
                    for img in images:
                        try:
                            if int(img.get('width', 0)) > 250:
                                best_image_url = img.get('src')
                                break
                        except:
                            pass

                # --- 3. СКАЧИВАНИЕ ---
                if best_image_url:
                    if best_image_url.startswith('//'):
                        best_image_url = 'https:' + best_image_url

                    # Пытаемся получить оригинал (убираем /thumb/)
                    if '/thumb/' in best_image_url:
                        parts = best_image_url.split('/thumb/')
                        extension_part = parts[1].split('/')
                        original_url = parts[0] + '/' + '/'.join(extension_part[:-1])
                        if not original_url.endswith('.svg'):  # Django плохо дружит с SVG
                            best_image_url = original_url

                    img_resp = requests.get(best_image_url, headers=headers, timeout=10)

                    if img_resp.status_code == 200:
                        ext = best_image_url.split('.')[-1].split('/')[0]
                        if len(ext) > 4: ext = 'jpg'
                        fname = f"{circuit.circuit_ref}.{ext}"

                        circuit.layout_image.save(fname, ContentFile(img_resp.content), save=True)
                        self.stdout.write(self.style.SUCCESS(" OK!"))
                        count_success += 1
                    else:
                        self.stdout.write(self.style.ERROR(" Ошибка загрузки."))
                else:
                    self.stdout.write(self.style.WARNING(" Не найдено подходящее фото."))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f" Ошибка: {e}"))

        self.stdout.write(self.style.SUCCESS(f"--- ЗАВЕРШЕНО. Загружено: {count_success} ---"))