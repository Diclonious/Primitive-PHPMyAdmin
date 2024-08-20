from fastapi import FastAPI, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from typing import List
from schemas import *
import database
import models
import schemas

app = FastAPI()

# Create tables if they don't exist
models.Base.metadata.create_all(bind=database.engine)

templates = Jinja2Templates(directory="templates")


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# main page
@app.get("/", response_class=HTMLResponse)
async def show_databases(request: Request, db: Session = Depends(get_db)):
    databases = db.query(models.Database).all()
    return templates.TemplateResponse("rootpage.html", {"request": request, "databases": databases})


# database functions
@app.get("/databases/create", response_class=HTMLResponse)
async def show_form(request: Request):
    # Include the "request" key in the context
    return templates.TemplateResponse("create_database.html", {"request": request})


@app.post("/databases")
def create_database(name: str = Form(...), db: Session = Depends(get_db)):
    existing_database = db.query(models.Database).filter(models.Database.name == name).first()
    if existing_database:
        raise HTTPException(status_code=400, detail="Database with this name already exists")
    new_database = models.Database(name=name)
    db.add(new_database)
    db.commit()
    db.refresh(new_database)
    return RedirectResponse(url="/", status_code=303)


@app.get("/databases/{database_id}", response_class=HTMLResponse)
async def show_database_details(request: Request, database_id: int, db: Session = Depends(get_db)):
    # Fetch the database and its tables
    database = db.query(models.Database).filter(models.Database.id == database_id).first()
    if not database:
        raise HTTPException(status_code=404, detail="Database not found")

    tables = db.query(models.Table).filter(models.Table.database_id == database_id).all()

    return templates.TemplateResponse("database_details.html", {
        "request": request,
        "database": database,
        "tables": tables
    })


# tables functions


@app.get("/tables/create/{database_id}", response_class=HTMLResponse)
async def create_table_form(request: Request, database_id: int, db: Session = Depends(get_db)):
    # Fetch databases for the dropdown
    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()
    return templates.TemplateResponse("create_table.html", {
        "request": request,
        "database_id": database_id
    })


@app.post("/tables/")
def create_table(
        name: str = Form(...),
        database_id: int = Form(...),
        column_names: List[str] = Form(...),
        column_types: List[str] = Form(...),
        db: Session = Depends(get_db)
):
    if len(column_names) != len(column_types):
        raise HTTPException(status_code=400, detail="Column names and types must be of the same length")

    columns = [ColumnCreate(name=column_names[i], data_type=column_types[i]) for i in range(len(column_names))]

    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()
    if not db_database:
        raise HTTPException(status_code=404, detail="Database not found")

    db_table = models.Table(name=name, database_id=database_id)
    db.add(db_table)
    db.commit()
    db.refresh(db_table)

    for column in columns:
        db_column = models.TableColumn(name=column.name, data_type=column.data_type, table_id=db_table.id)
        db.add(db_column)

    db.commit()

    return RedirectResponse(url=f"/databases/{database_id}", status_code=302)


@app.get("/tables/{database_id}/{table_id}", response_class=HTMLResponse)
async def show_table_details(request: Request, database_id: int, table_id: int, db: Session = Depends(get_db)):
    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()  # ova zima cel objekt
    db_table = db.query(models.Table).filter(models.Table.id == table_id,
                                             models.Table.database_id == database_id).first()
    return templates.TemplateResponse("table_details.html", {
        "request": request,
        "database": db_database,
        "table": db_table
    })


@app.post("/tables/{database_id}/{table_id}/delete")
async def delete_table(request: Request, database_id: int, table_id: int, db: Session = Depends(get_db)):
    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()  # ova zima cel objekt
    db_table = db.query(models.Table).filter(models.Table.id == table_id,
                                             models.Table.database_id == database_id).first()
    if db_table:
        db.delete(db_table)
        db.commit()
    else:
        raise HTTPException(status_code=404, detail="Table not found")
    return RedirectResponse(url=f"/databases/{database_id}", status_code=302)


# adding rows

@app.get("/tables/{database_id}/{table_id}/insert")
async def insert_into(request: Request, database_id: int, table_id: int, db: Session = Depends(get_db)):
    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()  # ova zima cel objekt
    db_table = db.query(models.Table).filter(models.Table.id == table_id,
                                             models.Table.database_id == database_id).first()

    return templates.TemplateResponse("insert_form.html", {
        "request": request,
        "database": db_database,
        "table": db_table
    })
