from django import template

from django_esi_auth.utils import construct_eve_login_url

register = template.Library()


@register.simple_tag(takes_context=True)
def eve_login_url(context, scopes: str = None):
    request = context["request"]
    return construct_eve_login_url(request, scopes=scopes)
