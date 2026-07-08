# LocalAWS — DynamoDB: Project Report

## What We Did
Built a fully custom DynamoDB clone from scratch, integrated into the existing LocalAWS project. It supports creating and deleting tables, putting/getting/deleting items, and scanning all items in a table — backed by JSON files on disk and exposed via a clean browser-based GUI consistent with the rest of the LocalAWS console.

## Why We Did It
DynamoDB is one of AWS's core services — a serverless NoSQL key-value and document store. Building our own version deepens understanding of how key-based storage, partition keys, sort keys, and table management work under the hood, without touching real AWS infrastructure.

## How It Works

**Architecture:**
- DynamoDB logic lives in its own folder (`dynamodb/`) as a Flask Blueprint, keeping it completely separate from S3 and auth code
- Each table is stored as a single JSON file under `dynamodb_data/` on disk
- A table file contains two sections: `meta` (partition key, sort key) and `items` (a dictionary keyed by partition key value, or `pk#sk` if a sort key exists)
- All routes require a valid session cookie — same login protection as S3

**Data structure (on disk):**
```json
{
  "meta": { "partition_key": "user_id", "sort_key": null },
  "items": {
    "1": { "user_id": "1", "name": "Yash", "email": "yash@gmail.com" }
  }
}
```

**API endpoints:**
| Method | Route | Action |
|---|---|---|
| GET | /api/dynamodb/tables | List all tables |
| POST | /api/dynamodb/tables | Create a table |
| GET | /api/dynamodb/tables/:table | Describe table (meta + count) |
| DELETE | /api/dynamodb/tables/:table | Delete table |
| PUT | /api/dynamodb/tables/:table/items | Put (upsert) an item |
| GET | /api/dynamodb/tables/:table/items/:key | Get single item by key |
| DELETE | /api/dynamodb/tables/:table/items/:key | Delete single item |
| GET | /api/dynamodb/tables/:table/scan | Return all items |

## Project Structure
```
LocalAWS/
  app.py
  dynamodb/
    __init__.py       <- makes it a Python package
    routes.py         <- Flask Blueprint with all API routes
    storage.py        <- file read/write logic
  dynamodb_data/      <- JSON files, one per table (persisted via volume)
  templates/
    dynamodb.html     <- browser GUI
```

## How To Run It
```bash
cd Y:\My-Projects\LocalAWS
docker-compose down
docker-compose up -d --build
```
Open `http://localhost:4566` → sign in → click **DynamoDB** on the Services page.

## Issues Faced & Fixes

**1. `NameError: name 'app' is not defined`**
The blueprint import lines were placed before `app = Flask(__name__)` in `app.py`.
*Fix:* moved the import and `app.register_blueprint(dynamo_bp)` to after `app` is created.

**2. `no configuration file provided: not found`**
docker-compose commands were run from the wrong directory (`C:\Users\yashj` instead of the project folder).
*Fix:* always `cd Y:\My-Projects\LocalAWS` first before running any docker-compose command.

**3. `{"error": "Not logged in"}` when testing with curl**
DynamoDB routes require a valid session cookie. curl doesn't automatically have one.
*Fix:* used `-c cookies.txt` to save the session cookie during login, then `-b cookies.txt` to send it with subsequent requests.

## How-To Guide (For Someone New)

**Prerequisites:** Docker Desktop running, project files in `LocalAWS/`.

**1. Start the stack:**
```bash
cd Y:\My-Projects\LocalAWS
docker-compose up -d --build
```

**2. Open the console:**
Go to `http://localhost:4566` → sign in → click **DynamoDB**.

**3. Create a table:**
- Enter a table name (e.g. `products`)
- Enter a partition key (e.g. `product_id`) — this is the unique identifier for each item
- Optionally enter a sort key (e.g. `category`) — allows composite keys
- Click **Create table**

**4. Add items:**
- Click **+ Put item**
- Edit the JSON in the modal — must include the partition key field
- Click **Save item**

**5. Query items:**
- **Scan all** — returns every item in the table
- **Get item** — type a partition key value and click Get item to fetch one specific record

**6. Delete items or tables:**
- Click **Delete** on any item row to remove it
- Click **✕ Delete** next to a table name in the left panel to delete the whole table (irreversible)

**7. Using the API directly (curl):**
```powershell
# Login first to get session cookie
curl.exe -X POST http://localhost:4566/api/login -H "Content-Type: application/json" --data-binary '{\"email\":\"you@email.com\",\"password\":\"yourpassword\"}' -c cookies.txt

# Create table
curl.exe -X POST http://localhost:4566/api/dynamodb/tables -H "Content-Type: application/json" --data-binary '{\"table_name\":\"users\",\"partition_key\":\"user_id\"}' -b cookies.txt

# Put item
curl.exe -X PUT http://localhost:4566/api/dynamodb/tables/users/items -H "Content-Type: application/json" --data-binary '{\"user_id\":\"1\",\"name\":\"Yash\"}' -b cookies.txt

# Scan
curl.exe http://localhost:4566/api/dynamodb/tables/users/scan -b cookies.txt

# Get single item
curl.exe http://localhost:4566/api/dynamodb/tables/users/items/1 -b cookies.txt

# Delete item
curl.exe -X DELETE http://localhost:4566/api/dynamodb/tables/users/items/1 -b cookies.txt

# Delete table
curl.exe -X DELETE http://localhost:4566/api/dynamodb/tables/users -b cookies.txt
```

**8. Data persistence:**
Table data lives in `./dynamodb_data/` on your host machine, mounted into the container via Docker volume. Safe across rebuilds — only wiped if you manually delete the folder or run `docker-compose down -v`.

## Final State
A working DynamoDB clone with full table and item CRUD, session-protected API, Blueprint-based modular code structure, JSON file storage, and a browser GUI — fully integrated into the LocalAWS services dashboard.
