#!/bin/sh

python manage.py makemigrations accounts locations menu orders inventory
python manage.py migrate

python manage.py runserver 0.0.0.0:8000