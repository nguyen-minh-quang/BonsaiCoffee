import random
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import cloudinary
import cloudinary.uploader

from app import create_app, db
from app.models import User, Category, Product, Area, Table, Shift, Order, OrderItem, Transaction, ShopSetting

app = create_app()

# Cloudinary config
cloudinary.config(
    cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
    api_key=app.config["CLOUDINARY_API_KEY"],
    api_secret=app.config["CLOUDINARY_API_SECRET"],
)


def upload_from_url(url, name):
    """Download ảnh từ URL rồi upload lên Cloudinary."""
    try:
        print(f"    Uploading: {name}...", end=" ", flush=True)
        result = cloudinary.uploader.upload(
            url,
            folder="brewmanager/products",
            public_id=name,
            overwrite=True,
            transformation=[{"width": 800, "height": 800, "crop": "limit", "quality": "auto"}],
        )
        print("OK")
        return result["secure_url"]
    except Exception as e:
        print(f"FAIL ({e})")
        return None


# Ảnh mẫu từ Unsplash (free, nhỏ 400px)
IMAGES = {
    # Cà phê
    "ca-phe-den": "https://images.unsplash.com/photo-1510707577719-ae7c14805e3a?w=400",
    "ca-phe-sua": "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=400",
    "bac-xiu": "https://images.unsplash.com/photo-1485808191679-5f86510681a2?w=400",
    "cappuccino": "https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=400",
    "latte": "https://images.unsplash.com/photo-1570968915860-54d5c301fa9f?w=400",
    "americano": "https://images.unsplash.com/photo-1521302080334-4bebac2763a6?w=400",
    "espresso": "https://images.unsplash.com/photo-1510591509098-f4fdc6d0ff04?w=400",
    # Trà
    "tra-dao-cam-sa": "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=400",
    "tra-vai": "https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400",
    "tra-sen": "https://images.unsplash.com/photo-1597318181409-cf64d0b5d8a2?w=400",
    "tra-oolong": "https://images.unsplash.com/photo-1564890369478-c89ca6d9cde9?w=400",
    # Nước ép & Sinh tố
    "nuoc-ep-cam": "https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400",
    "nuoc-ep-dua-hau": "https://images.unsplash.com/photo-1595981267035-7b04ca84a82d?w=400",
    "sinh-to-bo": "https://images.unsplash.com/photo-1638176066666-ffb2f013c7dd?w=400",
    "sinh-to-xoai": "https://images.unsplash.com/photo-1623065422902-30a2d299bbe4?w=400",
    # Đá xay
    "chocolate-da-xay": "https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=400",
    "matcha-da-xay": "https://images.unsplash.com/photo-1515823064-d6e0c04616a7?w=400",
    "cookie-da-xay": "https://images.unsplash.com/photo-1577805947697-89e18249d767?w=400",
    # Topping
    "tran-chau-den": "https://images.unsplash.com/photo-1558857563-b371033873b8?w=400",
    "thach-dua": "https://images.unsplash.com/photo-1551024506-0bccd828d307?w=400",
    "kem-cheese": "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=400",
    # Bánh & Snack
    "banh-mi-que": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400",
    "croissant-bo": "https://images.unsplash.com/photo-1530610476181-d83430b64dcd?w=400",
    "banh-tiramisu": "https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=400",
}

