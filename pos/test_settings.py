from .settings import *

# Use the Docker container's database for testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'pos_db',
        'USER': 'pos_user',
        'PASSWORD': 'pos_password',
        'HOST': 'localhost',  # Connect to the exposed Docker container
        'PORT': '5432',
    }
}

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Use in-memory email backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
