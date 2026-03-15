from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import numpy as np
import os, math
from datetime import datetime
import uvicorn
from auth import hash_password, verify_password, create_token, decode_token

app = FastAPI(title="EduTrack Pro", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
INDEX_FILE = os.path.join(STATIC_DIR, "index.html")
EXCEL_FILE = os.path.join(BASE_DIR, "sms_data.xlsx")

SHEETS = ["users","students","teachers","classes","subjects","marks","fees","attendance","timetable","notices"]

# ── Excel helpers ─────────────────────────────────────────────────────────────
def clean(val):
    if val is None: return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)): return None
    if isinstance(val, np.integer): return int(val)
    if isinstance(val, np.floating): return None if math.isnan(float(val)) else float(val)
    if isinstance(val, np.bool_): return bool(val)
    return val

def to_rec(df): return [{c: clean(r[c]) for c in df.columns} for _, r in df.iterrows()]

def init_excel():
    schemas = {
        "users":      ["id","username","password","role","full_name","email","phone","created_at"],
        "students":   ["id","user_id","roll_number","full_name","email","phone","course","semester","gender","dob","address","guardian","guardian_phone","created_at"],
        "teachers":   ["id","user_id","full_name","email","phone","subject_specialization","qualification","joining_date","created_at"],
        "classes":    ["id","name","course","semester","teacher_id","created_at"],
        "subjects":   ["id","name","code","class_id","teacher_id","max_marks","created_at"],
        "marks":      ["id","student_id","subject_id","class_id","teacher_id","marks_obtained","max_marks","exam_type","remarks","date","created_at"],
        "fees":       ["id","student_id","full_name","roll_number","amount","fee_type","status","due_date","paid_date","receipt_no","admin_id","remarks","created_at"],
        "attendance": ["id","student_id","class_id","subject_id","date","status","marked_by","created_at"],
        "timetable":  ["id","class_id","subject_id","teacher_id","day","start_time","end_time","room","created_at"],
        "notices":    ["id","title","content","target_role","posted_by","posted_by_name","created_at"],
    }
    if not os.path.exists(EXCEL_FILE):
        with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as w:
            for s, cols in schemas.items():
                pd.DataFrame(columns=cols).to_excel(w, sheet_name=s, index=False)
        # Create default admin
        _add_default_admin()
        return
    # Ensure all sheets exist
    try:
        existing = pd.ExcelFile(EXCEL_FILE).sheet_names
        with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="a", if_sheet_exists="overlay") as w:
            for s, cols in schemas.items():
                if s not in existing:
                    pd.DataFrame(columns=cols).to_excel(w, sheet_name=s, index=False)
    except Exception: pass

def _add_default_admin():
    df = read_sheet("users")
    if not df.empty and "admin" in df["username"].values: return
    new = {"id":1,"username":"admin","password":hash_password("admin123"),
           "role":"admin","full_name":"System Admin","email":"admin@edutrack.com",
           "phone":"","created_at":now()}
    save_sheet("users", pd.concat([df, pd.DataFrame([new])], ignore_index=True))

def read_sheet(name):
    init_excel()
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=name)
        return df
    except Exception:
        return pd.DataFrame()

def save_sheet(name, df):
    init_excel()
    try:
        with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
            df.to_excel(w, sheet_name=name, index=False)
    except Exception:
        with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as w:
            df.to_excel(w, sheet_name=name, index=False)

def next_id(df):
    if df.empty or "id" not in df.columns or df["id"].isnull().all(): return 1
    return int(df["id"].dropna().max()) + 1

def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def today(): return datetime.now().strftime("%Y-%m-%d")

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def require_teacher(user=Depends(get_current_user)):
    if user.get("role") not in ["admin","teacher"]:
        raise HTTPException(status_code=403, detail="Teacher access required")
    return user

# ── Models ────────────────────────────────────────────────────────────────────
class LoginModel(BaseModel):
    username: str
    password: str

class RegisterStudent(BaseModel):
    username: str; password: str; full_name: str; email: str; phone: str
    roll_number: str; course: str; semester: str; gender: str; dob: str
    address: Optional[str]=""; guardian: Optional[str]=""; guardian_phone: Optional[str]=""

