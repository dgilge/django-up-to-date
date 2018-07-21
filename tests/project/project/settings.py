import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = 'secret'

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'testapp',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
]

MIDDLEWARE = []

ROOT_URLCONF = 'project.urls'

TEMPLATES = []

WSGI_APPLICATION = 'project.wsgi.application'

DATABASES = {
    'default': os.environ.get('TEST_DATABASE', {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    })
}

AUTH_PASSWORD_VALIDATORS = []

STATIC_URL = os.environ.get('TEST_STATIC_URL', '/static/')

STATIC_ROOT = os.path.join(os.path.dirname(BASE_DIR), 'static')
