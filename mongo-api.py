from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, Any, List
import os

app = FastAPI(
    title="Dann-Alpes NoSQL API Middleware",
    description="API en Render para conectar Oracle APEX con MongoDB Atlas de forma autónoma",
    version="1.0.0"
)

# CORS totalmente abierto para que los servidores de Oracle APEX le peguen a Render sin líos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Render va a leer esta variable de entorno desde su Dashboard
MONGO_URI = os.environ.get("MONGO_URI")
DATABASE_NAME = "DannAlpesMongo"

if not MONGO_URI:
    raise RuntimeError("CRÍTICO: La variable de entorno MONGO_URI no está configurada en Render.")

client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]

def serializar_docs(docs):
    """Transforma ObjectIds en strings y fechas en ISO strings para que APEX no muera parseando"""
    if isinstance(docs, list):
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            for key, val in doc.items():
                if isinstance(val, datetime):
                    doc[key] = val.isoformat()
    elif isinstance(docs, dict):
        if "_id" in docs:
            docs["_id"] = str(docs["_id"])
        for key, val in docs.items():
            if isinstance(val, datetime):
                docs[key] = val.isoformat()
    return docs

# ==========================================
# OPERACIONES DE LA INTERFAZ (Tus RFs)
# ==========================================

@app.get("/hoteles/{hotel_id}/reseñas")
def obtener_reseñas_por_hotel(hotel_id: int):
    """Extrae las reseñas publicadas de un hotel para pintarlas en un reporte de APEX"""
    try:
        cursor = db.reviews.find({"hotelId": hotel_id, "status": "publicada"}).sort("createdAt", -1)
        return serializar_docs(list(cursor))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reseñas")
