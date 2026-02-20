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

from .models import SiteSettings


def site_settings(request):
    """Adds the singleton SiteSettings to template context as `site_settings`.

    Use `SiteSettings.get_solo()` to ensure an instance exists.
    """
    try:
        settings = SiteSettings.get_solo()
    except Exception:
        settings = None
    return {"site_settings": settings}
