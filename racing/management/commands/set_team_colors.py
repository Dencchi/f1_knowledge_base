from django.core.management.base import BaseCommand
from racing.models import Constructor


class Command(BaseCommand):
    help = 'Установка цветов для команд F1'

    def handle(self, *args, **kwargs):
        # Словарь: Часть названия -> Цвет
        colors = {
            'Red Bull': '#3671C6',  # Blue
            'Ferrari': '#E80020',  # Red
            'Mercedes': '#27F4D2',  # Cyan/Silver
            'McLaren': '#FF8000',  # Papaya Orange
            'Aston Martin': '#229971',  # Racing Green
            'Alpine': '#0093CC',  # Blue/Pink
            'Williams': '#64C4FF',  # Light Blue
            'RB': '#6692FF',  # Visa RB Blue
            'AlphaTauri': '#2B4562',  # Navy
            'Sauber': '#52E252',  # Kick Green
            'Haas': '#B6BABD',  # White/Grey
            'Renault': '#FFF500',  # Yellow
            'Force India': '#F596C8',  # Pink
            'Lotus': '#000000',  # Black/Gold
            'Jordan': '#F8F228',  # Yellow
            'Benetton': '#008C8D'  # Green/Blue
        }

        count = 0
        for name_part, color in colors.items():
            # Находим команды, в названии которых есть этот ключ (icontains - регистронезависимо)
            teams = Constructor.objects.filter(name__icontains=name_part)
            for team in teams:
                team.hex_color = color
                team.save()
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Раскрашено команд: {count}"))