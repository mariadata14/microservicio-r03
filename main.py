import os
import logging
import pandas as pd
import uvicorn
import requests

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def root():
    return FileResponse("index.html")

# =========================================================
# RUTAS
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# =========================================================
# DATAFRAMES GLOBALES
# =========================================================
clima_df    = None
caratula_df = None
cultivos_df = None

# fix: eliminado encode ascii para corregir tildes
# =========================================================
# CARGA DE DATOS
# =========================================================
def cargar_datos():
    try:
        clima_path    = os.path.join(DATA_DIR, "DATOS_CLIMATOLOGICOS_2024.xlsx")
        caratula_path = os.path.join(DATA_DIR, "CARATULA.xlsx")
        cultivos_path = os.path.join(DATA_DIR, "CULTIVOS.xlsx")

        def leer_limpio(path):
            df = pd.read_excel(path)
            df.columns = df.columns.str.strip().str.upper()
            return df

        clima_df    = leer_limpio(clima_path)
        caratula_df = leer_limpio(caratula_path)
        cultivos_df = leer_limpio(cultivos_path)

        for df in [clima_df, caratula_df, cultivos_df]:
            df.rename(columns={
                "DEPARTAMENTO": "NOMBREDD",
                "PROVINCIA"   : "NOMBREPV",
                "DISTRITO"    : "NOMBREDI",
            }, inplace=True)

        clima_df.rename(columns={
            "TMEAN": "TEMP_MEDIA_PROM",
            "TMAX" : "TEMP_MAX_PROM",
            "TMIN" : "TEMP_MIN_PROM",
            "HUMR" : "HUMEDAD_PROM",
            "PTOT" : "PRECIP_TOTAL",
            "TEMPERATURA MEDIA"  : "TEMP_MEDIA_PROM",
            "TEMPERATURA MAXIMA" : "TEMP_MAX_PROM",
            "TEMPERATURA MINIMA" : "TEMP_MIN_PROM",
            "HUMEDAD RELATIVA"   : "HUMEDAD_PROM",
            "PRECIPITACIÓN TOTAL": "PRECIP_TOTAL",
            "PRECIPITACION TOTAL": "PRECIP_TOTAL",
        }, inplace=True)

        cols_geo = ["NOMBREDD", "NOMBREPV", "NOMBREDI"]
        for df in [clima_df, caratula_df, cultivos_df]:
            for col in cols_geo:
                if col in df.columns:
                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.strip()
                        .str.upper()
                        .str.normalize("NFKD")
                        .str.encode("ascii", errors="ignore")
                        .str.decode("utf-8")
                    )

        cols_numericas = [
            "TEMP_MEDIA_PROM", "TEMP_MAX_PROM", "TEMP_MIN_PROM",
            "HUMEDAD_PROM", "PRECIP_TOTAL",
        ]
        for col in cols_numericas:
            if col in clima_df.columns:
                clima_df[col] = (
                    clima_df[col]
                    .astype(str)
                    .str.replace(",", ".", regex=False)
                    .str.strip()
                )
                clima_df[col] = pd.to_numeric(clima_df[col], errors="coerce")

        for col in ["LATITUD", "LONGITUD"]:
            if col in caratula_df.columns:
                caratula_df[col] = pd.to_numeric(
                    caratula_df[col].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce"
                )

        logger.info("✅ Datos cargados correctamente")
        return clima_df, caratula_df, cultivos_df

    except Exception as e:
        logger.error(f"❌ ERROR AL CARGAR DATOS: {e}")
        return None, None, None

# =========================================================
# STARTUP
# =========================================================
@app.on_event("startup")
async def startup():
    global clima_df, caratula_df, cultivos_df
    clima_df, caratula_df, cultivos_df = cargar_datos()

# =========================================================
# MODELO
# =========================================================
class Consulta(BaseModel):
    region:   str
    provincia: str
    distrito:  str

# =========================================================
# HELPER
# =========================================================
def validar_datos():
    if clima_df is None or caratula_df is None or cultivos_df is None:
        raise HTTPException(
            status_code=500,
            detail="Los datos no están cargados. Revisa los archivos en /data."
        )

