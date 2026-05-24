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
clima_df = None
cultivos_df = None
ubicacion_df = None

# =========================================================
# HELPERS
# =========================================================
def normalizar_texto(df, columnas):
    """
    Limpia textos:
    - mayúsculas
    - sin espacios
    - sin tildes
    """
    for col in columnas:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.upper()
                .str.replace("Ñ", "ENIE_TEMP", regex=False)
                .str.normalize("NFKD")
                .str.encode("ascii", errors="ignore")
                .str.decode("utf-8")
                .str.replace("ENIE_TEMP", "Ñ", regex=False)
            )
    return df


def convertir_numerico(df, columnas):
    for col in columnas:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", ".", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def limpiar(val):
    import numpy as np
    import math

    # numpy integer
    if isinstance(val, (np.integer,)):
        return int(val)

    # numpy float
    if isinstance(val, (np.floating,)):
        val = float(val)

    # float normal
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return 0
        return round(val, 2)

    # boolean
    if isinstance(val, (np.bool_,)):
        return bool(val)

    # null pandas
    if pd.isna(val):
        return 0

    return val

# =========================================================
# CARGA DE DATOS HISTÓRICOS
# =========================================================
def cargar_datos():
    try:
        # =====================================================
        # UBICACIONES HISTÓRICAS (LAT/LON)
        # =====================================================
        ubicacion_path = os.path.join(DATA_DIR,"ubi_historico","CARATULA_2024.csv")
        ubicacion_df = pd.read_csv(ubicacion_path,encoding="utf-8",low_memory=False)
        ubicacion_df.columns = (ubicacion_df.columns.str.strip().str.upper())

        # Renombrar
        ubicacion_df.rename(columns={
            "DEPARTAMENTO": "NOMBREDD",
            "PROVINCIA": "NOMBREPV",
            "DISTRITO": "NOMBREDI"
        }, inplace=True)

        # Normalizar texto
        ubicacion_df = normalizar_texto(ubicacion_df,
            ["NOMBREDD", "NOMBREPV", "NOMBREDI"]
        )

        # Coordenadas numéricas
        ubicacion_df = convertir_numerico(ubicacion_df,
            ["LATITUD", "LONGITUD"]
        )

        logger.info(f"✅ Ubicaciones cargadas: {len(ubicacion_df)} registros")

        # =====================================================
        # CLIMA HISTÓRICO
        # =====================================================
        clima_archivos = [
            "historico_clima_2021.xlsx",
            "historico_clima_2022.xlsx",
            "historico_clima_2023.xlsx",
            "historico_clima_2024.xlsx",
        ]
        lista_clima = []
        for archivo in clima_archivos:
            path = os.path.join(DATA_DIR, "clima_historico", archivo)
            if not os.path.exists(path):
                logger.warning(f"⚠️ No existe: {path}")
                continue
            df = pd.read_excel(path)
            df.columns = df.columns.str.strip().str.upper()
            # Renombrar clima
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

            df = normalizar_texto(df,["NOMBREDD", "NOMBREPV", "NOMBREDI"])
            df = convertir_numerico(df,["TEMP_MEDIA_PROM","TEMP_MAX_PROM","TEMP_MIN_PROM",
                                        "HUMEDAD_PROM","PRECIP_TOTAL"])
            lista_clima.append(df)

        clima_df = pd.concat(lista_clima, ignore_index=True)
        logger.info(f"✅ Clima histórico cargado: {len(clima_df)} registros")

        # =====================================================
        # CULTIVOS HISTÓRICOS
        # =====================================================
        archivos_agro = [
            # 2021
            {
                "anio": 2021,
                "archivo": os.path.join(
                    DATA_DIR,
                    "agro_historico",
                    "2021",
                    "02_Cap200ab.csv"
                )
            },

            # 2022
            {
                "anio": 2022,
                "archivo": os.path.join(
                    DATA_DIR,
                    "agro_historico",
                    "2022",
                    "02_Cap200ab.csv"
                )
            },

            # 2023
            {
                "anio": 2023,
                "archivo": os.path.join(
                    DATA_DIR,
                    "agro_historico",
                    "2023",
                    "03_CAP200AB.csv"
                )
            },

            # 2024
            {
                "anio": 2024,
                "archivo": os.path.join(
                    DATA_DIR,
                    "agro_historico",
                    "2024",
                    "03_CAP200AB.csv"
                )
            }
        ]

        lista_cultivos = []

        columnas_principales = [
            "ANIO",

            "CCDD",
            "NOMBREDD",

            "CCPP",
            "NOMBREPV",

            "CCDI",
            "NOMBREDI",

            "REGION",

            "P204_COD",
            "P204_NOM",

            "P217_SUP_HA",

            "P219_CANT_1",

            "P219_UM",

            "P220_1_PRE_KG",

            "P220_1_VAL"
        ]

        for item in archivos_agro:
            archivo = item["archivo"]
            anio = item["anio"]

            if not os.path.exists(archivo):
                logger.warning(f"⚠️ No existe: {archivo}")
                continue
            logger.info(f"📂 Cargando ENA {anio}")

            try:
                df = pd.read_csv(
                    archivo,
                    encoding="latin1",
                    low_memory=False
                )

            except:
                df = pd.read_csv(
                    archivo,
                    encoding="utf-8",
                    low_memory=False
                )
            df.columns = df.columns.str.strip().str.upper()

            # =================================================
            # FIX VARIABLES
            # =================================================
            # algunos años tienen SUP_ha
            if "P217_SUP_ha".upper() in df.columns:
                df.rename(columns={
                    "P217_SUP_ha".upper(): "P217_SUP_HA"
                }, inplace=True)

            # =================================================
            # CREAR COLUMNAS FALTANTES
            # =================================================
            for col in columnas_principales:
                if col not in df.columns:
                    df[col] = None

            # =================================================
            # SOLO VARIABLES NECESARIAS
            # =================================================
            df = df[columnas_principales]

            # =================================================
            # NORMALIZAR TEXTO
            # =================================================
            df = normalizar_texto(df,["NOMBREDD","NOMBREPV",
                                      "NOMBREDI","P204_NOM"])

            # =================================================
            # NUMÉRICOS
            # =================================================
            df = convertir_numerico(df,["P217_SUP_HA","P219_CANT_1",
                                        "P220_1_PRE_KG","P220_1_VAL"])

            # =================================================
            # VARIABLES DERIVADAS
            # =================================================

            # Rendimiento
            # Evitar divisiones por cero
            sup_segura = df["P217_SUP_HA"].replace(0, pd.NA)

            # Rendimiento por hectárea
            df["RENDIMIENTO_HA"] = (df["P219_CANT_1"] / sup_segura)

            # Valor económico por hectárea
            df["VALOR_X_HA"] = (df["P220_1_VAL"] / sup_segura)

            # Limpiar infinitos y NaN
            df["RENDIMIENTO_HA"] = (df["RENDIMIENTO_HA"]
                                    .replace([float("inf"), -float("inf")], 0).fillna(0))

            df["VALOR_X_HA"] = (df["VALOR_X_HA"]
                                .replace([float("inf"), -float("inf")], 0).fillna(0))

            lista_cultivos.append(df)

        cultivos_df = pd.concat(lista_cultivos, ignore_index=True)
        logger.info(f"✅ Agro histórico cargado: {len(cultivos_df)} registros")
        return clima_df, cultivos_df, ubicacion_df

    except Exception as e:
        logger.error(f"❌ ERROR CARGANDO DATOS: {e}")
        return None, None, None

