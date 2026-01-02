import os
from pathlib import Path

# 1. BASE DIRECTORY
# This points to the folder where manage.py is located.
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. SECURITY (Local vs. Production)
# For local development, keep SECRET_KEY as is. 
# On a server, use an environment variable.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-your-fixed-dev-key-here')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True 

ALLOWED_HOSTS = ['localhost', '127.0.0.1'] # Add your server domain later


# 3. APPLICATION DEFINITION
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Your Apps
    'scorelib',  # Make sure your app folder is named 'scorelib'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'skg_notenbank.urls' # Name of your project folder

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # For your custom scorelib/index.html
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'skg_notenbank.wsgi.application'


# 4. DATABASE
# We start with SQLite for easy setup. Later on the server, we switch to PostgreSQL.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# 5. AUTHENTICATION & LOGIN REDIRECTS
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Important for your Musician login:
LOGIN_REDIRECT_URL = 'next_concert'
LOGOUT_REDIRECT_URL = 'login'


# 6. INTERNATIONALIZATION
LANGUAGE_CODE = 'de-de' # Or 'en-us'
TIME_ZONE = 'Europe/Berlin'
USE_I18N = True
USE_TZ = True


# 7. STATIC AND MEDIA FILES (Crucial for PDFs and Images)

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles' # For production (collectstatic)

# Media files (Your uploaded Master-PDFs, Parts, Posters, Audio)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# 8. DEFAULT PRIMARY KEY FIELD
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Wo soll Django den User hinschicken, wenn er nicht eingeloggt ist?
LOGIN_URL = 'login'

