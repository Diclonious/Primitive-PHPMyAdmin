from fastapi import FastAPI, HTTPException, Depends, Form
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from typing import List

from starlette.responses import JSONResponse

from schemas import *
import database
import models
from sqlalchemy import JSON, create_engine
import json
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Column as SaColumn, Integer, String as SaString, Text, Boolean, Date, Float
from sqlalchemy import text

app = FastAPI()

# Create tables if they don't exist
models.Base.metadata.create_all(bind=database.engine)
DATABASE_URL_TEMPLATE = "mysql+pymysql://root:Anabela123!@localhost:3306/anabela"
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


def create_dynamic_session(database_name: str):
    """Creates a SQLAlchemy session for the specified database name."""
    # Ensure the database name is correctly inserted into the URL
    database_url = DATABASE_URL_TEMPLATE.format(database_name=database_name)
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal



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
def create_database(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    existing_database = db.query(models.Database).filter(models.Database.name == name).first()
    if existing_database:
        raise HTTPException(status_code=400, detail="Database with this name already exists")
    new_database = models.Database(name=name)
    db.add(new_database)
    db.commit()
    db.refresh(new_database)
    referer = request.headers.get("referer")
    if referer and referer.endswith("/databases/all"):
        return RedirectResponse(url="/databases/all", status_code=303)

    else:
        return RedirectResponse(url="/", status_code=303)


@app.get("/databases/all")
def list_databases(request: Request, db: Session = Depends(get_db)):
    databases = db.query(models.Database).all()
    return templates.TemplateResponse("databases.html", {"request": request, "databases": databases})


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


@app.post("/databases/{database_id}/delete", response_model=dict)
async def delete_database(request: Request, database_id: int, db: Session = Depends(get_db)):
    # Check if the database exists

    database = db.query(models.Database).filter(models.Database.id == database_id).first()

    if not database:
        raise HTTPException(status_code=404, detail="Database not found")

    # Delete all tables associated with the database
    else:
        db.delete(database)
        for table in database.tables:
            db.delete(table)

    db.commit()
    referer = request.headers.get("referer")
    if referer and referer.endswith("/databases/all"):
        return RedirectResponse(url="/databases/all", status_code=303)

    else:
        return RedirectResponse(url=f"/", status_code=303)


# tables functions


@app.get("/tables/create/{database_id}", response_class=HTMLResponse)  # create get
async def create_table_form(request: Request, database_id: int, db: Session = Depends(get_db)):
    # Fetch databases for the dropdown
    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()
    return templates.TemplateResponse("create_table.html", {
        "request": request,
        "database_id": database_id
    })


@app.post("/tables/")  # create post
def create_table(
        name: str = Form(...),
        primary_key: int = Form(...),
        database_id: int = Form(...),
        column_names: list[str] = Form(...),
        column_types: list[str] = Form(...),
        db: Session = Depends(get_db)
):
    db_table = models.Table(name=name, database_id=database_id)
    db.add(db_table)
    db.commit()
    db.refresh(db_table)

    for i, (col_name, col_type) in enumerate(zip(column_names, column_types)):
        # Map the type string to SQLAlchemy types
        column_type = {
            "INTEGER": Integer,
            "VARCHAR": SaString(255),
            "TEXT": Text,
            "BOOLEAN": Boolean,
            "DATE": Date,
            "FLOAT": Float,
        }[col_type]

        is_primary_key = i == primary_key
        db_column = models.TableColumn(
            name=col_name,
            data_type=col_type,
            table_id=db_table.id,
            is_primary_key=is_primary_key,
        )
        db.add(db_column)

    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()
    if not db_database:
        raise HTTPException(status_code=404, detail="Database not found")

    db.commit()

    return RedirectResponse(url=f"/databases/{database_id}", status_code=302)


@app.get("/tables/{database_id}/{table_id}", response_class=HTMLResponse)  # table details only columns
async def show_table_details(request: Request, database_id: int, table_id: int, db: Session = Depends(get_db)):
    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()  # ova zima cel objekt
    db_table = db.query(models.Table).filter(models.Table.id == table_id,
                                             models.Table.database_id == database_id).first()
    return templates.TemplateResponse("table_details.html", {
        "request": request,
        "database": db_database,
        "table": db_table
    })


@app.post("/tables/{database_id}/{table_id}/delete")  # delete table
async def delete_table(request: Request, database_id: int, table_id: int, db: Session = Depends(get_db)):
    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()  # ova zima cel objekt
    db_table = db.query(models.Table).filter(models.Table.id == table_id,
                                             models.Table.database_id == db_database.id).first()
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
    columns = db.query(models.TableColumn).filter(models.TableColumn.table_id == table_id).all()
    column_list = [{'id': col.id, 'name': col.name, 'data_type': col.data_type.value} for col in columns]
    return templates.TemplateResponse("insert_form.html", {
        "request": request,
        "database": db_database,
        "columns": column_list,
        "table": db_table
    })


@app.post("/tables/{database_id}/{table_id}/insert")
async def insert_into(
        request: Request,
        database_id: int,
        table_id: int,
        db: Session = Depends(get_db),
):
    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()
    db_table = db.query(models.Table).filter(models.Table.id == table_id,
                                             models.Table.database_id == database_id).first()

    if not db_database or not db_table:
        raise HTTPException(status_code=404, detail="Database or Table not found")

    column_data = await request.form()
    row_data = {}
    for key, value in column_data.items():
        if key.startswith("column-"):
            column_id = key.split('-')[-1]  # Extract column id from form input name
            column = db.query(models.TableColumn).filter(models.TableColumn.id == column_id).first()
            if column:
                row_data[column.name] = value
    print(f"Inserting row data: {row_data}")
    # Create a new row object
    new_row = models.Row(table_id=table_id, data=row_data)  # Pass JSON string

    # Add the new row to the database
    db.add(new_row)
    db.commit()

    # Redirect to a success page or back to the table view
    return RedirectResponse(url=f"/tables/{database_id}/{table_id}/viewdata", status_code=303)


# column drop
@app.post("/tables/{table_id}/columns/{column_id}/drop")  # form se koristi samo koga parametarot ne e vo urlto
def drop_column(
        table_id: int,  # Path parameter
        column_id: int,  # Path parameter
        database_id: int = Form(...),  # Form parameter
        db: Session = Depends(get_db)
):
    # Fetch the table and column
    db_column = db.query(models.TableColumn).filter(models.TableColumn.id == column_id).first()
    if not db_column:
        raise HTTPException(status_code=404, detail="Column not found")

    # Delete the column
    db.delete(db_column)
    db.commit()

    return RedirectResponse(url=f"/tables/{database_id}/{table_id}", status_code=302)


# viewdata
@app.get("/tables/{database_id}/{table_id}/viewdata", response_class=HTMLResponse)
async def read_table(request: Request, database_id: int, table_id: int, db: Session = Depends(get_db)):
    database = db.query(models.Database).filter(
        models.Database.id == database_id).first()  # ako nema .first vrakja query a ne objekt

    table = db.query(models.Table).filter(
        models.Table.id == table_id and models.Table.database_id == database.id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    # zimame podatoci preku modelite potoa gi transformirame so schema od pydantic za da gi pratime vo response
    columns = db.query(models.TableColumn).filter(models.TableColumn.table_id == table_id).all()
    rows = db.query(models.Row).filter(models.Row.table_id == table_id).all()

    column_list = [{'id': col.id, 'name': col.name, 'data_type': col.data_type.value} for col in columns]

    row_list = []
    for row in rows:
        print(f"Row ID: {row.id}, Data: {row.data}")
        row_data = row.data if isinstance(row.data, dict) else json.loads(row.data)
        row_list.append({
            'id': row.id,
            'table_id': row.table_id,
            'data': row_data,
            'values': row_data
        })
    return templates.TemplateResponse("view_table_data.html", {
        "table": table,
        "columns": column_list,
        "rows": row_list,
        "database": database,
        "database_id": database_id,
        "request": request
    })


@app.post("/tables/{table_id}/rows/{row_id}/drop")
async def drop_value(
        request: Request,
        table_id: int,
        row_id: int,
        db: Session = Depends(get_db)
):
    form = await request.form()
    database_id = int(form.get('database_id'))  # Retrieve database_id from form

    # Fetch the row
    row = db.query(models.Row).filter(models.Row.id == row_id).first()

    if not row:
        raise HTTPException(status_code=404, detail="Row not found")

    # Drop the row
    db.delete(row)
    db.commit()

    return RedirectResponse(url=f"/tables/{database_id}/{table_id}/viewdata", status_code=303)


@app.get("/tables/{database_id}/{table_id}/rows/{row_id}/edit", response_class=HTMLResponse)
async def edit_row_form(request: Request, database_id: int, table_id: int, row_id: int, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.id == table_id, models.Table.database_id == database_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    row = db.query(models.Row).filter(models.Row.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")

    columns = db.query(models.TableColumn).filter(models.TableColumn.table_id == table_id).all()
    column_list = [{'id': col.id, 'name': col.name, 'data_type': col.data_type.value} for col in columns]

    return templates.TemplateResponse("edit_row.html", {
        "request": request,
        "database": db.query(models.Database).filter(models.Database.id == database_id).first(),
        "table": table,
        "row": row,
        "columns": column_list
    })


@app.post("/tables/{table_id}/rows/{row_id}/update")
async def update_row(
        request: Request,
        table_id: int,
        row_id: int,
        db: Session = Depends(get_db),
):
    form = await request.form()
    database_id = int(form.get('database_id'))
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    row = db.query(models.Row).filter(models.Row.id == row_id).first()

    if not table or not row:
        raise HTTPException(status_code=404, detail="Table or Row not found")

    # Update row data
    row_data = {}
    for key, value in form.items():
        if key.startswith("column-"):
            column_id = key.split('-')[-1]
            column = db.query(models.TableColumn).filter(models.TableColumn.id == column_id).first()
            if column:
                row_data[column.name] = value

    # Update the row's data
    row.data = row_data
    db.commit()

    return RedirectResponse(url=f"/tables/{database_id}/{table_id}/viewdata", status_code=303)


# navbar others

@app.get("/sql")
async def get_sql_page(request: Request):

    return templates.TemplateResponse("sql.html", {"request": request})


@app.post("/sql")
async def post_sql(request: Request, sql_query: str = Form(...), db: Session = Depends(get_db)):
    try:
        # Execute the raw SQL query
        result = db.execute(text(sql_query))
        rows = result.fetchall()
        columns = result.keys()

        # Prepare results for response
        results = [dict(zip(columns, row)) for row in rows]

        return templates.TemplateResponse("sql_results.html", {
            "results": results,
            "request": request
        })
    except Exception as e:
        # Handle errors and return an error message
        return templates.TemplateResponse("sql_results.html", {
            "error_message": str(e),
            "request": request
        })