class RegisterTeacher(BaseModel):
    username: str; password: str; full_name: str; email: str; phone: str
    subject_specialization: str; qualification: str; joining_date: Optional[str]=""

class ClassModel(BaseModel):
    name: str; course: str; semester: str; teacher_id: Optional[int]=None

class SubjectModel(BaseModel):
    name: str; code: str; class_id: int; teacher_id: Optional[int]=None; max_marks: Optional[int]=100

class MarksModel(BaseModel):
    student_id: int; subject_id: int; class_id: int
    marks_obtained: float; max_marks: Optional[int]=100
    exam_type: Optional[str]="Mid Term"; remarks: Optional[str]=""

class FeeModel(BaseModel):
    student_id: int; amount: float; fee_type: str
    due_date: str; status: Optional[str]="Pending"; remarks: Optional[str]=""

class FeeUpdateModel(BaseModel):
    status: str; paid_date: Optional[str]=""; remarks: Optional[str]=""

class AttendanceModel(BaseModel):
    records: List[dict]

class TimetableModel(BaseModel):
    class_id: int; subject_id: int; teacher_id: int
    day: str; start_time: str; end_time: str; room: Optional[str]=""

class NoticeModel(BaseModel):
    title: str; content: str; target_role: Optional[str]="all"

class PasswordChange(BaseModel):
    old_password: str; new_password: str

# ── Static ────────────────────────────────────────────────────────────────────
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def root():
    if os.path.exists(INDEX_FILE): return FileResponse(INDEX_FILE)
    return HTMLResponse("<h1>EduTrack Pro API Running ✅</h1>")

@app.get("/health")
def health():
    return {"status":"ok","excel":os.path.exists(EXCEL_FILE),"static":os.path.isdir(STATIC_DIR)}

# ══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/auth/login")
def login(data: LoginModel):
    init_excel()
    df = read_sheet("users")
    if df.empty:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_row = df[df["username"] == data.username]
    if user_row.empty:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = user_row.iloc[0]
    if not verify_password(data.password, str(user["password"])):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"user_id": int(user["id"]), "username": str(user["username"]),
                          "role": str(user["role"]), "full_name": str(user["full_name"])})
    return {"token": token, "role": str(user["role"]), "full_name": str(user["full_name"]),
            "user_id": int(user["id"]), "username": str(user["username"])}

@app.post("/api/auth/change-password")
def change_password(data: PasswordChange, user=Depends(get_current_user)):
    df = read_sheet("users")
    idx = df.index[df["id"] == user["user_id"]].tolist()
    if not idx: raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(data.old_password, str(df.at[idx[0], "password"])):
        raise HTTPException(status_code=400, detail="Old password incorrect")
    df.at[idx[0], "password"] = hash_password(data.new_password)
    save_sheet("users", df)
    return {"message": "Password changed successfully"}

@app.get("/api/auth/me")
def get_me(user=Depends(get_current_user)):
    return user

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — STUDENT MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/admin/students", status_code=201)
def admin_add_student(data: RegisterStudent, user=Depends(require_admin)):
    users_df = read_sheet("users")
    if not users_df.empty and data.username in users_df["username"].values:
        raise HTTPException(status_code=400, detail="Username already exists")
    students_df = read_sheet("students")
    if not students_df.empty and data.roll_number in students_df["roll_number"].astype(str).values:
        raise HTTPException(status_code=400, detail="Roll number already exists")
    uid = next_id(users_df)
    new_user = {"id":uid,"username":data.username,"password":hash_password(data.password),
                "role":"student","full_name":data.full_name,"email":data.email,
                "phone":data.phone,"created_at":now()}
    users_df = pd.concat([users_df, pd.DataFrame([new_user])], ignore_index=True)
    save_sheet("users", users_df)
    sid = next_id(students_df)
    new_student = {"id":sid,"user_id":uid,"roll_number":data.roll_number,
                   "full_name":data.full_name,"email":data.email,"phone":data.phone,
                   "course":data.course,"semester":data.semester,"gender":data.gender,
                   "dob":data.dob,"address":data.address,"guardian":data.guardian,
                   "guardian_phone":data.guardian_phone,"created_at":now()}
    students_df = pd.concat([students_df, pd.DataFrame([new_student])], ignore_index=True)
    save_sheet("students", students_df)
    return {"message":"Student registered","student_id":sid,"user_id":uid}

