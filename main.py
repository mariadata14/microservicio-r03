import os
import pandas as pd
import uvicorn
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- CONFIGURACIÓN DE RUTAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Solo estas regiones tienen coordenadas
REGIONES_VALIDAS = ["LAMBAYEQUE", "LA LIBERTAD", "ICA", "CUSCO", "PUNO", "CAJAMARCA", "LIMA"]

COORDENADAS = {
    "LAMBAYEQUE": {"lat": -6.7, "lon": -79.9},
    "LA LIBERTAD": {"lat": -8.1, "lon": -79.0},
    "ICA": {"lat": -14.0, "lon": -75.7},
    "CUSCO": {"lat": -13.5, "lon": -71.9},
    "PUNO": {"lat": -15.8, "lon": -70.0},
    "CAJAMARCA": {"lat": -7.1, "lon": -78.5},
    "LIMA": {"lat": -12.0, "lon": -77.0}
}

def cargar_datos():
    try:
        # 1. Cargar Excels
        clima_path = os.path.join(DATA_DIR, "DATOS CLIMATOLOGICOS 2024.xlsx")
        caratula_path = os.path.join(DATA_DIR, "CARATULA.xlsx")
        
        c_df = pd.read_excel(clima_path)
        car_df = pd.read_excel(caratula_path)

        # 2. Limpieza Extrema de Columnas
        c_df.columns = c_df.columns.str.strip().str.upper()
        car_df.columns = car_df.columns.str.strip().str.upper()

        renames = {'DEPARTAMENTO': 'NOMBREDD', 'PROVINCIA': 'NOMBREPV', 'DISTRITO': 'NOMBREDI'}
        c_df = c_df.rename(columns=renames)
        car_df = car_df.rename(columns=renames)

        # 3. Limpieza de Contenido (Quitar espacios en blanco dentro de las celdas)
        for col in ['NOMBREDD', 'NOMBREPV', 'NOMBREDI']:
            if col in c_df.columns: c_df[col] = c_df[col].astype(str).str.strip().str.upper()
            if col in car_df.columns: car_df[col] = car_df[col].astype(str).str.strip().str.upper()

        print("✅ Datos normalizados y listos.")
        return c_df, car_df
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

clima_df, caratula_df = cargar_datos()

class Consulta(BaseModel):
    region: str
    provincia: str
    distrito: str

@app.get("/ubicaciones")
def get_ubicaciones():
    if caratula_df is None: return {}
    # Solo mostrar regiones con coordenadas
    df_filtrado = caratula_df[caratula_df['NOMBREDD'].isin(REGIONES_VALIDAS)]
    tree = {}
    df_mini = df_filtrado[['NOMBREDD', 'NOMBREPV', 'NOMBREDI']].drop_duplicates()
    for _, row in df_mini.iterrows():
        r, p, d = row['NOMBREDD'], row['NOMBREPV'], row['NOMBREDI']
        if r not in tree: tree[r] = {}
        if p not in tree[r]: tree[r][p] = []
        tree[r][p].append(d)
    return tree

@app.post("/consulta")
def post_consulta(req: Consulta):
    # Normalizar entrada del usuario para asegurar match
    d_user = req.distrito.strip().upper()
    r_user = req.region.strip().upper()
    
    # Filtrar
    dist_data = clima_df[clima_df['NOMBREDI'] == d_user]
    
    # Si por alguna razón el distrito no hace match, intentamos por provincia como respaldo
    if dist_data.empty:
        dist_data = clima_df[clima_df['NOMBREPV'] == req.provincia.strip().upper()]

    # Estadísticas
    registros = len(dist_data)
    media_h = round(dist_data['TEMPERATURA MEDIA'].mean(), 1) if not dist_data.empty else 0
    min_h = round(dist_data['TEMPERATURA MINIMA'].min(), 1) if not dist_data.empty else 0
    max_h = round(dist_data['TEMPERATURA MAXIMA'].max(), 1) if not dist_data.empty else 0
    precip_h = round(dist_data['PRECIPITACIÓN TOTAL'].mean(), 1) if not dist_data.empty else 0

    # Cultivos (Buscando la columna correcta)
    # Intenta buscar P204_NOM o NOM_CULTIVO o cualquier columna que mencione cultivo
    posibles_cols = [c for c in clima_df.columns if 'P204' in c or 'CULTIVO' in c]
    col_cultivo = posibles_cols[0] if posibles_cols else None
    
    cultivos_res = []
    if col_cultivo and not dist_data.empty:
        cultivos_res = dist_data[col_cultivo].value_counts().head(3).index.tolist()
    
    if not cultivos_res:
        cultivos_res = ["MAIZ AMILACEO", "PAPA", "ALFALFA"] # Default si el Excel está vacío

    # Clima Real
    geo = COORDENADAS.get(r_user, {"lat": -12.0, "lon": -77.0})
    temp_tr, hum_tr, r15 = 20.0, 65, "10° / 25°"
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={geo['lat']}&longitude={geo['lon']}&current=temperature_2m,relative_humidity_2m&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
        r = requests.get(url, timeout=5).json()
        temp_tr = r['current']['temperature_2m']
        hum_tr = r['current']['relative_humidity_2m']
        r15 = f"{min(r['daily']['temperature_2m_min'])}° / {max(r['daily']['temperature_2m_max'])}°"
    except: pass

    detalles = [{"nombre": f"{i+1}. {c}", "msg": "Época de siembra" if temp_tr > 15 else "Protección contra heladas"} for i, c in enumerate(cultivos_res)]

    return {
        "region": r_user,
        "provincia": req.provincia.upper(),
        "distrito": d_user,
        "registros_ena": registros,
        "temp_actual": temp_tr,
        "humedad": hum_tr,
        "rango_15d": r15,
        "ena_stats": {"media": media_h, "min": min_h, "max": max_h, "precip": precip_h},
        "top_distrito": ", ".join(cultivos_res),
        "top_region": ", ".join(cultivos_res),
        "recomendacion_principal": f"Con {temp_tr}°C, te sugerimos priorizar {cultivos_res[0]}.",
        "detalles_cultivos": detalles
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)