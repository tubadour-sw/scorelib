from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Login / Logout URLs (Django bringt diese fertig mit)
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Hier binden wir deine App-URLs ein
    path('', include('scorelib.urls')),
]

# WICHTIG: Damit PDFs und Bilder während der Entwicklung 
# im Browser angezeigt werden können:
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)