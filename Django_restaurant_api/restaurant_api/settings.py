



from pathlib import Path
import os
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DEBUG") == "True"

FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

NGROK_DJANGO =  os.getenv("NGROK_DJANGO") # your DRF server
NGROK_FAST_API = os.getenv('NGROK_FAST_API')



# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "web",
    ".ngrok-free.app",  # allow all ngrok subdomains
]

CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.app",
]

# CSRF_TRUSTED_ORIGINS = [
#     "https://d37d-159-26-119-220.ngrok-free.app",
# ]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'django.contrib.humanize',
    'bootstrap4',
    'widget_tweaks',
    'django_celery_results',
    'encrypted_model_fields',
    'django_celery_beat',


    # Your apps
    'orders',
    'userAuths',
    'userAdmin',
    'restaurants',
    'payments',
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

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
]
ROOT_URLCONF = 'restaurant_api.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'restaurant_api.wsgi.application'

# Only send cookies over HTTPS
SESSION_COOKIE_SECURE = True

# Prevent JavaScript from reading session cookie
SESSION_COOKIE_HTTPONLY = True

# Optional: limit session to a single browser
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Recommended: use signed cookies for extra integrity
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases


DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        "CONN_MAX_AGE": 1200, # 👉 Django will keep a database connection open for 10 minutes instead of opening a new one for every request.
    }
}


# DATABASES = {
#     "default": {
#         "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
#         "NAME": "restaurant_db_8p25",
#         "USER": "restaurant_db_8p25_user",
#         "PASSWORD": "IU6bHfw6uiWolpZe5gmCxvhxWx8bTDQm",
#         "HOST": "dpg-d6dg86f5r7bs73b0mkgg-a.oregon-postgres.render.com",
#         "PORT": os.getenv("DB_PORT"),
#         "CONN_MAX_AGE": 1200, # 👉 Django will keep a database connection open for 10 minutes instead of opening a new one for every request.
#     }
# }


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'echendujosh@gmail.com'
EMAIL_HOST_PASSWORD = 'epvd vi sj svtu kpes'



# Optional: fix auto-field warnings
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/


# | Type       | Examples                              |
# | ---------- | ------------------------------------- |
# | **STATIC** | CSS, JS, logos, icons                 |
# | **MEDIA**  | Product images, profile pics, uploads |


STATIC_URL = 'static/'

# When you run: python manage.py collectstatic, Django gathers all static files from every app and dumps them into: /staticfiles/
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# This tells Django: "Also look inside /static/ for my CSS, JS, images."
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')] 




# All uploaded files go into: /media/ e.g: media/burger.jpg
MEDIA_ROOT = os.path.join(BASE_DIR / 'media')

# When browser requests an uploaded file, it will use: http://localhost:8000/media/burger.jpg

MEDIA_URL = '/media/'



REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}


AUTH_USER_MODEL = 'userAuths.AdminUser'

REST_FRAMEWORK = {
    # 'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    # 'PAGE_SIZE': 3,
    # "DEFAULT_THROTTLE_CLASSES": [
    #     "orders.throttles.TelegramScopedThrottle",
    # ],
    "DEFAULT_THROTTLE_RATES": {
        "send_kitchen": "2/minute",  # only 1 request per 60 seconds per user
    },
}


# Celery settings
CELERYD_PREFETCH_MULTIPLIER = 1

# Celery settings
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')       # For sending tasks to Celery
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND')  # For storing Celery task results

# gives us access to more detailed task results (like status, start time, end time, etc.) instead of just the return value.
CELERY_RESULT_EXTENDED = True  # Store additional metadata like task start time, end time, etc.

# Telegram bot / general Redis
REDIS_URL = os.getenv('REDIS_URL')            # Separate Redis DB for Telegram message_ids


# Optional: task serialization
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Lagos'  # Or your timezone
TASK_TRACK_STARTED = True


# Concurrency: number of tasks each worker can run simultaneously
CELERY_WORKER_CONCURRENCY = 5

# How many tasks a worker prefetches at once (1 = fair distribution)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Only acknowledge a task **after it finishes successfully**
CELERY_TASK_ACKS_LATE = True

# If worker crashes mid-task, tell broker to requeue task
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Limit how many tasks a or each worker will process before restarting to prevent memory leak 
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100

# Soft time limit (raises exception for graceful stop)
CELERY_TASK_SOFT_TIME_LIMIT = 200

# Track when task starts (useful for monitoring)
CELERY_TASK_TRACK_STARTED = True

# Disable worker rate limits (improves throughput)
CELERY_WORKER_DISABLE_RATE_LIMITS = True # i.e remove speed bumbs(remove rate-limiting by celery)



# --------------------------- Here is for celery-beat (periodic tasks scheduler)-------------------------------------------

# This tells celery: 👉 “Don’t use the default in-memory schedule — use the database instead.”
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "send-weekly-restaurant-reminder": {
        "task": "orders.tasks.send_weekly_reminder",
        "schedule": crontab(hour=12, minute=0, day_of_week="sat"),
    },
}