from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, Any
import os

app = FastAPI()

# Configuración de CORS: Permite que el navegador desde Oracle APEX pueda consultar tu API en Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite conexiones desde cualquier origen para propósitos del taller
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conexión a la base de datos distribuida de la universidad
# Usamos os.getenv para leer las credenciales seguras configuradas en Render
MONGO_URI = os.getenv("MONGO_URI", "mongodb://157.253.236.88:8087")
DATABASE_NAME = "ParranderosNoSQL"  # Asegúrate de que coincida con el nombre que ves en Compass

try:
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
except Exception as e:
    print(f"Error crítico al conectar a MongoDB: {e}")


# =====================================================================
# REQUERIMIENTO 1: ENDPOINTS DE COMENTARIOS
# =====================================================================

@app.get("/bares/{bar_id}/comentarios")
def get_comentarios(bar_id: int):
    """
    Punto 6 del taller: Retorna todos los comentarios asociados a un bar específico.
    Colección: comentarios_bares. Filtro: bar_id.
    """
    try:
        # Consultamos en MongoDB usando un filtro de diccionario: {"bar_id": bar_id}
        cursor = db.comentarios_bares.find({"bar_id": bar_id})
        
        # El cursor es un iterador; lo transformamos en una lista de diccionarios Python
        comentarios = list(cursor)
        
        # Transformación obligatoria del ObjectId a string para evitar errores con JSON
        for comentario in comentarios:
            comentario["_id"] = str(comentario["_id"])
            
        return comentarios
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bares/{bar_id}/comentarios")
def post_comentario(bar_id: int, datos: Dict[str, Any]):
    """
    Punto 7 del taller: Inserta un nuevo comentario recibido desde APEX.
    Nota del taller: El enunciado indica que bar_id y la fecha ya vienen agregados
    en el objeto 'datos' por el código base antes del TODO.
    """
    try:
        # Por seguridad, si tu plantilla base no los inyectaba automáticamente,
        # nos aseguramos de que existan bajo la estructura del esquema de tu compañero:
        datos["bar_id"] = bar_id
        if "date" not in datos or not datos["date"]:
            datos["date"] = datetime.utcnow().strftime("%Y-%m-%d") # Formato "YYYY-MM-DD" como el de Samuel
            
        # Insertamos el documento directamente en la colección 'comentarios_bares'
        resultado = db.comentarios_bares.insert_one(datos)
        
        # Retornamos una respuesta de éxito con el ID asignado por MongoDB
        return {"status": "success", "inserted_id": str(resultado.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# REQUERIMIENTO 2: ENDPOINTS DE EVENTOS (ESTRUCTURA VARIABLE)
# =====================================================================

@app.get("/bares/{bar_id}/eventos")
def get_eventos(bar_id: int):
    """
    Punto 8 del taller: Retorna todos los eventos programados para el bar seleccionado.
    Colección: eventos.
    """
    try:
        # Buscamos en la colección 'eventos' usando el parámetro de la URL
        cursor = db.eventos.find({"bar_id": bar_id})
        eventos = list(cursor)
        
        # Limpieza y conversión de IDs
        for evento in eventos:
            evento["_id"] = str(evento["_id"])
            
        return eventos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bares/{bar_id}/eventos")
def post_evento(bar_id: int, evento: Dict[str, Any]):
    """
    Punto 9 del taller: Recibe un evento con estructura variable, le agrega obligatoriamente
    el bar_id y la fecha_creacion, y lo almacena.
    """
    try:
        # Inyectamos los campos estructurales fijos exigidos por el enunciado y el diseño
        evento["bar_id"] = bar_id
        evento["fecha_creacion"] = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Al ser un diccionario de Python de tipo flexible (Dict[str, Any]), MongoDB guardará
        # exactamente los campos que el usuario llenó en APEX sin importar su tipo (concierto, happy hour, etc.)
        resultado = db.eventos.insert_one(evento)
        
        return {"status": "success", "inserted_id": str(resultado.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
