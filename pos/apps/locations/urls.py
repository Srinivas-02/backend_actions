from django.urls import path

from pos.apps.locations._views.LocationView import LocationView,get_location_names


urlpatterns = [
    path('', LocationView.as_view(), name='locations'),
    path('get-location-names/', get_location_names)
]