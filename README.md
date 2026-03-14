# 🎓 EduSphere — Student Management System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.111-green?style=for-the-badge&logo=fastapi"/>
  <img src="https://img.shields.io/badge/Excel-Data_Storage-217346?style=for-the-badge&logo=microsoftexcel"/>
  <img src="https://img.shields.io/badge/UI-3D_Light_Theme-orange?style=for-the-badge"/>
</p>

> A full-stack **Student Management System** built with **Python FastAPI** backend and a stunning **3D-style HTML/CSS/JS** frontend. All student data is stored and retrieved from an **Excel (.xlsx)** file — no database required!

---

## ✨ Features

| Feature | Description |
|---|---|
| 📊 **Dashboard** | Live stats, course charts, top performers, recent additions |
| 👥 **View Students** | Full table with search, CGPA bars, color-coded badges |
| ➕ **Add Student** | Beautiful form with validation and duplicate detection |
| 🗑️ **Delete Student** | Safe deletion with confirmation modal |
| 🔍 **Search** | Real-time search by name, email, roll number, or course |
| 🌙 **Dark / Light Mode** | Toggle with animated switch — default Light |
| 📁 **Excel Storage** | Data saved to `students.xlsx` (open in Excel/Sheets) |
| ❓ **Help Center** | Documentation cards + FAQ accordion |

---

## 🗂️ Project Structure

```
student_management/
│
├── main.py               ← FastAPI backend (all API routes)
├── requirements.txt      ← Python dependencies
├── students.xlsx         ← Auto-created on first student add
│
└── static/
    └── index.html        ← Complete frontend (HTML + CSS + JS)
```

---

## ⚙️ Requirements

- **Python 3.10** or higher
- **pip** (Python package manager)
- A modern web browser (Chrome, Firefox, Edge, Safari)

---

## 🚀 Quick Start

### Step 1 — Clone or Download

```bash
# If using Git:
git clone https://github.com/yourusername/student-management.git
cd student-management

# Or just place all files in a folder called student_management/
```

### Step 2 — Create a Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Run the Server

```bash
python main.py
```

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

### Step 5 — Open in Browser

Navigate to 👉 **http://localhost:8000**

---

## 📡 API Reference

The FastAPI backend exposes the following REST endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serve the frontend HTML |
| `GET` | `/api/students` | Get all students |
| `POST` | `/api/students` | Add a new student |
| `GET` | `/api/students/{id}` | Get student by ID |
| `DELETE` | `/api/students/{id}` | Delete student by ID |
| `GET` | `/api/dashboard` | Dashboard stats & analytics |
| `GET` | `/api/search?q=query` | Search students |

### Interactive API Docs (Swagger UI)
FastAPI auto-generates interactive docs at:
- **http://localhost:8000/docs** — Swagger UI
- **http://localhost:8000/redoc** — ReDoc UI

### Example: Add Student (POST /api/students)

```json
{
  "name": "Rahul Sharma",
  "email": "rahul@example.com",
  "roll_number": "CS2024001",
  "course": "Computer Science",
  "year": 2,
  "phone": "+91 98765 43210",
  "address": "Hostel Block A",
  "cgpa": 8.75
}
```

**Success Response:**
```json
{
  "message": "Student added successfully",
  "id": "A1B2C3D4",
  "student": { ... }
}
```

---

## 📊 Excel File Structure

The `students.xlsx` file contains the following columns:

| Column | Type | Description |
|---|---|---|
| `id` | String | Auto-generated 8-char unique ID |
| `name` | String | Full name |
| `email` | String | Email (unique) |
| `roll_number` | String | Roll number (unique) |
| `course` | String | Course / branch |
| `year` | Integer | Academic year (1–5) |
| `phone` | String | Phone number |
| `address` | String | Home/hostel address |
| `cgpa` | Float | CGPA (0.0–10.0) |
| `created_at` | String | Registration timestamp |

---

## 🎨 UI Pages

### 🏠 Dashboard
- Hero banner with quick action button
- 4 stat cards: Total Students, Avg CGPA, Courses, Year Groups
- Bar chart showing students per course
- Top 5 performers by CGPA
- Recently added students table

### 👥 All Students
- Complete student table with avatars, CGPA progress bars, badges
- Real-time search in the top bar
- Delete button with confirmation dialog

### ➕ Add Student
- Gradient form header
- Validated inputs (required fields, email format, CGPA range)
- Duplicate roll number & email detection
- Clear form button

### ❓ Help Center
- 6 feature cards with icons
- FAQ accordion with smooth animations

---

## 🔧 Configuration

To change the **port**, edit `main.py`:

```python
uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
#                                                   ^^^^
#                                              Change this
```

To change the **Excel filename**, edit `main.py`:

```python
EXCEL_FILE = "students.xlsx"   # ← Change this
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Port already in use | Change port in `main.py` or kill the process on port 8000 |
| `students.xlsx` not created | Add at least one student first |
| Blank page in browser | Make sure server is running and you're on `http://localhost:8000` |
| CORS error | Only occurs if you open `index.html` directly — always run via FastAPI |

---

## 📦 Dependencies

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.111.0 | Web framework & REST API |
| `uvicorn` | 0.30.1 | ASGI server |
| `pandas` | 2.2.2 | Excel read/write & data analysis |
| `openpyxl` | 3.1.3 | Excel (.xlsx) file engine |
| `pydantic` | 2.7.4 | Data validation & models |
| `python-multipart` | 0.0.9 | Form data handling |

---

## 📄 License

MIT License — free for personal and commercial use.

---

## 🙌 Credits

Built with ❤️ using **FastAPI**, **Pandas**, **OpenPyXL**, and vanilla **HTML/CSS/JS**.

---

*EduSphere Student Management System — © 2024*