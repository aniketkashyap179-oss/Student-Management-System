from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import numpy as np
import os
from datetime import datetime
import uvicorn
import math

app = FastAPI(title="Student Management System", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EXCEL_FILE = "students.xlsx"

# ── All expected columns ───────────────────────────────────────────────────────
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

# ── Clean NaN/inf values so JSON never crashes ─────────────────────────────────
def clean_value(val):
    """Convert NaN, inf, numpy types → Python safe types"""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return None if math.isnan(float(val)) else float(val)
    if isinstance(val, np.bool_):
        return bool(val)
    return val

def df_to_records(df: pd.DataFrame) -> list:
    """Safely convert DataFrame to list of dicts — no NaN anywhere"""
    records = []
    for _, row in df.iterrows():
        record = {}
        for col in df.columns:
            record[col] = clean_value(row[col])
        records.append(record)
    return records

# ── Excel init — always ensure ALL columns exist ───────────────────────────────
def init_excel():
    if not os.path.exists(EXCEL_FILE):
        pd.DataFrame(columns=COLUMNS).to_excel(EXCEL_FILE, index=False)
        return

    # File exists — check and add any missing columns
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
        # Corrupt file — recreate
        pd.DataFrame(columns=COLUMNS).to_excel(EXCEL_FILE, index=False)

def read_students() -> pd.DataFrame:
    init_excel()
    df = pd.read_excel(EXCEL_FILE)
    # Ensure all columns exist even after read
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df

def save_students(df: pd.DataFrame):
    df.to_excel(EXCEL_FILE, index=False)

def generate_id(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns or df["id"].isnull().all():
        return 1
    valid_ids = df["id"].dropna()
    return int(valid_ids.max()) + 1 if not valid_ids.empty else 1

# ── Routes ─────────────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/api/students")
def get_all_students():
    df = read_students()
    return df_to_records(df)

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
        "id": new_id,
        "name": student.name,
        "roll_number": student.roll_number,
        "email": student.email,
        "phone": student.phone,
        "course": student.course,
        "semester": student.semester,
        "gender": student.gender,
        "date_of_birth": student.date_of_birth,
        "address": student.address or "",
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
        return {
            "total_students": 0,
            "courses": {},
            "semesters": {},
            "genders": {},
            "grades": {},
            "recent_students": []
        }

    # Safe value_counts — only on columns that exist and have data
    def safe_counts(col):
        if col not in df.columns:
            return {}
        series = df[col].dropna().astype(str)
        series = series[series.str.strip() != ""]
        return {str(k): int(v) for k, v in series.value_counts().items()}

    recent_df = df.tail(5)
    recent = df_to_records(recent_df)

    return {
        "total_students": len(df),
        "courses": safe_counts("course"),
        "semesters": safe_counts("semester"),
        "genders": safe_counts("gender"),
        "grades": safe_counts("grade"),
        "recent_students": recent
    }

@app.get("/api/search")
def search_students(q: str = ""):
    df = read_students()
    if not q or df.empty:
        return df_to_records(df)
    mask = df.apply(
        lambda row: row.astype(str).str.contains(q, case=False, na=False).any(), axis=1
    )
    return df_to_records(df[mask])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)