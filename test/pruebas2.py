import pandas as pd
import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)

from services.forecast_service import (
    preparar_fecha_iso,
    forecast_temperatura
)

# =====================================================
# ARCHIVOS
# =====================================================
archivos = [
    "historico_clima_2021.xlsx",
    "historico_clima_2022.xlsx",
    "historico_clima_2023.xlsx",
    "historico_clima_2024.xlsx"
]

lista_df = []

# =====================================================
# CARGAR DATASETS
# =====================================================
for archivo in archivos:

    path = os.path.join(
        "data",
        "clima_historico",
        archivo
    )

    df = pd.read_excel(path)

    # =================================================
    # NORMALIZAR COLUMNAS
    # =================================================
    df.columns = (
        df.columns
        .str.strip()
        .str.upper()
    )

    # =================================================
    # RENOMBRAR
    # =================================================
    df.rename(columns={
        "DEPARTAMENTO": "NOMBREDD",
        "PROVINCIA": "NOMBREPV",
        "DISTRITO": "NOMBREDI",
        "TMEAN": "TEMP_MEDIA_PROM",
        "TMAX": "TEMP_MAX_PROM",
        "TMIN": "TEMP_MIN_PROM",
        "HUMR": "HUMEDAD_PROM",
        "PTOT": "PRECIP_TOTAL",
        "ANO": "ANIO"
    }, inplace=True)

    # =================================================
    # FECHA ISO
    # =================================================
    df = preparar_fecha_iso(df)

    lista_df.append(df)

# =====================================================
# UNIR TODO
# =====================================================
df_total = pd.concat(
    lista_df,
    ignore_index=True
)

# =====================================================
# TESTS
# =====================================================

print("\n===== TEMP MEDIA =====\n")

temp_media = forecast_temperatura(
    df=df_total,
    region="APURIMAC",
    provincia="ABANCAY",
    distrito="ABANCAY",
    variable="TEMP_MEDIA_PROM"
)

for item in temp_media:
    print(item)

print("\n===== TEMP MIN =====\n")

temp_min = forecast_temperatura(
    df=df_total,
    region="APURIMAC",
    provincia="ABANCAY",
    distrito="ABANCAY",
    variable="TEMP_MIN_PROM"
)

for item in temp_min:
    print(item)

print("\n===== TEMP MAX =====\n")

temp_max = forecast_temperatura(
    df=df_total,
    region="APURIMAC",
    provincia="ABANCAY",
    distrito="ABANCAY",
    variable="TEMP_MAX_PROM"
)

for item in temp_max:
    print(item)

print("\n===== HUMEDAD =====\n")

humedad = forecast_temperatura(
    df=df_total,
    region="APURIMAC",
    provincia="ABANCAY",
    distrito="ABANCAY",
    variable="HUMEDAD_PROM"
)

for item in humedad:
    print(item)

print("\n===== PRECIPITACIÓN =====\n")

precip = forecast_temperatura(
    df=df_total,
    region="APURIMAC",
    provincia="ABANCAY",
    distrito="ABANCAY",
    variable="PRECIP_TOTAL"
)

for item in precip:
    print(item)