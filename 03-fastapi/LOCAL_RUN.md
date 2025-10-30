Run the FastAPI app locally (development)

1. Create a Python virtual environment and activate it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

2. Install the package and dependencies from the example subproject

```powershell
cd 03-fastapi
python -m pip install -e .
# if you don't want editable install, you can also:
# python -m pip install httpx python-dotenv uvicorn
```

3. Copy `.env.example` to `.env` and fill your Supabase values

```powershell
copy .env.example .env
# Edit .env to set SUPABASE_URL and SUPABASE_KEY
```

4. Run with uvicorn

```powershell
# run the FastAPI app locally on port 8000
uvicorn src.worker:app --reload --port 8000
```

5. Test the new endpoints

```powershell
# list rows
curl.exe http://localhost:8000/mobile01

# create a row (adjust fields to your Supabase table schema)
curl.exe -X POST http://localhost:8000/mobile01 -H "Content-Type: application/json" -d '{"name":"test","data":"hello"}'

# read
curl.exe http://localhost:8000/mobile01/1

# update
curl.exe -X PUT http://localhost:8000/mobile01/1 -H "Content-Type: application/json" -d '{"data":"updated"}'

# delete
curl.exe -X DELETE http://localhost:8000/mobile01/1

6. Try the RPC-backed endpoints and the tiny web UI

- Lists via RPC
```powershell
curl.exe http://localhost:8000/mobile01/lists
curl.exe -X POST http://localhost:8000/mobile01/lists -H "Content-Type: application/json" -d '{"title":"inbox","color":"#ff0000"}'
```

- Tasks via RPC
```powershell
curl.exe "http://localhost:8000/mobile01/tasks?list_id=YOUR_LIST_UUID"
curl.exe -X POST http://localhost:8000/mobile01/tasks -H "Content-Type: application/json" -d '{"title":"new task","list_id":"YOUR_LIST_UUID"}'
```

- Generic RPC passthrough
```powershell
curl.exe -X POST http://localhost:8000/mobile01/rpc/reminders_create -H "Content-Type: application/json" -d '{"p_task_id":"UUID","p_remind_at":"2025-10-31T10:30:00+07:00"}'
```

- Open local web UI: http://127.0.0.1:8000/web
```

Notes
- The code uses the Supabase REST endpoint (PostgREST). Ensure your Supabase project has a table named `mobile01` (or set `SUPABASE_TABLE` in `.env`).
- Example SQL to create a simple table in Supabase (run in SQL editor):

```sql
create table mobile01 (
  id serial primary key,
  name text,
  data text
);
```

- For production deploy to Cloudflare Workers, additional vendoring may be required; httpx isn't guaranteed to run on Pyodide/Workers without vendoring; use the CI workflow to vendor dependencies.
