from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import numpy as np
import os
from datetime import datetime
import uvicorn
import math

app = FastAPI(title="Student Management System", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
INDEX_FILE = os.path.join(STATIC_DIR, "index.html")
EXCEL_FILE = os.path.join(BASE_DIR, "students.xlsx")

COLUMNS = [
    "id", "name", "roll_number", "email", "phone",
    "course", "semester", "gender", "date_of_birth",
    "address", "grade", "created_at"
]

class Student(BaseModel):
    name: str
    roll_number: str
    email: str
    phone: str
    course: str
    semester: str
    gender: str
    date_of_birth: str
    address: Optional[str] = ""
    grade: Optional[str] = ""

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    course: Optional[str] = None
    semester: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    grade: Optional[str] = None

def clean_value(val):
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        return None if math.isnan(float(val)) else float(val)
    if isinstance(val, np.bool_):
        return bool(val)
    return val

def df_to_records(df):
    return [{col: clean_value(row[col]) for col in df.columns} for _, row in df.iterrows()]

def init_excel():
    if not os.path.exists(EXCEL_FILE):
        pd.DataFrame(columns=COLUMNS).to_excel(EXCEL_FILE, index=False)
        return
    try:
        df = pd.read_excel(EXCEL_FILE)
        changed = False
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = None
                changed = True
        if changed:
            df.to_excel(EXCEL_FILE, index=False)
    except Exception:
        pd.DataFrame(columns=COLUMNS).to_excel(EXCEL_FILE, index=False)

def read_students():
    init_excel()
    df = pd.read_excel(EXCEL_FILE)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df

def save_students(df):
    df.to_excel(EXCEL_FILE, index=False)

def generate_id(df):
    if df.empty or df["id"].isnull().all():
        return 1
    return int(df["id"].dropna().max()) + 1

# Static files mount
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def root():
    if os.path.exists(INDEX_FILE):
        return FileResponse(INDEX_FILE)
    return HTMLResponse("<h1>API Running OK</h1>")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "static_dir": os.path.isdir(STATIC_DIR),
        "index_html": os.path.exists(INDEX_FILE),
        "excel": os.path.exists(EXCEL_FILE)
    }

@app.get("/api/students")
def get_all_students():
    return df_to_records(read_students())

@app.get("/api/students/{student_id}")
def get_student(student_id: int):
    df = read_students()
    row = df[df["id"] == student_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Student not found")
    return df_to_records(row)[0]

@app.post("/api/students", status_code=201)
def add_student(student: Student):
    df = read_students()
    if not df.empty and student.roll_number in df["roll_number"].astype(str).values:
        raise HTTPException(status_code=400, detail="Roll number already exists")
    new_id = generate_id(df)
    new_row = {
        "id": new_id, "name": student.name, "roll_number": student.roll_number,
        "email": student.email, "phone": student.phone, "course": student.course,
        "semester": student.semester, "gender": student.gender,
        "date_of_birth": student.date_of_birth, "address": student.address or "",
        "grade": student.grade or "",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_students(df)
    return {"message": "Student added successfully", "id": new_id, "student": new_row}

@app.put("/api/students/{student_id}")
def update_student(student_id: int, student: StudentUpdate):
    df = read_students()
    idx = df.index[df["id"] == student_id].tolist()
    if not idx:
        raise HTTPException(status_code=404, detail="Student not found")
    for key, value in student.dict(exclude_none=True).items():
        df.at[idx[0], key] = value
    save_students(df)
    return {"message": "Student updated successfully"}

@app.delete("/api/students/{student_id}")
def delete_student(student_id: int):
    df = read_students()
    if student_id not in df["id"].values:
        raise HTTPException(status_code=404, detail="Student not found")
    df = df[df["id"] != student_id].reset_index(drop=True)
    save_students(df)
    return {"message": "Student deleted successfully"}

@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    df = read_students()
    if df.empty:
        return {"total_students": 0, "courses": {}, "semesters": {}, "genders": {}, "grades": {}, "recent_students": []}
    def safe_counts(col):
        if col not in df.columns:
            return {}
        s = df[col].dropna().astype(str)
        s = s[s.str.strip() != ""]
        return {str(k): int(v) for k, v in s.value_counts().items()}
    return {
        "total_students": len(df),
        "courses": safe_counts("course"),
        "semesters": safe_counts("semester"),
        "genders": safe_counts("gender"),
        "grades": safe_counts("grade"),
        "recent_students": df_to_records(df.tail(5))
    }

@app.get("/api/search")
def search_students(q: str = ""):
    df = read_students()
    if not q or df.empty:
        return df_to_records(df)
    mask = df.apply(lambda row: row.astype(str).str.contains(q, case=False, na=False).any(), axis=1)
    return df_to_records(df[mask])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)