@app.get("/api/admin/students")
def admin_get_students(user=Depends(require_admin)):
    return to_rec(read_sheet("students"))

@app.delete("/api/admin/students/{student_id}")
def admin_delete_student(student_id: int, user=Depends(require_admin)):
    df = read_sheet("students")
    row = df[df["id"]==student_id]
    if row.empty: raise HTTPException(status_code=404, detail="Student not found")
    uid = row.iloc[0]["user_id"]
    df = df[df["id"]!=student_id].reset_index(drop=True)
    save_sheet("students", df)
    udf = read_sheet("users")
    udf = udf[udf["id"]!=uid].reset_index(drop=True)
    save_sheet("users", udf)
    return {"message":"Student deleted"}

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — TEACHER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/admin/teachers", status_code=201)
def admin_add_teacher(data: RegisterTeacher, user=Depends(require_admin)):
    users_df = read_sheet("users")
    if not users_df.empty and data.username in users_df["username"].values:
        raise HTTPException(status_code=400, detail="Username already exists")
    uid = next_id(users_df)
    new_user = {"id":uid,"username":data.username,"password":hash_password(data.password),
                "role":"teacher","full_name":data.full_name,"email":data.email,
                "phone":data.phone,"created_at":now()}
    users_df = pd.concat([users_df, pd.DataFrame([new_user])], ignore_index=True)
    save_sheet("users", users_df)
    tdf = read_sheet("teachers")
    tid = next_id(tdf)
    new_teacher = {"id":tid,"user_id":uid,"full_name":data.full_name,"email":data.email,
                   "phone":data.phone,"subject_specialization":data.subject_specialization,
                   "qualification":data.qualification,
                   "joining_date":data.joining_date or today(),"created_at":now()}
    tdf = pd.concat([tdf, pd.DataFrame([new_teacher])], ignore_index=True)
    save_sheet("teachers", tdf)
    return {"message":"Teacher registered","teacher_id":tid,"user_id":uid}

@app.get("/api/admin/teachers")
def admin_get_teachers(user=Depends(require_admin)):
    return to_rec(read_sheet("teachers"))

@app.delete("/api/admin/teachers/{teacher_id}")
def admin_delete_teacher(teacher_id: int, user=Depends(require_admin)):
    df = read_sheet("teachers")
    row = df[df["id"]==teacher_id]
    if row.empty: raise HTTPException(status_code=404, detail="Teacher not found")
    uid = row.iloc[0]["user_id"]
    df = df[df["id"]!=teacher_id].reset_index(drop=True)
    save_sheet("teachers", df)
    udf = read_sheet("users")
    udf = udf[udf["id"]!=uid].reset_index(drop=True)
    save_sheet("users", udf)
    return {"message":"Teacher deleted"}

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — CLASSES
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/admin/classes", status_code=201)
def create_class(data: ClassModel, user=Depends(require_admin)):
    df = read_sheet("classes")
    new = {"id":next_id(df),"name":data.name,"course":data.course,
           "semester":data.semester,"teacher_id":data.teacher_id,"created_at":now()}
    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
    save_sheet("classes", df)
    return {"message":"Class created","id":new["id"]}

@app.get("/api/classes")
def get_classes(user=Depends(get_current_user)):
    return to_rec(read_sheet("classes"))

@app.delete("/api/admin/classes/{class_id}")
def delete_class(class_id: int, user=Depends(require_admin)):
    df = read_sheet("classes")
    df = df[df["id"]!=class_id].reset_index(drop=True)
    save_sheet("classes", df)
    return {"message":"Class deleted"}

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — SUBJECTS
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/admin/subjects", status_code=201)
def create_subject(data: SubjectModel, user=Depends(require_admin)):
    df = read_sheet("subjects")
    new = {"id":next_id(df),"name":data.name,"code":data.code,"class_id":data.class_id,
           "teacher_id":data.teacher_id,"max_marks":data.max_marks,"created_at":now()}
    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
    save_sheet("subjects", df)
    return {"message":"Subject created","id":new["id"]}

