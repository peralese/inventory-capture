from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import db

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Inventory Capture")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

db.init_db()


def _filter_query(availability_status: str, storage_location: str) -> str:
    params = []
    if availability_status:
        params.append(f"availability_status={availability_status}")
    if storage_location:
        params.append(f"storage_location={storage_location}")
    return ("?" + "&".join(params)) if params else ""


def _parse_float_field(raw: str, label: str, errors: list):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        errors.append(f"Invalid number for {label}: {raw!r}")
        return None


def _build_item_data(
    *,
    name, category, storage_location, availability_status, condition, photo_on_file, notes,
    acquired_date, acquired_from, acquisition_cost, listed, listing_platform, listing_price,
    listing_date, sold_date, sold_price, fees_shipping_cost, net_profit, final_disposition,
):
    errors = []
    if availability_status not in db.ALLOWED_STATUSES:
        errors.append(f"Invalid availability_status: {availability_status!r}")

    data = {
        "name": name,
        "category": category,
        "storage_location": storage_location,
        "availability_status": availability_status,
        "condition": condition,
        "photo_on_file": bool(photo_on_file),
        "notes": notes,
        "acquired_date": acquired_date,
        "acquired_from": acquired_from,
        "acquisition_cost": _parse_float_field(acquisition_cost, "Acquisition Cost", errors),
        "listed": bool(listed),
        "listing_platform": listing_platform,
        "listing_price": _parse_float_field(listing_price, "Listing Price", errors),
        "listing_date": listing_date,
        "sold_date": sold_date,
        "sold_price": _parse_float_field(sold_price, "Sold Price", errors),
        "fees_shipping_cost": _parse_float_field(fees_shipping_cost, "Fees/Shipping Cost", errors),
        "net_profit": _parse_float_field(net_profit, "Net Profit", errors),
        "final_disposition": final_disposition,
    }
    error = "; ".join(errors) if errors else None
    return data, error


@app.get("/")
def list_view(request: Request, availability_status: str = "", storage_location: str = ""):
    conn = db.get_connection()
    try:
        items = db.list_items(conn, availability_status, storage_location)
        locations = db.distinct_storage_locations(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "items": items,
            "locations": locations,
            "statuses": db.ALLOWED_STATUSES,
            "selected_status": availability_status,
            "selected_location": storage_location,
        },
    )


@app.get("/items/new")
def new_item_form(request: Request):
    return templates.TemplateResponse(
        "item_form.html",
        {
            "request": request,
            "item": None,
            "statuses": db.ALLOWED_STATUSES,
            "error": None,
        },
    )


@app.post("/items/new")
def create_item(
    request: Request,
    name: str = Form(...),
    category: str = Form(""),
    storage_location: str = Form(""),
    availability_status: str = Form(...),
    condition: str = Form(""),
    photo_on_file: str = Form(None),
    notes: str = Form(""),
    acquired_date: str = Form(""),
    acquired_from: str = Form(""),
    acquisition_cost: str = Form(""),
    listed: str = Form(None),
    listing_platform: str = Form(""),
    listing_price: str = Form(""),
    listing_date: str = Form(""),
    sold_date: str = Form(""),
    sold_price: str = Form(""),
    fees_shipping_cost: str = Form(""),
    net_profit: str = Form(""),
    final_disposition: str = Form(""),
):
    data, error = _build_item_data(
        name=name, category=category, storage_location=storage_location,
        availability_status=availability_status, condition=condition,
        photo_on_file=photo_on_file, notes=notes,
        acquired_date=acquired_date, acquired_from=acquired_from,
        acquisition_cost=acquisition_cost, listed=listed,
        listing_platform=listing_platform, listing_price=listing_price,
        listing_date=listing_date, sold_date=sold_date, sold_price=sold_price,
        fees_shipping_cost=fees_shipping_cost, net_profit=net_profit,
        final_disposition=final_disposition,
    )
    if error:
        return templates.TemplateResponse(
            "item_form.html",
            {"request": request, "item": data, "statuses": db.ALLOWED_STATUSES, "error": error},
            status_code=400,
        )

    conn = db.get_connection()
    try:
        item_id = db.create_item(conn, data)
    finally:
        conn.close()
    return RedirectResponse(url=f"/?highlight={item_id}", status_code=303)


@app.get("/items/{item_id}/edit")
def edit_item_form(request: Request, item_id: str):
    conn = db.get_connection()
    try:
        item = db.get_item(conn, item_id)
    finally:
        conn.close()
    if item is None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "item_form.html",
        {
            "request": request,
            "item": item,
            "statuses": db.ALLOWED_STATUSES,
            "error": None,
        },
    )


@app.post("/items/{item_id}/edit")
def update_item(
    request: Request,
    item_id: str,
    name: str = Form(...),
    category: str = Form(""),
    storage_location: str = Form(""),
    availability_status: str = Form(...),
    condition: str = Form(""),
    photo_on_file: str = Form(None),
    notes: str = Form(""),
    acquired_date: str = Form(""),
    acquired_from: str = Form(""),
    acquisition_cost: str = Form(""),
    listed: str = Form(None),
    listing_platform: str = Form(""),
    listing_price: str = Form(""),
    listing_date: str = Form(""),
    sold_date: str = Form(""),
    sold_price: str = Form(""),
    fees_shipping_cost: str = Form(""),
    net_profit: str = Form(""),
    final_disposition: str = Form(""),
):
    data, error = _build_item_data(
        name=name, category=category, storage_location=storage_location,
        availability_status=availability_status, condition=condition,
        photo_on_file=photo_on_file, notes=notes,
        acquired_date=acquired_date, acquired_from=acquired_from,
        acquisition_cost=acquisition_cost, listed=listed,
        listing_platform=listing_platform, listing_price=listing_price,
        listing_date=listing_date, sold_date=sold_date, sold_price=sold_price,
        fees_shipping_cost=fees_shipping_cost, net_profit=net_profit,
        final_disposition=final_disposition,
    )
    if error:
        data["item_id"] = item_id
        return templates.TemplateResponse(
            "item_form.html",
            {"request": request, "item": data, "statuses": db.ALLOWED_STATUSES, "error": error},
            status_code=400,
        )

    conn = db.get_connection()
    try:
        db.update_item(conn, item_id, data)
    finally:
        conn.close()
    return RedirectResponse(url=f"/?highlight={item_id}", status_code=303)


@app.post("/items/{item_id}/quick-update")
def quick_update(
    item_id: str,
    availability_status: str = Form(None),
    storage_location: str = Form(None),
    return_status: str = Form(""),
    return_location: str = Form(""),
):
    if availability_status is not None and availability_status not in db.ALLOWED_STATUSES:
        return RedirectResponse(
            url=f"/{_filter_query(return_status, return_location)}", status_code=303
        )
    conn = db.get_connection()
    try:
        db.quick_update_item(
            conn,
            item_id,
            availability_status=availability_status,
            storage_location=storage_location,
        )
    finally:
        conn.close()
    return RedirectResponse(
        url=f"/{_filter_query(return_status, return_location)}", status_code=303
    )


@app.get("/items/{item_id}/delete")
def delete_item_form(request: Request, item_id: str):
    conn = db.get_connection()
    try:
        item = db.get_item(conn, item_id)
    finally:
        conn.close()
    if item is None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "delete_item.html", {"request": request, "item": item}
    )


@app.post("/items/{item_id}/delete")
def delete_item(item_id: str):
    conn = db.get_connection()
    try:
        db.delete_item(conn, item_id)
    finally:
        conn.close()
    return RedirectResponse(url="/", status_code=303)
