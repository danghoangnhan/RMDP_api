from datetime import timedelta
from pathlib import Path
from mongoengine import connect
import os
from RMDP_ml import tasks

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'm&66a4$(n1m+a*&u^!5#^y^^kw=1azxu@fra10ps63evf6c#n='
DEBUG = False if int(os.environ['DEBUG']) == 1 else True


def mongoClientUrl(DEBUG):
    if DEBUG:
        return os.environ.get("localhostmongoClientUrl")
    else:
        return os.environ.get("dockermongoClientUrl")


connect("RMDP_mongodb", host=mongoClientUrl(DEBUG))

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'driver',
    'restaurant',
    'geolocation',
    'menu',
    'order',
    'RMDP_ml'
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]
ROOT_URLCONF = 'core.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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
WSGI_APPLICATION = 'core.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

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
CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://\w+\.example\.com$", ]
CORS_ALLOW_ALL_ORIGINS = True
ALLOWED_HOSTS = ['*']
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True
STATIC_URL = '/static/'

CELERY_BROKER_URL = broker = [os.environ.get("CELERY_BROKER_0"),
                              os.environ.get("CELERY_BROKER_1"),
                              os.environ.get("CELERY_BROKER_2")]

CELERY_RESULT_BACKEND = [os.environ.get("CELERY_BROKER_0"),
                         os.environ.get("CELERY_BROKER_1"),
                         os.environ.get("CELERY_BROKER_2")]

CELERY_BEAT_SCHEDULE = {
    "run_RMDP": {
        "task": "RMDP_ml.tasks.run_RMDP",
        "schedule": timedelta(seconds=15),
    },
    "generatingOrder": {
        "task": "RMDP_ml.tasks.generatingOrder",
        "schedule": timedelta(seconds=15),
    },
    "driverSimulator": {
        "task": "RMDP_ml.tasks.updateDriver",
        "schedule": timedelta(seconds=1),
    },
}
