import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from time import sleep
from typing import Any, List, Union

import requests
from requests.structures import CaseInsensitiveDict

from .exceptions import ESIRequestError, ESIResponseDecodeError
from .models import Token


class ESIResponse:
    """Response class for ESI API calls"""

    def __init__(
        self, headers: CaseInsensitiveDict[str], next_page: requests.Request = None, page: int = 1, all: bool = False
    ):
        self._page = page
        self._next_page = next_page
        self._total_pages = int(headers["x-pages"]) if "x-pages" in headers else 1

        if all:
            self._total_pages = 1

        self._etag = headers["ETag"].strip('"') if "ETag" in headers else None
        self._expires = parsedate_to_datetime(headers["expires"]) if "expires" in headers else None
        self._last_modified = parsedate_to_datetime(headers["last-modified"]) if "last-modified" in headers else None
        self._data = []

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

    @data.setter
    def data(self, value: List[Any]):
        self._data = value

    @property
    def next_page(self) -> requests.Request:
        return self._next_page


class ESIClient:

    def __init__(self, token: Union[Token | None]):
        self.headers = {
            "X-User-Agent": "Eve Broker v1 (fecal.matters@binarymethod.com)",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.base_url = "https://esi.evetech.net"
        self.token = token

    def get_character_contracts(self, character_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET", "/v1/characters/{character_id}/contracts/", character_id=character_id, success_code=200, etag=etag
        )

    def get_character_contract_items(self, character_id: int, contract_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/v1/characters/{character_id}/contracts/{contract_id}/items/",
            character_id=character_id,
            contract_id=contract_id,
            success_code=200,
            etag=etag,
        )

    def get_character_transactions(self, character_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/v1/characters/{character_id}/wallet/transactions/",
            character_id=character_id,
            etag=etag,
            success_code=200,
        )

    def get_character_journal(self, character_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/v6/characters/{character_id}/wallet/journal/",
            character_id=character_id,
            etag=etag,
            success_code=200,
        )

    def get_structure(self, structure_id: int, etag=None, **kwargs) -> ESIResponse:
        return self._get_response(
            "GET",
            "/v2/universe/structures/{structure_id}/",
            structure_id=structure_id,
            etag=etag,
            success_code=200,
            no_page=True,
        )

    def get_names(self, ids: List[int], etag=None, **kwargs) -> ESIResponse:
        return self._get_response("POST", "/v3/universe/names/", data=ids, success_code=200, public=True, no_page=True)

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
        result = self._send_request(request)

        if "all" in kwargs:
            next_page = result
            for page in range(result.page + 1, result.total_pages + 1):
                next_page = self._send_request(next_page.next_page)

                result.data += next_page.data

        return result

    def _send_request(self, request: requests.Request) -> ESIResponse:
        session = requests.Session()

        retries = 0
        while retries < 6:
            try:
                response = session.send(request.prepare(), timeout=(6, 10))
                break
            except requests.exceptions.Timeout:
                sleep(10)
                retries += 1
        else:
            raise ESIRequestError(f"Max retries exceeded for {request.url}")

        response.raise_for_status()

        if "page" in request.params:
            if request.params["page"] < int(response.headers.get("x-pages", 1)):
                request.params["page"] += 1
                result = ESIResponse(headers=response.headers, next_page=request)
            else:
                result = ESIResponse(headers=response.headers)
        else:
            result = ESIResponse(headers=response.headers)

        response.raise_for_status()

        if 200 <= response.status_code <= 299:
            try:
                result.data = response.json()
            except json.decoder.JSONDecodeError as e:
                raise ESIResponseDecodeError(f"Failed to decode response from ESI.\n{response.text}\n\n{e}")
        elif response.status_code == 304:
            result.data = []

        return result
