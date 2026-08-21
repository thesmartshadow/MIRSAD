# MIRSAD Browser Capture

Load this directory as an unpacked Chromium extension. On a public X, Threads, or Reddit
post/comment page, select the visible text to preserve and open the extension. Capture sends only the
current URL, tab title, and selected text to `http://127.0.0.1:8000` after explicit confirmation.

MIRSAD validates and canonicalizes the URL without fetching the page. The extension has no cookie,
history, login, CAPTCHA, background, or broad browsing permission.
