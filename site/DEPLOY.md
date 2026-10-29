# Putting Manimo online

The installer (`dist\Manimo-Setup-1.9.1.exe`, 241 MB) is too big to keep inside the website folder. Host it as a **GitHub Release** (free, up to 2 GB per file, a direct download link, no CLI needed) and host the website itself on **GitHub Pages**, both in one repository.

## One-time setup (about 10 minutes)

1. On github.com, signed in as `mathanmj92`, create a new **public** repository named `manimo`.
2. Upload the website: add the contents of this `site/` folder to the repository (drag the files into the web page, or use GitHub Desktop). Do **not** upload `Manimo-Setup-*.exe` into the repository itself.
3. Turn on the site: Settings, Pages, Source "Deploy from a branch", branch `main`, folder `/ (root)`. It goes live at `https://mathanmj92.github.io/manimo/`.
4. Publish the installer: repository page, Releases, "Create a new release". Tag `v1.9.1`, title `Manimo 1.9.1`. Drag `dist\Manimo-Setup-1.9.1.exe` into the "Attach binaries" box, wait for the upload bar, then Publish release.
5. The download buttons on the page already point to
   `https://github.com/mathanmj92/manimo/releases/download/v1.9.1/Manimo-Setup-1.9.1.exe`.
   If you pick another repository name or tag, search `index.html` for `releases/download` and change all 3 links.

## Each new version

New release with a new tag, attach the new installer, then in `index.html` update the 3 download links, the version and SHA-256 line near the bottom, and the size. Get the hash with:

    Get-FileHash dist\Manimo-Setup-X.Y.Z.exe -Algorithm SHA256

SHA-256 of 1.9.1: `C3188B29523CA546ABCCD67D0E62CC69EB27269430C4B474B41CCF3CCA8E7508`

## Notes

- The installer is not signed with a commercial certificate, so Windows SmartScreen shows "unknown publisher". The FAQ explains it, and the SHA-256 on the page lets careful users check their download.
- Alternatives if GitHub is not wanted: Cloudflare R2 or Backblaze B2 (free tier, public bucket), or Google Drive (not recommended: virus-scan interstitial for big files breaks direct downloads).
