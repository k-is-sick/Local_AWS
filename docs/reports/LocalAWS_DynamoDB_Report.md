# LocalAWS — DynamoDB: Project Report

## What We Did
Built a fully custom DynamoDB clone from scratch, integrated into the existing LocalAWS platform. It supports creating and deleting tables, putting/getting/deleting items, and scanning all items in a table — backed by JSON files on disk and exposed via a clean browser-based GUI consistent with the rest of the LocalAWS console.

## Why We Did It
DynamoDB is one of AWS's core serverless NoSQL key-value and document stores. Building our own version deepens understanding of partition keys, sort keys, table management, and document CRUD without relying on real AWS infrastructure.

## How It Works
- **Flask Blueprint**: Dedicated `dynamodb/` package registered at `/api/dynamodb`.
- **JSON Storage Engine**: Each table is stored as an atomic JSON document under `dynamodb_data/<table_name>.json`.
- **Primary & Composite Keys**: Supports partition keys (`PK`) and sort keys (`PK#SK`).
- **Dual Authentication**: Accepts session cookies from web browser console and `X-Access-Key-Id` / `X-Secret-Key` headers evaluated by the IAM policy engine.

## API Endpoints
| Method | Route | Action |
|---|---|---|
| GET | /api/dynamodb/tables | List all tables |
| POST | /api/dynamodb/tables | Create a table |
| GET | /api/dynamodb/tables/:table | Describe table (meta + count) |
| DELETE | /api/dynamodb/tables/:table | Delete table |
| PUT | /api/dynamodb/tables/:table/items | Put (upsert) an item |
| GET | /api/dynamodb/tables/:table/items/:key | Get single item by key |
| DELETE | /api/dynamodb/tables/:table/items/:key | Delete single item |
| GET | /api/dynamodb/tables/:table/scan | Scan & return all items |

## Project Structure
```
LocalAWS/
  dynamodb/
    __init__.py
    routes.py
    storage.py
  dynamodb_data/
  templates/
    dynamodb.html
```
