from .models import SiteSettings


def site_settings(request):
    """Adds the singleton SiteSettings to template context as `site_settings`.

    Use `SiteSettings.get_solo()` to ensure an instance exists.
    """
    try:
        settings = SiteSettings.get_solo()
    except Exception:
        settings = None
    return {
        'site_settings': settings
    }
