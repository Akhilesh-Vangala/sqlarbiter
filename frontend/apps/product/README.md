# Product frontend

Native ES modules, semantic HTML and CSS. `app.js` owns route/controller transitions; `state.js` holds unsaved browser state; `lib/` owns DOM, HTTP/SSE and explicit IndexedDB writes; `views/` owns landing/workspace, guided intake, checked reports and account/settings pages. Source data is rendered as text, never HTML. Saving requires explicit consent.

[Page map and product/storage boundaries](../../../docs/product/WORKSPACE.md). Run `python scripts/demos/product_browser.py` from the repository root in the installed development environment. Actual browser execution parses the modules; syntax-only checks must use ES module mode.
