import os
import pandas as pd
import uvicorn
import requests

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# =========================================================
# APP
# =========================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# =========================================================
# RUTAS
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# =========================================================
# OPEN METEO
# =========================================================

COORDENADAS = {
    "LAMBAYEQUE": {"lat": -6.7, "lon": -79.9},
    "LA LIBERTAD": {"lat": -8.1, "lon": -79.0},
    "ICA": {"lat": -14.0, "lon": -75.7},
    "CUSCO": {"lat": -13.5, "lon": -71.9},
    "PUNO": {"lat": -15.8, "lon": -70.0},
    "CAJAMARCA": {"lat": -7.1, "lon": -78.5},
    "LIMA": {"lat": -12.0, "lon": -77.0}
}

# =========================================================
# CARGA DE DATOS-
# =========================================================

def cargar_datos():
    try:

        # =====================================================
        # ARCHIVOS
        # =====================================================
        clima_path = os.path.join(DATA_DIR,"DATOS_CLIMATOLOGICOS_2024.xlsx")
        caratula_path = os.path.join(DATA_DIR,"CARATULA.xlsx")
        cultivos_path = os.path.join(DATA_DIR,"CULTIVOS.xlsx")

        # =====================================================
        # LEER EXCELS
        # =====================================================
        clima_df = pd.read_excel(clima_path)
        caratula_df = pd.read_excel(caratula_path)
        cultivos_df = pd.read_excel(cultivos_path)

        # =====================================================
        # LIMPIAR COLUMNAS
        # =====================================================
        clima_df.columns = (clima_df.columns.str.strip().str.upper())
        caratula_df.columns = (caratula_df.columns.str.strip().str.upper())
        cultivos_df.columns = (cultivos_df.columns.str.strip().str.upper())

        # =====================================================
        # RENOMBRE GEOGRAFIA
        # =====================================================
        renames_geo = {
            "DEPARTAMENTO": "NOMBREDD",
            "PROVINCIA": "NOMBREPV",
            "DISTRITO": "NOMBREDI"
        }
        clima_df.rename(columns=renames_geo, inplace=True)
        caratula_df.rename(columns=renames_geo, inplace=True)
        cultivos_df.rename(columns=renames_geo, inplace=True)

        # =====================================================
        # RENOMBRE CLIMA
        # =====================================================

        clima_df.rename(columns={
            "TMEAN": "TEMP_MEDIA_PROM",
            "TMAX": "TEMP_MAX_PROM",
            "TMIN": "TEMP_MIN_PROM",
            "HUMR": "HUMEDAD_PROM",
            "PTOT": "PRECIP_TOTAL"
        }, inplace=True)

        # =====================================================
        # LIMPIAR TEXTO
        # =====================================================
        for df in [clima_df, caratula_df, cultivos_df]:
            for col in [
                "NOMBREDD",
                "NOMBREPV",
                "NOMBREDI"
            ]:
                if col in df.columns:
                    df[col] = (df[col].astype(str).str.strip().str.upper())

        # =====================================================
        # COLUMNAS NUMERICAS
        # =====================================================

        columnas_clima = [
            "TEMP_MEDIA_PROM",
            "TEMP_MAX_PROM",
            "TEMP_MIN_PROM",
            "HUMEDAD_PROM",
            "PRECIP_TOTAL"
        ]

        for col in columnas_clima:
            if col in clima_df.columns:
                clima_df[col] = (clima_df[col].astype(str).str.replace(",", ".", regex=False))
                clima_df[col] = pd.to_numeric(clima_df[col],errors="coerce")

        # =====================================================
        # DEBUG
        # =====================================================
        print("\n========== COLUMNAS CLIMA ==========")
        print(clima_df.columns.tolist())
        print("\n========== COLUMNAS CULTIVOS ==========")
        print(cultivos_df.columns.tolist())
        print("\n✅ Datos cargados correctamente")
        return clima_df, caratula_df, cultivos_df

    except Exception as e:
        print(f"\n❌ ERROR AL CARGAR DATOS: {e}")
        return None, None, None

clima_df, caratula_df, cultivos_df = cargar_datos()

# =========================================================
# MODELO
# =========================================================

class Consulta(BaseModel):
    region: str
    provincia: str
    distrito: str

# =========================================================
# UBICACIONES
# =========================================================
@app.get("/ubicaciones")
def get_ubicaciones():
    if caratula_df is None:
        return {}
    tree = {}

    df_mini = caratula_df[
        ["NOMBREDD", "NOMBREPV", "NOMBREDI"]
    ].drop_duplicates()

    for _, row in df_mini.iterrows():
        region = row["NOMBREDD"]
        provincia = row["NOMBREPV"]
        distrito = row["NOMBREDI"]
        if region not in tree:
            tree[region] = {}

        if provincia not in tree[region]:
            tree[region][provincia] = []
        tree[region][provincia].append(distrito)
    return tree

