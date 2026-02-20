from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.urls import path, reverse
from django.utils.html import format_html

from ..models import LoanRecord, MusicianProfile
from ..views import import_musicians


@admin.register(MusicianProfile)
class MusicianProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_groups", "has_full_archive_access")
    list_editable = ("has_full_archive_access",)
    filter_horizontal = ("instrument_groups",)
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "instrument_groups__name",
    )

    def display_groups(self, obj):
        return ", ".join([g.name for g in obj.instrument_groups.all()])

    display_groups.short_description = "Instrumente"


class MusicianProfileInline(admin.StackedInline):
    model = MusicianProfile
    can_delete = False
    verbose_name_plural = "Musician Profile / Instrument Filter"
    fk_name = "user"


class UserAdmin(BaseUserAdmin):
    inlines = (MusicianProfileInline,)
    change_list_template = "admin/user_changelist_custom.html"
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "get_instruments",
        "is_staff",
        "is_active",
    )
    list_editable = ("is_active",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-user-csv/",
                self.admin_site.admin_view(import_musicians),
                name="import_musicians",
            ),
        ]
        return custom_urls + urls

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

    def get_instruments(self, obj):
        if hasattr(obj, "profile"):
            return ", ".join([g.name for g in obj.profile.instrument_groups.all()])
        return "-"

    get_instruments.short_description = "Instrumente"


class CurrentLoanFilter(admin.SimpleListFilter):
    title = "Aktueller Status"
    parameter_name = "is_active"

    def lookups(self, request, model_admin):
        return (
            ("active", "Nur laufende Vorgänge"),
            ("closed", "Abgeschlossen"),
        )

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(return_date__isnull=True)
        if self.value() == "closed":
            return queryset.filter(return_date__isnull=False)


@admin.register(LoanRecord)
class LoanRecordAdmin(admin.ModelAdmin):
    list_display = (
        "piece_link",
        "get_type",
        "partner_name",
        "loan_date",
        "return_date",
        "is_active_badge",
    )

    list_filter = (
        "piece__is_owned_by_orchestra",
        "loan_date",
        "return_date",
        CurrentLoanFilter,
    )

    search_fields = ("piece__title", "partner_name", "notes")

    def get_type(self, obj):
        if obj.piece.is_owned_by_orchestra:
            return format_html('<span style="color: #d63384;">↗ Verleih</span>')
        return format_html('<span style="color: #0dcaf0;">↘ Fremd-Leihgabe</span>')

    get_type.short_description = "Art"

    def is_active_badge(self, obj):
        if obj.return_date is None:
            return format_html(
                '<span style="background: #ffc107; color: #000; padding: 2px 8px; border-radius: 10px;">AKTUELL</span>'
            )
        return format_html('<span style="color: #6c757d;">Abgeschlossen</span>')

    is_active_badge.short_description = "Status"

    def piece_link(self, obj):
        url = reverse("admin:scorelib_piece_change", args=[obj.piece.id])
        return format_html('<strong><a href="{}">{}</a></strong>', url, obj.piece)

    piece_link.short_description = "Piece"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
