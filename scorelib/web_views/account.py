from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..forms import UserProfileUpdateForm


def legal_view(request):
    return render(request, "scorelib/legal.html")


@login_required
def profile_view(request):
    user_profile = getattr(request.user, "profile", None)

    if request.method == "POST":
        form = UserProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil erfolgreich aktualisiert!")
            return redirect("profile_view")
    else:
        form = UserProfileUpdateForm(instance=request.user)

    context = {
        "form": form,
        "user_profile": user_profile,
    }
    return render(request, "registration/profile.html", context)