# =========================================================
# RIESGO CLIMATICO
# =========================================================
def calcular_riesgo(temp_min, temp_max, precip):
    if temp_min <= 5:
        return "HELADA"
    elif temp_max >= 35:
        return "CALOR EXTREMO"

    elif precip >= 150:
        return "EXCESO LLUVIA"
    else:
        return "NORMAL"

# =========================================================
# CONSULTA
# =========================================================

@app.post("/consulta")
def post_consulta(req: Consulta):

    region = req.region.strip().upper()
    provincia = req.provincia.strip().upper()
    distrito = req.distrito.strip().upper()

    # =====================================================
    # FILTRO CLIMA
    # =====================================================

    clima_filtrado = clima_df[
        (clima_df["NOMBREDD"] == region) &
        (clima_df["NOMBREPV"] == provincia) &
        (clima_df["NOMBREDI"] == distrito)
    ]

    # =====================================================
    # FILTRO CULTIVOS
    # =====================================================

    cultivos_filtrado = cultivos_df[
        (cultivos_df["NOMBREDD"] == region) &
        (cultivos_df["NOMBREPV"] == provincia) &
        (cultivos_df["NOMBREDI"] == distrito)
    ]

    # =====================================================
    # VALIDAR DATOS
    # =====================================================

    print("========== FILTRO ==========")
    print(region, provincia, distrito)

    print("CLIMA:")
    print(clima_filtrado.shape)

    print("CULTIVOS:")
    print(cultivos_filtrado.shape)

    # =====================================================
    # VARIABLES CLIMATICAS
    # =====================================================

    registros = len(clima_filtrado)

    media_temp = round(
        clima_filtrado["TEMP_MEDIA_PROM"].mean(), 1
    ) if not clima_filtrado.empty else 0

    temp_min = round(
        clima_filtrado["TEMP_MIN_PROM"].mean(), 1
    ) if not clima_filtrado.empty else 0

    temp_max = round(
        clima_filtrado["TEMP_MAX_PROM"].mean(), 1
    ) if not clima_filtrado.empty else 0

    humedad = round(
        clima_filtrado["HUMEDAD_PROM"].mean(), 1
    ) if not clima_filtrado.empty else 0

    precip = round(
        clima_filtrado["PRECIP_TOTAL"].mean(), 1
    ) if not clima_filtrado.empty else 0

    # =====================================================
    # CULTIVOS
    # =====================================================

    cultivos_res = ["SIN DATOS"]

    if (
        not cultivos_filtrado.empty and
        "P204_NOM" in cultivos_filtrado.columns
    ):

        cultivos_res = (
            cultivos_filtrado["P204_NOM"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .value_counts()
            .head(3)
            .index
            .tolist()
        )

    # =====================================================
    # RIESGO CLIMATICO
    # =====================================================

    riesgo = calcular_riesgo(
        temp_min,
        temp_max,
        precip
    )

    # =====================================================
    # OPEN METEO
    # =====================================================

    geo = COORDENADAS.get(
        region,
        {"lat": -12.0, "lon": -77.0}
    )

    temp_actual = 0
    humedad_actual = 0
    rango_15d = "No disponible"

    try:

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={geo['lat']}"
            f"&longitude={geo['lon']}"
            f"&current=temperature_2m,relative_humidity_2m"
            f"&daily=temperature_2m_max,temperature_2m_min"
            f"&timezone=auto"
        )

        response = requests.get(url, timeout=5).json()

        temp_actual = response["current"]["temperature_2m"]

        humedad_actual = response["current"]["relative_humidity_2m"]

        rango_15d = (
            f"{min(response['daily']['temperature_2m_min'])}° / "
            f"{max(response['daily']['temperature_2m_max'])}°"
        )

    except Exception as e:
        print(f"⚠️ ERROR OPEN METEO: {e}")

    # =====================================================
    # DETALLES
    # =====================================================

    detalles = []

    for i, cultivo in enumerate(cultivos_res):

        detalles.append({
            "nombre": f"{i+1}. {cultivo}",
            "msg": f"RiesGO climático: {riesgo}"
        })

    # =====================================================
    # RESPUESTA
    # =====================================================

    return {

        "region": region,
        "provincia": provincia,
        "distrito": distrito,

        "registros_ena": registros,

        "temp_actual": temp_actual,
        "humedad_actual": humedad_actual,
        "rango_15d": rango_15d,

        "riesgo_climatico": riesgo,

        "ena_stats": {
            "temp_media": media_temp,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "humedad": humedad,
            "precipitacion": precip
        },

        "top_cultivos": cultivos_res,

        "recomendacion_principal":
            f"Según el historial climático de {distrito}, "
            f"se recomienda priorizar el cultivo {cultivos_res[0]}.",

        "detalles_cultivos": detalles
    }
# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    uvicorn.run(app,host="127.0.0.1",port=8000)