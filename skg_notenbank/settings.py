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

import os
from pathlib import Path

# 1. BASE DIRECTORY
# This points to the folder where manage.py is located.
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. SECURITY (Local vs. Production)
# For local development, keep SECRET_KEY as is.
# On a server, use an environment variable.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "django-insecure-your-fixed-dev-key-here"
)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# for debugging behind a reverse proxy, we need to trust the X-Forwarded headers
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    "uni-brachbach.de",
    "www.uni-brachbach.de",
    "raspimusic",
    "192.168.178.40",
    "localhost",
    "127.0.0.1",
]  # Add your server domain later
CSRF_TRUSTED_ORIGINS = [
    "https://uni-brachbach.de",
    "https://www.uni-brachbach.de",
    "http://192.168.178.40",
    "http://raspimusic",
]


# 3. APPLICATION DEFINITION
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Your Apps
    "scorelib",  # Make sure your app folder is named 'scorelib'
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "skg_notenbank.urls"  # Name of your project folder

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # For your custom scorelib/index.html
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "scorelib.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "skg_notenbank.wsgi.application"


# 4. DATABASE
# We start with SQLite for easy setup. Later on the server, we switch to PostgreSQL.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# 5. AUTHENTICATION & LOGIN REDIRECTS
AUTH_PASSWORD_VALIDATORS = [
    # Verhindert Passwörter, die dem Benutzernamen zu ähnlich sind
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    # Setzt eine Mindestlänge (hier auf 6 Zeichen reduziert)
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 6,
        },
    },
]

# Important for your Musician login:
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "next_concert"
LOGOUT_REDIRECT_URL = "login"


# 6. INTERNATIONALIZATION
LANGUAGE_CODE = "de-de"  # Or 'en-us'
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True


# 7. STATIC AND MEDIA FILES (Crucial for PDFs and Images)

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # For production (collectstatic)

# Media files (Your uploaded Master-PDFs, Parts, Posters, Audio)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# 8. DEFAULT PRIMARY KEY FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
