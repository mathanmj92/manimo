# Putting ManimGX Studio online

`web/` is a **static site**: HTML, CSS and one JavaScript file. There is no server to run, no database,
and no uploaded code. Each visitor's own browser runs their Python (Pyodide, in a Web Worker) and draws
with their own graphics card (WebGPU). That is why it is safe and almost free to host: a stranger's code
can only ever run inside that stranger's own browser tab.

## Deploy (pick one, all free, all give you HTTPS, which WebGPU requires)

**Cloudflare Pages** (fastest)
1. dash.cloudflare.com, Workers & Pages, Create, Pages, Upload assets.
2. Drag the whole `web` folder in. Name the project. Done: `https://<name>.pages.dev`.
   `_headers` is read automatically.

**Netlify**
1. app.netlify.com/drop, drag the `web` folder in. `_headers` is read automatically.

**GitHub Pages**
1. Put the contents of `web/` at the root of a repository (or in `/docs`).
2. Settings, Pages, Deploy from a branch. (GitHub Pages ignores `_headers`; that is fine.)

Add a custom domain in the host's dashboard if you want one.

## What visitors need

| Needed | Detail |
|---|---|
| Browser | Chrome or Edge 113+, Safari 26+, Firefox 141+ on Windows. The page detects missing support and says so |
| Graphics | An adapter with `float32-blendable` and `depth32float-stencil8` (most laptops and phones from the last ~5 years) |
| First visit | Downloads about 26 MB (Python + ManimGX). The browser keeps it, so later visits start in seconds |
| Saving video | Chrome and Edge record MP4, others WebM. The animation plays through once while it is recorded, so a 3-minute animation takes 3 minutes to save |

## Known limits (from the ManimGX docs)

- Chinese, Japanese and Korean text, and shapes built from other shapes (`Union`, etc.), do not work in the browser yet.
- A scene that is not finished rendering can be previewed, but only a finished one can be saved.

## Things you control

- **Self-host Python:** download Pyodide, put it in `web/pyodide/`, and set `PYODIDE_URL = "./pyodide/"` at the top of the
  script in `index.html`. Without it the page loads Pyodide from the jsDelivr CDN and the ManimGX wheel from PyPI.
- **Update ManimGX:** replace `vendor/manimgx.js` with the newest `dist/manimgx.js` from the `manimgx` npm package.
  The file pins the matching PyPI version itself.
- **Privacy:** nothing is sent to any server of yours. Share links keep the code inside the link's `#` part, which browsers
  never send to a server.
