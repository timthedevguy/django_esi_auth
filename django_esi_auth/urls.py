from django.urls import path

from . import views

app_name = "auth"
urlpatterns = [
    path("callback/", views.from_auth_redirect, name="callback"),
]
