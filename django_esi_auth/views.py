import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.core.signing import BadSignature, SignatureExpired, loads
from django.http import HttpRequest
from django.middleware.csrf import CSRF_TOKEN_LENGTH
from django.shortcuts import redirect, render

from django_esi_auth.exceptions import EveCallbackStateInvalidError, EveTokenRequestError, EveTokenValidationError
from .models import Token, TokenManager


def from_auth_redirect(request: HttpRequest):
    signed_state = request.GET.get("state") or ""
    code = request.GET.get("code")

    try:
        state = loads(signed_state, salt=settings.SECRET_KEY, max_age=300)
    except SignatureExpired:
        raise EveCallbackStateInvalidError("State signature expired.")
    except BadSignature:
        raise EveCallbackStateInvalidError("State has bad signature.")

    csrf_token = state["token"] or ""
    next_url = state["next"] or "/"
    save_user = True

    if "save_user" in state:
        save_user = state["save_user"]

    checks = (
        re.search("[a-zA-Z0-9]", csrf_token),
        len(csrf_token) == CSRF_TOKEN_LENGTH,
    )

    # Check all conditions
    if not all(checks):
        raise EveCallbackStateInvalidError("State failed validation checks")

    token_response = TokenManager.request_access_token_from_auth_code(code)

    if token_response is None:
        raise EveTokenRequestError("Error getting token.")

    if "aud" not in token_response["claims"]:
        raise EveTokenValidationError("Token missing 'aud' key.")

    if (
        token_response["claims"]["aud"][0] != settings.ESI_SSO_CLIENT_ID
        or token_response["claims"]["aud"][1] != "EVE Online"
    ):
        raise EveTokenValidationError("Invalid token audience.")

    if save_user:
        user = authenticate(request=request, token_response=token_response)

        if user:
            login(request, user)

            if "scp" in token_response["claims"]:
                if token_response["claims"]["scp"]:
                    Token.objects.save_sso_response(token_response)

            return redirect(next_url)

        messages.error(request, f"{token_response['identity']['character_name']} is not authorized to login.")

        return render(request, "registration/login.html")

    Token.objects.save_sso_response(token_response)
    return redirect(next_url)
