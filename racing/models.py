from django.db import models


# --- 1. ТРАССЫ (Circuits) ---
class Circuit(models.Model):
    circuit_ref = models.SlugField(primary_key=True, verbose_name="ID трассы (slug)")
    name = models.CharField(max_length=200, verbose_name="Название")
    location = models.CharField(max_length=100, verbose_name="Город")
    country = models.CharField(max_length=100, verbose_name="Страна")
    lat = models.FloatField(null=True, blank=True, verbose_name="Широта")
    lng = models.FloatField(null=True, blank=True, verbose_name="Долгота")
    url = models.URLField(verbose_name="Ссылка на Wiki", blank=True)

    # --- НОВОЕ ПОЛЕ ---
    layout_image = models.ImageField(upload_to='circuits/', verbose_name="Схема трассы", blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.country})"

    class Meta:
        verbose_name = "Трасса"
        verbose_name_plural = "Трассы"


# --- 2. КОМАНДА / КОНСТРУКТОР (Constructors) ---
class Constructor(models.Model):
    constructor_ref = models.SlugField(primary_key=True, verbose_name="ID команды (slug)")
    name = models.CharField(max_length=100, verbose_name="Название")
    nationality = models.CharField(max_length=100, verbose_name="Национальность")
    url = models.URLField(verbose_name="Ссылка на Wiki", blank=True)

    # --- НОВЫЕ ПОЛЯ ---
    logo = models.ImageField(upload_to='constructors/', verbose_name="Логотип", blank=True, null=True)
    description = models.TextField(verbose_name="Описание/История", blank=True)
    is_active = models.BooleanField(default=False, verbose_name="Активная команда (текущий сезон)")
    championships = models.IntegerField(default=0, verbose_name="Кубков Конструкторов")
    hex_color = models.CharField(max_length=7, default='#333333', verbose_name="Цвет (HEX)",
                                 help_text="Например: #FF0000")
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Команда"
        verbose_name_plural = "Команды"


# --- 3. ПИЛОТЫ (Drivers) ---
class Driver(models.Model):
    driver_ref = models.SlugField(primary_key=True, verbose_name="ID пилота (slug)")
    code = models.CharField(max_length=10, blank=True, verbose_name="Код (VER)")
    number = models.IntegerField(null=True, blank=True, verbose_name="Номер")

    # Имена (как в API)
    forename = models.CharField(max_length=100, verbose_name="Имя")
    surname = models.CharField(max_length=100, verbose_name="Фамилия")

    dob = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    nationality = models.CharField(max_length=100, verbose_name="Национальность")
    url = models.URLField(verbose_name="Ссылка на Wiki", blank=True)

    # --- Поля для ручного заполнения (для красивого сайта) ---
    photo = models.ImageField(upload_to='drivers/', verbose_name="Фото", blank=True, null=True)
    photo_cutout = models.ImageField(upload_to='drivers/cutouts/', verbose_name="Фото (Вырезка/Подиум)", blank=True, null=True)
    biography = models.TextField(verbose_name="Биография (RU)", blank=True, help_text="Текст на русском")
    championships = models.IntegerField(default=0, verbose_name="Титулов Чемпиона Мира")


    def __str__(self):
        return f"{self.forename} {self.surname}"

    # Хелпер для полного имени
    def full_name(self):
        return f"{self.forename} {self.surname}"

    class Meta:
        verbose_name = "Пилот"
        verbose_name_plural = "Пилоты"


# --- 4. ГОНКИ (Races) ---
class Race(models.Model):
    year = models.IntegerField(verbose_name="Сезон (Год)")
    round = models.IntegerField(verbose_name="Этап")
    circuit = models.ForeignKey(Circuit, on_delete=models.CASCADE, verbose_name="Трасса")
    name = models.CharField(max_length=200, verbose_name="Название Гран-при")
    date = models.DateField(verbose_name="Дата гонки")
    url = models.URLField(verbose_name="Ссылка на Wiki", blank=True)

    fp1_time = models.DateTimeField(null=True, blank=True, verbose_name="Практика 1")
    fp2_time = models.DateTimeField(null=True, blank=True, verbose_name="Практика 2")
    fp3_time = models.DateTimeField(null=True, blank=True, verbose_name="Практика 3")
    qualifying_time = models.DateTimeField(null=True, blank=True, verbose_name="Квалификация")
    sprint_quali_time = models.DateTimeField(null=True, blank=True, verbose_name="Спринт-квалификация")
    race_time = models.TimeField(null=True, blank=True, verbose_name="Время старта гонки")  # Отдельно время старта

    def __str__(self):
        return f"{self.year} {self.name}"

    class Meta:
        verbose_name = "Гонка"
        verbose_name_plural = "Гонки"
        ordering = ['-year', 'round']  # Сортировка: сначала новые


# --- 5. РЕЗУЛЬТАТЫ (Results) - Главная связующая таблица ---
class Result(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='results', verbose_name="Гонка")
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='results', verbose_name="Пилот")
    constructor = models.ForeignKey(Constructor, on_delete=models.CASCADE, verbose_name="Команда")

    grid = models.IntegerField(verbose_name="Старт")
    position = models.IntegerField(null=True, verbose_name="Финиш (место)")
    position_text = models.CharField(max_length=10, verbose_name="Финиш (текст)", help_text="R для схода")
    points = models.FloatField(verbose_name="Очки")
    status = models.CharField(max_length=100, verbose_name="Статус", help_text="Finished, Collision...")

    def __str__(self):
        return f"{self.race} - {self.driver} ({self.position})"

    class Meta:
        verbose_name = "Результат"
        verbose_name_plural = "Результаты"


# --- 6. РЕЗУЛЬТАТЫ СПРИНТОВ (Новая таблица) ---
class SprintResult(models.Model):
    # Связи такие же, как у основной гонки
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='sprint_results', verbose_name="Гонка")
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='sprint_results', verbose_name="Пилот")
    constructor = models.ForeignKey(Constructor, on_delete=models.CASCADE, verbose_name="Команда")

    grid = models.IntegerField(verbose_name="Старт")
    position = models.IntegerField(null=True, verbose_name="Финиш (место)")
    position_text = models.CharField(max_length=10, verbose_name="Финиш (текст)", help_text="R для схода")
    points = models.FloatField(verbose_name="Очки")
    status = models.CharField(max_length=100, verbose_name="Статус", help_text="Finished, Collision...")

    def __str__(self):
        return f"Sprint {self.race} - {self.driver}"

    class Meta:
        verbose_name = "Результат Спринта"
        verbose_name_plural = "Результаты Спринтов"