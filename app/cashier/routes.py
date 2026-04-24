from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps

from flask import Blueprint, abort, jsonify, render_template, redirect, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    Area,
    Category,
    Order,
    OrderItem,
    Product,
    Shift,
    ShopSetting,
    Table,
    Transaction,
)

cashier_bp = Blueprint("cashier", __name__, template_folder="templates")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def cashier_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role not in ("admin", "cashier"):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def _get_open_shift():
    """Tra ve ca dang mo cua user hien tai (neu co)."""
    return Shift.query.filter_by(
        user_id=current_user.id, status="open"
    ).first()


def _generate_order_number():
    """Tao ma hoa don dang HD + timestamp ngan."""
    now = datetime.now(timezone.utc)
    ts = now.strftime("%y%m%d%H%M%S")
    return f"HD{ts}"


def _recalc_order_total(order):
    """Tinh lai tong tien cua order."""
    subtotal = sum(item.quantity * item.unit_price for item in order.items)
    if order.discount_type == "percent" and order.discount_value:
        discount = subtotal * order.discount_value / 100
    elif order.discount_type == "fixed" and order.discount_value:
        discount = order.discount_value
    else:
        discount = 0
    order.total_amount = max(subtotal - discount, 0)


@cashier_bp.context_processor
def inject_current_shift():
    if current_user.is_authenticated and current_user.role in ("admin", "cashier"):
        return {"current_shift": _get_open_shift()}
    return {"current_shift": None}


def _ok(data=None, message="Thành công"):
    return jsonify({"success": True, "data": data, "message": message})


def _err(message="Có lỗi xảy ra", status=400):
    return jsonify({"success": False, "data": None, "message": message}), status


# ---------------------------------------------------------------------------
# Ca lam viec
# ---------------------------------------------------------------------------
@cashier_bp.route("/")
@cashier_required
def index():
    shift = _get_open_shift()
    if shift is None:
        return render_template("cashier/open_shift.html")
    return redirect(url_for("cashier.pos"))


@cashier_bp.route("/shift/open", methods=["POST"])
@cashier_required
def shift_open():
    opening_amount = request.form.get("starting_cash", 0, type=float)
    shift = Shift(
        user_id=current_user.id,
        opening_amount=Decimal(str(opening_amount)),
        status="open",
    )
    db.session.add(shift)
    db.session.commit()
    return redirect(url_for("cashier.pos"))


@cashier_bp.route("/shift/close", methods=["POST"])
@cashier_required
def shift_close():
    shift = _get_open_shift()
    if shift is None:
        return _err("Không có ca đang mở", 404)

    closing_amount = request.form.get("closing_amount", 0, type=float)
    note = request.form.get("note", "")

    shift.closing_amount = Decimal(str(closing_amount))
    shift.note = note
    shift.end_time = datetime.now(timezone.utc)
    shift.status = "closed"
    db.session.commit()
    return redirect(url_for("cashier.index"))


# ---------------------------------------------------------------------------
# POS - Trang chinh
# ---------------------------------------------------------------------------
@cashier_bp.route("/pos")
@cashier_required
def pos():
    shift = _get_open_shift()
    if shift is None:
        return redirect(url_for("cashier.index"))
    return render_template("cashier/pos.html", shift=shift)


# ---------------------------------------------------------------------------
# API - Tables
# ---------------------------------------------------------------------------
@cashier_bp.route("/api/tables")
@cashier_required
def api_tables():
    areas = Area.query.filter_by(is_active=True).order_by(Area.sort_order).all()
    data = []
    for area in areas:
        tables = (
            Table.query.filter_by(area_id=area.id, is_active=True)
            .order_by(Table.sort_order)
            .all()
        )
        tables_data = []
        for t in tables:
            t_data = {
                "id": t.id,
                "name": t.name,
                "capacity": t.capacity,
                "status": t.status,
                "order_id": None,
                "order_total": 0
            }
            if t.status == "occupied":
                order = Order.query.filter_by(table_id=t.id).filter(Order.status.in_(["pending", "confirmed"])).first()
                if order:
                    t_data["order_id"] = order.id
                    t_data["order_total"] = float(order.total_amount)
            tables_data.append(t_data)

        data.append(
            {
                "area_id": area.id,
                "area_name": area.name,
                "tables": tables_data,
            }
        )
    return _ok(data)


