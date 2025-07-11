import urllib

from django.conf import settings
from django.core.signing import dumps
from django.http import HttpRequest
from django.middleware.csrf import get_token
from django.shortcuts import reverse


def construct_eve_login_url(request: HttpRequest, scopes: str = None, next_url: str = None, save_user: bool = True):
    """
    Construct an Eve SSO Login URL to start Auth flow

    Args:
        request: Current request
        scopes: List of scopes to auth for
        next_url: Next URL to redirect to upon login
        save_user: Wether or not to save the user object or just a token

    Returns:
        Full Eve SSO login URL
    """
    # Grab a CSRF Token and use it for state validation
    state = {"token": get_token(request), "next": request.GET.get("next", "/"), "save_user": save_user}

    if next_url:
        state["next"] = next_url

    signed_state = dumps(state, salt=settings.SECRET_KEY)
    redirect_url = f"{request.scheme}://{settings.SITE_DOMAIN}{reverse('auth:callback')}"

    if scopes:
        if " " in scopes:
            scopes = scopes.split(" ")
        if "," in scopes:
            scopes = scopes.split(",")

    query_params = {
        "response_type": "code",
        "client_id": settings.ESI_SSO_CLIENT_ID,
        "redirect_uri": redirect_url,
        "state": signed_state,
    }

    if scopes:
        query_params["scope"] = " ".join(scopes)

    url_encoded_query = urllib.parse.urlencode(query_params)
    return f"https://login.eveonline.com/v2/oauth/authorize?{url_encoded_query}"
