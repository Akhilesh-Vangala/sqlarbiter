"""One coherent product frontend; existing operator and guided apps remain reachable."""
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

WRITE_PATHS = {
    "/api/account/sign-in", "/api/account/sign-up", "/api/account/sign-out", "/api/account/refresh",
    "/api/account/projects", "/api/account/projects/delete", "/api/account/investigations",
    "/api/account/investigations/delete",
}


def attach(app, root):
    static = Path(root)/"frontend/apps/product"
    app.mount("/product-assets", StaticFiles(directory=static), name="product-assets")

    @app.get("/workspace", include_in_schema=False)
    @app.get("/workspace/{page:path}", include_in_schema=False)
    def workspace(page=""):
        return FileResponse(static/"index.html", headers={"Cache-Control": "no-store"})

    from .accounts import attach as attach_accounts
    attach_accounts(app)
