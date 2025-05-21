from django.urls import path

from . import views

urlpatterns = [
    path("to-auth-redirect/", views.to_auth_redirect, name="eve_auth_redirect"),
    path("from-auth-redirect/", views.from_auth_redirect, name="eve_auth_callback"),
]
