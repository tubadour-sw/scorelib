from django.urls import path
from . import views

urlpatterns = [
    # Home page for musicians (next concert)
    path('', views.concert_detail_view, name='next_concert'),
    path('next-concert/', views.concert_detail_view, name='next_concert'),
    
    
    # API for live search
    path('api/search/', views.scorelib_search, name='scorelib_api_search'),
    path('concerts/', views.concert_list_view, name='concert_list'),
    path('concerts/<int:concert_id>/', views.concert_detail_view, name='concert_detail'),
    path('concerts/<int:concert_id>/export/gema/', views.export_concert_setlist_gema, name='export_concert_gema'),
    path('archive/', views.scorelib_index, name='scorelib_index'),
    
    # abgesicherter Download
    path('download/part/<int:part_id>/', views.protected_part_download, name='protected_part_download'),
    path('download/audio/<int:audio_id>/', views.protected_audio_download, name='protected_audio_download'),
    path('piece/<int:pk>/', views.piece_detail, name='scorelib_piece_detail'),
    path('legal/', views.legal_view, name='legal'),
    path('profile/', views.profile_view, name='profile_view'),
    path('import-csv-user/export/', views.export_import_results_csv, name='export_musicians_results'),
    
    # Merge suggestions workflow
    path('suggest-merges/<str:model_name>/', views.suggest_merges_page, name='suggest_merges_page'),
    path('merge-cluster/<str:model_name>/', views.merge_cluster_confirm, name='merge_cluster_confirm'),

    # audio ripping workflow
    path('admin/audio-ripping/<int:concert_id>/', views.audio_ripping_page, name='audio_ripping_page'),
    path('admin/api/process-audio/', views.process_single_audio, name='process_single_audio'),
    path('admin/api/delete-audio/', views.delete_audio_recording, name='delete_audio_recording')
]
