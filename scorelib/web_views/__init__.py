"""
SKG Notenbank - Sheet Music Database and Archive Management System
Copyright (C) 2026 Arno Euteneuer

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

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
