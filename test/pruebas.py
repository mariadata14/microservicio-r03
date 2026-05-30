import os
import pandas as pd
import unicodedata

# =====================================================
# PATHS
# =====================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# =====================================================
# LIMPIEZA
# =====================================================
def limpiar_texto(valor):

    if pd.isna(valor):
        return None

    valor = str(valor).strip().upper()

    # quitar tildes
    valor = unicodedata.normalize("NFKD", valor)
    valor = valor.encode("ascii", "ignore").decode("utf-8")

    # quitar ?
    valor = valor.replace("?", "")

    # espacios
    valor = " ".join(valor.split())

    return valor

# =====================================================
# FUNCION
# =====================================================
def ver_departamentos():

    # =================================================
    # CLIMA
    # =================================================
    clima_path = os.path.join(
        DATA_DIR,
        "clima_historico",
        "historico_clima_2024.xlsx"
    )

    clima_df = pd.read_excel(clima_path)

    clima_df.columns = clima_df.columns.str.strip().str.upper()

    clima_df.rename(columns={
        "DEPARTAMENTO": "NOMBREDD"
    }, inplace=True)

    clima_df["NOMBREDD"] = (
        clima_df["NOMBREDD"]
        .apply(limpiar_texto)
    )

    # =================================================
    # UBICACIONES
    # =================================================
    ubi_path = os.path.join(
        DATA_DIR,
        "ubi_historico",
        "CARATULA_2024.csv"
    )

    ubi_df = pd.read_csv(
        ubi_path,
        encoding="utf-8",
        low_memory=False
    )

    ubi_df.columns = ubi_df.columns.str.strip().str.upper()

    ubi_df.rename(columns={
        "DEPARTAMENTO": "NOMBREDD"
    }, inplace=True)

    ubi_df["NOMBREDD"] = (
        ubi_df["NOMBREDD"]
        .apply(limpiar_texto)
    )

    # =================================================
    # CULTIVOS
    # =================================================
    agro_path = os.path.join(
        DATA_DIR,
        "agro_historico",
        "2024",
        "03_CAP200AB.csv"
    )

    agro_df = pd.read_csv(
        agro_path,
        encoding="latin1",
        low_memory=False
    )

    agro_df.columns = agro_df.columns.str.strip().str.upper()

    agro_df["NOMBREDD"] = (
        agro_df["NOMBREDD"]
        .apply(limpiar_texto)
    )

    # =================================================
    # MOSTRAR
    # =================================================
    print("\n========== CLIMA ==========")
    print(
        sorted(
            clima_df["NOMBREDD"]
            .dropna()
            .unique()
            .tolist()
        )
    )

    print("\n========== UBICACIONES ==========")
    print(
        sorted(
            ubi_df["NOMBREDD"]
            .dropna()
            .unique()
            .tolist()
        )
    )

    print("\n========== CULTIVOS ==========")
    print(
        sorted(
            agro_df["NOMBREDD"]
            .dropna()
            .unique()
            .tolist()
        )
    )

# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    ver_departamentos()