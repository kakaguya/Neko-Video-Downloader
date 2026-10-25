# Troubleshooting

## `E_AUTH_REQUIRED`

The site requires authentication or account entitlement. Export a valid Netscape-format `cookies.txt` from a browser session that can play the content and select it in the app.

## `E_HTTP_403`

Try these in order:

1. Update yt-dlp from the app.
2. If login is required, select valid cookies.
3. Confirm the URL plays in a normal browser on the same network.
4. Check whether the site blocks your region/network/request type.

## `E_RATE_LIMIT`

The server returned HTTP 429 or a similar throttling response. Stop repeatedly parsing the same URL and retry later.

## `E_FFMPEG_MISSING`

Install real FFmpeg binaries, not a Python package named `ffmpeg`. Both `ffmpeg` and `ffprobe` should be resolvable from `PATH`.

Check from a terminal:

```bash
ffmpeg -version
ffprobe -version
```

If you cannot install FFmpeg, choose **最佳单文件** or manually select one self-contained audio+video format.

## `E_JS_RUNTIME_MISSING`

YouTube currently needs a supported external JavaScript runtime for full extraction. Deno is preferred and the current minimum supported version is 2.3.0. v1.0.0 checks the actual Deno version and passes the detected executable path directly to yt-dlp.

If the badge is yellow, hover it or use **复制诊断信息** to inspect the runtime path/version.

## `E_EJS_MISSING` / JavaScript challenge solving failed

Deno alone is not enough; yt-dlp also needs the `yt-dlp-ejs` challenge solver scripts. Use the app's one-click update so that `yt-dlp[default]` and `yt-dlp-ejs` are upgraded together.

v1.0.0 also enables the `ejs:github` remote fallback. If that fallback fails, confirm that GitHub release assets are reachable from the current network.

## `E_UPDATE_FAILED`

The app runs:

```text
<sys.executable> -m pip install ...
```

If this fails:

- Confirm the active Python environment has `pip`.
- Confirm the environment is writable.
- Confirm DNS/network access to the Python package index.
- In Conda, activate the environment first and start the application from that same terminal.

## Formats suddenly disappear / Deno is installed but formats are still missing

Do not assume only numeric format IDs are valid. The app preserves all yt-dlp format IDs.

For YouTube, check three independent layers:

1. JavaScript runtime: Deno is detected, supported, and the path shown by the app is correct.
2. EJS solver: `yt-dlp-ejs` is installed/updated, or `ejs:github` fallback is reachable.
3. PO Token/SABR: even with Deno + EJS working, yt-dlp may skip formats that require a PO Token for the selected YouTube client.

The app now surfaces these warnings in the runtime log. See `docs/YOUTUBE_FORMATS.md` for the full decision tree.

## Why is there no detailed traceback log?

v1.0.0 intentionally removed the persistent traceback log. The UI shows a structured error code, a concise reason, and recovery suggestions. Use **复制诊断信息** when reporting a reproducible issue; it includes environment versions but not URL/Cookie contents or Python stack traces.

## My cookies.txt became smaller after using an older build

yt-dlp treats its `cookiefile` option as a read/write cookie jar and may save it again when the downloader closes. Neko Video Downloader v2.0.1+ never passes the user-selected source file directly to yt-dlp; it uses a disposable temporary copy instead.

If a pre-v2.0.1 build already rewrote the source file, re-export a fresh Netscape-format cookies.txt from the browser. Missing cookie entries cannot be reconstructed reliably from the shortened file alone.

## Cookie works once, then YouTube says it is no longer valid

There are two different failure modes:

1. **YouTube rotated the browser session cookies.** YouTube currently rotates account cookies frequently on active/open YouTube browser sessions. Export from a dedicated private/incognito session, navigate to `https://www.youtube.com/robots.txt` in the same tab, export only the YouTube cookies, then close that private session and never browse YouTube with it again.
2. **Old Neko v2.1.1 discarded yt-dlp's mutable CookieJar state after every operation.** v2.1.2 keeps the user-selected file immutable but persists yt-dlp's updated working CookieJar under the application-data `cookie-sessions` directory. Each operation uses a temporary copy and commits it atomically only after successful completion.

If you re-export a fresh Cookie file to the same path, v2.1.2 detects the source revision change and automatically resets its working session. Pressing the Cookie row's **清空** button removes only the app-owned working session; it never deletes or edits your source `cookies.txt`.

## Why no longer opens Chrome/Chromium for PO Token?

v1.0.0 sets the YouTube extractor argument `fetch_pot=never`. This prevents yt-dlp from invoking installed PO Token provider plugins automatically, including browser-backed providers. Deno/EJS remains enabled because JavaScript challenge solving is independent from PO Token generation. The tradeoff is that YouTube formats requiring a PO Token may be skipped.
