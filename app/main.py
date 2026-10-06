import math
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import db

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Inventory Capture")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

db.init_db()


PER_PAGE_OPTIONS = [25, 50, 100]
DEFAULT_PER_PAGE = 50


def _filter_query(availability_status: str = "", storage_location: str = "", q: str = "",
                  page: int = 1, per_page: int = DEFAULT_PER_PAGE) -> str:
    params = {
        "availability_status": availability_status,
        "storage_location": storage_location,
        "q": q,
        "page": page if page > 1 else "",
        "per_page": per_page if per_page != DEFAULT_PER_PAGE else "",
    }
    params = {k: v for k, v in params.items() if v}
    return ("?" + urlencode(params)) if params else ""


def _int_param(raw, default: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


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
    quantity_on_hand="1", quantity_listed="0", quantity_sold="0",
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
    for field, raw in (("quantity_on_hand", quantity_on_hand),
                       ("quantity_listed", quantity_listed), ("quantity_sold", quantity_sold)):
        try:
            value = int(raw)
            if value < 0:
                raise ValueError
            data[field] = value
        except (ValueError, TypeError):
            data[field] = raw
            errors.append(f"{field.replace('_', ' ').capitalize()} must be a nonnegative whole number.")
    if not errors and data["quantity_listed"] > data["quantity_on_hand"]:
        errors.append("Quantity listed cannot exceed quantity on hand.")
    error = "; ".join(errors) if errors else None
    return data, error


@app.get("/")
def list_view(
    request: Request,
    availability_status: str = "",
    storage_location: str = "",
    q: str = "",
    page: str = "",
    per_page: str = "",
    highlight: str = "",
):
    q = q.strip()
    per_page = _int_param(per_page, DEFAULT_PER_PAGE)
    if per_page not in PER_PAGE_OPTIONS:
        per_page = DEFAULT_PER_PAGE
    filters = dict(availability_status=availability_status, storage_location=storage_location, search=q)

    conn = db.get_connection()
    try:
        total = db.count_items(conn, **filters)
        page_count = max(1, math.ceil(total / per_page))
        if not page and highlight:
            # Open on the page holding a just-saved item rather than page 1.
            position = db.item_position(conn, highlight, **filters)
            page_num = position // per_page + 1 if position is not None else 1
        else:
            page_num = _int_param(page, 1)
        page_num = min(max(page_num, 1), page_count)
        items = db.list_items(conn, **filters, limit=per_page, offset=(page_num - 1) * per_page)
        locations = db.distinct_storage_locations(conn)
    finally:
        conn.close()

    def page_url(n):
        return "/" + _filter_query(availability_status, storage_location, q, n, per_page)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "items": items,
            "locations": locations,
            "statuses": db.ALLOWED_STATUSES,
            "selected_status": availability_status,
            "selected_location": storage_location,
            "q": q,
            "page": page_num,
            "page_count": page_count,
            "per_page": per_page,
            "per_page_options": PER_PAGE_OPTIONS,
            "total": total,
            "first_shown": (page_num - 1) * per_page + 1 if total else 0,
            "last_shown": min(page_num * per_page, total),
            "page_url": page_url,
            "clear_url": "/" + _filter_query(per_page=per_page),
            "highlight": highlight,
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
    quantity_on_hand: str = Form("1"),
    quantity_listed: str = Form("0"),
    quantity_sold: str = Form("0"),
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
        quantity_on_hand=quantity_on_hand, quantity_listed=quantity_listed,
        quantity_sold=quantity_sold,
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
    quantity_on_hand: str = Form("1"),
    quantity_listed: str = Form("0"),
    quantity_sold: str = Form("0"),
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
        quantity_on_hand=quantity_on_hand, quantity_listed=quantity_listed,
        quantity_sold=quantity_sold,
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
    return_q: str = Form(""),
    return_page: str = Form(""),
    return_per_page: str = Form(""),
):
    return_url = "/" + _filter_query(
        return_status, return_location, return_q,
        _int_param(return_page, 1), _int_param(return_per_page, DEFAULT_PER_PAGE),
    )
    if availability_status is not None and availability_status not in db.ALLOWED_STATUSES:
        return RedirectResponse(url=return_url, status_code=303)
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
    return RedirectResponse(url=return_url, status_code=303)


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
