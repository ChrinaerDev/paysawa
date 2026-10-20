"""Thin HTTP client for the Paysawa API. The CLI never touches the database."""
import httpx


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class Api:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.last_status = 0
        self._keys: dict[str, str] = {}
        # no keep-alive: avoids confusing errors after a server restart
        self._http = httpx.Client(timeout=45, limits=httpx.Limits(max_keepalive_connections=0))

    def request(self, method: str, path: str, *, auth: str = "jwt", key: str | None = None,
                json=None, params=None, headers: dict | None = None):
        hdrs = dict(headers or {})
        if auth == "jwt":
            if not self.token:
                raise ApiError(401, "unauthorized", "Not logged in.")
            hdrs["Authorization"] = f"Bearer {self.token}"
        elif auth == "key":
            hdrs["Authorization"] = f"Bearer {key}"
        try:
            response = self._http.request(method, self.base_url + path, json=json, params=params, headers=hdrs)
        except httpx.ConnectError:
            raise ApiError(0, "unreachable", f"Cannot reach {self.base_url}. Is the server running?")
        except httpx.TimeoutException:
            raise ApiError(0, "timeout", "The server did not answer in time (database waking up or stuck). Try again.")
        except httpx.HTTPError as exc:
            raise ApiError(0, "network", f"Network problem: {type(exc).__name__}")
        self.last_status = response.status_code
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code >= 400:
            error = data.get("error") if isinstance(data, dict) else None
            error = error or {}
            raise ApiError(response.status_code, error.get("code", "http_error"), error.get("message", f"HTTP {response.status_code}"))
        return data

    def health(self) -> bool:
        try:
            self.request("GET", "/health", auth="none")
            return True
        except ApiError:
            return False

    def key_for(self, mode: str) -> str:
        """Secret key used for /v1 calls. Fetched through the dashboard login (keys are revealable),
        created automatically (label 'cli') if the merchant has none. Kept in memory only."""
        if mode in self._keys:
            return self._keys[mode]
        keys = self.request("GET", "/me/api-keys")["data"]
        usable = [k for k in keys if k["mode"] == mode and k["revealable"]]
        usable.sort(key=lambda k: k.get("label") != "cli")
        if usable:
            secret = self.request("GET", f"/me/api-keys/{usable[0]['id']}/secret")["secret"]
        else:
            secret = self.request("POST", "/me/api-keys", json={"mode": mode, "label": "cli"})["secret"]
        self._keys[mode] = secret
        return secret

    def forget_keys(self) -> None:
        self._keys.clear()