@app.get("/api/subjects")
def get_subjects(user=Depends(get_current_user)):
    return to_rec(read_sheet("subjects"))

@app.delete("/api/admin/subjects/{subject_id}")
def delete_subject(subject_id: int, user=Depends(require_admin)):
    df = read_sheet("subjects")
    df = df[df["id"]!=subject_id].reset_index(drop=True)
    save_sheet("subjects", df)
    return {"message":"Subject deleted"}

# ══════════════════════════════════════════════════════════════════════════════
# MARKS
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/marks", status_code=201)
def add_marks(data: MarksModel, user=Depends(require_teacher)):
    df = read_sheet("marks")
    # Check if marks already exist for this student+subject+exam_type
    exists = df[(df["student_id"]==data.student_id) &
                (df["subject_id"]==data.subject_id) &
                (df["exam_type"]==data.exam_type)]
    if not exists.empty:
        idx = exists.index[0]
        df.at[idx,"marks_obtained"] = data.marks_obtained
        df.at[idx,"remarks"] = data.remarks
        save_sheet("marks", df)
        return {"message":"Marks updated"}
    new = {"id":next_id(df),"student_id":data.student_id,"subject_id":data.subject_id,
           "class_id":data.class_id,"teacher_id":user["user_id"],
           "marks_obtained":data.marks_obtained,"max_marks":data.max_marks,
           "exam_type":data.exam_type,"remarks":data.remarks,
           "date":today(),"created_at":now()}
    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
    save_sheet("marks", df)
    return {"message":"Marks added","id":new["id"]}

@app.get("/api/marks")
def get_marks(user=Depends(get_current_user)):
    df = read_sheet("marks")
    if user["role"] == "student":
        sdf = read_sheet("students")
        srow = sdf[sdf["user_id"]==user["user_id"]]
        if srow.empty: return []
        sid = int(srow.iloc[0]["id"])
        df = df[df["student_id"]==sid]
    elif user["role"] == "teacher":
        df = df[df["teacher_id"]==user["user_id"]]
    return to_rec(df)

@app.get("/api/marks/student/{student_id}")
def get_student_marks(student_id: int, user=Depends(get_current_user)):
    df = read_sheet("marks")
    return to_rec(df[df["student_id"]==student_id])

@app.delete("/api/marks/{mark_id}")
def delete_marks(mark_id: int, user=Depends(require_teacher)):
    df = read_sheet("marks")
    df = df[df["id"]!=mark_id].reset_index(drop=True)
    save_sheet("marks", df)
    return {"message":"Marks deleted"}

# ══════════════════════════════════════════════════════════════════════════════
# FEES
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/admin/fees", status_code=201)
def add_fee(data: FeeModel, user=Depends(require_admin)):
    df = read_sheet("fees")
    sdf = read_sheet("students")
    srow = sdf[sdf["id"]==data.student_id]
    if srow.empty: raise HTTPException(status_code=404, detail="Student not found")
    student = srow.iloc[0]
    receipt = f"RCP{next_id(df):05d}"
    new = {"id":next_id(df),"student_id":data.student_id,
           "full_name":str(student["full_name"]),"roll_number":str(student["roll_number"]),
           "amount":data.amount,"fee_type":data.fee_type,"status":data.status,
           "due_date":data.due_date,"paid_date":"","receipt_no":receipt,
           "admin_id":user["user_id"],"remarks":data.remarks,"created_at":now()}
    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
    save_sheet("fees", df)
    return {"message":"Fee record added","receipt_no":receipt,"id":new["id"]}

@app.put("/api/admin/fees/{fee_id}")
def update_fee(fee_id: int, data: FeeUpdateModel, user=Depends(require_admin)):
    df = read_sheet("fees")
    idx = df.index[df["id"]==fee_id].tolist()
    if not idx: raise HTTPException(status_code=404, detail="Fee record not found")
    df.at[idx[0],"status"] = data.status
    df.at[idx[0],"paid_date"] = data.paid_date or (today() if data.status=="Paid" else "")
    df.at[idx[0],"remarks"] = data.remarks
    save_sheet("fees", df)
    return {"message":"Fee updated"}

