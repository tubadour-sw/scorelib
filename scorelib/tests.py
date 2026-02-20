import shutil
import tempfile
from unittest.mock import mock_open, patch

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Composer,
    Concert,
    InstrumentGroup,
    MusicianProfile,
    Part,
    Piece,
    ProgramItem,
    AudioRecording,
)


class ScorelibSmokeTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media = tempfile.mkdtemp(prefix="scorelib_test_media_")
        cls._override = override_settings(MEDIA_ROOT=cls._temp_media)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._temp_media, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.composer = Composer.objects.create(name="Test Composer")
        cls.piece = Piece.objects.create(title="Test Piece", composer=cls.composer)
        cls.concert = Concert.objects.create(
            title="Test Concert",
            date=timezone.now() + timedelta(days=1),
        )
        ProgramItem.objects.create(concert=cls.concert, piece=cls.piece, order=1)

        cls.part = Part.objects.create(
            piece=cls.piece,
            part_name="Trumpet 1",
        )
        cls.part.pdf_file.save("part.pdf", ContentFile(b"%PDF-1.4 test"), save=True)

        cls.audio = AudioRecording.objects.create(
            piece=cls.piece,
            concert=cls.concert,
            description="test",
        )
        cls.audio.audio_file.save("recording.mp3", ContentFile(b"ID3test"), save=True)

        cls.staff_user = User.objects.create_user(username="staff", password="x")
        cls.staff_user.is_staff = True
        cls.staff_user.save(update_fields=["is_staff"])

        cls.regular_user = User.objects.create_user(username="regular", password="x")
        cls.group = InstrumentGroup.objects.create(
            name="Trumpet Group",
            filter_strings="Trumpet*",
        )
        profile, _ = MusicianProfile.objects.get_or_create(user=cls.regular_user)
        profile.instrument_groups.set([cls.group])
        profile.has_full_archive_access = True
        profile.save(update_fields=["has_full_archive_access"])

        cls.user_without_profile = User.objects.create_user(
            username="no_profile", password="x"
        )
        MusicianProfile.objects.filter(user=cls.user_without_profile).delete()

    def test_named_urls_resolve(self):
        urls = [
            reverse("next_concert"),
            reverse("scorelib_index"),
            reverse("concert_list"),
            reverse("concert_detail", args=[self.concert.id]),
            reverse("protected_part_download", args=[self.part.id]),
            reverse("protected_audio_download", args=[self.audio.id]),
            reverse("scorelib_piece_detail", args=[self.piece.id]),
            reverse("profile_view"),
            reverse("suggest_merges_page", args=["composer"]),
            reverse("merge_cluster_confirm", args=["composer"]),
            reverse("audio_ripping_page", args=[self.concert.id]),
            reverse("process_single_audio"),
            reverse("delete_audio_recording"),
        ]
        self.assertEqual(len(urls), 13)

    def test_login_required_views_redirect_for_anonymous(self):
        protected = [
            reverse("next_concert"),
            reverse("scorelib_index"),
            reverse("concert_list"),
            reverse("scorelib_piece_detail", args=[self.piece.id]),
            reverse("profile_view"),
            reverse("protected_part_download", args=[self.part.id]),
        ]
        for url in protected:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response.url)

    def test_staff_only_audio_workflows_forbidden_for_non_staff(self):
        self.client.force_login(self.regular_user)

        response_page = self.client.get(
            reverse("audio_ripping_page", args=[self.concert.id])
        )
        self.assertEqual(response_page.status_code, 302)

        response_process = self.client.post(reverse("process_single_audio"))
        self.assertEqual(response_process.status_code, 403)

        response_delete = self.client.post(
            reverse("delete_audio_recording"),
            {"recording_id": self.audio.id},
        )
        self.assertEqual(response_delete.status_code, 403)

    def test_part_download_allowed_for_staff_user(self):
        self.client.force_login(self.staff_user)
        with patch(
            "scorelib.web_views.downloads.os.path.exists", return_value=True
        ), patch(
            "scorelib.web_views.downloads.open", mock_open(read_data=b"%PDF-1.4 test")
        ):
            response = self.client.get(
                reverse("protected_part_download", args=[self.part.id])
            )
        self.assertEqual(response.status_code, 200)

    def test_part_download_denied_without_profile(self):
        self.client.force_login(self.user_without_profile)
        response = self.client.get(
            reverse("protected_part_download", args=[self.part.id])
        )
        self.assertEqual(response.status_code, 403)
