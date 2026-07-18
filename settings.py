
from pathlib import Path
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())


INSTALLED_APPS = [
    'daphne',
    'channels',
    'axes',
    'storages',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'users',
    'courses',
    'chat',
    'moderation',
    'schedule',
    'materials',
]
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": config("R2_ACCESS_KEY_ID"),
            "secret_key": config("R2_SECRET_ACCESS_KEY"),
            "bucket_name": config("R2_BUCKET_NAME"),
            "endpoint_url": config("R2_ENDPOINT_URL"),
            "region_name": "auto",
            "default_acl": "private",
            "querystring_auth": True,
            "querystring_expire": 300,
            "file_overwrite": False,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
MIDDLEWARE = [
    'axes.middleware.AxesMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'SevenStarsSchool.security_middleware.SecurityHeadersMiddleware',
]

if config('CHANNEL_LAYER_BACKEND', default='redis') == 'inmemory':
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [config('REDIS_URL', default='redis://127.0.0.1:6379/0')],
            },
        }
    }

ROOT_URLCONF = 'urls'

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
                'users.context_processors.user_role',
            ],
        },
    },
]

WSGI_APPLICATION = 'wsgi.application'
ASGI_APPLICATION = 'asgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('DB_PORT', default='5432'),
    }
}
 

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'uk'

TIME_ZONE = 'Europe/Kyiv'

USE_I18N = True

USE_TZ = True

STATICFILES_DIRS = [BASE_DIR / 'static']

# Static and media files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'show_my_groups'
LOGOUT_REDIRECT_URL = 'index'

INTERNAL_IPS = [
    '127.0.0.1',
]

MAX_FILE_SIZE = 15 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 500 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024

AXES_FAILURE_LIMIT = 20
AXES_COOLOFF_TIME = 1
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']
AXES_RESET_ON_SUCCESS = True

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

SESSION_EXPIRE_AT_BROWSER_CLOSE = False

SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

X_FRAME_OPTIONS = 'DENY'


SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')