# =========================================================
# STARTUP
# =========================================================
@app.on_event("startup")
async def startup():
    global clima_df
    global cultivos_df
    global ubicacion_df
    clima_df, cultivos_df, ubicacion_df = cargar_datos()

# =========================================================
# VALIDAR
# =========================================================
def validar_datos():
    if (clima_df is None or cultivos_df is None or ubicacion_df is None):
        raise HTTPException(
            status_code=500,
            detail="Error cargando datos históricos"
        )

# =========================================================
# MODELO
# =========================================================
class Consulta(BaseModel):
    region: str
    provincia: str
    distrito: str

# =========================================================
# RIESGO CLIMÁTICO
# =========================================================
def calcular_riesgo(
    temp_min_prom,
    temp_min_abs,
    temp_max_prom,
    precip_max,
    temp_actual
):

    # HELADA ACTUAL O HISTÓRICA
    if temp_actual <= 4 or temp_min_abs <= 4:
        return "HELADA"

    # FRÍO HISTÓRICO DEL DISTRITO
    elif temp_min_prom <= 8:
        return "FRÍO INTENSO"

    # CALOR EXTREMO
    elif temp_max_prom >= 35:
        return "CALOR EXTREMO"

    # EXCESO DE LLUVIA
    elif precip_max >= 150:
        return "EXCESO LLUVIA"

    else:
        return "NORMAL"

