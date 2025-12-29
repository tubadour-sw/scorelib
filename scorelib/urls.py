from django.urls import path
from . import views

urlpatterns = [
    # Startseite für Musiker (Suche)
    path('', views.scorelib_index, name='scorelib_index'),
    
    # API für die Live-Suche
    path('api/search/', views.scorelib_search, name='scorelib_api_search'),
    
    # Die "Nächstes Konzert" Ansicht
    path('next-concert/', views.next_concert_view, name='next_concert'),
	
    # abgesicherter Download
    path('download/part/<int:part_id>/', views.protected_part_download, name='protected_part_download'),
	path('download/audio/<int:audio_id>/', views.protected_audio_download, name='protected_audio_download'),
]