# =========================================================
# HELPER — convierte tipos numpy a Python nativos para JSON
# =========================================================
def limpiar(val):
    import numpy as np
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    return val

# =========================================================
# RIESGO CLIMÁTICO
# =========================================================
def calcular_riesgo(temp_min_prom, temp_min_abs, temp_max_prom, precip_max, temp_actual):
    if temp_actual <= 4 or temp_min_abs <= 4:
        return "HELADA"
    elif temp_max_prom >= 35:
        return "CALOR EXTREMO"
    elif precip_max >= 150:
        return "EXCESO LLUVIA"
    else:
        return "NORMAL"

# =========================================================
# 🌿 NUEVA FUNCIÓN: RIESGO FITOSANITARIO (Detección de Plagas por Clima)
# Detecta condiciones climáticas que favorecen la aparición de plagas y enfermedades
# =========================================================
def calcular_riesgo_fitosanitario(humedad_actual: float, temp_actual: float, precip_prom: float) -> list:
    """
    Evalúa las condiciones climáticas actuales y retorna una lista de alertas
    fitosanitarias con el riesgo, la plaga/enfermedad y la recomendación.
    """
    alertas = []

    # ── Regla 1: Hongos (Roya, Mildiu, Botrytis) ──────────────────────────
    # Se desarrollan con humedad alta y temperaturas moderadas
    if humedad_actual >= 85 and 15 <= temp_actual <= 28:
        alertas.append({
            "nivel": "ALTO",
            "icono": "🍄",
            "tipo": "Hongos foliares (Roya / Mildiu)",
            "condicion": f"Humedad {humedad_actual}% + Temp {temp_actual}°C",
            "mensaje": "Condiciones ideales para el desarrollo de hongos. Aplicar fungicida preventivo y mejorar ventilación entre cultivos.",
            "color": "red"
        })
    elif humedad_actual >= 70 and 15 <= temp_actual <= 28:
        alertas.append({
            "nivel": "MODERADO",
            "icono": "🍄",
            "tipo": "Hongos foliares (Roya / Mildiu)",
            "condicion": f"Humedad {humedad_actual}% + Temp {temp_actual}°C",
            "mensaje": "Humedad elevada puede favorecer hongos. Monitorear hojas y aplicar fungicida si aparecen manchas.",
            "color": "yellow"
        })

    # ── Regla 2: Ácaros e Insectos (trips, pulgones) ──────────────────────
    # Se reproducen con calor seco
    if temp_actual >= 28 and humedad_actual < 50:
        alertas.append({
            "nivel": "ALTO",
            "icono": "🕷️",
            "tipo": "Ácaros / Trips / Pulgones",
            "condicion": f"Temp {temp_actual}°C + Humedad baja {humedad_actual}%",
            "mensaje": "El calor seco acelera la reproducción de ácaros e insectos chupadores. Revisar el envés de las hojas y aplicar acaricida si es necesario.",
            "color": "red"
        })

    # ── Regla 3: Mosquilla / Larvas (suelo húmedo y cálido) ───────────────
    if humedad_actual >= 80 and temp_actual >= 22 and precip_prom >= 50:
        alertas.append({
            "nivel": "MODERADO",
            "icono": "🐛",
            "tipo": "Larvas de suelo / Mosquilla",
            "condicion": f"Suelo húmedo + Temp {temp_actual}°C",
            "mensaje": "Las lluvias recientes y el calor favorecen larvas en el suelo. Inspeccionar raíces y base de tallos.",
            "color": "yellow"
        })

    # ── Regla 4: Bacterias (calor extremo + humedad alta) ─────────────────
    if temp_actual >= 30 and humedad_actual >= 75:
        alertas.append({
            "nivel": "ALTO",
            "icono": "🦠",
            "tipo": "Enfermedades bacterianas",
            "condicion": f"Temp {temp_actual}°C + Humedad {humedad_actual}%",
            "mensaje": "Combinación de calor y humedad favorece bacterias como Xanthomonas y Pseudomonas. Evitar el riego por aspersión y usar cobre como preventivo.",
            "color": "red"
        })

    # ── Regla 5: Helada — daño directo a cultivos ─────────────────────────
    if temp_actual <= 4:
        alertas.append({
            "nivel": "CRÍTICO",
            "icono": "🧊",
            "tipo": "Daño por helada",
            "condicion": f"Temp actual {temp_actual}°C",
            "mensaje": "Temperatura bajo cero detectada. Riesgo crítico de daño celular en cultivos. Cubrir plantas sensibles y suspender el riego.",
            "color": "purple"
        })

    # ── Sin alertas ────────────────────────────────────────────────────────
    if not alertas:
        alertas.append({
            "nivel": "BAJO",
            "icono": "✅",
            "tipo": "Sin riesgos detectados",
            "condicion": f"Humedad {humedad_actual}% + Temp {temp_actual}°C",
            "mensaje": "Las condiciones climáticas actuales no representan un riesgo fitosanitario significativo. Continuar con el monitoreo rutinario.",
            "color": "green"
        })

    return alertas

