from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from analyzer import AnalysisResult, analyze_v2
from exporter import build_csv, build_excel

BASE = Path(__file__).resolve().parent
MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", str(90 * 1024 * 1024)))
PUBLIC_HOST = os.getenv("PUBLIC_HOST", "").strip()
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "0").strip().lower() in {"1", "true", "yes"}

app = FastAPI(title="Sürü Risk Analizi V2", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS or ["*"])
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


class AnalysisPayload(BaseModel):
    saglik: str = Field(min_length=20)
    beslenme: str = Field(min_length=20)
    sut: str = Field(min_length=20)
    ureme: str = Field(min_length=20)


class ExportPayload(BaseModel):
    ozet: Dict[str, Any]
    laktasyon: List[Dict[str, Any]]
    ureme: List[Dict[str, Any]]
    risk_sonuc: List[Dict[str, Any]]
    metodoloji: List[Dict[str, Any]]


def _records_json(df: pd.DataFrame):
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


def _result_from_export_payload(payload: ExportPayload) -> AnalysisResult:
    return AnalysisResult(
        risk=pd.DataFrame(payload.risk_sonuc),
        summary=payload.ozet,
        lactation=pd.DataFrame(payload.laktasyon),
        reproduction=pd.DataFrame(payload.ureme),
        methodology=pd.DataFrame(payload.metodoloji),
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BYTES:
        return JSONResponse({"detail": "Yükleme boyutu izin verilen sınırı aşıyor."}, status_code=413)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if ENABLE_HSTS:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True, "service": "risk-sagmal", "host": PUBLIC_HOST or None}


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "templates" / "index.html").read_text(encoding="utf-8")


@app.post("/api/analiz")
def analyze(payload: AnalysisPayload):
    try:
        result = analyze_v2(payload.saglik, payload.beslenme, payload.sut, payload.ureme)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Dosyalar analiz edilemedi: {exc}") from exc

    risk_cols = [
        "Hayvan No", "V2 Genel Öncelik", "V2 Seviye", "Genel Sağlık Risk",
        "Meme Sağlığı Risk", "Sağım/Robot Risk", "Üreme Durumu", "Laktasyon No",
        "Laktasyon Günü (DIM)", "Süt 7 Gün Ort. (kg/gün)", "V2 Açıklama",
    ]
    return {
        "ozet": result.summary,
        "laktasyon": _records_json(result.lactation),
        "ureme": _records_json(result.reproduction),
        "oncelikli_hayvanlar": _records_json(result.risk[risk_cols].head(25)),
        "risk_sonuc": _records_json(result.risk),
        "metodoloji": _records_json(result.methodology),
    }


@app.post("/api/indir/excel")
def download_excel(payload: ExportPayload):
    result = _result_from_export_payload(payload)
    body = build_excel(result)
    return Response(
        body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="suru_risk_analizi_v2.xlsx"'},
    )


@app.post("/api/indir/csv")
def download_csv(payload: ExportPayload):
    result = _result_from_export_payload(payload)
    body = build_csv(result)
    return Response(
        body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="suru_risk_analizi_v2.csv"'},
    )


@app.post("/api/oturum/sil")
def clear_session():
    return {"ok": True, "mesaj": "Sunucuda saklanan kullanıcı verisi yok. Tarayıcı oturum verileri temizlenebilir."}