@app.get("/api/fees")
def get_fees(user=Depends(get_current_user)):
    df = read_sheet("fees")
    if user["role"] == "student":
        sdf = read_sheet("students")
        srow = sdf[sdf["user_id"]==user["user_id"]]
        if srow.empty: return []
        sid = int(srow.iloc[0]["id"])
        df = df[df["student_id"]==sid]
    return to_rec(df)

@app.delete("/api/admin/fees/{fee_id}")
def delete_fee(fee_id: int, user=Depends(require_admin)):
    df = read_sheet("fees")
    df = df[df["id"]!=fee_id].reset_index(drop=True)
    save_sheet("fees", df)
    return {"message":"Fee deleted"}

# ══════════════════════════════════════════════════════════════════════════════
# ATTENDANCE
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/attendance")
def mark_attendance(data: AttendanceModel, user=Depends(require_teacher)):
    df = read_sheet("attendance")
    added = 0
    for rec in data.records:
        date = rec.get("date", today())
        # Remove existing for same student+subject+date
        df = df[~((df["student_id"]==rec["student_id"]) &
                  (df["subject_id"]==rec.get("subject_id","")) &
                  (df["date"]==date))]
        new = {"id":next_id(df),"student_id":rec["student_id"],
               "class_id":rec.get("class_id",""),"subject_id":rec.get("subject_id",""),
               "date":date,"status":rec.get("status","Present"),
               "marked_by":user["user_id"],"created_at":now()}
        df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
        added += 1
    save_sheet("attendance", df)
    return {"message":f"{added} attendance records saved"}

@app.get("/api/attendance")
def get_attendance(user=Depends(get_current_user)):
    df = read_sheet("attendance")
    if user["role"] == "student":
        sdf = read_sheet("students")
        srow = sdf[sdf["user_id"]==user["user_id"]]
        if srow.empty: return []
        sid = int(srow.iloc[0]["id"])
        df = df[df["student_id"]==sid]
    return to_rec(df)

# ══════════════════════════════════════════════════════════════════════════════
# TIMETABLE
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/admin/timetable", status_code=201)
def add_timetable(data: TimetableModel, user=Depends(require_admin)):
    df = read_sheet("timetable")
    new = {"id":next_id(df),"class_id":data.class_id,"subject_id":data.subject_id,
           "teacher_id":data.teacher_id,"day":data.day,"start_time":data.start_time,
           "end_time":data.end_time,"room":data.room,"created_at":now()}
    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
    save_sheet("timetable", df)
    return {"message":"Timetable entry added","id":new["id"]}

@app.get("/api/timetable")
def get_timetable(user=Depends(get_current_user)):
    return to_rec(read_sheet("timetable"))

@app.delete("/api/admin/timetable/{entry_id}")
def delete_timetable(entry_id: int, user=Depends(require_admin)):
    df = read_sheet("timetable")
    df = df[df["id"]!=entry_id].reset_index(drop=True)
    save_sheet("timetable", df)
    return {"message":"Entry deleted"}

# ══════════════════════════════════════════════════════════════════════════════
# NOTICES
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/notices", status_code=201)
def add_notice(data: NoticeModel, user=Depends(require_teacher)):
    df = read_sheet("notices")
    new = {"id":next_id(df),"title":data.title,"content":data.content,
           "target_role":data.target_role,"posted_by":user["user_id"],
           "posted_by_name":user["full_name"],"created_at":now()}
    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
    save_sheet("notices", df)
    return {"message":"Notice posted","id":new["id"]}

@app.get("/api/notices")
def get_notices(user=Depends(get_current_user)):
    df = read_sheet("notices")
    if df.empty: return []
    role = user["role"]
    filtered = df[(df["target_role"]=="all") | (df["target_role"]==role)]
    return to_rec(filtered.sort_values("created_at", ascending=False) if not filtered.empty else filtered)