# ---------------------------------------------------------------------------
# API - Menu
# ---------------------------------------------------------------------------
@cashier_bp.route("/api/menu")
@cashier_required
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
@cashier_bp.route("/api/order/<int:table_id>")
@cashier_required
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
@cashier_bp.route("/api/order/create", methods=["POST"])
@cashier_required
def api_order_create():
    shift = _get_open_shift()
    if shift is None:
        return _err("Chưa mở ca làm việc", 400)

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
@cashier_bp.route("/api/order/<int:order_id>/add-item", methods=["POST"])
@cashier_required
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
@cashier_bp.route(
    "/api/order/<int:order_id>/remove-item/<int:item_id>", methods=["POST"]
)
@cashier_required
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
@cashier_bp.route(
    "/api/order/<int:order_id>/update-item/<int:item_id>", methods=["POST"]
)
@cashier_required
def api_order_update_item(order_id, item_id):
    order = db.session.get(Order, order_id)
    if order is None:
        return _err("Order không tồn tại", 404)
    if order.status not in ("pending", "confirmed"):
        return _err("Order đã đóng, không thể cập nhật")

    payload = request.get_json(silent=True) or {}
    quantity = payload.get("quantity")
    note = payload.get("note")

    item = OrderItem.query.filter_by(id=item_id, order_id=order_id).first()
    if item is None:
        return _err("Món không tồn tại trong order", 404)

    if quantity is not None:
        if quantity < 1:
            return _err("Số lượng không hợp lệ")
        item.quantity = quantity
    if note is not None:
        item.note = note

    db.session.flush()
    _recalc_order_total(order)
    db.session.commit()

    return _ok(
        {"total_amount": float(order.total_amount)},
        "Cập nhật thành công",
    )


# ---------------------------------------------------------------------------
# API - Thanh toan
# ---------------------------------------------------------------------------
@cashier_bp.route("/api/order/<int:order_id>/pay", methods=["POST"])
@cashier_required
def api_order_pay(order_id):
    order = db.session.get(Order, order_id)
    if order is None:
        return _err("Order không tồn tại", 404)
    if order.status not in ("pending", "confirmed"):
        return _err("Order không ở trạng thái thanh toán được")

    payload = request.get_json(silent=True) or {}
    payment_method = payload.get("payment_method", "cash")
    if payment_method not in ("cash", "transfer", "card"):
        return _err("Phương thức thanh toán không hợp lệ")

    # Chốt order vào ca làm việc hiện tại của thu ngân
    shift = _get_open_shift()
    if shift:
        order.shift_id = shift.id

    order.payment_method = payment_method
    order.paid_at = datetime.now(timezone.utc)
    order.status = "completed"

    # Giai phong ban
    table = db.session.get(Table, order.table_id)
    if table:
        table.status = "available"

    db.session.commit()

    return _ok(
        {
            "order_id": order.id,
            "order_number": order.order_number,
            "total_amount": float(order.total_amount),
            "payment_method": order.payment_method,
        },
        "Thanh toán thành công",
    )


# ---------------------------------------------------------------------------
# API - Giam gia
# ---------------------------------------------------------------------------
@cashier_bp.route("/api/order/<int:order_id>/discount", methods=["POST"])
@cashier_required
def api_order_discount(order_id):
    order = db.session.get(Order, order_id)
    if order is None:
        return _err("Order không tồn tại", 404)
    if order.status not in ("pending", "confirmed"):
        return _err("Order đã đóng")

    payload = request.get_json(silent=True) or {}
    dtype = payload.get("discount_type")
    dvalue = payload.get("discount_value", 0)

    if dtype not in ("percent", "fixed", None, ""):
        return _err("Loại giảm giá không hợp lệ")

    if not dtype or float(dvalue) == 0:
        order.discount_type = None
        order.discount_value = 0
    else:
        order.discount_type = dtype
        order.discount_value = Decimal(str(dvalue))

    _recalc_order_total(order)
    db.session.commit()
    return _ok({"total_amount": float(order.total_amount)}, "Cập nhật giảm giá")


# ---------------------------------------------------------------------------
# Hoa don
# ---------------------------------------------------------------------------
@cashier_bp.route("/invoice/<int:order_id>")
@cashier_required
def invoice(order_id):
    order = db.session.get(Order, order_id)
    if order is None:
        abort(404)
    is_temp = request.args.get("temp") == "1"
    return render_template(
        "cashier/invoice.html",
        order=order,
        is_temp=is_temp,
        shop_name=ShopSetting.get('shop_name', 'Bonsai Coffee'),
        shop_address=ShopSetting.get('shop_address', '26 Đường Bát Tràng, Bát Tràng, Tp.Hà Nội'),
        shop_phone=ShopSetting.get('shop_phone', '0369 986 435'),
        invoice_footer=ShopSetting.get('invoice_footer', 'Cảm ơn quý khách!'),
    )


