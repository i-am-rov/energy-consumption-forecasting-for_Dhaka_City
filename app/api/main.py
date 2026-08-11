"""FastAPI application entry point."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .features import FeatureValidationError
from .schemas import (
    ApiError,
    ApiMetadata,
    ErrorResponse,
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
    ModelCatalogResponse,
    SevenDayForecastRequest,
    SevenDayForecastResponse,
    ValidationIssue,
    WeatherHorizonResponse,
)
from .service import ForecastService, ModelPredictionError
from .weather import WeatherServiceError

STATIC_DIRECTORY = Path(__file__).resolve().parent / "static"
STATIC_INDEX = STATIC_DIRECTORY / "index.html"
_service = ForecastService()


def get_forecast_service() -> ForecastService:
    return _service


app = FastAPI(
    title="Dhaka Energy Consumption Forecasting API",
    summary="Validated one-day and seven-day electricity-demand forecasts from 11 models.",
    description=(
        "Forecast demand recursively for the next seven days after the available history. "
        "Choose one stable model number or run all 11. Temperature may be entered "
        "manually or calculated as the mean of Dhaka's forecast daily high and low "
        "from Open-Meteo. The advanced hybrid ensemble is intentionally not exposed."
    ),
    version="2.0.0",
    contact={"name": "Energy Consumption Forecasting Project"},
    license_info={"name": "Project internal use"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Forecasting", "description": "Generate validated demand forecasts."},
        {"name": "Configuration", "description": "Read UI choices and date restrictions."},
        {"name": "Operations", "description": "Service health and artifact checks."},
    ],
)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")


def _json_error(
    http_status: int,
    code: str,
    message: str,
    details: list[ValidationIssue] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(error=ApiError(code=code, message=message, details=details or []))
    return JSONResponse(status_code=http_status, content=payload.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ()) if part != "body"]
        message = str(error.get("msg", "Invalid value"))
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        details.append(
            ValidationIssue(
                field=".".join(location) or "request",
                message=message,
                type=str(error.get("type", "validation_error")),
            )
        )
    return _json_error(422, "validation_error", "Request validation failed.", details)


@app.exception_handler(FeatureValidationError)
async def feature_validation_error_handler(
    _request: Request,
    exc: FeatureValidationError,
) -> JSONResponse:
    return _json_error(
        422,
        "forecast_date_not_allowed",
        str(exc),
        [ValidationIssue(field="forecast_date", message=str(exc), type="value_error")],
    )


@app.exception_handler(WeatherServiceError)
async def weather_service_error_handler(
    _request: Request,
    exc: WeatherServiceError,
) -> JSONResponse:
    return _json_error(502, "weather_service_error", str(exc))


@app.exception_handler(ModelPredictionError)
async def model_prediction_error_handler(
    _request: Request,
    exc: ModelPredictionError,
) -> JSONResponse:
    return _json_error(500, "model_prediction_error", str(exc))


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home() -> HTMLResponse:
    return HTMLResponse(STATIC_INDEX.read_text(encoding="utf-8"))


@app.get(
    "/api/v1/metadata",
    response_model=ApiMetadata,
    tags=["Configuration"],
    summary="Get valid dates, holidays, and model choices",
)
async def metadata(service: ForecastService = Depends(get_forecast_service)) -> ApiMetadata:
    return service.metadata()


@app.get(
    "/api/v1/models",
    response_model=ModelCatalogResponse,
    tags=["Configuration"],
    summary="Get the stable model-number mapping",
    description=(
        "Frontend applications may populate their model selector from this endpoint. "
        "Send the returned integer id as the forecast request's model value, or send 'all'."
    ),
)
async def models(service: ForecastService = Depends(get_forecast_service)) -> ModelCatalogResponse:
    return service.model_catalog()


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Operations"],
    summary="Check configuration and model artifact availability",
)
async def health(service: ForecastService = Depends(get_forecast_service)) -> HealthResponse:
    return service.health()


@app.post(
    "/api/v1/forecast",
    response_model=ForecastResponse,
    tags=["Forecasting"],
    summary="Forecast next-day demand",
    status_code=status.HTTP_200_OK,
    responses={
        422: {"model": ErrorResponse, "description": "Invalid request or forecast date"},
        502: {
            "model": ErrorResponse,
            "description": "Dhaka weather provider unavailable or returned invalid data",
        },
        500: {
            "model": ErrorResponse,
            "description": "A selected model artifact could not produce a forecast",
        },
    },
)
async def forecast(
    request: ForecastRequest,
    service: ForecastService = Depends(get_forecast_service),
) -> ForecastResponse:
    return await service.forecast(request)


@app.get(
    "/api/v1/weather/7-day",
    response_model=WeatherHorizonResponse,
    tags=["Forecasting"],
    summary="Fetch Dhaka temperatures for the next seven forecast dates",
    responses={
        502: {
            "model": ErrorResponse,
            "description": "Dhaka weather provider unavailable or returned invalid data",
        }
    },
)
async def weather_horizon(
    service: ForecastService = Depends(get_forecast_service),
) -> WeatherHorizonResponse:
    return await service.weather_horizon()


@app.post(
    "/api/v1/forecast/7-day",
    response_model=SevenDayForecastResponse,
    tags=["Forecasting"],
    summary="Forecast seven consecutive days recursively",
    status_code=status.HTTP_200_OK,
    responses={
        422: {"model": ErrorResponse, "description": "Invalid seven-day inputs"},
        502: {
            "model": ErrorResponse,
            "description": "Dhaka weather provider unavailable or returned invalid data",
        },
        500: {
            "model": ErrorResponse,
            "description": "A selected model artifact could not produce a forecast",
        },
    },
)
async def forecast_horizon(
    request: SevenDayForecastRequest,
    service: ForecastService = Depends(get_forecast_service),
) -> SevenDayForecastResponse:
    return await service.forecast_horizon(request)
