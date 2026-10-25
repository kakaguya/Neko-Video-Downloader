# Third-party notices

This project is a graphical frontend and depends on upstream software. The list below highlights major direct/runtime components; dependency metadata remains the authoritative source for complete terms.

- **PyQt5** — GPL v3 or a commercial Riverbank license. This project is distributed under GPLv3 to remain compatible with the GPL distribution path used here.
- **Qt 5 runtime distributed by PyQt5-Qt5 wheels** — LGPL v3 according to the package metadata; other Qt licensing options may also exist upstream.
- **yt-dlp** — the Python package/repository code is distributed under the Unlicense; standalone release bundles may contain components under additional licenses.
- **yt-dlp-ejs / EJS challenge solver scripts** — installed through the `yt-dlp[default]` dependency group where applicable. The upstream package bundles JavaScript code under its own ISC/MIT-related notices. This app may also allow yt-dlp to fetch the upstream `ejs:github` remote component at runtime.
- **FFmpeg/ffprobe** — external optional-but-strongly-recommended executables. Their exact license depends on the build and enabled components.
- **JavaScript runtimes** such as Deno, Node.js, Bun, or QuickJS — external tools with their own licenses.

Do not assume this file replaces the license files or notices shipped by those projects.