# ---------------------------------------------------------------------------
# Phieu bep / pha che
# ---------------------------------------------------------------------------
@cashier_bp.route("/kitchen-ticket/<int:order_id>")
@cashier_required
def kitchen_ticket(order_id):
    order = db.session.get(Order, order_id)
    if order is None:
        abort(404)
    return render_template(
        "cashier/kitchen_ticket.html",
        order=order,
        now=datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# API - Chuyen ban
# ---------------------------------------------------------------------------
@cashier_bp.route("/api/order/<int:order_id>/transfer", methods=["POST"])
@cashier_required
def api_order_transfer(order_id):
    order = db.session.get(Order, order_id)
    if order is None:
        return _err("Order không tồn tại", 404)
    if order.status not in ("pending", "confirmed"):
        return _err("Order đã đóng, không thể chuyển bàn")

    payload = request.get_json(silent=True) or {}
    new_table_id = payload.get("new_table_id")
    if not new_table_id:
        return _err("Thiếu new_table_id")

    new_table = db.session.get(Table, new_table_id)
    if new_table is None:
        return _err("Bàn đích không tồn tại", 404)

    # Kiem tra ban dich co order chua
    existing = (
        Order.query.filter_by(table_id=new_table_id)
        .filter(Order.status.in_(["pending", "confirmed"]))
        .first()
    )
    if existing:
        return _err("Bàn đích đã có order chưa thanh toán")

    # Giai phong ban cu
    old_table = db.session.get(Table, order.table_id)
    if old_table:
        old_table.status = "available"

    # Chuyen sang ban moi
    order.table_id = new_table_id
    new_table.status = "occupied"
    db.session.commit()

    return _ok(
        {"order_id": order.id, "new_table_id": new_table_id},
        "Chuyển bàn thành công",
    )


# ---------------------------------------------------------------------------
# API - Gop ban
# ---------------------------------------------------------------------------
@cashier_bp.route("/api/order/merge", methods=["POST"])
@cashier_required
def api_order_merge():
    payload = request.get_json(silent=True) or {}
    source_order_ids = payload.get("source_order_ids", [])
    target_table_id = payload.get("target_table_id")

    if not source_order_ids or not target_table_id:
        return _err("Thiếu source_order_ids hoặc target_table_id")

    target_table = db.session.get(Table, target_table_id)
    if target_table is None:
        return _err("Bàn đích không tồn tại", 404)

    # Tim hoac tao order tren ban dich
    target_order = (
        Order.query.filter_by(table_id=target_table_id)
        .filter(Order.status.in_(["pending", "confirmed"]))
        .first()
    )

    shift = _get_open_shift()
    if shift is None:
        return _err("Chưa mở ca làm việc")

    if target_order is None:
        target_order = Order(
            table_id=target_table_id,
            shift_id=shift.id,
            user_id=current_user.id,
            order_number=_generate_order_number(),
            status="pending",
        )
        db.session.add(target_order)
        db.session.flush()

    for src_id in source_order_ids:
        src_order = db.session.get(Order, src_id)
        if src_order is None or src_order.status not in ("pending", "confirmed"):
            continue
        if src_order.id == target_order.id:
            continue

        # Chuyen tat ca item sang order dich
        for item in src_order.items:
            item.order_id = target_order.id

        # Huy order nguon va giai phong ban
        src_order.status = "cancelled"
        src_table = db.session.get(Table, src_order.table_id)
        if src_table:
            src_table.status = "available"

    db.session.flush()
    _recalc_order_total(target_order)
    target_table.status = "occupied"
    db.session.commit()

    return _ok(
        {"target_order_id": target_order.id, "total_amount": float(target_order.total_amount)},
        "Gộp bàn thành công",
    )


# ---------------------------------------------------------------------------
# Thu chi - Trang
# ---------------------------------------------------------------------------
@cashier_bp.route("/transactions")
@cashier_required
def transactions():
    shift = _get_open_shift()
    return render_template("cashier/transactions.html", shift=shift)


# ---------------------------------------------------------------------------
# API - Danh sach thu/chi trong ca
# ---------------------------------------------------------------------------
@cashier_bp.route("/api/transactions")
@cashier_required
def api_transactions():
    shift = _get_open_shift()
    if shift is None:
        return _ok([], "Chưa mở ca")

    txs = (
        Transaction.query.filter_by(shift_id=shift.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )
    data = [
        {
            "id": t.id,
            "type": t.type,
            "amount": float(t.amount),
            "description": t.description,
            "created_at": t.created_at.strftime("%H:%M %d/%m") if t.created_at else "",
        }
        for t in txs
    ]
    return _ok(data)


# ---------------------------------------------------------------------------
# API - Tao thu/chi
# ---------------------------------------------------------------------------
@cashier_bp.route("/api/transaction/create", methods=["POST"])
@cashier_required
def api_transaction_create():
    shift = _get_open_shift()
    if shift is None:
        return _err("Chưa mở ca làm việc")

    payload = request.get_json(silent=True) or {}
    tx_type = payload.get("type")
    amount = payload.get("amount")
    description = payload.get("description", "")

    if tx_type not in ("income", "expense"):
        return _err("Loại giao dịch không hợp lệ (income/expense)")
    if amount is None or float(amount) <= 0:
        return _err("Số tiền không hợp lệ")

    tx = Transaction(
        shift_id=shift.id,
        user_id=current_user.id,
        type=tx_type,
        amount=Decimal(str(amount)),
        description=description,
    )
    db.session.add(tx)
    db.session.commit()

    return _ok({"transaction_id": tx.id}, "Tạo giao dịch thành công")


# ---------------------------------------------------------------------------
# Trang bao cao ca
# ---------------------------------------------------------------------------
@cashier_bp.route("/shift-report")
@cashier_required
def shift_report():
    shift = _get_open_shift()
    if shift is None:
        return redirect(url_for("cashier.index"))

    completed_orders = (
        Order.query.filter_by(shift_id=shift.id, status="completed")
        .order_by(Order.paid_at.desc())
        .all()
    )
    pending_orders = (
        Order.query.filter_by(shift_id=shift.id)
        .filter(Order.status.in_(["pending", "confirmed"]))
        .all()
    )
    txs = (
        Transaction.query.filter_by(shift_id=shift.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )

    revenue = sum(float(o.total_amount) for o in completed_orders)
    total_income = sum(float(t.amount) for t in txs if t.type == "income")
    total_expense = sum(float(t.amount) for t in txs if t.type == "expense")

    # Thống kê thanh toán theo phương thức
    pay_cash = sum(float(o.total_amount) for o in completed_orders if o.payment_method == "cash")
    pay_transfer = sum(float(o.total_amount) for o in completed_orders if o.payment_method == "transfer")
    pay_card = sum(float(o.total_amount) for o in completed_orders if o.payment_method == "card")

    # Top sản phẩm bán chạy
    from sqlalchemy import func
    top_products = (
        db.session.query(
            Product.name,
            func.sum(OrderItem.quantity).label("total_qty"),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("total_revenue"),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.shift_id == shift.id, Order.status == "completed")
        .group_by(Product.id, Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(10)
        .all()
    )

    template_name = "cashier/shift_report_print.html" if request.args.get("print") == "1" else "cashier/shift_report.html"
    return render_template(
        template_name,
        shift=shift,
        completed_orders=completed_orders,
        pending_orders=pending_orders,
        transactions=txs,
        revenue=revenue,
        total_income=total_income,
        total_expense=total_expense,
        balance=float(shift.opening_amount) + revenue + total_income - total_expense,
        pay_cash=pay_cash,
        pay_transfer=pay_transfer,
        pay_card=pay_card,
        top_products=top_products,
        now=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# API - Tong ket ca
# ---------------------------------------------------------------------------
@cashier_bp.route("/api/shift-summary")
@cashier_required
def api_shift_summary():
    shift = _get_open_shift()
    if shift is None:
        return _err("Chưa mở ca làm việc", 404)

    # Doanh thu tu cac order da thanh toan trong ca
    completed_orders = Order.query.filter_by(
        shift_id=shift.id, status="completed"
    ).all()
    revenue = sum(float(o.total_amount) for o in completed_orders)
    order_count = len(completed_orders)

    # Thu chi trong ca
    txs = Transaction.query.filter_by(shift_id=shift.id).all()
    total_income = sum(float(t.amount) for t in txs if t.type == "income")
    total_expense = sum(float(t.amount) for t in txs if t.type == "expense")

    data = {
        "shift_id": shift.id,
        "start_time": shift.start_time.isoformat(),
        "opening_amount": float(shift.opening_amount),
        "revenue": revenue,
        "order_count": order_count,
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": float(shift.opening_amount) + revenue + total_income - total_expense,
    }
    return _ok(data)