def crear_reseña(datos: Dict[str, Any] = Body(...)):
    """Inserta una nueva reseña validando estrictamente los tipos del $jsonSchema de la entrega"""
    try:
        doc_reseña = {
            "reviewId": int(datos["reviewId"]),
            "hotelId": int(datos["hotelId"]),
            "hotelName": str(datos.get("hotelName", "Hotel Dann-Alpes")),
            "cityId": int(datos.get("cityId", 0)),
            "cityName": str(datos.get("cityName", "")),
            "clientId": int(datos["clientId"]),
            "reservationId": int(datos["reservationId"]),
            "rating": int(datos["rating"]),
            "text": str(datos["text"]),
            "status": str(datos.get("status", "publicada")),
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
            "helpfulCount": 0,
            "helpfulVotes": [],
            "adminResponse": None,
            "featured": False
        }
        resultado = db.reviews.insert_one(doc_reseña)
        return {"status": "success", "inserted_id": str(resultado.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fallo de validación NoSQL (revisa el esquema): {str(e)}")

@app.put("/reseñas/{review_id}/respuesta")
def agregar_respuesta_administrativa(review_id: int, datos: Dict[str, Any] = Body(...)):
    """Guarda la respuesta de la administración como un subdocumento embebido en la reseña"""
    try:
        respuesta = {
            "adminId": int(datos["adminId"]),
            "text": str(datos["text"]),
            "respondedAt": datetime.utcnow()
        }
        resultado = db.reviews.update_one(
            {"reviewId": review_id},
            {"$set": {"adminResponse": respuesta, "updatedAt": datetime.utcnow()}}
        )
        if resultado.matched_count == 0:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        return {"status": "success", "message": "Respuesta administrativa guardada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/reseñas/{review_id}/votar")
def agregar_voto_utilidad(review_id: int, datos: Dict[str, Any] = Body(...)):
    """Incrementa el contador e inserta el voto en el array si el usuario no ha votado antes"""
    try:
        user_id = int(datos["userId"])
        resultado = db.reviews.update_one(
            {"reviewId": review_id, "helpfulVotes.userId": {"$ne": user_id}},
            {
                "$push": {"helpfulVotes": {"userId": user_id, "votedAt": datetime.utcnow()}},
                "$inc": {"helpfulCount": 1},
                "$set": {"updatedAt": datetime.utcnow()}
            }
        )
        if resultado.modified_count == 0:
            return {"status": "ignored", "message": "Este usuario ya votó o la reseña no existe"}
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/reseñas/{review_id}/destacar")
def alternar_destacado(review_id: int, featured: bool = Body(embed=True)):
    """Modifica el flag booleano de reseñas destacadas de forma directa"""
    try:
        resultado = db.reviews.update_one(
            {"reviewId": review_id}, 
            {"$set": {"featured": featured, "updatedAt": datetime.utcnow()}}
        )
        if resultado.matched_count == 0:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        return {"status": "success", "featured": featured}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# REPORTES DE AGREGACIÓN (RFC1, RFC2, RFC3)
# ==========================================

@app.get("/reportes/rfc1")
def obtener_rfc1():
    """RFC1: Top 10 hoteles por calificación promedio durante el 2025"""
    try:
        pipeline = [
            { "$match": { "status": "publicada", "createdAt": { "$gte": datetime(2025, 1, 1), "$lte": datetime(2025, 12, 31, 23, 59, 59) } } },
            { "$group": { "_id": "$hotelId", "hotelName": { "$first": "$hotelName" }, "cityName": { "$first": "$cityName" }, "avgRating": { "$avg": "$rating" }, "totalReviews": { "$sum": 1 } } },
            { "$addFields": { "avgRating": { "$round": ["$avgRating", 2] } } },
            { "$sort": { "avgRating": -1, "totalReviews": -1 } },
            { "$limit": 10 },
            { "$project": { "_id": 0, "hotelId": "$_id", "hotelName": 1, "cityName": 1, "avgRating": 1, "totalReviews": 1 } }
        ]
        return serializar_docs(list(db.reviews.aggregate(pipeline)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reportes/rfc2/{hotel_id}")
def obtener_rfc2(hotel_id: int):
    """RFC2: Evolución mensual del promedio de un hotel específico durante el 2025"""
    try:
        pipeline = [
            { "$match": { "hotelId": hotel_id, "status": "publicada", "createdAt": { "$gte": datetime(2025, 1, 1), "$lte": datetime(2025, 12, 31, 23, 59, 59) } } },
            { "$group": { "_id": { "anio": { "$year": "$createdAt" }, "mes": { "$month": "$createdAt" } }, "avgRating": { "$avg": "$rating" }, "totalReviews": { "$sum": 1 } } },
            { "$addFields": { "avgRating": { "$round": ["$avgRating", 2] } } },
            { "$sort": { "_id.anio": 1, "_id.mes": 1 } },
            { "$project": { "_id": 0, "anio": "$_id.anio", "mes": "$_id.mes", "avgRating": 1, "totalReviews": 1 } }
        ]
        return serializar_docs(list(db.reviews.aggregate(pipeline)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reportes/rfc3")
def obtener_rfc3():
    """RFC3: Análisis comparativo complejo de hoteles en Cartagena usando analítica por ventanas"""
    try:
        pipeline = [
            { "$match": { "cityName": "Cartagena", "status": "publicada" } },
            { "$group": { "_id": "$hotelId", "hotelName": { "$first": "$hotelName" }, "cityName": { "$first": "$cityName" }, "avgRating": { "$avg": "$rating" }, "totalReviews": { "$sum": 1 }, "reviewsWithResponse": { "$sum": { "$cond": [{ "$and": [{ "$ifNull": ["$adminResponse", False] }, { "$ne": ["$adminResponse", None] }] }, 1, 0] } }, "reviewsFeatured": { "$sum": { "$cond": ["$featured", 1, 0] } } } },
            { "$addFields": { "avgRating": { "$round": ["$avgRating", 2] }, "pctConRespuesta": { "$round": [{ "$multiply": [{ "$divide": ["$reviewsWithResponse", "$totalReviews"] }, 100] }, 1] }, "pctDestacadas": { "$round": [{ "$multiply": [{ "$divide": ["$reviewsFeatured", "$totalReviews"] }, 100] }, 1] } } },
            { "$setWindowFields": { "partitionBy": "$cityName", "sortBy": { "avgRating": -1 }, "output": { "rankingCiudad": { "$rank": {} } } } },
            { "$project": { "_id": 0, "hotelId": "$_id", "hotelName": 1, "cityName": 1, "avgRating": 1, "totalReviews": 1, "pctConRespuesta": 1, "pctDestacadas": 1, "rankingCiudad": 1 } }
        ]
        return serializar_docs(list(db.reviews.aggregate(pipeline)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))