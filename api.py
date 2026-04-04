# This script is NOT made by me as I am NOT dealing with networking issues!
import threading
import time
import random
import requests
from requests.adapters import HTTPAdapter

SERVER_URL = "https://roman-expanding-alias-talent.trycloudflare.com/"
SUPABASE_URL = "https://ewtyvhvrsozprrmximfj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3dHl2aHZyc296cHJybXhpbWZqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI1NjE5NjYsImV4cCI6MjA4ODEzNzk2Nn0.yqfZYfA_rVyUwpM9C03wnEnnYZgHR-sKEYkMGEjUlBM"
VERSION_TABLE = "version"
VERSION_COLUMN = "version"

threadLocal = threading.local()

defaultConnectTimeout = 8
defaultReadTimeout = 15
defaultAttempts = 3
backoffBase = 0.35


class ApiError(RuntimeError):
    pass


def normalizeBaseUrl(url: str) -> str:
    return url.rstrip("/")


def buildSession() -> requests.Session:
    session = requests.Session()

    adapter = HTTPAdapter(
        pool_connections=8,
        pool_maxsize=8,
        max_retries=0,
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({
        "Accept": "application/json",
        "Connection": "keep-alive",
        "User-Agent": "customNodeClient/1.0",
    })

    return session


def getSession() -> requests.Session:
    session = getattr(threadLocal, "session", None)
    if session is None:
        session = buildSession()
        threadLocal.session = session
    return session


def resetSession():
    oldSession = getattr(threadLocal, "session", None)
    if oldSession is not None:
        try:
            oldSession.close()
        except Exception:
            pass
    threadLocal.session = buildSession()


def safeJson(response: requests.Response):
    try:
        return response.json()
    except Exception as e:
        preview = response.text[:300] if response.text else ""
        raise ApiError(
            f"Invalid JSON from {response.request.method} {response.url} "
            f"(status={response.status_code}): {preview!r}"
        ) from e


def requestJson(
    method: str,
    url: str,
    *,
    params=None,
    jsonBody=None,
    connectTimeout: float = defaultConnectTimeout,
    readTimeout: float = defaultReadTimeout,
    attempts: int = defaultAttempts,
):
    lastError = None

    for attempt in range(1, attempts + 1):
        try:
            response = getSession().request(
                method=method,
                url=url,
                params=params,
                json=jsonBody,
                timeout=(connectTimeout, readTimeout),
            )

            if not (200 <= response.status_code < 300):
                preview = response.text[:300] if response.text else ""
                raise ApiError(
                    f"HTTP {response.status_code} for {method} {url}: {preview!r}"
                )

            return safeJson(response)

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ContentDecodingError,
            requests.exceptions.RequestException,
            ApiError,
        ) as e:
            lastError = e

            if attempt >= attempts:
                break

            resetSession()
            time.sleep(backoffBase * (2 ** (attempt - 1)) + random.uniform(0.0, 0.15))

    raise ApiError(f"Request failed after {attempts} attempts: {method} {url} | lastError={lastError}") from lastError


# ----------- NODE MANAGEMENT -----------

def newId() -> int:
    data = requestJson(
        "GET",
        f"{normalizeBaseUrl(SERVER_URL)}/newId",
    )
    try:
        return int(data["id"])
    except Exception as e:
        raise ApiError(f"Malformed response from /newId: {data!r}") from e


def removeId(nodeId: int):
    requestJson(
        "POST",
        f"{normalizeBaseUrl(SERVER_URL)}/removeId",
        jsonBody={"id": int(nodeId)},
    )


def getAllIds() -> list[int]:
    data = requestJson(
        "GET",
        f"{normalizeBaseUrl(SERVER_URL)}/allIds",
    )
    try:
        return [int(x) for x in data["ids"]]
    except Exception as e:
        raise ApiError(f"Malformed response from /allIds: {data!r}") from e


# ----------- MESSAGING -----------

def sendMessage(toId: int, fromId: int, message: str):
    requestJson(
        "POST",
        f"{normalizeBaseUrl(SERVER_URL)}/sendMessage",
        jsonBody={
            "toId": int(toId),
            "fromId": int(fromId),
            "message": str(message),
        },
    )


def getNextMessage(nodeId: int, timeout=10):
    pollTimeout = float(timeout)

    data = requestJson(
        "GET",
        f"{SERVER_URL}/nextMessage",
        params={
            "id": int(nodeId),
            "timeout": pollTimeout,
            "_": time.time_ns(),  # avoid caching
        },
        # IMPORTANT:
        # read timeout must be LONGER than poll timeout
        connectTimeout=defaultConnectTimeout,
        readTimeout=pollTimeout + 10,
        attempts=2,
    )

    try:
        return data["message"], int(data["senderId"]), int(data["rowId"])
    except Exception as e:
        raise ApiError(f"Malformed response from /nextMessage: {data!r}") from e


def deleteMessageRow(rowId: int):
    if int(rowId) < 0:
        return

    requestJson(
        "POST",
        f"{normalizeBaseUrl(SERVER_URL)}/deleteMessageRow",
        jsonBody={"rowId": int(rowId)},
    )


def getLatestVersion() -> str:
    url = (
        f"{SUPABASE_URL}/rest/v1/{VERSION_TABLE}"
        f"?select={VERSION_COLUMN}"
        f"&apikey={SUPABASE_KEY}"
    )

    r = requests.get(url, timeout=15)
    r.raise_for_status()

    data = r.json()

    if not data:
        return "-1.-1.-1"

    return str(data[0][VERSION_COLUMN])