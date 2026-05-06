# 🌱 AgroClima Perú — Sistema Predictivo ENA 2024

Sistema inteligente de consulta agroclimática que integra datos reales de la **Encuesta Nacional Agropecuaria (ENA 2024)** con el clima en tiempo real mediante la API de **Open-Meteo**. Proyecto desarrollado para el análisis y optimización de cultivos en diversas regiones del Perú.

## 🚀 Características
- **Datos Reales:** Basado en los módulos del INEI/MIDAGRI (2024).
- **Clima TR:** Consulta de temperatura y humedad en tiempo real por geolocalización regional.
- **Análisis Predictivo:** Sugerencias de cultivos basadas en el historial climatológico del distrito seleccionado.
- **Interfaz Moderna:** Dashboard dinámico diseñado para facilitar la lectura técnica.

## 🛠️ Tecnologías Utilizadas
* **Backend:** Python 3.9+ con [FastAPI](https://fastapi.tiangolo.com/).
* **Frontend:** HTML5, CSS3 ([Tailwind CSS](https://tailwindcss.com/)) y JavaScript Vanilla.
* **Procesamiento de Datos:** Pandas y Openpyxl para el manejo de Excels.
* **API Externa:** Open-Meteo para datos meteorológicos.

## 📂 Estructura del Proyecto
```text
PROYECTO_AGRO/
├── data/                   # Archivos Excel (ENA 2024)
├── main.py                 # Servidor Backend (FastAPI)
├── index.html              # Interfaz de Usuario
├── requirements.txt        # Dependencias del proyecto
└── README.md               # Documentación

## 👥 Equipo de Desarrollo
Maria Serrano, Dapdne Gutiérrez, Benjamín Quispe y Diego Atoche.
