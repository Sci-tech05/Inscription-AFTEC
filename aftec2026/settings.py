from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(name, default):
    value = str(config(name, default=str(default))).strip().lower()
    return value in {'1', 'true', 'yes', 'on'}

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = env_bool('DEBUG', True)
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    'inscription-aftec-2026.onrender.com',
    default='127.0.0.1,localhost,testserver',
    cast=lambda value: [host.strip() for host in value.split(',') if host.strip()],
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_bootstrap5',
    'inscription',
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

ROOT_URLCONF = 'aftec2026.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'inscription.context_processors.kcomat_info',
            ],
        },
    },
]

WSGI_APPLICATION = 'aftec2026.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Porto-Novo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

KCOMAT_INFO = {
    'name': 'KcoMat',
    'site': 'https://kcomat0.pythonanywhere.com',
    'ifu': '0202290628090',
    'rccm': 'LOKOSSA N° RB/LKS/25 A 10147',
    'phone': '+229 01 96 78 00 99',
    'whatsapp': '22996780099',
    'email': 'kcomat0@gmail.com',
    'address': 'Lokossa, Mono, Bénin',
    'youtube': 'https://youtube.com/@KcoMat',
    'tiktok': 'https://www.tiktok.com/@kcomat3',
    'facebook': 'https://www.facebook.com/profile.php?id=61581135667007',
    'maps_embed': 'https://maps.app.goo.gl/UXMLViYtf7Sjm6267',
}

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = env_bool('EMAIL_USE_SSL', False)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='kcomat0@gmail.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=20, cast=int)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='KcoMat <kcomat0@gmail.com>')
