# Photo Cleaner

A single page (`index.html`), no server, no dependencies and no connection: open it with a double click in any modern browser.

## What it does

- Removes **all** metadata (GPS, camera, dates, author) by redrawing the image on a canvas, which is the most reliable way to leave nothing hidden.
- Shows you what data the photo had (in JPEG: GPS location, make and model, dates, author).
- Converts between JPEG, WebP and PNG, limits the width and can aim for a **maximum size in KB** (it finds the highest quality that fits and, if needed, reduces the dimensions).
- Respects the photo orientation and names the output `name-clean.ext`. The originals are never touched.

## Limits

- Only JPG, PNG and WebP images. PDFs are not supported.
- When re-encoding, a JPEG or WebP loses a little quality. PNG has no quality setting: to reduce its size, use the maximum width or switch to WebP/JPEG.
- The browser may ask for permission to download several files at once.

Quick test: open the page, drag a photo taken with your phone and check that the list shows "GPS location" crossed out.
