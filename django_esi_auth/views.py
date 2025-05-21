from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.module_loading import import_string
from esi.models import CallbackRedirect
from esi.views import sso_redirect

from .choices import EVE_ENTITY_TYPE
from .models import DynamicObject, LoginAccessRight


def to_auth_redirect(request: HttpRequest) -> HttpResponse:
    """Initiates the Eve Online Authentication flow.

    The ```next``` parameter is stored in session for use by the callback.

    Args:
        request (HttpRequest): Current request

    Returns:
        HttpResponse: Redirect to Eve Online login
    """
    if request.GET.get("next"):
        request.session["next"] = request.GET.get("next")
    return sso_redirect(request=request, return_to="eve_auth_callback")


def from_auth_redirect(request: HttpRequest) -> HttpResponse:
    """Completes the Eve Online Authentication flow.

    The ```next``` parameter is retrieved from the session and is used
    as redirect target after login.

    Args:
        request (HttpRequest): Current request

    Raises:
        Exception: CallbackRedirect.DoesNotExist

    Returns:
        HttpResponse: Redirect to the original ```next``` destination
    """
    next_url = request.session.pop("next", "/")
    try:
        callback = CallbackRedirect.objects.get(session_key=request.session.session_key)
    except CallbackRedirect.DoesNotExist as exc:
        raise Exception("Something is very wrong") from exc

    token = { 
        "access_token": callback.token.access_token,
        "character_id": callback.token.character_id,
        "character_name": callback.token.character_name,
        "character_owner_hash": callback.token.character_owner_hash
        }

    user = authenticate(request=request, token=DynamicObject(token))

    # Cleanup the CallbackRedirect and Token objects created
    # by the signin as we don't need them for just authentication.
    #callback.token.delete()
    

    if user:
        login(request, user)
        request.session['character_id'] = token['character_id']
        callback.token.delete()
        return redirect(next_url)

    messages.error(request, f"{token['character_name']} is not authorized to login.")
    callback.token.delete()
    #callback.delete()
    return render(request, "registration/login.html")