@app.delete("/api/notices/{notice_id}")
def delete_notice(notice_id: int, user=Depends(require_teacher)):
    df = read_sheet("notices")
    df = df[df["id"]!=notice_id].reset_index(drop=True)
    save_sheet("notices", df)
    return {"message":"Notice deleted"}

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD STATS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/dashboard/stats")
def dashboard_stats(user=Depends(get_current_user)):
    role = user["role"]
    students_df = read_sheet("students")
    teachers_df = read_sheet("teachers")
    fees_df     = read_sheet("fees")
    marks_df    = read_sheet("marks")
    notices_df  = read_sheet("notices")
    attend_df   = read_sheet("attendance")
    classes_df  = read_sheet("classes")

    if role == "admin":
        total_fees = float(fees_df["amount"].sum()) if not fees_df.empty and "amount" in fees_df.columns else 0
        paid_fees  = float(fees_df[fees_df["status"]=="Paid"]["amount"].sum()) if not fees_df.empty else 0
        return {
            "total_students": len(students_df),
            "total_teachers": len(teachers_df),
            "total_classes":  len(classes_df),
            "total_fees":     round(total_fees,2),
            "paid_fees":      round(paid_fees,2),
            "pending_fees":   round(total_fees-paid_fees,2),
            "total_notices":  len(notices_df),
            "recent_students": to_rec(students_df.tail(5)),
        }
    elif role == "teacher":
        tdf = teachers_df[teachers_df["user_id"]==user["user_id"]]
        tid = int(tdf.iloc[0]["id"]) if not tdf.empty else None
        my_marks = marks_df[marks_df["teacher_id"]==user["user_id"]] if not marks_df.empty else pd.DataFrame()
        my_attend = attend_df[attend_df["marked_by"]==user["user_id"]] if not attend_df.empty else pd.DataFrame()
        return {
            "my_marks_given": len(my_marks),
            "my_attendance_records": len(my_attend),
            "total_students": len(students_df),
            "total_notices":  len(notices_df),
        }
    else:  # student
        sdf = students_df[students_df["user_id"]==user["user_id"]]
        if sdf.empty:
            return {"marks":[],"fees":[],"attendance_pct":0,"notices":[]}
        sid = int(sdf.iloc[0]["id"])
        my_marks   = marks_df[marks_df["student_id"]==sid] if not marks_df.empty else pd.DataFrame()
        my_fees    = fees_df[fees_df["student_id"]==sid] if not fees_df.empty else pd.DataFrame()
        my_attend  = attend_df[attend_df["student_id"]==sid] if not attend_df.empty else pd.DataFrame()
        pct = 0
        if not my_attend.empty:
            present = len(my_attend[my_attend["status"]=="Present"])
            pct = round(present/len(my_attend)*100, 1)
        pending_fees = float(my_fees[my_fees["status"]=="Pending"]["amount"].sum()) if not my_fees.empty else 0
        return {
            "total_marks": len(my_marks),
            "pending_fees": round(pending_fees,2),
            "attendance_pct": pct,
            "total_notices": len(notices_df),
            "student_info": to_rec(sdf)[0] if not sdf.empty else {},
        }

# ══════════════════════════════════════════════════════════════════════════════
# PROFILE
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/profile")
def get_profile(user=Depends(get_current_user)):
    role = user["role"]
    if role == "student":
        df = read_sheet("students")
        row = df[df["user_id"]==user["user_id"]]
        return to_rec(row)[0] if not row.empty else {}
    elif role == "teacher":
        df = read_sheet("teachers")
        row = df[df["user_id"]==user["user_id"]]
        return to_rec(row)[0] if not row.empty else {}
    else:
        df = read_sheet("users")
        row = df[df["id"]==user["user_id"]]
        if row.empty: return {}
        r = to_rec(row)[0]
        r.pop("password", None)
        return r

# ══════════════════════════════════════════════════════════════════════════════
# ALL USERS (admin)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/admin/users")
def get_all_users(user=Depends(require_admin)):
    df = read_sheet("users")
    records = to_rec(df)
    for r in records: r.pop("password", None)
    return records

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 EduTrack Pro starting on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)