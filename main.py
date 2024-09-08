from fastapi import FastAPI, HTTPException, Depends, Form

from sqlalchemy.orm import Session, sessionmaker
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import csv
from io import StringIO
from fastapi.responses import StreamingResponse

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
@app.get("/tables/{database_id}/{table_id}/export", response_class=StreamingResponse)
async def export_table_to_csv(database_id: int, table_id: int, db: Session = Depends(get_db)):
    # Fetch the database and table
    db_table = db.query(models.Table).filter(
        models.Table.id == table_id,
        models.Table.database_id == database_id
    ).first()

    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")

    # Fetch the columns of the table
    db_columns = db.query(models.TableColumn).filter(models.TableColumn.table_id == table_id).all()

    # Fetch the rows of the table
    db_rows = db.query(models.Row).filter(models.Row.table_id == table_id).all()

    # Create a CSV string buffer
    csv_buffer = StringIO()
    csv_writer = csv.writer(csv_buffer)

    # Write the headers (column names)
    column_names = [col.name for col in db_columns]
    csv_writer.writerow(column_names)

    # Write the rows of the table
    for row in db_rows:
        row_data = json.loads(row.data) if isinstance(row.data, str) else row.data
        csv_writer.writerow([row_data.get(col.name, "") for col in db_columns])

    # Reset buffer position to the start
    csv_buffer.seek(0)

    # Create a StreamingResponse to return the CSV file
    response = StreamingResponse(
        iter([csv_buffer.getvalue()]),
        media_type="text/csv"
    )

    response.headers["Content-Disposition"] = f"attachment; filename={db_table.name}.csv"
    return response

@app.get("/tables/create/{database_id}", response_class=HTMLResponse)  # create get
async def create_table_form(request: Request, database_id: int, db: Session = Depends(get_db)):
    # Fetch databases for the dropdown
    db_database = db.query(models.Database).filter(models.Database.id == database_id).first()
    return templates.TemplateResponse("create_table.html", {
        "request": request,
        "database_id": database_id
    })


