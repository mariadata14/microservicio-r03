import pandas as pd

from datetime import datetime
from statsmodels.tsa.arima.model import ARIMA


# =====================================================
# FECHA ISO
# =====================================================
def preparar_fecha_iso(df):
    if "ANIO" not in df.columns:
        return df

    if "SEMANA" not in df.columns:
        return df

    df["FECHA"] = pd.to_datetime(
        df["ANIO"].astype(str)
        + "-W" +
        df["SEMANA"].astype(str)
        + "-1",
        format="%G-W%V-%u",
        errors="coerce"
    )
    return df


# =====================================================
# FORECAST
# =====================================================
def forecast_temperatura(
    df,
    region,
    provincia,
    distrito,
    variable="TEMP_MEDIA_PROM",
    pasos=5,
    ajuste_actual=None
):

    # =================================================
    # FILTRAR
    # =================================================
    df_f = df[
        (df["NOMBREDD"] == region) &
        (df["NOMBREPV"] == provincia) &
        (df["NOMBREDI"] == distrito)
    ].copy()

    # =================================================
    # VALIDAR
    # =================================================
    if df_f.empty:
        return []

    if variable not in df_f.columns:
        return []

    if "FECHA" not in df_f.columns:
        return []

    # =================================================
    # LIMPIAR
    # =================================================
    df_f = df_f.dropna(subset=["FECHA", variable])

    if len(df_f) < 10:
        return []

    # =================================================
    # SERIES
    # =================================================
    serie = (df_f.groupby("FECHA")[variable].mean().sort_index())

    # =================================================
    # FRECUENCIA SEMANAL
    # =================================================
    serie.index = pd.DatetimeIndex(serie.index)

    serie = serie.asfreq("W-MON")

    serie = serie.ffill()
    serie = serie.bfill()

    # =================================================
    # MODELO ARIMA
    # =================================================
    modelo = ARIMA(serie,order=(1, 1, 1))

    modelo_fit = modelo.fit()

    forecast = modelo_fit.forecast(steps=pasos)

    # =================================================
    # SEMANA ACTUAL REAL
    # =================================================
    hoy = datetime.now()

    future_dates = pd.date_range(
        start=hoy,
        periods=pasos + 1,
        freq="W-MON"
    )[1:]

    # =================================================
    # RESULTADO
    # =================================================
    resultado = []

    for fecha, pred in zip(future_dates, forecast):

        # =============================================
        # AJUSTE OPEN METEO
        # =============================================
        if ajuste_actual is not None:
            pred = (
                pred * 0.8 +
                ajuste_actual * 0.2
            )
        semana_iso = fecha.isocalendar()

        resultado.append({
            "semana_iso": f"{semana_iso.year}-W{semana_iso.week:02d}",
            "fecha": fecha.strftime("%Y-%m-%d"),
            "valor_predicho": round(float(pred), 2),
            "margen_error":"±5%"
        })

    return resultado