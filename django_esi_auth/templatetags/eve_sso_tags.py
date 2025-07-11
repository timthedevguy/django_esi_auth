from django import template
from django.shortcuts import reverse

from django_esi_auth.utils import construct_eve_login_url

register = template.Library()


@register.simple_tag(takes_context=True)
def eve_login_url(context, scopes: str = None, next_url: str = None, **kwargs):
    request = context["request"]
    if next_url:
        next_url = reverse(next_url, kwargs=kwargs)
    return construct_eve_login_url(request, scopes=scopes, next_url=next_url)


@register.simple_tag(takes_context=True)
def eve_token_url(context, scopes: str = None, next_url: str = None, **kwargs):
    request = context["request"]
    if next_url:
        next_url = reverse(next_url, kwargs=kwargs)
    return construct_eve_login_url(request, scopes=scopes, next_url=next_url, save_user=False)
