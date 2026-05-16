from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, Any
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URI = os.environ("MONGO_URI")
DATABASE_NAME = "ParranderosNoSQL" 

client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]


@app.get("/bares/{bar_id}/comentarios")
def get_comentarios(bar_id: int):
    try:
        cursor = db.comentarios_bares.find({"bar_id": bar_id})
        comentarios = list(cursor)

        for comentario in comentarios:
            comentario["_id"] = str(comentario["_id"])
            
        return comentarios
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bares/{bar_id}/comentarios")
def post_comentario(bar_id: int, datos: Dict[str, Any]):
    
    try:
        datos["bar_id"] = bar_id
        if "date" not in datos or not datos["date"]:
            datos["date"] = datetime.utcnow().strftime("%Y-%m-%d") 
        resultado = db.comentarios_bares.insert_one(datos)
        
        return {"status": "success", "inserted_id": str(resultado.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bares/{bar_id}/eventos")
def get_eventos(bar_id: int):
    
    try:
        cursor = db.eventos.find({"bar_id": bar_id})
        eventos = list(cursor)
        
        for evento in eventos:
            evento["_id"] = str(evento["_id"])
            
        return eventos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bares/{bar_id}/eventos")
def post_evento(bar_id: int, evento: Dict[str, Any]):
    
    try:
        evento["bar_id"] = bar_id
        evento["fecha_creacion"] = datetime.utcnow().strftime("%Y-%m-%d")
        
        resultado = db.eventos.insert_one(evento)
        
        return {"status": "success", "inserted_id": str(resultado.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
