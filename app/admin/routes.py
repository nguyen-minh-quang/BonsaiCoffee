from functools import wraps
from datetime import datetime, date, timedelta, timezone

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models import User, Category, Product, Area, Table, Order, OrderItem, Transaction, ShopSetting

admin_bp = Blueprint('admin', __name__)


# ---------------------------------------------------------------------------
# Helper: kiểm tra quyền admin
# ---------------------------------------------------------------------------
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ===========================================================================
# DASHBOARD
# ===========================================================================
@admin_bp.route('/')
@admin_required
def dashboard():
    """Trang tổng quan cho admin."""
    total_products = Product.query.count()
    total_categories = Category.query.filter_by(is_active=True).count()
    total_tables = Table.query.count()
    total_employees = User.query.filter_by(is_active=True).count()

    # Doanh thu hôm nay
    today = date.today()
    today_orders = Order.query.filter(
        func.date(Order.paid_at) == today,
        Order.status == 'completed'
    ).all()
    today_revenue = sum(float(o.total_amount) for o in today_orders)

    # Biểu đồ 7 ngày
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        chart_labels.append(d.strftime('%d/%m'))
        day_orders = Order.query.filter(
            func.date(Order.paid_at) == d,
            Order.status == 'completed'
        ).all()
        chart_data.append(sum(float(o.total_amount) for o in day_orders))

    # Top 5 sản phẩm tuần
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    top_products = (
        db.session.query(
            Product.name,
            func.sum(OrderItem.quantity).label('total_qty'),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.paid_at >= week_ago, Order.status == 'completed')
        .group_by(Product.id, Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
        .all()
    )

    return render_template(
        'admin/dashboard.html',
        total_products=total_products,
        total_categories=total_categories,
        total_tables=total_tables,
        total_employees=total_employees,
        today_revenue=today_revenue,
        today_orders=len(today_orders),
        chart_labels=chart_labels,
        chart_data=chart_data,
        top_products=top_products,
    )


# ===========================================================================
# QUẢN LÝ DANH MỤC (Category)
# ===========================================================================
@admin_bp.route('/categories')
@admin_required
def categories():
    """Danh sách danh mục."""
    all_categories = Category.query.order_by(Category.name).all()
    return render_template('admin/categories.html', categories=all_categories)


@admin_bp.route('/categories/create', methods=['POST'])
@admin_required
def category_create():
    """Tạo danh mục mới."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Tên danh mục không được để trống.', 'error')
        return redirect(url_for('admin.categories'))

    if Category.query.filter_by(name=name).first():
        flash('Danh mục này đã tồn tại.', 'error')
        return redirect(url_for('admin.categories'))

    sort_order = request.form.get('sort_order', 0, type=int)
    category = Category(name=name, description=description, sort_order=sort_order)
    db.session.add(category)
    db.session.commit()
    flash('Thêm danh mục thành công.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<int:id>/update', methods=['POST'])
@admin_required
def category_update(id):
    """Cập nhật danh mục."""
    category = Category.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Tên danh mục không được để trống.', 'error')
        return redirect(url_for('admin.categories'))

    existing = Category.query.filter(Category.name == name, Category.id != id).first()
    if existing:
        flash('Tên danh mục đã tồn tại.', 'error')
        return redirect(url_for('admin.categories'))

    category.name = name
    category.description = description
    category.sort_order = request.form.get('sort_order', 0, type=int)
    db.session.commit()
    flash('Cập nhật danh mục thành công.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<int:id>/toggle', methods=['POST'])
@admin_required
def category_toggle(id):
    """Mở/khóa danh mục."""
    category = Category.query.get_or_404(id)
    category.is_active = not category.is_active
    db.session.commit()
    status = "mở khóa" if category.is_active else "ẩn"
    flash(f'Đã {status} danh mục.', 'success')
    return redirect(url_for('admin.categories'))


# ===========================================================================
# QUẢN LÝ MENU / SẢN PHẨM (Product)
# ===========================================================================
@admin_bp.route('/products')
@admin_required
def products():
    """Danh sách sản phẩm, có filter theo danh mục."""
    category_id = request.args.get('category_id', type=int)
    query = Product.query

    if category_id:
        query = query.filter_by(category_id=category_id)

    all_products = query.order_by(Product.name).all()
    all_categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()

    return render_template(
        'admin/products.html',
        products=all_products,
        categories=all_categories,
        selected_category=category_id,
    )


@admin_bp.route('/products/create', methods=['POST'])
@admin_required
def product_create():
    """Tạo sản phẩm mới."""
    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id', type=int)
    price = request.form.get('price', type=float)
    description = request.form.get('description', '').strip()
    image_url = request.form.get('image_url', '').strip()

    if not name:
        flash('Tên sản phẩm không được để trống.', 'error')
        return redirect(url_for('admin.products'))

    if not category_id:
        flash('Vui lòng chọn danh mục.', 'error')
        return redirect(url_for('admin.products'))

    if price is None or price < 0:
        flash('Giá sản phẩm không hợp lệ.', 'error')
        return redirect(url_for('admin.products'))

    product = Product(
        name=name,
        category_id=category_id,
        price=price,
        description=description,
        image_url=image_url,
    )
    db.session.add(product)
    db.session.commit()
    flash('Thêm sản phẩm thành công.', 'success')
    return redirect(url_for('admin.products'))


@admin_bp.route('/products/<int:id>/update', methods=['POST'])
@admin_required
def product_update(id):
    """Cập nhật sản phẩm."""
    product = Product.query.get_or_404(id)

    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id', type=int)
    price = request.form.get('price', type=float)
    description = request.form.get('description', '').strip()
    image_url = request.form.get('image_url', '').strip()

    if not name:
        flash('Tên sản phẩm không được để trống.', 'error')
        return redirect(url_for('admin.products'))

    if not category_id:
        flash('Vui lòng chọn danh mục.', 'error')
        return redirect(url_for('admin.products'))

    if price is None or price < 0:
        flash('Giá sản phẩm không hợp lệ.', 'error')
        return redirect(url_for('admin.products'))

    product.name = name
    product.category_id = category_id
    product.price = price
    product.description = description
    product.image_url = image_url
    db.session.commit()
    flash('Cập nhật sản phẩm thành công.', 'success')
    return redirect(url_for('admin.products'))


@admin_bp.route('/products/<int:id>/delete', methods=['POST'])
@admin_required
def product_delete(id):
    """Xóa cứng sản phẩm nếu chưa phát sinh đơn hàng."""
    from sqlalchemy.exc import IntegrityError
    product = Product.query.get_or_404(id)
    
    try:
        db.session.delete(product)
        db.session.commit()
        flash('Đã xóa vĩnh viễn sản phẩm.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('LỖI: Món này đã từng được khách đặt! Để không làm sai lệch báo cáo doanh thu cũ, bạn không thể xóa vĩnh viễn món này. Hãy gạt công tắc sang trạng thái "Hết hàng" để ẩn món này thay vì xóa!', 'error')
        
    return redirect(url_for('admin.products'))


@admin_bp.route('/products/<int:id>/toggle', methods=['POST'])
@admin_required
def product_toggle(id):
    """Bật/tắt trạng thái is_available của sản phẩm."""
    product = Product.query.get_or_404(id)
    product.is_available = not product.is_available
    db.session.commit()

    status = 'còn hàng' if product.is_available else 'hết hàng'
    flash(f'Sản phẩm "{product.name}" đã chuyển sang {status}.', 'success')
    return redirect(url_for('admin.products'))


# ===========================================================================
# QUẢN LÝ KHU VỰC (Area)
# ===========================================================================
@admin_bp.route('/areas')
@admin_required
def areas():
    """Danh sách khu vực."""
    all_areas = Area.query.filter_by(is_active=True).order_by(Area.name).all()
    return render_template('admin/areas.html', areas=all_areas)


@admin_bp.route('/areas/create', methods=['POST'])
@admin_required
def area_create():
    """Tạo khu vực mới."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Tên khu vực không được để trống.', 'error')
        return redirect(url_for('admin.areas'))

    if Area.query.filter_by(name=name).first():
        flash('Khu vực này đã tồn tại.', 'error')
        return redirect(url_for('admin.areas'))

    sort_order = request.form.get('sort_order', 0, type=int)
    area = Area(name=name, description=description, sort_order=sort_order)
    db.session.add(area)
    db.session.commit()
    flash('Thêm khu vực thành công.', 'success')
    return redirect(url_for('admin.areas'))


@admin_bp.route('/areas/<int:id>/update', methods=['POST'])
@admin_required
def area_update(id):
    """Cập nhật khu vực."""
    area = Area.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Tên khu vực không được để trống.', 'error')
        return redirect(url_for('admin.areas'))

    existing = Area.query.filter(Area.name == name, Area.id != id).first()
    if existing:
        flash('Tên khu vực đã tồn tại.', 'error')
        return redirect(url_for('admin.areas'))

    area.name = name
    area.description = description
    area.sort_order = request.form.get('sort_order', 0, type=int)
    db.session.commit()
    flash('Cập nhật khu vực thành công.', 'success')
    return redirect(url_for('admin.areas'))


@admin_bp.route('/areas/<int:id>/delete', methods=['POST'])
@admin_required
def area_delete(id):
    """Xóa mềm khu vực."""
    area = Area.query.get_or_404(id)
    area.is_active = False
    db.session.commit()
    flash('Đã xóa khu vực.', 'success')
    return redirect(url_for('admin.areas'))


# ===========================================================================
# QUẢN LÝ BÀN (Table)
# ===========================================================================
@admin_bp.route('/tables')
@admin_required
def tables():
    """Danh sách bàn, có filter theo khu vực."""
    area_id = request.args.get('area_id', type=int)
    query = Table.query.filter_by(is_active=True)

    if area_id:
        query = query.filter_by(area_id=area_id)

    all_tables = query.order_by(Table.name).all()
    all_areas = Area.query.filter_by(is_active=True).order_by(Area.name).all()

    return render_template(
        'admin/tables.html',
        tables=all_tables,
        areas=all_areas,
        selected_area=area_id,
    )


@admin_bp.route('/tables/create', methods=['POST'])
@admin_required
def table_create():
    """Tạo bàn mới."""
    name = request.form.get('name', '').strip()
    area_id = request.form.get('area_id', type=int)
    capacity = request.form.get('capacity', type=int)

    if not name:
        flash('Tên bàn không được để trống.', 'error')
        return redirect(url_for('admin.tables'))

    if not area_id:
        flash('Vui lòng chọn khu vực.', 'error')
        return redirect(url_for('admin.tables'))

    table = Table(name=name, area_id=area_id, capacity=capacity or 4)
    db.session.add(table)
    db.session.commit()
    flash('Thêm bàn thành công.', 'success')
    return redirect(url_for('admin.tables'))


@admin_bp.route('/tables/<int:id>/update', methods=['POST'])
@admin_required
def table_update(id):
    """Cập nhật bàn."""
    table = Table.query.get_or_404(id)

    name = request.form.get('name', '').strip()
    area_id = request.form.get('area_id', type=int)
    capacity = request.form.get('capacity', type=int)

    if not name:
        flash('Tên bàn không được để trống.', 'error')
        return redirect(url_for('admin.tables'))

    if not area_id:
        flash('Vui lòng chọn khu vực.', 'error')
        return redirect(url_for('admin.tables'))

    table.name = name
    table.area_id = area_id
    table.capacity = capacity or 4
    db.session.commit()
    flash('Cập nhật bàn thành công.', 'success')
    return redirect(url_for('admin.tables'))


@admin_bp.route('/tables/<int:id>/delete', methods=['POST'])
@admin_required
def table_delete(id):
    """Xóa mềm bàn."""
    table = Table.query.get_or_404(id)
    table.is_active = False
    db.session.commit()
    flash('Đã xóa bàn.', 'success')
    return redirect(url_for('admin.tables'))


# ===========================================================================
# QUẢN LÝ NHÂN VIÊN (User)
# ===========================================================================
@admin_bp.route('/employees')
@admin_required
def employees():
    """Danh sách nhân viên."""
    all_employees = User.query.order_by(User.full_name).all()
    return render_template('admin/employees.html', employees=all_employees)


@admin_bp.route('/employees/create', methods=['POST'])
@admin_required
def employee_create():
    """Tạo nhân viên mới."""
    username = request.form.get('username', '').strip()
    full_name = request.form.get('full_name', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'waiter').strip()
    phone = request.form.get('phone', '').strip()

    if not username or not full_name or not password:
        flash('Vui lòng điền đầy đủ thông tin bắt buộc.', 'error')
        return redirect(url_for('admin.employees'))

    if role not in ('admin', 'cashier', 'waiter'):
        flash('Vai trò không hợp lệ.', 'error')
        return redirect(url_for('admin.employees'))

    if User.query.filter_by(username=username).first():
        flash('Tên đăng nhập đã tồn tại.', 'error')
        return redirect(url_for('admin.employees'))

    user = User(
        username=username,
        full_name=full_name,
        role=role,
        phone=phone,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash('Thêm nhân viên thành công.', 'success')
    return redirect(url_for('admin.employees'))


@admin_bp.route('/employees/<int:id>/update', methods=['POST'])
@admin_required
def employee_update(id):
    """Cập nhật thông tin nhân viên."""
    user = User.query.get_or_404(id)

    full_name = request.form.get('full_name', '').strip()
    role = request.form.get('role', '').strip()
    phone = request.form.get('phone', '').strip()

    if not full_name:
        flash('Họ tên không được để trống.', 'error')
        return redirect(url_for('admin.employees'))

    if role and role not in ('admin', 'cashier', 'waiter'):
        flash('Vai trò không hợp lệ.', 'error')
        return redirect(url_for('admin.employees'))

    user.full_name = full_name
    if role:
        user.role = role
    user.phone = phone
    db.session.commit()
    flash('Cập nhật nhân viên thành công.', 'success')
    return redirect(url_for('admin.employees'))


@admin_bp.route('/employees/<int:id>/toggle', methods=['POST'])
@admin_required
def employee_toggle(id):
    """Khóa/mở khóa nhân viên."""
    user = User.query.get_or_404(id)

    if user.id == current_user.id:
        flash('Không thể tự thao tác với chính mình.', 'error')
        return redirect(url_for('admin.employees'))

    user.is_active = not user.is_active
    db.session.commit()
    status = "mở khóa" if user.is_active else "vô hiệu hóa"
    flash(f'Đã {status} nhân viên.', 'success')
    return redirect(url_for('admin.employees'))


@admin_bp.route('/employees/<int:id>/reset-password', methods=['POST'])
@admin_required
def employee_reset_password(id):
    """Reset mật khẩu nhân viên."""
    user = User.query.get_or_404(id)
    new_password = request.form.get('new_password', '').strip()

    if not new_password:
        flash('Mật khẩu mới không được để trống.', 'error')
        return redirect(url_for('admin.employees'))

    if len(new_password) < 6:
        flash('Mật khẩu phải có ít nhất 6 ký tự.', 'error')
        return redirect(url_for('admin.employees'))

    user.set_password(new_password)
    db.session.commit()
    flash(f'Đã đặt lại mật khẩu cho "{user.full_name}".', 'success')
    return redirect(url_for('admin.employees'))


# ===========================================================================
# BÁO CÁO
# ===========================================================================
@admin_bp.route('/reports')
@admin_required
def reports():
    """Báo cáo doanh thu và thu chi."""
    # Khoảng thời gian mặc định: 30 ngày gần nhất
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')

    today = date.today()

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else today - timedelta(days=30)
    except ValueError:
        start_date = today - timedelta(days=30)

    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else today
    except ValueError:
        end_date = today

    # Doanh thu từ đơn hàng hoàn thành
    orders = Order.query.filter(
        db.func.date(Order.created_at) >= start_date,
        db.func.date(Order.created_at) <= end_date,
        Order.status == 'completed',
    ).order_by(Order.paid_at.desc()).all()

    total_revenue = sum(o.total_amount for o in orders)
    total_orders = len(orders)

    # Thu chi
    transactions = Transaction.query.filter(
        db.func.date(Transaction.created_at) >= start_date,
        db.func.date(Transaction.created_at) <= end_date,
    ).order_by(Transaction.created_at.desc()).all()

    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expense = sum(t.amount for t in transactions if t.type == 'expense')

    return render_template(
        'admin/reports.html',
        orders=orders,
        transactions=transactions,
        total_revenue=total_revenue,
        total_orders=total_orders,
        total_income=total_income,
        total_expense=total_expense,
        start_date=start_date,
        end_date=end_date,
    )


# ===========================================================================
# CÀI ĐẶT QUÁN (ShopSetting)
# ===========================================================================
@admin_bp.route('/settings')
@admin_required
def settings():
    """Trang cài đặt quán."""
    settings = {
        'shop_name': ShopSetting.get('shop_name', 'Bonsai Coffee'),
        'shop_address': ShopSetting.get('shop_address', ''),
        'shop_phone': ShopSetting.get('shop_phone', ''),
        'shop_wifi': ShopSetting.get('shop_wifi', ''),
        'invoice_footer': ShopSetting.get('invoice_footer', 'Cảm ơn quý khách!'),
    }
    return render_template('admin/settings.html', settings=settings)


@admin_bp.route('/settings/update', methods=['POST'])
@admin_required
def settings_update():
    """Cập nhật cài đặt quán."""
    for key in ['shop_name', 'shop_address', 'shop_phone', 'shop_wifi', 'invoice_footer']:
        ShopSetting.set(key, request.form.get(key, ''))
    db.session.commit()
    flash('Cập nhật cài đặt thành công!', 'success')
    return redirect(url_for('admin.settings'))
