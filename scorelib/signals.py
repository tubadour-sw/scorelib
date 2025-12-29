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
        # Bei Updates (z.B. Passwortänderung) nur sicherstellen, dass es da ist
        if hasattr(instance, 'profile'):
            instance.profile.save()