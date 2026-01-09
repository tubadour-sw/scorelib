from django.urls import path
from . import views

urlpatterns = [
    # Startseite für Musiker (Suche)
    path('', views.scorelib_index, name='scorelib_index'),
    
    # API für die Live-Suche
    path('api/search/', views.scorelib_search, name='scorelib_api_search'),
    path('concerts/', views.concert_list_view, name='concert_list'),
    path('concerts/<int:concert_id>/', views.concert_detail_view, name='concert_detail'),
    # Der alte Link "Nächstes Konzert" nutzt den View einfach ohne ID
    path('next-concert/', views.concert_detail_view, name='next_concert'),
    # abgesicherter Download
    path('download/part/<int:part_id>/', views.protected_part_download, name='protected_part_download'),
    path('download/audio/<int:audio_id>/', views.protected_audio_download, name='protected_audio_download'),
    path('piece/<int:pk>/', views.piece_detail, name='scorelib_piece_detail'),
    path('legal/', views.legal_view, name='legal'),
    path('profile/', views.profile_view, name='profile_view'),
]