# =========================================================
# RIESGO FITOSANITARIO
# =========================================================
def calcular_riesgo_fitosanitario(
    humedad_actual: float,
    temp_actual: float,
    precip_prom: float
) -> list:

    alertas = []

    # =====================================================
    # HONGOS
    # =====================================================
    if humedad_actual >= 85 and 15 <= temp_actual <= 28:
        alertas.append({
            "nivel": "ALTO",
            "icono": "🍄",
            "tipo": "Hongos foliares",
            "condicion": "HUMEDAD EXTREMA",
            "mensaje": "Condiciones ideales para roya y mildiu."
        })

    elif humedad_actual >= 70 and 15 <= temp_actual <= 28:
        alertas.append({
            "nivel": "MODERADO",
            "icono": "🍄",
            "tipo": "Hongos foliares",
            "condicion": "HUMEDAD ELEVADA",
            "mensaje": "Humedad elevada favorece hongos."
        })

    # =====================================================
    # ÁCAROS
    # =====================================================
    if temp_actual >= 28 and humedad_actual < 50:
        alertas.append({
            "nivel": "ALTO",
            "icono": "🕷️",
            "tipo": "Ácaros / Trips",
            "condicion": "CALOR SECO",
            "mensaje": "Calor seco favorece insectos."
        })

    # =====================================================
    # LARVAS
    # =====================================================
    if humedad_actual >= 80 and temp_actual >= 22 and precip_prom >= 50:
        alertas.append({
            "nivel": "MODERADO",
            "icono": "🐛",
            "tipo": "Larvas de suelo",
            "condicion": "SUELO HÚMEDO",
            "mensaje": "Lluvias y humedad favorecen larvas."
        })

    # =====================================================
    # BACTERIAS
    # =====================================================
    if temp_actual >= 30 and humedad_actual >= 75:
        alertas.append({
            "nivel": "ALTO",
            "icono": "🦠",
            "tipo": "Bacterias",
            "condicion": "CALOR + HUMEDAD",
            "mensaje": "Calor y humedad favorecen bacterias."
        })

    # =====================================================
    # HELADA
    # =====================================================
    if temp_actual <= 4:
        alertas.append({
            "nivel": "CRÍTICO",
            "icono": "🧊",
            "tipo": "Helada",
            "condicion": "TEMPERATURA CRÍTICA",
            "mensaje": "Riesgo de daño por helada."
        })

    # =====================================================
    # SIN RIESGOS
    # =====================================================
    if not alertas:
        alertas.append({
            "nivel": "BAJO",
            "icono": "✅",
            "tipo": "Sin riesgos",
            "condicion": "CLIMA ESTABLE",
            "mensaje": "No se detectaron riesgos."
        })

    return alertas

# =========================================================
# ENDPOINT UBICACIONES
# =========================================================
@app.get("/ubicaciones")
def get_ubicaciones():
    validar_datos()
    tree = {}
    df_mini = (
        cultivos_df[
            ["NOMBREDD", "NOMBREPV", "NOMBREDI"]
        ]
        .fillna("SIN_DATO")
        .drop_duplicates()
    )

    for _, row in df_mini.iterrows():
        region = str(row["NOMBREDD"])
        provincia = str(row["NOMBREPV"])
        distrito = str(row["NOMBREDI"])

        if region not in tree:
            tree[region] = {}
        if provincia not in tree[region]:
            tree[region][provincia] = []

        if distrito not in tree[region][provincia]:
            tree[region][provincia].append(distrito)
    return tree

