import json
import ipaddress
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

MAX_TABS = 12
MAX_HISTORY = 100
MAX_BOOKMARKS = 48
MAX_RECENT_SEARCHES = 20
MAX_DOWNLOADS = 64
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
ALLOWED_SCHEMES = {"http", "https"}

DEFAULT_BROWSER_STATE = {
    "tabs": [{"id": "tab-1", "title": "Home", "url": "https://example.com"}],
    "active_tab_id": "tab-1",
    "history": ["https://example.com"],
    "recent_searches": [],
    "downloads": [],
}


def _store(context):
    return context["services"]["store"]


def _normalized_state(context):
    raw_state = _store(context).read("browser", DEFAULT_BROWSER_STATE) or {}
    return _sanitize_browser_state(raw_state)


def _save_state(context, state):
    _store(context).write("browser", _sanitize_browser_state(state))


def _trim_text(value, fallback, limit):
    text = str(value or fallback).strip()
    return text[:limit] or fallback


def _normalize_url(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        if "." in text and " " not in text:
            text = f"https://{text}"
        else:
            text = f"https://duckduckgo.com/?q={quote(text)}"
    parsed = urlparse(text)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES or not parsed.netloc:
        return ""
    if parsed.netloc.lower() in ("google.com", "www.google.com") and parsed.path in ("", "/"):
        return "https://www.google.com/webhp?igu=1"
    return text


def _sanitize_tab(item, fallback_id="tab-1", fallback_url="https://example.com"):
    if not isinstance(item, dict):
        item = {}
    tab_id = _trim_text(item.get("id"), fallback_id, 64)
    url = _normalize_url(item.get("url") or fallback_url) or fallback_url
    title = _trim_text(item.get("title"), "New Tab", 80)
    return {"id": tab_id, "title": title, "url": url}


def _sanitize_bookmarks(items):
    if not isinstance(items, list):
        return []
    bookmarks = []
    seen = set()
    for item in items[:MAX_BOOKMARKS]:
        if not isinstance(item, dict):
            continue
        url = _normalize_url(item.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        bookmarks.append(
            {
                "label": _trim_text(item.get("label") or item.get("title"), url, 80),
                "url": url,
            }
        )
    return bookmarks


def _sanitize_browser_state(state):
    if not isinstance(state, dict):
        state = {}

    raw_tabs = state.get("tabs") if isinstance(state.get("tabs"), list) else []
    tabs = []
    seen_ids = set()
    for index, item in enumerate(raw_tabs[:MAX_TABS], start=1):
        tab = _sanitize_tab(item, fallback_id=f"tab-{index}")
        if tab["id"] in seen_ids:
            tab["id"] = f"{tab['id']}-{index}"
        seen_ids.add(tab["id"])
        tabs.append(tab)
    if not tabs:
        tabs = [_sanitize_tab({}, fallback_id="tab-1")]

    active_tab_id = str(state.get("active_tab_id") or tabs[0]["id"]).strip()
    if active_tab_id not in {tab["id"] for tab in tabs}:
        active_tab_id = tabs[0]["id"]

    history = []
    for item in (state.get("history") or [])[:MAX_HISTORY]:
        url = _normalize_url(item)
        if url:
            history.append(url)
    if not history:
        history = [tabs[0]["url"]]

    recent_searches = [
        _trim_text(item, "", 120)
        for item in (state.get("recent_searches") or [])[:MAX_RECENT_SEARCHES]
        if str(item or "").strip()
    ]

    downloads = (state.get("downloads") or [])[:MAX_DOWNLOADS]
    if not isinstance(downloads, list):
        downloads = []

    return {
        "tabs": tabs,
        "active_tab_id": active_tab_id,
        "history": history,
        "recent_searches": recent_searches,
        "downloads": downloads,
    }


def get_manifest():
    return {
        "id": "browser",
        "title": "Browser",
        "capabilities": ["network"],
        "routes": ["tabs", "page", "render"],
        "required_services": ["store"],
    }


def get_app_payload(context):
    state = _normalized_state(context)
    return {
        "view": "browser",
        "title": "Browser",
        "browser": state,
        "home_url": (
            state["tabs"][0]["url"] if state.get("tabs") else "https://example.com"
        ),
    }


def handle_action(context, action, payload):
    state = _normalized_state(context)
    if action == "save_browser_state" and isinstance(payload, dict):
        state = _sanitize_browser_state({**state, **payload})
        _save_state(context, state)
    return {"app": get_app_payload(context), "system": context["system"]}


def _browser_error_page(target, message, details=""):
    detail_html = (
        f"<div style='margin-top:12px;font-size:13px;color:#70829f;'>{details}</div>"
        if details
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<title>Browser Error</title>
<style>
body {{
    margin: 0;
    min-height: 100vh;
    display: grid;
    place-items: center;
    background: linear-gradient(180deg, #f3f7ff 0%, #dbe7fb 100%);
    color: #10203a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.card {{
    width: min(520px, calc(100vw - 32px));
    background: rgba(255, 255, 255, 0.92);
    border-radius: 24px;
    padding: 24px;
    box-shadow: 0 24px 60px rgba(16, 32, 58, 0.16);
}}
.eyebrow {{
    font-size: 12px;
    letter-spacing: .16em;
    text-transform: uppercase;
    color: #5f789a;
    margin-bottom: 8px;
}}
.title {{
    font-size: 28px;
    font-weight: 800;
    margin-bottom: 10px;
}}
.copy {{
    font-size: 15px;
    line-height: 1.55;
    color: #304563;
}}
.target {{
    margin-top: 16px;
    padding: 12px 14px;
    border-radius: 16px;
    background: #eef4ff;
    color: #17325c;
    font-size: 13px;
    word-break: break-word;
}}
</style>
</head>
<body>
<section class="card">
<div class="eyebrow">Unlim8ted Browser</div>
<div class="title">{message}</div>
<div class="copy">The browser backend could not load this page directly. This can be a DNS problem, a server-side refusal, or a browser compatibility limitation in the current shell browser.</div>
<div class="target">{target}</div>
{detail_html}
</section>
</body>
</html>""".encode("utf-8")


def _rewrite_browser_document(html_text, final_url):
    injected = (
        f'<base href="{final_url}">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        "<style>html,body{min-height:100%;max-width:100%;scrollbar-width:thin;scrollbar-color:rgba(88,118,168,.55) transparent;}img,video,canvas,iframe{max-width:100%;height:auto;}::-webkit-scrollbar{width:8px;height:8px;}::-webkit-scrollbar-track{background:transparent;}::-webkit-scrollbar-thumb{background:rgba(88,118,168,.45);border-radius:999px;}::-webkit-scrollbar-thumb:hover{background:rgba(88,118,168,.7);}</style>"
        "<script>"
        "(function(){"
        f"const currentUrl={json.dumps(final_url)};"
        "function proxyUrl(url){return '/api/apps/browser/render?url='+encodeURIComponent(url);}"
        "function announce(){try{parent.postMessage({type:'browser-location',url:window.__unlim8tedRealUrl||currentUrl,title:document.title||''},'*');}catch(_err){}}"
        "document.addEventListener('click',function(event){const link=event.target.closest('a[href]');if(!link)return;const href=link.getAttribute('href')||'';if(!href||href.startsWith('#')||link.target==='_blank'||event.defaultPrevented)return;event.preventDefault();const target=new URL(href,currentUrl).toString();window.__unlim8tedRealUrl=target;location.href=proxyUrl(target);},true);"
        "document.addEventListener('submit',function(event){const form=event.target;if(!form)return;event.preventDefault();const method=(form.getAttribute('method')||form.method||'get').toLowerCase();const action=form.getAttribute('action')||currentUrl;const target=new URL(action,currentUrl);const params=new URLSearchParams(new FormData(form));if(method==='get'){target.search=params.toString();window.__unlim8tedRealUrl=target.toString();location.href=proxyUrl(target.toString());return;}fetch(target.toString(),{method:method.toUpperCase(),body:params,redirect:'follow',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'}}).then(function(response){return response.url||target.toString();}).then(function(nextUrl){window.__unlim8tedRealUrl=nextUrl;location.href=proxyUrl(nextUrl);}).catch(function(){window.__unlim8tedRealUrl=target.toString();location.href=proxyUrl(target.toString());});},true);"
        "var nativeSubmit=HTMLFormElement.prototype.submit;HTMLFormElement.prototype.submit=function(){try{var submitEvent=new Event('submit',{cancelable:true,bubbles:true});if(this.dispatchEvent(submitEvent)){nativeSubmit.call(this);}}catch(_err){nativeSubmit.call(this);}};"
        "window.addEventListener('load',announce);announce();})();"
        "</script>"
    )
    if re.search(r"<head[^>]*>", html_text, flags=re.IGNORECASE):
        return re.sub(
            r"(<head[^>]*>)", r"\1" + injected, html_text, count=1, flags=re.IGNORECASE
        )
    return (
        f"<!doctype html><html><head>{injected}</head><body>{html_text}</body></html>"
    )


def _browser_fetch(target):
    request = Request(
        target,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 14; Unlim8ted CM4) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Accept-Encoding": "identity",
        },
    )
    with urlopen(request, timeout=18) as response:
        content_type = response.headers.get_content_type()
        charset = response.headers.get_content_charset() or "utf-8"
        final_url = response.geturl()
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("response exceeds size limit")
    return content_type, charset, final_url, body


def _is_private_host(hostname):
    if not hostname:
        return True
    normalized = hostname.strip().rstrip(".")
    if not normalized:
        return True
    lowered = normalized.lower()
    if lowered in {"localhost", "localhost.localdomain"}:
        return True
    try:
        ip = ipaddress.ip_address(normalized)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        pass

    try:
        results = socket.getaddrinfo(normalized, None)
    except socket.gaierror:
        return False

    for result in results:
        try:
            ip = ipaddress.ip_address(result[4][0])
        except (ValueError, IndexError):
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
    return False


def _validate_target(requested):
    normalized = _normalize_url(requested)
    if not normalized:
        return None, "Only public http(s) addresses are supported"
    parsed = urlparse(normalized)
    if _is_private_host(parsed.hostname):
        return None, "Private and local network addresses are blocked"
    return normalized, ""


def handle_http(context, request):
    if request["method"] != "GET" or request["subpath"] != "render":
        return {
            "type": "json",
            "status": 404,
            "body": {"ok": False, "code": "route_not_found"},
        }

    requested = (request.get("query", {}).get("url") or [""])[0].strip()
    if not requested:
        return {
            "type": "raw",
            "status": 400,
            "content_type": "text/html; charset=utf-8",
            "body": _browser_error_page("", "No address provided"),
        }

    requested, validation_error = _validate_target(requested)
    if not requested:
        return {
            "type": "raw",
            "status": 400,
            "content_type": "text/html; charset=utf-8",
            "body": _browser_error_page("", "The address is blocked", validation_error),
        }

    try:
        content_type, charset, final_url, body = _browser_fetch(requested)
        final_url, validation_error = _validate_target(final_url)
        if not final_url:
            return {
                "type": "raw",
                "status": 400,
                "content_type": "text/html; charset=utf-8",
                "body": _browser_error_page(
                    requested, "The final destination is blocked", validation_error
                ),
            }
    except HTTPError as exc:
        return {
            "type": "raw",
            "status": 502,
            "content_type": "text/html; charset=utf-8",
            "body": _browser_error_page(
                requested, "The site returned an error", f"HTTP {exc.code}"
            ),
        }
    except URLError as exc:
        return {
            "type": "raw",
            "status": 502,
            "content_type": "text/html; charset=utf-8",
            "body": _browser_error_page(
                requested, "The site could not be reached", str(exc.reason)
            ),
        }
    except (OSError, ValueError) as exc:
        return {
            "type": "raw",
            "status": 502,
            "content_type": "text/html; charset=utf-8",
            "body": _browser_error_page(requested, "The page failed to load", str(exc)),
        }

    if content_type == "text/html":
        try:
            html_text = body.decode(charset, errors="replace")
        except LookupError:
            html_text = body.decode("utf-8", errors="replace")
        rewritten = _rewrite_browser_document(html_text, final_url).encode("utf-8")
        return {
            "type": "raw",
            "status": 200,
            "content_type": "text/html; charset=utf-8",
            "body": rewritten,
            "apply_security_headers": False,
        }

    content_type_value = (
        f"{content_type}; charset={charset}"
        if content_type.startswith("text/")
        else content_type
    )
    return {
        "type": "raw",
        "status": 200,
        "content_type": content_type_value,
        "body": body,
    }

