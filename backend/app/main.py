"""App factory: routes, CORS, error mapping, 60 second SLA tick, static front end with SPA fallback."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import func, select

from app.api import i18n, dashboard, routes, routes_more, schemas
from app.api.constants import APP_NAME, FRONTEND_DIST
from app.api.core import ApiError, tick_all
from app.db import Database
from app.db.models import User
from app.demo import clock
from app.demo.seed import seed

TICK_SECONDS = 60
log = logging.getLogger("app.tick")


async def tick_loop(app: FastAPI, interval: float = TICK_SECONDS) -> None:
    """Evaluate every open case on a timer. A failed pass is logged with its traceback and the loop keeps running."""

    def run() -> None:
        with app.state.db.session() as db:
            tick_all(db, clock.now(db))

    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(run)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("SLA tick failed; it will run again in %s seconds", interval)


def _openapi_with_payloads(app: FastAPI) -> dict[str, Any]:
    """Add the per-action payload models to components so clients can type ActionRequest.payload."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(title=f"{APP_NAME} API", version="0.1.0", routes=app.routes,
                         description="Hypertension follow-up loop. Synthetic data only. Thresholds are placeholders pending clinician sign-off.")
    comps = schema.setdefault("components", {}).setdefault("schemas", {})
    for model in dict.fromkeys(schemas.PAYLOAD_MODELS.values()):
        js = model.model_json_schema(ref_template="#/components/schemas/{model}")
        for name, sub in js.pop("$defs", {}).items():
            comps.setdefault(name, sub)
        comps.setdefault(model.__name__, js)
    comps["ActionRequest"]["x-payload-models"] = {a.value: m.__name__ for a, m in schemas.PAYLOAD_MODELS.items()}
    app.openapi_schema = schema
    return schema


def create_app(database_url: str | None = None, *, seed_on_start: bool = True, start_tick: bool = True) -> FastAPI:
    database = Database(database_url)
    database.create_all()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        if seed_on_start:
            with database.session() as db:
                if db.scalar(select(func.count(User.id))) == 0:
                    seed(db, clock.real_now())
        task = asyncio.create_task(tick_loop(app, TICK_SECONDS)) if start_tick else None
        yield
        if task:
            task.cancel()

    app = FastAPI(title=f"{APP_NAME} API", version="0.1.0", openapi_url="/api/openapi.json", docs_url="/api/docs", lifespan=lifespan)
    app.state.db = database
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"],
                       allow_credentials=True)

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        lang = i18n.pick_language(request.headers.get("accept-language"))  # en, ar or fr; the {code, message} shape is unchanged
        return JSONResponse({"code": exc.code, "message": i18n.translate_error(exc.code, exc.message, lang)}, status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Framework errors (unknown route, wrong method) use the same {code, message} shape as
        # domain errors, whether or not the built front end is present.
        lang = i18n.pick_language(request.headers.get("accept-language"))
        if exc.status_code == 404:
            return JSONResponse({"code": "NOT_FOUND", "message": i18n.translate_error("NOT_FOUND", "No such route.", lang)}, status_code=404)
        return JSONResponse({"code": "HTTP_ERROR", "message": str(exc.detail)}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    app.include_router(routes.router)
    app.include_router(routes_more.router)
    app.include_router(dashboard.router)
    app.openapi = lambda: _openapi_with_payloads(app)  # type: ignore[method-assign]

    if FRONTEND_DIST.is_dir():
        if (FRONTEND_DIST / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str, request: Request):
            if path.startswith("api/"):
                lang = i18n.pick_language(request.headers.get("accept-language"))
                return JSONResponse({"code": "NOT_FOUND", "message": i18n.translate_error("NOT_FOUND", "No such route.", lang)}, status_code=404)
            candidate = (FRONTEND_DIST / path).resolve()
            if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


_default_app: FastAPI | None = None


def __getattr__(name: str) -> FastAPI:
    """`uvicorn app.main:app` builds the default app lazily, so importing this module never touches a database."""
    global _default_app
    if name == "app":
        if _default_app is None:
            _default_app = create_app()
        return _default_app
    raise AttributeError(name)
