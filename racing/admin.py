from django.contrib import admin
from .models import Circuit, Constructor, Driver, Race, Result, SprintResult

@admin.register(Circuit)
class CircuitAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'country')
    search_fields = ('name', 'country')

@admin.register(Constructor)
class ConstructorAdmin(admin.ModelAdmin):
    list_display = ('name', 'nationality')
    search_fields = ('name',)

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('surname', 'forename', 'nationality', 'dob')
    search_fields = ('surname', 'forename')
    list_filter = ('nationality',)

@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ('year', 'name', 'circuit', 'date')
    list_filter = ('year',) # Удобный фильтр по годам справа
    search_fields = ('name',)

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('race', 'driver', 'constructor', 'position', 'points')
    list_filter = ('race__year', 'constructor') # Фильтр по году гонки и команде
    search_fields = ('driver__surname', 'race__name')

@admin.register(SprintResult)
class SprintResultAdmin(admin.ModelAdmin):
    list_display = ('race', 'driver','constructor', 'position', 'points')
    list_filter = ('race__year', 'constructor')
    search_fields = ('driver__surname', 'race__name')