# =========================================================
# ENDPOINT: /ubicaciones
# =========================================================
@app.get("/ubicaciones")
def get_ubicaciones():
    validar_datos()
    tree = {}
    df_mini = caratula_df[["NOMBREDD", "NOMBREPV", "NOMBREDI"]].drop_duplicates()
    for _, row in df_mini.iterrows():
        region    = row["NOMBREDD"]
        provincia = row["NOMBREPV"]
        distrito  = row["NOMBREDI"]
        if region not in tree:
            tree[region] = {}
        if provincia not in tree[region]:
            tree[region][provincia] = []
        tree[region][provincia].append(distrito)
    return tree

# =========================================================
# ENDPOINT: /consulta
# =========================================================
@app.post("/consulta")
def post_consulta(req: Consulta):
    validar_datos()

    region    = req.region.strip().upper()
    provincia = req.provincia.strip().upper()
    distrito  = req.distrito.strip().upper()

    def filtrar(df):
        return df[
            (df["NOMBREDD"] == region) &
            (df["NOMBREPV"] == provincia) &
            (df["NOMBREDI"] == distrito)
        ]

    clima_f    = filtrar(clima_df)
    caratula_f = filtrar(caratula_df)
    cultivos_f = filtrar(cultivos_df)

    logger.info(f"Consulta: {region} / {provincia} / {distrito}")

    registros = len(clima_f)

    def mean_col(df, col):
        return round(df[col].mean(), 1) if not df.empty and col in df.columns else 0.0
    def min_col(df, col):
        return round(df[col].min(), 1) if not df.empty and col in df.columns else 0.0
    def max_col(df, col):
        return round(df[col].max(), 1) if not df.empty and col in df.columns else 0.0

    temp_media_prom = mean_col(clima_f, "TEMP_MEDIA_PROM")
    temp_min_prom   = mean_col(clima_f, "TEMP_MIN_PROM")
    temp_max_prom   = mean_col(clima_f, "TEMP_MAX_PROM")
    temp_min_abs    = min_col(clima_f,  "TEMP_MIN_PROM")
    temp_max_abs    = max_col(clima_f,  "TEMP_MAX_PROM")
    humedad_prom    = mean_col(clima_f, "HUMEDAD_PROM")
    precip_prom     = mean_col(clima_f, "PRECIP_TOTAL")
    precip_max      = max_col(clima_f,  "PRECIP_TOTAL")

    region_natural = "N/A"
    if not caratula_f.empty and "REGION" in caratula_f.columns:
        region_natural = caratula_f["REGION"].mode()[0] if not caratula_f["REGION"].isna().all() else "N/A"

    lat, lon = -12.0, -77.0
    if not caratula_f.empty and "LATITUD" in caratula_f.columns and "LONGITUD" in caratula_f.columns:
        lat_calc = caratula_f["LATITUD"].mean()
        lon_calc = caratula_f["LONGITUD"].mean()
        if pd.notna(lat_calc) and pd.notna(lon_calc):
            lat, lon = round(lat_calc, 4), round(lon_calc, 4)

    temp_actual    = 0.0
    humedad_actual = 0
    rango_15d      = "No disponible"

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m"
            f"&daily=temperature_2m_max,temperature_2m_min"
            f"&timezone=auto"
        )
        response = requests.get(url, timeout=5).json()
        temp_actual    = response["current"]["temperature_2m"]
        humedad_actual = response["current"]["relative_humidity_2m"]
        rango_15d = (
            f"{min(response['daily']['temperature_2m_min'])}° / "
            f"{max(response['daily']['temperature_2m_max'])}°"
        )
    except Exception as e:
        logger.warning(f"⚠️ Error Open Meteo: {e}")

    cultivos_res = ["SIN DATOS"]
    if not cultivos_f.empty and "P204_NOM" in cultivos_f.columns:
        top = (
            cultivos_f["P204_NOM"]
            .dropna().astype(str).str.strip().str.upper()
            .value_counts().head(3).index.tolist()
        )
        if top:
            cultivos_res = top

    riesgo = calcular_riesgo(temp_min_prom, temp_min_abs, temp_max_prom, precip_max, temp_actual)

    # 🌿 NUEVA: Calcular alertas fitosanitarias
    alertas_fitosanitarias = calcular_riesgo_fitosanitario(
        humedad_actual=humedad_actual,
        temp_actual=temp_actual,
        precip_prom=precip_prom
    )

    detalles = [
        {"nombre": f"{i+1}. {cultivo}", "msg": f"Riesgo climático: {riesgo}"}
        for i, cultivo in enumerate(cultivos_res)
    ]

    return {
        "region":   region,
        "provincia": provincia,
        "distrito":  distrito,
        "region_natural": str(region_natural),
        "coordenadas": {"lat": limpiar(lat), "lon": limpiar(lon)},
        "registros_ena": limpiar(registros),
        "temp_actual":   limpiar(temp_actual),
        "humedad_actual": limpiar(humedad_actual),
        "rango_15d": rango_15d,
        "riesgo_climatico": riesgo,
        "ena_stats": {
            "media":      limpiar(temp_media_prom),
            "min":        limpiar(temp_min_prom),
            "max":        limpiar(temp_max_prom),
            "min_abs":    limpiar(temp_min_abs),
            "max_abs":    limpiar(temp_max_abs),
            "humedad":    limpiar(humedad_prom),
            "precip":     limpiar(precip_prom),
            "precip_max": limpiar(precip_max),
        },
        "top_cultivos":   cultivos_res,
        "top_distrito":   cultivos_res[0] if cultivos_res else "N/A",
        "top_region":     region,
        "recomendacion_principal": (
            f"Según el historial climático de {distrito}, "
            f"se recomienda priorizar el cultivo {cultivos_res[0]}."
        ),
        "detalles_cultivos": detalles,
        # 🌿 NUEVO CAMPO: alertas fitosanitarias
        "alertas_fitosanitarias": alertas_fitosanitarias
    }


