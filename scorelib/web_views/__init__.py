from .account import legal_view, profile_view
from .workflows import (
    audio_ripping_page,
    delete_audio_recording,
    export_import_results_csv,
    import_musicians,
    merge_cluster_confirm,
    piece_csv_import,
    process_single_audio,
    suggest_merges_page,
)
from .archive import index, piece_detail, scorelib_index, scorelib_search
from .concerts import (
    concert_detail_view,
    concert_list_view,
    export_concert_setlist_gema,
)
from .downloads import protected_audio_download, protected_part_download

__all__ = [
    "audio_ripping_page",
    "concert_detail_view",
    "concert_list_view",
    "delete_audio_recording",
    "export_concert_setlist_gema",
    "export_import_results_csv",
    "import_musicians",
    "index",
    "legal_view",
    "merge_cluster_confirm",
    "piece_csv_import",
    "piece_detail",
    "process_single_audio",
    "profile_view",
    "protected_audio_download",
    "protected_part_download",
    "scorelib_index",
    "scorelib_search",
    "suggest_merges_page",
]
