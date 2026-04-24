from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.models import (
    Area,
    Category,
    Order,
    OrderItem,
    Product,
    Shift,
    Table,
)

waiter_bp = Blueprint("waiter", __name__, template_folder="templates")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def staff_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role not in ("admin", "cashier", "waiter"):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def _get_open_shift():
    """Tra ve ca dang mo cua bat ky user nao (uu tien ca mo gan nhat)."""
    return Shift.query.filter_by(status="open").order_by(Shift.start_time.desc()).first()


def _generate_order_number():
    """Tao ma hoa don dang HD + timestamp ngan."""
    now = datetime.now(timezone.utc)
    ts = now.strftime("%y%m%d%H%M%S")
    return f"HD{ts}"


def _recalc_order_total(order):
    """Tinh lai tong tien cua order."""
    order.total_amount = sum(
        item.quantity * item.unit_price for item in order.items
    )


def _ok(data=None, message="Thành công"):
    return jsonify({"success": True, "data": data, "message": message})


def _err(message="Có lỗi xảy ra", status=400):
    return jsonify({"success": False, "data": None, "message": message}), status


# ---------------------------------------------------------------------------
# Trang chinh - So do ban
# ---------------------------------------------------------------------------
@waiter_bp.route("/")
@staff_required
def index():
    return render_template("waiter/index.html")


# ---------------------------------------------------------------------------
# Trang order cho ban
# ---------------------------------------------------------------------------
@waiter_bp.route("/order/<int:table_id>")
@staff_required
def order_page(table_id):
    table = db.session.get(Table, table_id)
    if table is None:
        abort(404)
    return render_template("waiter/order.html", table=table)


# ---------------------------------------------------------------------------
# API - Tables
# ---------------------------------------------------------------------------
@waiter_bp.route("/api/tables")
@staff_required
def api_tables():
    areas = Area.query.filter_by(is_active=True).order_by(Area.sort_order).all()
    data = []
    for area in areas:
        tables = (
            Table.query.filter_by(area_id=area.id, is_active=True)
            .order_by(Table.sort_order)
            .all()
        )
        table_list = []
        for t in tables:
            td = {"id": t.id, "name": t.name, "capacity": t.capacity, "status": t.status, "item_count": 0, "total": 0}
            if t.status == "occupied":
                ao = Order.query.filter_by(table_id=t.id).filter(Order.status.in_(["pending", "confirmed"])).first()
                if ao:
                    td["item_count"] = sum(i.quantity for i in ao.items)
                    td["total"] = float(ao.total_amount)
            table_list.append(td)
        data.append({"area_id": area.id, "area_name": area.name, "tables": table_list})
    return _ok(data)


# ---------------------------------------------------------------------------
# API - Menu
# ---------------------------------------------------------------------------
@waiter_bp.route("/api/menu")
@staff_required
def api_menu():
    categories = (
        Category.query.filter_by(is_active=True)
        .order_by(Category.sort_order)
        .all()
    )
    data = []
    for cat in categories:
        products = (
            Product.query.filter_by(category_id=cat.id, is_available=True)
            .order_by(Product.sort_order)
            .all()
        )
        data.append(
            {
                "category_id": cat.id,
                "category_name": cat.name,
                "products": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "price": float(p.price),
                        "image_url": p.image_url,
                        "description": p.description,
                    }
                    for p in products
                ],
            }
        )
    return _ok(data)


# ---------------------------------------------------------------------------
# API - Order cua ban
# ---------------------------------------------------------------------------
@waiter_bp.route("/api/order/<int:table_id>")
@staff_required
def api_order_by_table(table_id):
    order = (
        Order.query.filter_by(table_id=table_id)
        .filter(Order.status.in_(["pending", "confirmed"]))
        .order_by(Order.created_at.desc())
        .first()
    )
    if order is None:
        return _ok(None, "Bàn chưa có order")

    items = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product.name,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "subtotal": float(item.subtotal),
            "note": item.note,
        }
        for item in order.items
    ]
    data = {
        "order_id": order.id,
        "order_number": order.order_number,
        "table_id": order.table_id,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "created_at": order.created_at.isoformat(),
        "note": order.note,
        "items": items,
    }
    return _ok(data)


