from __future__ import annotations

import io
from typing import Dict

import pandas as pd
import xlsxwriter

from analyzer import AnalysisResult


_PERCENT_COLUMNS = [
    "Geviş Düşüş %", "Beslenme Süre Düşüş %", "Kalan/Talep %", "İnaktiflik Artış %",
    "Süt Kısa Düşüş %", "Ham Süt Düşüş %", "İletkenlik Asimetri %", "İletkenlik Trend Artışı %",
    "İletkenlik Alarm Oranı %", "Beklenen/Gerçek Süt Açığı %", "En Kötü Çeyrek Süt Açığı %",
    "Milk Flow Düşüş %", "Süt Verim Alarm Oranı %", "OK Ziyaret Düşüş %",
    "Başarısız Ziyaret Artışı (puan)", "Incomplete Artışı (puan)", "Attachment Abort Artışı (puan)",
    "Reattach Artışı %", "Kickoff Artışı %",
]


def _write_df(writer, sheet_name: str, df: pd.DataFrame, startrow: int = 0) -> None:
    df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=startrow)
    wb = writer.book
    ws = writer.sheets[sheet_name]
    header = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D", "border": 0, "align": "center", "valign": "vcenter", "text_wrap": True})
    percent = wb.add_format({"num_format": "0.0%"})
    decimal = wb.add_format({"num_format": "0.0"})
    riskfmt = wb.add_format({"num_format": "0.0"})
    for col, name in enumerate(df.columns):
        ws.write(startrow, col, name, header)
        width = min(34, max(12, len(str(name)) + 2))
        if name in {"V2 Açıklama", "Konu", "Açıklama"}:
            width = 38
        fmt = None
        if name in _PERCENT_COLUMNS:
            fmt = percent
        elif "Risk" in name or "Kapsama" in name or "Öncelik" in name:
            fmt = riskfmt
        elif "Süt" in name or "Milk Flow" in name:
            fmt = decimal
        ws.set_column(col, col, width, fmt)
    ws.freeze_panes(startrow + 1, 0)
    if len(df):
        ws.autofilter(startrow, 0, startrow + len(df), len(df.columns) - 1)


def build_excel(result: AnalysisResult) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        wb = writer.book
        title_fmt = wb.add_format({"bold": True, "font_size": 16, "font_color": "#17365D"})
        kpi_name = wb.add_format({"bold": True, "bg_color": "#DCEAF5", "font_color": "#17365D"})
        kpi_value = wb.add_format({"bold": True, "num_format": "0.00"})

        ws = wb.add_worksheet("Özet")
        writer.sheets["Özet"] = ws
        ws.write("A1", "SÜRÜ RİSK ANALİZİ V2", title_fmt)
        summary_df = pd.DataFrame(list(result.summary.items()), columns=["Gösterge", "Değer"])
        summary_df.to_excel(writer, sheet_name="Özet", index=False, startrow=2, startcol=0)
        ws.write_row(2, 0, ["Gösterge", "Değer"], wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D"}))
        for r in range(len(summary_df)):
            ws.write(r + 3, 0, summary_df.iloc[r, 0], kpi_name)
            ws.write(r + 3, 1, summary_df.iloc[r, 1], kpi_value)
        ws.set_column("A:A", 38)
        ws.set_column("B:B", 27)

        levels = ["YÜKSEK", "ORTA", "İZLE", "DÜŞÜK", "VERİ EKSİK"]
        rc = result.risk["V2 Seviye"].value_counts()
        dist = pd.DataFrame({"Risk Seviyesi": levels, "Hayvan Sayısı": [int(rc.get(x, 0)) for x in levels]})
        dist.to_excel(writer, sheet_name="Özet", index=False, startrow=2, startcol=3)
        ws.write_row(2, 3, ["Risk Seviyesi", "Hayvan Sayısı"], wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D"}))

        result.reproduction.to_excel(writer, sheet_name="Özet", index=False, startrow=10, startcol=3)
        result.lactation.to_excel(writer, sheet_name="Özet", index=False, startrow=2, startcol=6)
        for row, col, headers in [
            (10, 3, result.reproduction.columns.tolist()),
            (2, 6, result.lactation.columns.tolist()),
        ]:
            ws.write_row(row, col, headers, wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D", "text_wrap": True}))
        ws.set_column("D:E", 23)
        ws.set_column("G:J", 24)

        top_cols = ["Hayvan No", "V2 Genel Öncelik", "V2 Seviye", "Genel Sağlık Risk", "Meme Sağlığı Risk", "Sağım/Robot Risk", "Üreme Durumu", "Laktasyon No", "Laktasyon Günü (DIM)", "Süt 7 Gün Ort. (kg/gün)", "V2 Açıklama"]
        top = result.risk[top_cols].head(20)
        top.to_excel(writer, sheet_name="Özet", index=False, startrow=24, startcol=0)
        ws.write_row(24, 0, top.columns.tolist(), wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D", "text_wrap": True}))
        ws.set_column("A:K", 18)
        ws.set_column("K:K", 35)
        ws.freeze_panes(3, 0)

        _write_df(writer, "V2 Risk Analizi", result.risk)
        _write_df(writer, "Laktasyon Özeti", result.lactation)
        _write_df(writer, "Üreme Özeti", result.reproduction)
        _write_df(writer, "Metodoloji", result.methodology)

        rws = writer.sheets["V2 Risk Analizi"]
        if len(result.risk):
            score_col = result.risk.columns.get_loc("V2 Genel Öncelik")
            level_col = result.risk.columns.get_loc("V2 Seviye")
            rws.conditional_format(1, score_col, len(result.risk), score_col, {"type": "data_bar", "bar_color": "#5B9BD5"})
            for level, color in [("YÜKSEK", "#F8CECB"), ("ORTA", "#FFE1A6"), ("İZLE", "#FFF3D6"), ("DÜŞÜK", "#E4F3E6"), ("VERİ EKSİK", "#E1E8F2")]:
                rws.conditional_format(1, level_col, len(result.risk), level_col, {"type": "text", "criteria": "containing", "value": level, "format": wb.add_format({"bg_color": color})})

    return output.getvalue()


def build_csv(result: AnalysisResult) -> bytes:
    text = result.risk.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig")
    return text.encode("utf-8-sig") if not text.startswith("\ufeff") else text.encode("utf-8")
