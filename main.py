import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Note

app = FastAPI(title="Papyrus Notes API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NoteCreate(Note):
    pass

class NoteOut(Note):
    id: str

@app.get("/")
def read_root():
    return {"message": "Papyrus Notes Backend is running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected"
            response["collections"] = db.list_collection_names()
        else:
            response["database"] = "❌ Not Connected"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:120]}"
    return response

# Helper to convert Mongo docs

def serialize_note(doc) -> NoteOut:
    return NoteOut(
        id=str(doc.get("_id")),
        title=doc.get("title", ""),
        content=doc.get("content", ""),
        tags=doc.get("tags", []),
        color=doc.get("color"),
        is_pinned=doc.get("is_pinned", False),
        mood=doc.get("mood"),
    )

@app.post("/api/notes", response_model=dict)
async def create_note(note: NoteCreate):
    try:
        note_id = create_document("note", note)
        return {"id": note_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notes", response_model=List[NoteOut])
async def list_notes(tag: Optional[str] = None, q: Optional[str] = None, pinned: Optional[bool] = None):
    try:
        filter_dict = {}
        if tag:
            filter_dict["tags"] = {"$in": [tag]}
        if pinned is not None:
            filter_dict["is_pinned"] = pinned
        if q:
            filter_dict["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"content": {"$regex": q, "$options": "i"}},
            ]
        docs = get_documents("note", filter_dict)
        # Sort pinned first then newest
        docs.sort(key=lambda d: (not d.get("is_pinned", False), d.get("created_at", 0)), reverse=False)
        return [serialize_note(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/notes/{note_id}", response_model=dict)
async def delete_note(note_id: str):
    try:
        if db is None:
            raise Exception("Database not available")
        result = db["note"].delete_one({"_id": ObjectId(note_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/notes/{note_id}", response_model=dict)
async def update_note(note_id: str, payload: dict):
    try:
        if db is None:
            raise Exception("Database not available")
        payload.pop("_id", None)
        payload["updated_at"] = payload.get("updated_at")
        result = db["note"].update_one({"_id": ObjectId(note_id)}, {"$set": payload})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
