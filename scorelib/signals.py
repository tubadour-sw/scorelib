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

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import MusicianProfile

#@receiver(post_save, sender=User)
#def save_user_profile(sender, instance, **kwargs):
#    if hasattr(instance, 'profile'):
#        instance.profile.save()
		

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        # NUR wenn der User ganz neu ist, erstellen wir das Profil
        MusicianProfile.objects.get_or_create(user=instance)
    else:
        # On updates (e.g. password change) just ensure it exists
        if hasattr(instance, 'profile'):
            instance.profile.save()