# =========================================================
# ENDPOINT: /ubicacion-gps
# Recibe lat/lon del celular y devuelve el distrito más cercano
# =========================================================
class CoordsGPS(BaseModel):
    lat: float
    lon: float

@app.post("/ubicacion-gps")
def ubicacion_por_gps(coords: CoordsGPS):
    validar_datos()

    if "LATITUD" not in caratula_df.columns or "LONGITUD" not in caratula_df.columns:
        raise HTTPException(
            status_code=400,
            detail="El archivo CARATULA.xlsx no tiene columnas LATITUD/LONGITUD."
        )

    df = caratula_df[["NOMBREDD","NOMBREPV","NOMBREDI","LATITUD","LONGITUD"]].dropna().drop_duplicates().copy()

    if df.empty:
        raise HTTPException(status_code=404, detail="No hay coordenadas disponibles.")

    df["distancia"] = ((df["LATITUD"] - coords.lat)**2 + (df["LONGITUD"] - coords.lon)**2)**0.5
    fila = df.loc[df["distancia"].idxmin()]

    logger.info(f"GPS ({coords.lat},{coords.lon}) -> {fila['NOMBREDI']} / {fila['NOMBREPV']} / {fila['NOMBREDD']}")

    return {
        "region":       fila["NOMBREDD"],
        "provincia":    fila["NOMBREPV"],
        "distrito":     fila["NOMBREDI"],
        "lat":          round(float(fila["LATITUD"]), 4),
        "lon":          round(float(fila["LONGITUD"]), 4),
        "distancia_km": round(float(fila["distancia"]) * 111, 2)
    }

# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