# ---------------------------------------------------------------------------
# API - Tao order
# ---------------------------------------------------------------------------
@waiter_bp.route("/api/order/create", methods=["POST"])
@staff_required
def api_order_create():
    shift = _get_open_shift()
    if shift is None:
        return _err("Chưa có ca làm việc nào được mở", 400)

    payload = request.get_json(silent=True) or {}
    table_id = payload.get("table_id")
    items_data = payload.get("items", [])

    if not table_id:
        return _err("Thiếu table_id")

    table = db.session.get(Table, table_id)
    if table is None:
        return _err("Bàn không tồn tại", 404)

    # Kiem tra ban da co order chua thanh toan
    existing = (
        Order.query.filter_by(table_id=table_id)
        .filter(Order.status.in_(["pending", "confirmed"]))
        .first()
    )
    if existing:
        return _err("Bàn đã có order chưa thanh toán", 400)

    order = Order(
        table_id=table_id,
        shift_id=shift.id,
        user_id=current_user.id,
        order_number=_generate_order_number(),
        status="pending",
    )
    db.session.add(order)

    for item in items_data:
        product = db.session.get(Product, item.get("product_id"))
        if product is None or not product.is_available:
            continue
        oi = OrderItem(
            order=order,
            product_id=product.id,
            quantity=item.get("quantity", 1),
            unit_price=product.price,
            note=item.get("note", ""),
        )
        db.session.add(oi)

    db.session.flush()
    _recalc_order_total(order)

    # Cap nhat trang thai ban
    table.status = "occupied"
    db.session.commit()

    return _ok(
        {"order_id": order.id, "order_number": order.order_number},
        "Tạo order thành công",
    )


# ---------------------------------------------------------------------------
# API - Them mon
# ---------------------------------------------------------------------------
@waiter_bp.route("/api/order/<int:order_id>/add-item", methods=["POST"])
@staff_required
def api_order_add_item(order_id):
    order = db.session.get(Order, order_id)
    if order is None:
        return _err("Order không tồn tại", 404)
    if order.status not in ("pending", "confirmed"):
        return _err("Order đã đóng, không thể thêm món")

    payload = request.get_json(silent=True) or {}
    product_id = payload.get("product_id")
    quantity = payload.get("quantity", 1)
    note = payload.get("note", "")

    product = db.session.get(Product, product_id)
    if product is None or not product.is_available:
        return _err("Sản phẩm không tồn tại hoặc đã hết", 404)

    oi = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=quantity,
        unit_price=product.price,
        note=note,
    )
    db.session.add(oi)
    db.session.flush()
    _recalc_order_total(order)
    db.session.commit()

    return _ok(
        {"item_id": oi.id, "total_amount": float(order.total_amount)},
        "Thêm món thành công",
    )


# ---------------------------------------------------------------------------
# API - Xoa mon
# ---------------------------------------------------------------------------
@waiter_bp.route(
    "/api/order/<int:order_id>/remove-item/<int:item_id>", methods=["POST"]
)
@staff_required
def api_order_remove_item(order_id, item_id):
    order = db.session.get(Order, order_id)
    if order is None:
        return _err("Order không tồn tại", 404)
    if order.status not in ("pending", "confirmed"):
        return _err("Order đã đóng, không thể xóa món")

    item = OrderItem.query.filter_by(id=item_id, order_id=order_id).first()
    if item is None:
        return _err("Món không tồn tại trong order", 404)

    db.session.delete(item)
    db.session.flush()
    _recalc_order_total(order)
    db.session.commit()

    return _ok(
        {"total_amount": float(order.total_amount)},
        "Xóa món thành công",
    )


# ---------------------------------------------------------------------------
# API - Cap nhat so luong
# ---------------------------------------------------------------------------
@waiter_bp.route(
    "/api/order/<int:order_id>/update-item/<int:item_id>", methods=["POST"]
)
@staff_required
def api_order_update_item(order_id, item_id):
    order = db.session.get(Order, order_id)
    if order is None:
        return _err("Order không tồn tại", 404)
    if order.status not in ("pending", "confirmed"):
        return _err("Order đã đóng, không thể cập nhật")

    payload = request.get_json(silent=True) or {}

    item = OrderItem.query.filter_by(id=item_id, order_id=order_id).first()
    if item is None:
        return _err("Món không tồn tại trong order", 404)
    
    quantity = payload.get("quantity")
    if quantity is not None:
        if quantity < 1:
            return _err("Số lượng không hợp lệ")
        item.quantity = quantity

    if "note" in payload:
        item.note = payload.get("note", "")

    db.session.flush()
    _recalc_order_total(order)
    db.session.commit()

    return _ok(
        {"total_amount": float(order.total_amount)},
        "Cập nhật thành công",
    )