# =========================================================
# ENDPOINT CONSULTA
# =========================================================
@app.post("/consulta")
def post_consulta(req: Consulta):
    validar_datos()
    region = req.region.strip().upper()
    provincia = req.provincia.strip().upper()
    distrito = req.distrito.strip().upper()

    # =====================================================
    # FILTRAR
    # =====================================================
    def filtrar(df):
        return df[
            (df["NOMBREDD"] == region) &
            (df["NOMBREPV"] == provincia) &
            (df["NOMBREDI"] == distrito)
        ]

    clima_f = filtrar(clima_df)
    cultivos_f = filtrar(cultivos_df)
    logger.info(
        f"Consulta: {region} / {provincia} / {distrito}"
    )

    # =====================================================
    # HELPERS
    # =====================================================
    def mean_col(df, col):
        if df.empty or col not in df.columns:
            return 0
        val = df[col].mean()

        if pd.isna(val):
            return 0
        return round(float(val), 2)


    def max_col(df, col):
        if df.empty or col not in df.columns:
            return 0
        val = df[col].max()
        if pd.isna(val):
            return 0
        return round(float(val), 2)

    def min_col(df, col):
        if df.empty or col not in df.columns:
            return 0
        val = df[col].min()
        if pd.isna(val):
            return 0
        return round(float(val), 2)

    # =====================================================
    # CLIMA HISTÓRICO
    # =====================================================
    temp_media_prom = mean_col(clima_f, "TEMP_MEDIA_PROM")
    temp_min_prom = mean_col(clima_f, "TEMP_MIN_PROM")
    temp_max_prom = mean_col(clima_f, "TEMP_MAX_PROM")

    temp_min_abs = min_col(clima_f, "TEMP_MIN_PROM")
    temp_max_abs = max_col(clima_f, "TEMP_MAX_PROM")

    humedad_prom = mean_col(clima_f, "HUMEDAD_PROM")

    precip_prom = mean_col(clima_f, "PRECIP_TOTAL")
    precip_max = max_col(clima_f, "PRECIP_TOTAL")

    # =====================================================
    # CULTIVOS PRINCIPALES
    # =====================================================
    cultivos_res = ["SIN DATOS"]
    if not cultivos_f.empty:
        top = (
            cultivos_f[
                cultivos_f["ANIO"].between(2021, 2024)
            ]["P204_NOM"]
            .dropna()
            .astype(str)
            .value_counts()
            .head(5)
            .index
            .tolist()
        )

        if top:
            cultivos_res = top

    # =====================================================
    # PRODUCCIÓN TOTAL
    # =====================================================
    produccion_total = limpiar(cultivos_f["P219_CANT_1"].sum())

    superficie_total = limpiar(cultivos_f["P217_SUP_HA"].sum())

    precio_promedio = limpiar(cultivos_f["P220_1_PRE_KG"].mean())

    rendimiento_promedio = limpiar(cultivos_f["RENDIMIENTO_HA"].mean())

    valor_total = limpiar(cultivos_f["P220_1_VAL"].sum())

    # =====================================================
    # TENDENCIA HISTÓRICA
    # =====================================================
    tendencia = []
    if not cultivos_f.empty:
        agrupado = (
            cultivos_f
            .groupby("ANIO")
            .agg({
                "P219_CANT_1": "sum",
                "P217_SUP_HA": "sum",
                "P220_1_VAL": "sum"
            })
            .reset_index()
        )

        for _, row in agrupado.iterrows():
            tendencia.append({
                "anio":
                    limpiar(row["ANIO"]),
                "produccion":
                    limpiar(round(row["P219_CANT_1"], 2)),
                "superficie":
                    limpiar(round(row["P217_SUP_HA"], 2)),
                "valor":
                    limpiar(round(row["P220_1_VAL"], 2))
            })

    # =====================================================
    # OPEN METEO
    # =====================================================
    temp_actual = 0
    humedad_actual = 0
    riesgo = "NORMAL"
    rango_15d = "No disponible"

    # =====================================================
    # COORDENADAS REALES DEL DISTRITO
    # =====================================================
    lat = -12.0464
    lon = -77.0428

    ubicacion_f = ubicacion_df[
        (ubicacion_df["NOMBREDD"] == region) &
        (ubicacion_df["NOMBREPV"] == provincia) &
        (ubicacion_df["NOMBREDI"] == distrito)
    ]

    if not ubicacion_f.empty:

        lat_tmp = ubicacion_f["LATITUD"].mean()
        lon_tmp = ubicacion_f["LONGITUD"].mean()

        if pd.notna(lat_tmp):
            lat = round(float(lat_tmp), 4)

        if pd.notna(lon_tmp):
            lon = round(float(lon_tmp), 4)

    logger.info(f"📍 Coordenadas: {lat}, {lon}")

    try:

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m"
            f"&daily=temperature_2m_max,temperature_2m_min"
            f"&timezone=auto"
        )

        r = requests.get(url, timeout=5)

        if r.status_code == 200:

            response = r.json()

            temp_actual = response.get("current", {}).get("temperature_2m", 0)

            humedad_actual = response.get("current", {}).get("relative_humidity_2m", 0)

            temp_min_15d = min(
                response.get("daily", {}).get("temperature_2m_min", [0])
            )

            temp_max_15d = max(
                response.get("daily", {}).get("temperature_2m_max", [0])
            )

            rango_15d = f"{temp_min_15d}° / {temp_max_15d}°"

        else:
            logger.warning(
                f"⚠️ Open Meteo respondió: {r.status_code}"
            )

    except Exception as e:
        logger.warning(f"⚠️ Error Open Meteo: {e}")

    # =====================================================
    # RIESGO
    # =====================================================
    riesgo = calcular_riesgo(
        temp_min_prom,
        temp_min_abs,
        temp_max_prom,
        precip_max,
        temp_actual
    )

    # =====================================================
    # RIESGO FITOSANITARIO
    # =====================================================
    alertas_fitosanitarias = calcular_riesgo_fitosanitario(
        humedad_actual,temp_actual,precip_prom)


    # =====================================================
    # TOP CULTIVOS REGIÓN
    # =====================================================
    cultivos_region = cultivos_df[
        cultivos_df["NOMBREDD"] == region
    ]

    top_region = (
        cultivos_region["P204_NOM"]
        .dropna()
        .astype(str)
        .value_counts()
        .head(5)
        .index
        .tolist()
    )


    # =====================================================
    # RESPUESTA
    # =====================================================
    return {
        "region": region,
        "provincia": provincia,
        "distrito": distrito,

        "registros_ena":
            limpiar(len(cultivos_f)),

        # =================================================
        # CLIMA
        # =================================================
        "clima": {

            "temp_media_prom":
                limpiar(temp_media_prom),

            "temp_min_prom":
                limpiar(temp_min_prom),

            "temp_max_prom":
                limpiar(temp_max_prom),

            "humedad_prom":
                limpiar(humedad_prom),

            "precip_prom":
                limpiar(precip_prom),

            "temp_actual":
                limpiar(temp_actual),

            "humedad_actual":
                limpiar(humedad_actual),

            "rango_15d":
                rango_15d
        },

        # =================================================
        # AGRICULTURA
        # =================================================
        "agricultura": {
            
            "top_region":
                top_region,

            "top_cultivos":
                cultivos_res,

            "produccion_total":
                limpiar(produccion_total),

            "superficie_total":
                limpiar(superficie_total),

            "precio_promedio":
                limpiar(precio_promedio),

            "rendimiento_promedio":
                limpiar(rendimiento_promedio),

            "valor_total":
                limpiar(valor_total)
        },

        # =================================================
        # TENDENCIA
        # =================================================
        "tendencia_historica":
            tendencia,

        # =================================================
        # RIESGOS
        # =================================================
        "riesgo_climatico":
            riesgo,

        "alertas_fitosanitarias":
            alertas_fitosanitarias,

        # =================================================
        # RECOMENDACIÓN
        # =================================================
        "recomendacion_principal":
            (
                f"Según el análisis histórico de "
                f"{distrito}, el cultivo más frecuente es "
                f"{cultivos_res[0]}"
            )
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

    if "LATITUD" not in ubicacion_df.columns or "LONGITUD" not in ubicacion_df.columns:
        raise HTTPException(
            status_code=400,
            detail="El archivo CARATULA.xlsx no tiene columnas LATITUD/LONGITUD."
        )

    df = ubicacion_df[["NOMBREDD","NOMBREPV","NOMBREDI","LATITUD","LONGITUD"]].dropna().drop_duplicates().copy()

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
    uvicorn.run(app,host="127.0.0.1",port=8000)