from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Главная
    path('', views.index, name='home'),

    # --- ПИЛОТЫ ---
    path('drivers/', views.driver_list, name='driver_list'),
    path('drivers/<slug:driver_ref>/', views.driver_detail, name='driver_detail'),

    # --- КОМАНДЫ (сделаем позже) ---
    path('constructors/', views.constructor_list, name='constructor_list'),
    path('constructors/<slug:constructor_ref>/', views.constructor_detail, name='constructor_detail'),

    # --- ТРАССЫ (сделаем позже) ---
    path('circuits/', views.circuit_list, name='circuit_list'),
    path('circuits/<slug:circuit_ref>/', views.circuit_detail, name='circuit_detail'),

    # --- СЕЗОНЫ И ГОНКИ (сделаем позже) ---
    path('season/<int:year>/', views.season_detail, name='season_detail'),
    path('season/<int:year>/race/<int:round>/', views.race_detail, name='race_detail'),
    path('calendar/<int:year>/', views.calendar_view, name='calendar'),

    path('search/', views.search, name='search'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)