with app.app_context():
    db.drop_all()
    db.create_all()

    # --- Users ---
    users = [
        {"username": "admin", "password": "admin123", "full_name": "Quản lý", "role": "admin"},
        {"username": "thungan", "password": "123456", "full_name": "Nguyễn Văn Thu", "role": "cashier"},
        {"username": "phucvu", "password": "123456", "full_name": "Trần Thị Phục", "role": "waiter"},
    ]
    for u in users:
        user = User(username=u["username"], full_name=u["full_name"], role=u["role"])
        user.set_password(u["password"])
        db.session.add(user)

    # --- Categories ---
    cat_cafe = Category(name="Cà phê", sort_order=1)
    cat_tra = Category(name="Trà", sort_order=2)
    cat_nuocep = Category(name="Nước ép & Sinh tố", sort_order=3)
    cat_daxay = Category(name="Đá xay", sort_order=4)
    cat_topping = Category(name="Topping", sort_order=5)
    cat_banh = Category(name="Bánh & Snack", sort_order=6)

    categories = [cat_cafe, cat_tra, cat_nuocep, cat_daxay, cat_topping, cat_banh]
    db.session.add_all(categories)
    db.session.flush()

    # --- Upload ảnh lên Cloudinary ---
    print("\nĐang upload ảnh lên Cloudinary...")
    img_urls = {}
    for key, url in IMAGES.items():
        img_urls[key] = upload_from_url(url, key)

    # --- Products ---
    products = [
        # Cà phê
        Product(name="Cà phê đen", price=25000, category=cat_cafe, image_url=img_urls.get("ca-phe-den")),
        Product(name="Cà phê sữa", price=29000, category=cat_cafe, image_url=img_urls.get("ca-phe-sua")),
        Product(name="Bạc xỉu", price=32000, category=cat_cafe, image_url=img_urls.get("bac-xiu")),
        Product(name="Cappuccino", price=45000, category=cat_cafe, image_url=img_urls.get("cappuccino")),
        Product(name="Latte", price=45000, category=cat_cafe, image_url=img_urls.get("latte")),
        Product(name="Americano", price=39000, category=cat_cafe, image_url=img_urls.get("americano")),
        Product(name="Espresso", price=35000, category=cat_cafe, image_url=img_urls.get("espresso")),
        # Trà
        Product(name="Trà đào cam sả", price=39000, category=cat_tra, image_url=img_urls.get("tra-dao-cam-sa")),
        Product(name="Trà vải", price=35000, category=cat_tra, image_url=img_urls.get("tra-vai")),
        Product(name="Trà sen", price=32000, category=cat_tra, image_url=img_urls.get("tra-sen")),
        Product(name="Trà oolong", price=35000, category=cat_tra, image_url=img_urls.get("tra-oolong")),
        # Nước ép & Sinh tố
        Product(name="Nước ép cam", price=35000, category=cat_nuocep, image_url=img_urls.get("nuoc-ep-cam")),
        Product(name="Nước ép dưa hấu", price=29000, category=cat_nuocep, image_url=img_urls.get("nuoc-ep-dua-hau")),
        Product(name="Sinh tố bơ", price=39000, category=cat_nuocep, image_url=img_urls.get("sinh-to-bo")),
        Product(name="Sinh tố xoài", price=35000, category=cat_nuocep, image_url=img_urls.get("sinh-to-xoai")),
        # Đá xay
        Product(name="Chocolate đá xay", price=49000, category=cat_daxay, image_url=img_urls.get("chocolate-da-xay")),
        Product(name="Matcha đá xay", price=49000, category=cat_daxay, image_url=img_urls.get("matcha-da-xay")),
        Product(name="Cookie đá xay", price=52000, category=cat_daxay, image_url=img_urls.get("cookie-da-xay")),
        # Topping
        Product(name="Trân châu đen", price=10000, category=cat_topping, image_url=img_urls.get("tran-chau-den")),
        Product(name="Thạch dừa", price=8000, category=cat_topping, image_url=img_urls.get("thach-dua")),
        Product(name="Kem cheese", price=15000, category=cat_topping, image_url=img_urls.get("kem-cheese")),
        # Bánh & Snack
        Product(name="Bánh mì que", price=15000, category=cat_banh, image_url=img_urls.get("banh-mi-que")),
        Product(name="Croissant bơ", price=25000, category=cat_banh, image_url=img_urls.get("croissant-bo")),
        Product(name="Bánh tiramisu", price=35000, category=cat_banh, image_url=img_urls.get("banh-tiramisu")),
    ]
    db.session.add_all(products)

    # --- Areas ---
    area_t1 = Area(name="Tầng 1", sort_order=1)
    area_t2 = Area(name="Tầng 2", sort_order=2)
    area_sv = Area(name="Sân vườn", sort_order=3)

    db.session.add_all([area_t1, area_t2, area_sv])
    db.session.flush()

    # --- Tables ---
    tables = []
    for i in range(1, 7):
        tables.append(Table(name=f"Bàn {i:02d}", capacity=4, area=area_t1))
    for i in range(7, 13):
        tables.append(Table(name=f"Bàn {i:02d}", capacity=4, area=area_t2))
    tables.append(Table(name="Bàn 13", capacity=8, area=area_t2))
    for i in range(14, 19):
        tables.append(Table(name=f"Bàn {i:02d}", capacity=4, area=area_sv))

    db.session.add_all(tables)
    db.session.flush()

    # --- Lấy reference sau flush ---
    cashier_user = User.query.filter_by(username="thungan").first()
    waiter_user = User.query.filter_by(username="phucvu").first()
    all_products = Product.query.all()
    all_tables = Table.query.all()

    # --- Shifts, Orders, OrderItems, Transactions (7 ngày gần đây) ---
    print("\nDang tao du lieu shifts, orders, transactions...")
    random.seed(42)
    now = datetime.now(timezone.utc)
    total_shifts = 0
    total_orders = 0
    total_order_items = 0
    total_transactions = 0

    payment_methods = ["cash", "cash", "cash", "transfer", "card"]  # cash nhieu hon

    for day_offset in range(7, 0, -1):
        day = now - timedelta(days=day_offset)
        morning_start = day.replace(hour=7, minute=0, second=0, microsecond=0)
        morning_end = day.replace(hour=14, minute=30, second=0, microsecond=0)
        afternoon_start = day.replace(hour=14, minute=30, second=0, microsecond=0)
        afternoon_end = day.replace(hour=22, minute=0, second=0, microsecond=0)

        # 2 ca moi ngay: sang (thu ngan) + chieu (thu ngan)
        for shift_idx, (s_start, s_end) in enumerate([(morning_start, morning_end), (afternoon_start, afternoon_end)]):
            opening = Decimal(random.choice([500000, 1000000, 1500000]))
            shift = Shift(
                user=cashier_user,
                start_time=s_start,
                end_time=s_end,
                opening_amount=opening,
                closing_amount=opening + Decimal(random.randint(800000, 3000000)),
                status="closed",
                note=f"Ca {'sang' if shift_idx == 0 else 'chieu'} ngay {day.strftime('%d/%m')}",
            )
            db.session.add(shift)
            db.session.flush()
            total_shifts += 1

            # Moi ca co 5-12 don hang
            num_orders = random.randint(5, 12)
            shift_minutes = int((s_end - s_start).total_seconds() / 60)

            for order_idx in range(num_orders):
                # Thoi gian order ngau nhien trong ca
                rand_minutes = random.randint(5, shift_minutes - 10)
                order_time = s_start + timedelta(minutes=rand_minutes)

                # Chon ban ngau nhien
                table = random.choice(all_tables)

                # Tao order number
                order_num = f"HD{order_time.strftime('%y%m%d%H%M%S')}{order_idx:02d}"

                order = Order(
                    table=table,
                    shift=shift,
                    user=random.choice([cashier_user, waiter_user]),
                    order_number=order_num,
                    status="completed",
                    payment_method=random.choice(payment_methods),
                    paid_at=order_time + timedelta(minutes=random.randint(10, 45)),
                    note="",
                    created_at=order_time,
                    updated_at=order_time + timedelta(minutes=random.randint(10, 45)),
                )
                db.session.add(order)
                db.session.flush()

                # Moi don co 1-5 mon
                num_items = random.randint(1, 5)
                chosen_products = random.sample(all_products, min(num_items, len(all_products)))
                order_total = Decimal(0)

                for prod in chosen_products:
                    qty = random.randint(1, 3)
                    item = OrderItem(
                        order=order,
                        product=prod,
                        quantity=qty,
                        unit_price=prod.price,
                        note="",
                    )
                    db.session.add(item)
                    order_total += prod.price * qty
                    total_order_items += 1

                order.total_amount = order_total
                total_orders += 1

            # Moi ca co 1-3 khoan thu/chi
            # Thu
            for _ in range(random.randint(0, 2)):
                t = Transaction(
                    shift=shift,
                    user=cashier_user,
                    type="income",
                    amount=Decimal(random.choice([50000, 100000, 150000, 200000])),
                    description=random.choice([
                        "Khach tra tien no",
                        "Ban nuoc mang di",
                        "Tip khach",
                        "Thu tien gui do",
                    ]),
                    created_at=s_start + timedelta(minutes=random.randint(30, shift_minutes - 30)),
                )
                db.session.add(t)
                total_transactions += 1

            # Chi
            for _ in range(random.randint(0, 2)):
                t = Transaction(
                    shift=shift,
                    user=cashier_user,
                    type="expense",
                    amount=Decimal(random.choice([30000, 50000, 80000, 120000, 200000])),
                    description=random.choice([
                        "Mua da",
                        "Mua sua tuoi",
                        "Mua ly giay",
                        "Sua may pha",
                        "Mua trai cay",
                        "Tien dien nuoc",
                        "Mua khan giay",
                    ]),
                    created_at=s_start + timedelta(minutes=random.randint(30, shift_minutes - 30)),
                )
                db.session.add(t)
                total_transactions += 1

    # --- Ca hom nay (dang mo) ---
    today_start = now.replace(hour=7, minute=0, second=0, microsecond=0)
    current_shift = Shift(
        user=cashier_user,
        start_time=today_start,
        opening_amount=Decimal(1000000),
        status="open",
        note="Ca hom nay",
    )
    db.session.add(current_shift)
    db.session.flush()
    total_shifts += 1

    # 3 don hom nay (1 completed, 2 dang pending tren ban)
    # Don 1: completed
    t1 = all_tables[0]
    order1 = Order(
        table=t1, shift=current_shift, user=cashier_user,
        order_number=f"HD{now.strftime('%y%m%d')}001",
        status="completed", payment_method="cash",
        paid_at=today_start + timedelta(hours=1),
        created_at=today_start + timedelta(minutes=15),
        updated_at=today_start + timedelta(hours=1),
    )
    db.session.add(order1)
    db.session.flush()
    items1_products = random.sample(all_products, 3)
    total1 = Decimal(0)
    for p in items1_products:
        q = random.randint(1, 2)
        db.session.add(OrderItem(order=order1, product=p, quantity=q, unit_price=p.price))
        total1 += p.price * q
        total_order_items += 1
    order1.total_amount = total1
    total_orders += 1

    # Don 2: pending (ban dang co khach)
    t2 = all_tables[2]
    t2.status = "occupied"
    order2 = Order(
        table=t2, shift=current_shift, user=waiter_user,
        order_number=f"HD{now.strftime('%y%m%d')}002",
        status="pending",
        created_at=now - timedelta(minutes=30),
        updated_at=now - timedelta(minutes=30),
    )
    db.session.add(order2)
    db.session.flush()
    items2_products = random.sample(all_products, 4)
    total2 = Decimal(0)
    for p in items2_products:
        q = random.randint(1, 2)
        db.session.add(OrderItem(order=order2, product=p, quantity=q, unit_price=p.price))
        total2 += p.price * q
        total_order_items += 1
    order2.total_amount = total2
    total_orders += 1

    # Don 3: pending (ban khac dang co khach)
    t3 = all_tables[5]
    t3.status = "occupied"
    order3 = Order(
        table=t3, shift=current_shift, user=cashier_user,
        order_number=f"HD{now.strftime('%y%m%d')}003",
        status="pending",
        created_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(minutes=10),
    )
    db.session.add(order3)
    db.session.flush()
    items3_products = random.sample(all_products, 2)
    total3 = Decimal(0)
    for p in items3_products:
        q = 1
        db.session.add(OrderItem(order=order3, product=p, quantity=q, unit_price=p.price))
        total3 += p.price * q
        total_order_items += 1
    order3.total_amount = total3
    total_orders += 1

    # Thu chi hom nay
    db.session.add(Transaction(
        shift=current_shift, user=cashier_user, type="expense",
        amount=Decimal(80000), description="Mua da va sua tuoi",
        created_at=today_start + timedelta(minutes=20),
    ))
    db.session.add(Transaction(
        shift=current_shift, user=cashier_user, type="income",
        amount=Decimal(50000), description="Khach tra tien no hom qua",
        created_at=today_start + timedelta(minutes=45),
    ))
    total_transactions += 2

    # --- Shop Settings ---
    settings_data = [
        ('shop_name', 'BrewManager Coffee'),
        ('shop_address', '123 Nguyễn Huệ, Quận 1, TP.HCM'),
        ('shop_phone', '0909 123 456'),
        ('shop_wifi', 'BrewManager_Free'),
        ('invoice_footer', 'Cảm ơn quý khách! Hẹn gặp lại!'),
    ]
    for k, v in settings_data:
        db.session.add(ShopSetting(key=k, value=v))

    db.session.commit()

    ok_count = sum(1 for v in img_urls.values() if v)
    print(f"\nSeed data thanh cong!")
    print(f"  - 3 users")
    print(f"  - {len(categories)} categories")
    print(f"  - {len(products)} products ({ok_count}/{len(IMAGES)} anh upload OK)")
    print(f"  - 3 areas")
    print(f"  - {len(all_tables)} tables (2 ban dang co khach)")
    print(f"  - {total_shifts} shifts (1 ca dang mo)")
    print(f"  - {total_orders} orders ({total_order_items} order items)")
    print(f"  - {total_transactions} transactions")
