# Medic video visuals

Open any HTML file directly in Chrome. Each scene is a static 1920 × 1080 canvas, with uniform scaling for other window sizes. Fonts are bundled locally; there are no network requests or runtime dependencies.

| File | Video timing |
| --- | --- |
| `problem.html` | 0:00–0:25 |
| `medic.html` | 0:25–0:43 |
| `architecture.html` | 2:58–3:19 |
| `end.html` | 3:19–3:34 |

For recording, use fullscreen Chrome with a 1920 × 1080 content area and 100% browser zoom. All content appears immediately and remains still so cuts can follow the separate voiceover. The actual clinician workspace supplies 0:43–2:58.

`scenes.css` shares the clinician workspace palette and typography without importing or changing application files. `fit.js` only fits the canvas to the viewport. Font license notices are in `assets/`.
