from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(128), nullable=False)
    role = db.Column(
        db.String(20),
        nullable=False,
        default="cashier",
        comment="admin | cashier | waiter",
    )
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # relationships
    shifts = db.relationship("Shift", back_populates="user", lazy="dynamic")
    orders = db.relationship("Order", back_populates="user", lazy="dynamic")
    transactions = db.relationship(
        "Transaction", back_populates="user", lazy="dynamic"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # relationships
    products = db.relationship("Product", back_populates="category", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Category {self.name}>"


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True
    )
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    image_url = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=True)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # relationships
    category = db.relationship("Category", back_populates="products")
    order_items = db.relationship("OrderItem", back_populates="product", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Product {self.name}>"


# ---------------------------------------------------------------------------
# Area
# ---------------------------------------------------------------------------
class Area(db.Model):
    __tablename__ = "areas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # relationships
    tables = db.relationship("Table", back_populates="area", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Area {self.name}>"


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------
class Table(db.Model):
    __tablename__ = "tables"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    area_id = db.Column(
        db.Integer, db.ForeignKey("areas.id"), nullable=False, index=True
    )
    capacity = db.Column(db.Integer, default=4, nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="available",
        comment="available | occupied | reserved",
    )
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # relationships
    area = db.relationship("Area", back_populates="tables")
    orders = db.relationship("Order", back_populates="table", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Table {self.name}>"


# ---------------------------------------------------------------------------
# Shift
# ---------------------------------------------------------------------------
class Shift(db.Model):
    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    start_time = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    opening_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    closing_amount = db.Column(db.Numeric(12, 2), nullable=True)
    note = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="open",
        comment="open | closed",
    )

    # relationships
    user = db.relationship("User", back_populates="shifts")
    orders = db.relationship("Order", back_populates="shift", lazy="dynamic")
    transactions = db.relationship(
        "Transaction", back_populates="shift", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Shift {self.id} - {self.status}>"


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------
class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(
        db.Integer, db.ForeignKey("tables.id"), nullable=False, index=True
    )
    shift_id = db.Column(
        db.Integer, db.ForeignKey("shifts.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    order_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
        comment="pending | confirmed | completed | cancelled",
    )
    total_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    payment_method = db.Column(
        db.String(20),
        nullable=True,
        comment="cash | transfer | card",
    )
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    note = db.Column(db.Text, nullable=True)
    discount_type = db.Column(db.String(20), nullable=True, comment="percent | fixed")
    discount_value = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # relationships
    table = db.relationship("Table", back_populates="orders")
    shift = db.relationship("Shift", back_populates="orders")
    user = db.relationship("User", back_populates="orders")
    items = db.relationship(
        "OrderItem",
        back_populates="order",
        lazy="select",
        cascade="all, delete-orphan",
    )

    @staticmethod
    def generate_order_number() -> str:
        """Tao ma don hang tu dong theo dinh dang ORD-YYYYMMDD-XXXX."""
        now = datetime.now(timezone.utc)
        prefix = now.strftime("ORD-%Y%m%d-")
        last = (
            Order.query.filter(Order.order_number.like(f"{prefix}%"))
            .order_by(Order.id.desc())
            .first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.order_number.split("-")[-1]) + 1
            except ValueError:
                pass
        return f"{prefix}{seq:04d}"

    def __repr__(self) -> str:
        return f"<Order {self.order_number}>"


# ---------------------------------------------------------------------------
# OrderItem
# ---------------------------------------------------------------------------
class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False, index=True
    )
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    note = db.Column(db.String(255), nullable=True)

    # relationships
    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    def __repr__(self) -> str:
        return f"<OrderItem {self.product_id} x{self.quantity}>"


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------
class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(
        db.Integer, db.ForeignKey("shifts.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    type = db.Column(
        db.String(20),
        nullable=False,
        comment="income | expense",
    )
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # relationships
    shift = db.relationship("Shift", back_populates="transactions")
    user = db.relationship("User", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction {self.type} {self.amount}>"


# ---------------------------------------------------------------------------
# ShopSetting
# ---------------------------------------------------------------------------
class ShopSetting(db.Model):
    __tablename__ = "shop_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    @staticmethod
    def get(key, default=""):
        s = ShopSetting.query.filter_by(key=key).first()
        return s.value if s else default

    @staticmethod
    def set(key, value):
        s = ShopSetting.query.filter_by(key=key).first()
        if s:
            s.value = value
        else:
            s = ShopSetting(key=key, value=value)
            db.session.add(s)

    def __repr__(self) -> str:
        return f"<ShopSetting {self.key}>"
