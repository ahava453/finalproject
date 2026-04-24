Apify Authentication & Proxy Options
=================================

This project supports two ways to enable authenticated or proxied scraping with Apify:

1) UI / API-passed token and options
   - Include your Apify token in the `api_key` field when calling `POST /api/analyze`.
   - Optionally pass `apify_options` (JSON) in the request body to provide `sessionCookie`,
     `sessionCookies`, or `proxyConfig` for the Apify actor.

2) Environment-driven fallback
   - The fetcher falls back to `APIFY_API_TOKEN` from the environment (or `.env`).
   - Additional environment variables (useful for Codespaces / server deployments):
     - `APIFY_USE_PROXY=1` — enable Apify Proxy usage
     - `APIFY_PROXY_GROUPS=RESIDENTIAL` — comma-separated proxy groups
     - `APIFY_PROXY_SESSION=<session-id>` — optional session identifier
     - `APIFY_SESSION_COOKIE='<cookie-string>'` — Facebook/Instagram session cookie to authenticate actor requests
     - `APIFY_COOKIES_JSON='[{"name":"c_user","value":"..."}, ...]'` — JSON array of cookies

Security Notes
--------------
- Treat session cookies and tokens as secrets. Store them in Codespaces Secrets, `.env` (not committed), or your deployment secret manager.
- Do not paste session cookies into public issues or chat channels.

Examples
--------
Set environment variables locally (Linux/macOS):

```bash
export APIFY_API_TOKEN="apify_api_..."
export APIFY_USE_PROXY=1
export APIFY_PROXY_GROUPS=RESIDENTIAL
export APIFY_SESSION_COOKIE='c_user=...; xs=...'
```

Or pass options in the API request JSON:

```json
{
  "platform": "facebook",
  "target_account": "https://www.facebook.com/nasa",
  "api_key": "apify_api_...",
  "apify_options": {
    "sessionCookie": "c_user=...; xs=...",
    "proxyConfig": {"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]}
  }
}
```
