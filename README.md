# Backend Quick Start (Flask)

This guide explains how to set up and run the backend locally for development.

---

## 🧰 Prerequisites
- Python 3.10+ installed (`python3 --version`)
- Pip installed (`python3 -m pip --version`)

---

## 🚀 1. Clone & Enter the Project
```bash
git clone <YOUR_REPO_URL>
cd <YOUR_BACKEND_FOLDER>
```

---

## 🐍 2. Create & Activate a Virtual Environment
```bash
# Create venv
python3 -m venv venv

# Activate venv (macOS/Linux)
source venv/bin/activate
```

> You should now see `(venv)` in your terminal prompt.  
> To deactivate later: `deactivate`

---

## 📦 3. Install Dependencies
```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

> **Important:**  
> If you install any new package locally, **add it (with version) to `requirements.txt`** to prevent Railway deploy crashes.
>
> Example:
> ```txt
> Flask==3.0.3
> python-dotenv==1.0.1
> ```
> Then commit and push the updated `requirements.txt`.

---

## ⚙️ 4. Environment Variables
There is a file called **`.env.example`** in the repo.  
**Do not delete or edit it.** Instead, make your own `.env` file by copying it:

```bash
cp .env.example .env
```

Then fill in the real values. Example content from `.env.example`:

```env
# Supabase Configuration
SUPABASE_URL=...
SUPABASE_KEY=...
SUPABASE_JWT_SECRET=...

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
```

### 🔑 Getting these values
- **SUPABASE_URL** → Supabase Dashboard → *Project Settings → API → Project URL*  
- **SUPABASE_KEY** → Supabase Dashboard → *Project Settings → API → anon/public key*  
- **SUPABASE_JWT_SECRET** → Supabase Dashboard → *Authentication → Settings → JWT Secret*  
- **FLASK_ENV / FLASK_DEBUG** → Use `development` and `True` for local setup.

💡 **Tip:** You can also just ask one of the backend devs for their working `.env` file and copy the values.

---

## ▶️ 5. Run the App
The backend entry point is **`app.py`**, running on port **5001**.

```bash
python3 app.py
```

Expected output:
```
Starting Salon Booking Platform Backend...
Debug mode: True
 * Running on http://0.0.0.0:5001
```

Now visit [http://localhost:5001](http://localhost:5001).

---

## 📘 6. Swagger (API Docs)
Once running, open your browser to:

```
http://localhost:5001/apidocs
```

This will show the interactive Swagger UI for all API endpoints.

---

## 🧩 7. Useful Commands
```bash
# Freeze current dependencies (pin versions)
python3 -m pip freeze > requirements.txt

# Quick health check
curl -i http://localhost:5001/
```

---

## 🧠 Common Issues & Tips

**`.env` not loading or variables missing**  
- Ensure `.env` exists in the root folder and contains all variables.  
- The app should automatically load `.env` via `python-dotenv`.

**ModuleNotFoundError**  
- Re-activate your venv and reinstall:
  ```bash
  source venv/bin/activate
  python3 -m pip install -r requirements.txt
  ```

**Port already in use (5001)**  
- Stop the existing process or change the port inside `app.py`.

**Railway deploy crashes**  
- Someone installed a new package locally but didn’t update `requirements.txt`.

**CORS or Supabase auth issues**  
- Double-check your `SUPABASE_URL`, `SUPABASE_KEY`, and JWT secret.

---

## 👥 Contributing
1. Create a new branch:
   ```bash
   git checkout -b feature/my-change
   ```
2. Make your changes and update `requirements.txt` if needed.  
3. Commit & push:
   ```bash
   git add .
   git commit -m "feat: describe your change"
   git push -u origin feature/my-change
   ```
4. Open a pull request.

---

## ❓ Questions
If anything’s unclear, open an issue or ask in the backend channel.
