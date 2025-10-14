import json
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from time import sleep
from typing import Any, List, Union
from urllib.parse import parse_qs

import requests

from .exceptions import ESIRequestError, ESIResponseDecodeError
from .models import Token

logger = logging.getLogger(__name__)


class ESIResponse:
    """Response class for ESI API calls"""

    def __init__(self, response: requests.Response, request: requests.Request = None):
        self._request = request
        self._response = response
        self._err = None
        self._page = request.params.get("page", 1) or 1
        self._total_pages = int(response.headers.get("x-pages", 1))
        self._next_page = None
        self._etag = response.headers["ETag"].strip('"') if "ETag" in response.headers else None
        self._expires = parsedate_to_datetime(response.headers["expires"]) if "expires" in response.headers else None
        self._last_modified = (
            parsedate_to_datetime(response.headers["last-modified"]) if "last-modified" in response.headers else None
        )
        self._data = []

        if 200 <= response.status_code <= 299:
            # Set next page if we have one
            if self._page + 1 <= self._total_pages:
                request.params["page"] = self._page + 1
                self._next_page = request
            try:
                self._data = response.json()
            except json.decoder.JSONDecodeError as e:
                raise ESIResponseDecodeError(f"Failed to decode response from ESI.\n{response.text}\n\n{e}")

        elif response.status_code == 304:
            # No new Data
            self._total_pages = 1
        else:
            self._err = f"{response.status_code} :: {response.text}"

    @property
    def page(self) -> int:
        return self._page

    @property
    def total_pages(self) -> int:
        return self._total_pages

    @property
    def etag(self) -> str:
        return self._etag

    @property
    def expires(self) -> datetime:
        return self._expires

    @property
    def last_modified(self) -> datetime:
        return self._last_modified

    @property
    def data(self) -> List[Any]:
        return self._data

    @property
    def next_page(self) -> requests.Request:
        return self._next_page

    @property
    def err(self) -> str:
        return self._err

    @property
    def request(self) -> requests.Request:
        return self._request

    @property
    def response(self) -> requests.Response:
        return self._response


class ESIClient:

    def __init__(self, token: Union[Token | None] = None):
        """
        Creates a new ESI Client class.  If no token is provided then only public endpoints will function.
        Args:
            token: Token to use for authenticated endpoints
        """
        self.headers = {
            "X-User-Agent": "Eve Broker v1 (fecal.matters@binarymethod.com)",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.base_url = "https://esi.evetech.net"
        self.token = token

    def get_character_contracts(self, character_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET", "/characters/{character_id}/contracts/", character_id=character_id, success_code=200, etag=etag
        )

    def get_corporation_contracts(self, corporation_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/corporations/{corporation_id}/contracts/",
            corporation_id=corporation_id,
            success_code=200,
            etag=etag,
        )

    def get_corporation_contract_items(self, corporation_id: int, contract_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/corporations/{corporation_id}/contracts/{contract_id}/items",
            corporation_id=corporation_id,
            contract_id=contract_id,
            success_code=200,
            etag=etag,
            allow_401=True,
        )

    def get_character_contract_items(self, character_id: int, contract_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/characters/{character_id}/contracts/{contract_id}/items/",
            character_id=character_id,
            contract_id=contract_id,
            success_code=200,
            etag=etag,
            allow_401=True,
        )

    def get_character_transactions(self, character_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/characters/{character_id}/wallet/transactions/",
            character_id=character_id,
            etag=etag,
            success_code=200,
        )

    def get_character_journal(self, character_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/characters/{character_id}/wallet/journal/",
            character_id=character_id,
            etag=etag,
            success_code=200,
        )

    def get_structure(self, structure_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/universe/structures/{structure_id}/",
            structure_id=structure_id,
            etag=etag,
            success_code=200,
            no_page=True,
        )

    def get_names(self, ids: List[int], etag=None, **kwargs) -> ESIResponse:
        return self._get_response("POST", "/universe/names/", data=ids, success_code=200, public=True, no_page=True)

    def get_public_character_data(self, character_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/characters/{character_id}/",
            character_id=character_id,
            etag=etag,
            success_code=200,
            no_page=True,
            public=True,
        )

    def get_page(self, request: requests.Request) -> ESIResponse:
        return self._send_request(request)

    def _get_response(self, method: str, endpoint: str, **kwargs: Any) -> ESIResponse:
        result = None

        headers = self.headers.copy()

        if "public" in kwargs:
            if not kwargs["public"]:
                headers["Authorization"] = f"Bearer {self.token.access_token}"
            kwargs.pop("public")
        else:
            headers["Authorization"] = f"Bearer {self.token.access_token}"

        if "page" not in kwargs:
            if "no_page" in kwargs:
                kwargs.pop("no_page")
            else:
                kwargs["page"] = 1

        if "etag" in kwargs and kwargs["etag"]:
            headers["If-None-Match"] = kwargs.pop("etag")

        data = None
        if "data" in kwargs:
            data = kwargs.pop("data")
            if type(data) is not str:
                data = json.dumps(data)

        params = {}
        for key, value in kwargs.items():
            if key != "success_code" and f"{key}" not in endpoint and key != "etag" and key != "all":
                params[key] = value

        url = f"{self.base_url}{str.format(endpoint, **kwargs)}"

        request = requests.Request(method, url, headers=headers, params=params, data=data)
        result = self._send_request(request, kwargs.get("allow_401", False))

        if "all" in kwargs:
            next_page = result
            for page in range(result.page + 1, result.total_pages + 1):
                next_page = self._send_request(next_page.next_page)

                result.data += next_page.data

        return result

    def _send_request(self, request: requests.Request, allow_401: bool = False) -> ESIResponse:
        session = requests.Session()

        retries = 0
        while retries < 6:
            try:
                response = session.send(request.prepare(), timeout=(6, 10))

                response.raise_for_status()
                params = parse_qs(response.url.split("?")[1])
                key = response.url.split("?")[0].split("/")[-2]

                with open(f"results_{key}_{params['page'][0]}.txt", "w") as file:
                    try:
                        file.write(json.dumps(response.json(), indent=4))
                    except json.decoder.JSONDecodeError:
                        file.write(response.text)

                if 200 <= response.status_code <= 299 or response.status_code == 304:
                    break

                sleep(60)
                retries += 1
            except requests.exceptions.Timeout:
                sleep(60)
                retries += 1
            except requests.exceptions.HTTPError:
                if response.status_code == 401:
                    logger.error(f"Unauthorized response for {request.url}")
                    if allow_401:
                        logger.info("401 Unauthorized ignored")
                        return ESIResponse(response, request)
                if response.status_code == 403:
                    return ESIResponse(response, request)
                sleep(60)
                retries += 1
        else:
            raise ESIRequestError(f"Max retries exceeded for {request.url}")

        return ESIResponse(response, request)

        if "page" in request.params:
            if request.params["page"] < int(response.headers.get("x-pages", 1)):
                current_page = request.params["page"]
                request.params["page"] += 1
                result = ESIResponse(headers=response.headers, next_page=request, page=current_page)
            else:
                result = ESIResponse(headers=response.headers)
        else:
            result = ESIResponse(headers=response.headers)

        if response.status_code == 304:
            result.data = []
            return result

        try:
            result.data = response.json()
        except json.decoder.JSONDecodeError as e:
            raise ESIResponseDecodeError(f"Failed to decode response from ESI.\n{response.text}\n\n{e}")

        return result