@app.post("/tables/")
async def create_table(
        request: Request,
        name: str = Form(...),
        primary_key: Optional[int] = Form(...),
        database_id: int = Form(...),
        column_names: List[str] = Form(...),
        column_types: List[str] = Form(...),
        db: Session = Depends(get_db)
):
    form_data = await request.form()

    db_table = models.Table(name=name, database_id=database_id)
    db.add(db_table)
    db.commit()
    db.refresh(db_table)

    is_nullable = []
    for i in range(len(column_names)):
        nullable_value = form_data.get(f'is_nullable_{i + 1}')
        is_nullable.append(nullable_value)

    print(f"Received column_names: {column_names}")
    print(f"Received column_types: {column_types}")
    print(f"Received is_nullable: {is_nullable}")

    if len(column_names) != len(column_types) or len(column_names) != len(is_nullable):
        raise HTTPException(status_code=400,
                            detail="Column names, column types, and is_nullable lists must have the same length.")

    for i, (col_name, col_type, nullable) in enumerate(zip(column_names, column_types, is_nullable)):
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
        is_nullable_bool = nullable == "1"
        db_column = models.TableColumn(
            name=col_name,
            data_type=col_type,
            table_id=db_table.id,
            is_primary_key=is_primary_key,
            is_nullable=is_nullable_bool,
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
    flag = request.query_params.get("flag")

    if flag == "fail":
        error_message = "Cannot delete primary key!"
        return templates.TemplateResponse("table_details.html", {
            "request": request,
            "database": db_database,
            "table": db_table,
            "error_message": error_message
        })
    else:
        return templates.TemplateResponse("table_details.html", {
            "request": request,
            "database": db_database,
            "table": db_table,
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
    flag = request.query_params.get("flag")
    existing_value = request.query_params.get("existing_value")

    column = request.query_params.get("column")
    column_list = [{'id': col.id, 'name': col.name, 'data_type': col.data_type.value, 'is_nullable': col.is_nullable}
                   for col in columns]
    if flag == 'fail':
        error_message = f"Duplicate Primary Key detected in column '{column}': Existing value = {existing_value}"
        return templates.TemplateResponse("insert_form.html", {
            "request": request,
            "database": db_database,
            "columns": column_list,
            "table": db_table,
            "error_message": error_message,
        })

    return templates.TemplateResponse("insert_form.html", {
        "request": request,
        "database": db_database,
        "columns": column_list,
        "table": db_table,
    })


# add rows
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

    # Query existing rows for duplicate checking
    existing_rows = db.query(models.Row).filter(models.Row.table_id == table_id).all()

    # Extract form data
    form_data = await request.form()
    rows_data = {}

    # Process the form data to get all rows
    for key, value in form_data.items():
        if key.startswith("columns["):
            # Extract row index and column ID using regex
            import re
            match = re.match(r'columns\[(\d+)]\[(\d+)]', key)
            if match:
                row_index, column_id = match.groups()
                row_index = int(row_index)  # Convert row index to an integer
                column_id = int(column_id)  # Convert column ID to an integer

                if row_index not in rows_data:
                    rows_data[row_index] = {}

                column = db.query(models.TableColumn).filter(models.TableColumn.id == column_id).first()
                if column:
                    rows_data[row_index][column.name] = value

                    if column.is_primary_key:
                        # Check for duplicate primary keys
                        for row in existing_rows:
                            existing_row_data = row.data
                            if column.name in existing_row_data and existing_row_data[column.name] == value:
                                return RedirectResponse(
                                    url=f"/tables/{database_id}/{table_id}/insert?flag=fail&existing_value={value}&column={column.name}",
                                    status_code=303
                                )

    # Insert all rows into the database
    for row_data in rows_data.values():
        new_row = models.Row(table_id=table_id, data=row_data)  # Pass JSON string
        db.add(new_row)

    db.commit()

    return RedirectResponse(url=f"/tables/{database_id}/{table_id}/viewdata", status_code=303)


# column drop
@app.post("/tables/{table_id}/columns/{column_id}/drop")  # form se koristi samo koga parametarot ne e vo urlto
def drop_column(
        request: Request,
        table_id: int,  # Path parameter
        column_id: int,  # Path parameter
        database_id: int = Form(...),  # Form parameter
        db: Session = Depends(get_db)
):
    # Fetch the table and column
    db_database = db.query(models.Database).filter(models.Database.id == table_id).first()

    db_column = db.query(models.TableColumn).filter(models.TableColumn.id == column_id).first()
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not db_column:
        raise HTTPException(status_code=404, detail="Column not found")
    if db_column.is_primary_key:
        # Pass the error message to the template
        return RedirectResponse(url=f"/tables/{database_id}/{table_id}?flag=fail", status_code=303)
    else:
        db.delete(db_column)
        db.commit()

        return RedirectResponse(url=f"/tables/{database_id}/{table_id}?flag=success", status_code=303)


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


# drop rows
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


# edit rows
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
@app.get("/sql/{database_id}")
async def get_sql_page(request: Request, database_id: int):
    return templates.TemplateResponse("sql.html", {"request": request, "database_id": database_id})


@app.post("/sql/{database_id}")
async def post_sql(request: Request, database_id: int, sql_query: str = Form(...), db: Session = Depends(get_db)):
    sql_query = sql_query.strip()
    results = []

    try:
        if sql_query.lower() == "show databases;":
            result = db.execute(text(sql_query))
            rows = result.fetchall()
            databases = [row[0] for row in rows]
            results = [{"Database": db} for db in databases]

        elif sql_query.lower().startswith("use "):
            db_name = sql_query.split()[1]
            results = [{"message": f"Attempted to switch to database {db_name}"}]

        elif sql_query.lower().startswith("drop table "):
            table_name = sql_query[len("drop table "):].strip().strip(";")
            table = db.query(models.Table).filter(models.Table.name == table_name).first()

            if not table:
                raise ValueError(f"Table '{table_name}' not found.")
            db.query(models.Row).filter(models.Row.table_id == table.id).delete()

            # Delete dependent columns
            db.query(models.TableColumn).filter(models.TableColumn.table_id == table.id).delete()
            db.query(models.Table).filter(models.Table.name == table_name).delete()
            db.commit()

            results = [{"message": f"Table '{table_name}' dropped successfully."}]

        elif sql_query.lower().startswith("select * from tables where name="):
            dbuse = db.query(models.Database).filter(models.Database.id == database_id).first()
            table_name = sql_query.split("name='")[1].split("'")[0]

            if not dbuse:
                raise ValueError("Database instance not found.")

            table = db.query(models.Table).filter(models.Table.name == table_name,
                                                  models.Table.database_id == dbuse.id).first()
            if not table:
                raise ValueError(f"Table '{table_name}' not found in the database with ID {database_id}.")

            columns = db.query(models.TableColumn).filter(models.TableColumn.table_id == table.id).all()
            columns_info = [
                {
                    "id": col.id,
                    "name": col.name,
                    "data_type": col.data_type,
                    "is_primary_key": col.is_primary_key,
                    "is_nullable": col.is_nullable
                }
                for col in columns
            ]

            rows = db.query(models.Row).filter(models.Row.table_id == table.id).all()
            rows_data = [row.data for row in rows]

            results = {
                "Table": table_name,
                "Columns": columns_info,
                "Rows": rows_data
            }

        elif sql_query.lower().startswith("insert into "):
            parts = sql_query.lower().split("values")
            table_part = parts[0].split("insert into")[1].strip().split("(")[0].strip()
            values_part = parts[1].strip().strip("();")

            table = db.query(models.Table).filter(models.Table.name == table_part).first()
            if not table:
                raise ValueError(f"Table '{table_part}' not found.")

            columns = db.query(models.TableColumn).filter(models.TableColumn.table_id == table.id).all()
            columns_mapping = {col.name: col.id for col in columns}

            values = values_part.split(", ")
            row_data = dict(zip(columns_mapping.keys(), values))

            new_row = models.Row(table_id=table.id, data=row_data)
            db.add(new_row)
            db.commit()

            rows = db.query(models.Row).filter(models.Row.table_id == table.id).all()
            rows_data = [row.data for row in rows]
            columns_info = [{"id": col.id, "name": col.name, "data_type": col.data_type} for col in columns]
            results = {
                "Table": table.name,
                "Columns": columns_info,
                "Rows": rows_data
            }

        else:
            result = db.execute(text(sql_query))
            if result.returns_rows:
                rows = result.fetchall()
                columns = result.keys()
                results = [dict(zip(columns, row)) for row in rows]
            else:
                results = [{"message": "Query executed successfully, but no rows returned."}]

        return templates.TemplateResponse("sql.html", {
            "results": results,
            "request": request,
            "database_id": database_id,
        })

    except Exception as e:
        return templates.TemplateResponse("sql.html", {
            "error_message": str(e),
            "request": request,
            "database_id": database_id
        })
