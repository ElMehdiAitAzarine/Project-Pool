# settings.py
DEBUG = False  # CRITIQUE : désactiver en prod


SECRET_KEY = os.environ.get('SECRET_KEY')  # Ne jamais coder en dur

# Database MariaDB 11.4.10
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'nuxe0125_CueClubDB', # Change with your ACTUAL MariaDB database name
        'USER': 'nuxe0125_MehdiAitAzarine',           # Change with your ACTUAL MariaDB username
        'PASSWORD': 'Mehdi-Ismail@007', # Change with your ACTUAL MariaDB password
        'HOST': '127.0.0.1',           # Change if your MariaDB is not local
        'PORT': '3306',                # MariaDB default port
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        }
    }
}

# Fichiers statiques
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')