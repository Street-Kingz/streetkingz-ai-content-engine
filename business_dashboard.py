import csv
import os
import sqlite3
from datetime import datetime

DATABASE_FILE = "data/street_kingz.db"

TIKTOK_FEE_RATE = 0.15
PACKAGING_PER_ORDER = 0.35
POSTAGE_COST_PER_ORDER = 3.08

SK_COGS = {
    "TS800": 4.11,
    "TS1200": 4.76,
    "CORAL2PK": 1.74,
    "WAFFLE": 1.36,
    "WM": 2.05,
    "WM2PK": 4.10,
    "XLBRUSH": 1.88,
    "SLIMBRUSH": 1.74,
    "BF": 1.08,
    "MSP": 1.15,
    "MSP-4PK": 4.60,
    "SDB-N": 16.89,
    "STUBBY": 9.17,
    "WHG4PK": 4.08,
    "ORIGIN-SHAMPOO": 5.45,
    "ORIGIN-MULTICLEAN": 5.07,
    "ORIGIN-GLASS": 5.19,
}

PRODUCT_NAME_COGS = {
    "barrel brushes": 3.62,
    "xl barrel brush": 1.88,
    "small barrel brush": 1.74,
    "slim wheel brush": 1.74,
    "foam cannon": 16.89,
    "foam lance": 16.89,
    "1200gsm": 4.76,
    "800gsm": 4.11,
    "wash mitt": 2.05,
    "scrub pads": 4.60,
    "waffle": 1.36,
    "glass cloth": 1.36,
}

TIKTOK_ORDER_REQUIRED_COLUMNS = [
    "Order ID",
    "Seller SKU",
    "Product Name",
    "Variation",
    "Quantity",
    "SKU Subtotal After Discount",
    "Shipping Fee After Discount",
]

TIKTOK_ORDER_DATE_COLUMNS = [
    "Created Time",
    "Order Creation Date",
    "Paid Time",
]


def get_db_connection():
    os.makedirs("data", exist_ok=True)
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_at TEXT,
            order_date TEXT,
            order_id TEXT,
            sku TEXT,
            product TEXT,
            variation TEXT,
            quantity INTEGER,
            revenue REAL,
            shipping_charged REAL,
            cogs REAL,
            gross_profit REAL,
            UNIQUE(order_id, sku, variation)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ad_spend (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spend_date TEXT UNIQUE,
            ad_spend REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_catalogue (
            sku TEXT PRIMARY KEY,
            product_name TEXT,
            clean_name TEXT,
            category TEXT,
            selling_price REAL,
            cogs REAL,
            gross_margin REAL,
            current_stock INTEGER,
            is_bundle INTEGER,
            is_hero_product INTEGER,
            content_priority INTEGER,
            notes TEXT
        )
    """)

    connection.commit()
    connection.close()


def money_to_float(value):
    if value is None:
        return 0.0

    value = str(value)
    value = value.replace("GBP", "")
    value = value.replace("£", "")
    value = value.replace(",", "")
    value = value.strip()

    try:
        return float(value)
    except ValueError:
        return 0.0


def safe_int(value, fallback=1):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def checkbox_to_int(value):
    return 1 if value in ["1", "on", "true", "yes"] else 0


def validate_tiktok_order_headers(fieldnames, require_date=False):
    headers = set(fieldnames or [])
    missing = [
        column for column in TIKTOK_ORDER_REQUIRED_COLUMNS
        if column not in headers
    ]

    if require_date and not any(column in headers for column in TIKTOK_ORDER_DATE_COLUMNS):
        missing.append("one of: " + ", ".join(TIKTOK_ORDER_DATE_COLUMNS))

    if missing:
        raise ValueError(
            "TikTok Orders CSV is missing required column(s): "
            + ", ".join(missing)
        )


def get_catalogue_unit_cogs(sku, product_name):
    init_database()
    connection = get_db_connection()
    cursor = connection.cursor()

    sku = (sku or "").strip()
    product_name = (product_name or "").strip()

    row = None

    if sku:
        cursor.execute("""
            SELECT cogs
            FROM product_catalogue
            WHERE sku = ?
              AND cogs > 0
            LIMIT 1
        """, (sku,))
        row = cursor.fetchone()

    if not row and product_name:
        product_key = product_name.lower()
        cursor.execute("""
            SELECT cogs
            FROM product_catalogue
            WHERE (
                lower(product_name) = ?
                OR lower(clean_name) = ?
            )
              AND cogs > 0
            LIMIT 1
        """, (
            product_key,
            product_key,
        ))
        row = cursor.fetchone()

    connection.close()

    if row:
        return row["cogs"]

    return None


def get_order_date(row):
    raw_date = (
        row.get("Created Time")
        or row.get("Order Creation Date")
        or row.get("Paid Time")
        or ""
    ).strip()

    if not raw_date:
        return ""

    raw_date = raw_date.split(" ")[0].strip()

    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
    ]

    for date_format in date_formats:
        try:
            return datetime.strptime(raw_date, date_format).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return raw_date

def get_product_cogs(row):
    sku = (row.get("Seller SKU") or "").strip()
    product_name = (row.get("Product Name") or "").lower()
    quantity = safe_int(row.get("Quantity"), 1)
    catalogue_cogs = get_catalogue_unit_cogs(sku, product_name)

    if catalogue_cogs is not None:
        return catalogue_cogs * quantity

    if sku in SK_COGS:
        return SK_COGS[sku] * quantity

    for keyword, cogs in PRODUCT_NAME_COGS.items():
        if keyword in product_name:
            return cogs * quantity

    return 0.0


def get_catalogue_products():
    init_database()
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM product_catalogue
        ORDER BY is_hero_product DESC, content_priority DESC, clean_name, sku
    """)
    products = [dict(row) for row in cursor.fetchall()]
    connection.close()

    return products


def get_catalogue_product(sku):
    init_database()
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM product_catalogue
        WHERE sku = ?
    """, ((sku or "").strip(),))
    row = cursor.fetchone()
    connection.close()

    if row:
        return dict(row)

    return None


def save_catalogue_product(form):
    sku = (form.get("sku") or "").strip()

    if not sku:
        raise ValueError("SKU is required.")

    selling_price = money_to_float(form.get("selling_price"))
    cogs = money_to_float(form.get("cogs"))
    gross_margin = 0.0

    if selling_price > 0:
        gross_margin = ((selling_price - cogs) / selling_price) * 100

    product = {
        "sku": sku,
        "product_name": (form.get("product_name") or "").strip(),
        "clean_name": (form.get("clean_name") or "").strip(),
        "category": (form.get("category") or "").strip(),
        "selling_price": selling_price,
        "cogs": cogs,
        "gross_margin": gross_margin,
        "current_stock": safe_int(form.get("current_stock"), 0),
        "is_bundle": checkbox_to_int(form.get("is_bundle")),
        "is_hero_product": checkbox_to_int(form.get("is_hero_product")),
        "content_priority": safe_int(form.get("content_priority"), 0),
        "notes": (form.get("notes") or "").strip(),
    }

    init_database()
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO product_catalogue (
            sku,
            product_name,
            clean_name,
            category,
            selling_price,
            cogs,
            gross_margin,
            current_stock,
            is_bundle,
            is_hero_product,
            content_priority,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sku)
        DO UPDATE SET
            product_name = excluded.product_name,
            clean_name = excluded.clean_name,
            category = excluded.category,
            selling_price = excluded.selling_price,
            cogs = excluded.cogs,
            gross_margin = excluded.gross_margin,
            current_stock = excluded.current_stock,
            is_bundle = excluded.is_bundle,
            is_hero_product = excluded.is_hero_product,
            content_priority = excluded.content_priority,
            notes = excluded.notes
    """, (
        product["sku"],
        product["product_name"],
        product["clean_name"],
        product["category"],
        product["selling_price"],
        product["cogs"],
        product["gross_margin"],
        product["current_stock"],
        product["is_bundle"],
        product["is_hero_product"],
        product["content_priority"],
        product["notes"],
    ))

    connection.commit()
    connection.close()

    return product


def analyse_tiktok_orders(file, ad_spend):
    decoded = file.stream.read().decode("utf-8-sig")
    reader = csv.DictReader(decoded.splitlines())
    validate_tiktok_order_headers(reader.fieldnames)
    rows = list(reader)

    total_revenue = 0.0
    total_cogs = 0.0
    total_shipping_charged = 0.0
    order_ids = set()
    product_rows = []
    missing_cogs = []

    for row in rows:
        order_id = row.get("Order ID", "").strip()
        if order_id:
            order_ids.add(order_id)

        revenue = money_to_float(row.get("SKU Subtotal After Discount"))
        shipping_charged = money_to_float(row.get("Shipping Fee After Discount"))
        cogs = get_product_cogs(row)

        total_revenue += revenue
        total_shipping_charged += shipping_charged
        total_cogs += cogs

        if cogs == 0:
            missing_cogs.append({
                "sku": row.get("Seller SKU", ""),
                "product": row.get("Product Name", ""),
                "variation": row.get("Variation", ""),
            })

        product_rows.append({
            "order_id": order_id,
            "sku": row.get("Seller SKU", ""),
            "product": row.get("Product Name", ""),
            "variation": row.get("Variation", ""),
            "qty": row.get("Quantity", ""),
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": revenue - cogs,
        })

    order_count = len(order_ids)
    tiktok_fees = total_revenue * TIKTOK_FEE_RATE
    postage_cost = order_count * POSTAGE_COST_PER_ORDER
    packaging_cost = order_count * PACKAGING_PER_ORDER

    profit_before_ads = (
        total_revenue
        + total_shipping_charged
        - total_cogs
        - tiktok_fees
        - postage_cost
        - packaging_cost
    )

    net_profit = profit_before_ads - ad_spend

    profit_per_ad_pound = 0.0
    if ad_spend > 0:
        profit_per_ad_pound = net_profit / ad_spend

    return {
        "order_count": order_count,
        "line_count": len(rows),
        "revenue": total_revenue,
        "shipping_charged": total_shipping_charged,
        "cogs": total_cogs,
        "tiktok_fees": tiktok_fees,
        "postage_cost": postage_cost,
        "packaging_cost": packaging_cost,
        "ad_spend": ad_spend,
        "profit_before_ads": profit_before_ads,
        "net_profit": net_profit,
        "profit_per_ad_pound": profit_per_ad_pound,
        "product_rows": product_rows,
        "missing_cogs": missing_cogs,
    }


def import_tiktok_orders(file, total_ad_spend):
    decoded = file.stream.read().decode("utf-8-sig")
    reader = csv.DictReader(decoded.splitlines())
    validate_tiktok_order_headers(reader.fieldnames, require_date=True)
    rows = list(reader)

    init_database()

    connection = get_db_connection()
    cursor = connection.cursor()

    imported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    imported_count = 0
    skipped_duplicates = 0
    order_dates = set()
    missing_cogs = []

    for row in rows:
        order_date = get_order_date(row)
        order_id = (row.get("Order ID") or "").strip()
        sku = (row.get("Seller SKU") or "").strip()
        product = row.get("Product Name", "")
        variation = row.get("Variation", "")
        quantity = safe_int(row.get("Quantity"), 1)
        revenue = money_to_float(row.get("SKU Subtotal After Discount"))
        shipping_charged = money_to_float(row.get("Shipping Fee After Discount"))
        cogs = get_product_cogs(row)
        gross_profit = revenue - cogs

        if order_date:
            order_dates.add(order_date)

        if cogs == 0:
            missing_cogs.append({
                "sku": sku,
                "product": product,
                "variation": variation,
            })

        try:
            cursor.execute("""
                INSERT INTO order_lines (
                    imported_at,
                    order_date,
                    order_id,
                    sku,
                    product,
                    variation,
                    quantity,
                    revenue,
                    shipping_charged,
                    cogs,
                    gross_profit
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                imported_at,
                order_date,
                order_id,
                sku,
                product,
                variation,
                quantity,
                revenue,
                shipping_charged,
                cogs,
                gross_profit,
            ))
            imported_count += 1
        except sqlite3.IntegrityError:
            skipped_duplicates += 1

    sorted_dates = sorted(order_dates)

    if sorted_dates and total_ad_spend > 0:
        daily_spend = total_ad_spend / len(sorted_dates)

        for spend_date in sorted_dates:
            cursor.execute("""
                INSERT INTO ad_spend (spend_date, ad_spend)
                VALUES (?, ?)
                ON CONFLICT(spend_date)
                DO UPDATE SET ad_spend = excluded.ad_spend
            """, (
                spend_date,
                round(daily_spend, 2),
            ))

    connection.commit()
    connection.close()

    return {
        "imported_count": imported_count,
        "skipped_duplicates": skipped_duplicates,
        "date_from": sorted_dates[0] if sorted_dates else "",
        "date_to": sorted_dates[-1] if sorted_dates else "",
        "date_count": len(sorted_dates),
        "total_ad_spend": total_ad_spend,
        "missing_cogs": missing_cogs,
    }

def get_date_filter(period):
    if period == "today":
        return "WHERE order_date = date('now', 'localtime')"

    if period == "7d":
        return "WHERE order_date >= date('now', '-6 days', 'localtime')"

    if period == "30d":
        return "WHERE order_date >= date('now', '-29 days', 'localtime')"

    return ""


def get_business_summary(period="all"):
    init_database()
    connection = get_db_connection()
    cursor = connection.cursor()

    where_clause = get_date_filter(period)

    cursor.execute(f"""
        SELECT
            COUNT(DISTINCT order_id) AS orders,
            COUNT(*) AS lines,
            COALESCE(SUM(revenue), 0) AS revenue,
            COALESCE(SUM(shipping_charged), 0) AS shipping_charged,
            COALESCE(SUM(cogs), 0) AS cogs,
            COALESCE(SUM(gross_profit), 0) AS gross_profit
        FROM order_lines
        {where_clause}
    """)
    totals = dict(cursor.fetchone())

    ad_where_clause = ""

    if period == "today":
        ad_where_clause = "WHERE spend_date = date('now', 'localtime')"
    elif period == "7d":
        ad_where_clause = "WHERE spend_date >= date('now', '-6 days', 'localtime')"
    elif period == "30d":
        ad_where_clause = "WHERE spend_date >= date('now', '-29 days', 'localtime')"

    cursor.execute(f"""
        SELECT COALESCE(SUM(ad_spend), 0) AS ad_spend
        FROM ad_spend
        {ad_where_clause}
    """)
    ad_spend = cursor.fetchone()["ad_spend"]

    tiktok_fees = totals["revenue"] * TIKTOK_FEE_RATE
    postage_cost = totals["orders"] * POSTAGE_COST_PER_ORDER
    packaging_cost = totals["orders"] * PACKAGING_PER_ORDER

    net_profit = (
        totals["revenue"]
        + totals["shipping_charged"]
        - totals["cogs"]
        - tiktok_fees
        - postage_cost
        - packaging_cost
        - ad_spend
    )

    profit_margin = 0.0
    if totals["revenue"] > 0:
        profit_margin = (net_profit / totals["revenue"]) * 100

    average_order_value = 0.0
    if totals["orders"] > 0:
        average_order_value = totals["revenue"] / totals["orders"]

    connection.close()

    return {
        **totals,
        "period": period,
        "ad_spend": ad_spend,
        "tiktok_fees": tiktok_fees,
        "postage_cost": postage_cost,
        "packaging_cost": packaging_cost,
        "net_profit": net_profit,
        "profit_margin": profit_margin,
        "average_order_value": average_order_value,
    }

def clean_product_name(product_name):
    name = (product_name or "").lower()

    if "barrel brushes" in name or "xl barrel brush" in name:
        return "XL + Small Barrel Brush Set"

    if "wash mitt" in name:
        return "Wash Mitt 2 Pack"

    if "1200gsm" in name:
        return "1200GSM Drying Towel"

    if "800gsm" in name:
        return "800GSM Drying Towel"

    if "foam cannon" in name or "foam lance" in name:
        return "Foam Cannon Kit"

    if "scrub pads" in name:
        return "Scrub Pads 4 Pack"

    if "waffle" in name or "glass cloth" in name:
        return "Glass Waffle Cloth"

    return product_name


def get_product_scoreboard(period="all"):
    init_database()
    connection = get_db_connection()
    cursor = connection.cursor()

    where_clause = get_date_filter(period)

    cursor.execute(f"""
        SELECT
            product,
            COALESCE(SUM(quantity), 0) AS units,
            COALESCE(SUM(revenue), 0) AS revenue,
            COALESCE(SUM(cogs), 0) AS cogs,
            COALESCE(SUM(gross_profit), 0) AS gross_profit,
            COUNT(DISTINCT order_id) AS orders
        FROM order_lines
        {where_clause}
        GROUP BY product
    """)
    raw_rows = [dict(row) for row in cursor.fetchall()]
    connection.close()

    grouped = {}

    for row in raw_rows:
        product = clean_product_name(row["product"])

        if product not in grouped:
            grouped[product] = {
                "product": product,
                "units": 0,
                "orders": 0,
                "revenue": 0,
                "cogs": 0,
                "gross_profit": 0,
            }

        grouped[product]["units"] += row["units"]
        grouped[product]["orders"] += row["orders"]
        grouped[product]["revenue"] += row["revenue"]
        grouped[product]["cogs"] += row["cogs"]
        grouped[product]["gross_profit"] += row["gross_profit"]

    rows = list(grouped.values())

    total_revenue = sum(row["revenue"] for row in rows)
    total_profit = sum(row["gross_profit"] for row in rows)
    total_units = sum(row["units"] for row in rows)

    for row in rows:
        estimated_tiktok_fees = row["revenue"] * TIKTOK_FEE_RATE
        estimated_postage = row["orders"] * POSTAGE_COST_PER_ORDER
        estimated_packaging = row["orders"] * PACKAGING_PER_ORDER

        row["net_contribution"] = (
            row["revenue"]
            - row["cogs"]
            - estimated_tiktok_fees
            - estimated_postage
            - estimated_packaging
        )

        row["sales_percent"] = (row["revenue"] / total_revenue * 100) if total_revenue else 0
        row["profit_percent"] = (row["gross_profit"] / total_profit * 100) if total_profit else 0
        row["margin"] = (row["gross_profit"] / row["revenue"] * 100) if row["revenue"] else 0
        row["profit_per_unit"] = (row["gross_profit"] / row["units"]) if row["units"] else 0

    rows.sort(key=lambda item: item["gross_profit"], reverse=True)

    highest_profit = max(rows, key=lambda r: r["gross_profit"], default=None)
    highest_margin = max(rows, key=lambda r: r["margin"], default=None)
    most_units = max(rows, key=lambda r: r["units"], default=None)
    highest_revenue = max(rows, key=lambda r: r["revenue"], default=None)

    insight = ""
    if highest_profit:
        insight = (
            f"{highest_profit['product']} generated the most gross profit at "
            f"£{highest_profit['gross_profit']:.2f}. "
            f"It contributed {highest_profit['profit_percent']:.1f}% of total product profit."
        )

    return {
        "period": period,
        "rows": rows,
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "total_units": total_units,
        "highest_profit": highest_profit,
        "highest_margin": highest_margin,
        "most_units": most_units,
        "highest_revenue": highest_revenue,
        "insight": insight,
    }

def get_sales_trends(period="30d"):
    init_database()
    connection = get_db_connection()
    cursor = connection.cursor()

    where_clause = get_date_filter(period)

    cursor.execute(f"""
        SELECT
            order_date,
            COUNT(DISTINCT order_id) AS orders,
            COALESCE(SUM(revenue), 0) AS revenue,
            COALESCE(SUM(shipping_charged), 0) AS shipping_charged,
            COALESCE(SUM(cogs), 0) AS cogs,
            COALESCE(SUM(gross_profit), 0) AS gross_profit
        FROM order_lines
        {where_clause}
        GROUP BY order_date
        ORDER BY order_date DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]

    ad_where_clause = ""

    if period == "7d":
        ad_where_clause = "WHERE spend_date >= date('now', '-6 days', 'localtime')"
    elif period == "30d":
        ad_where_clause = "WHERE spend_date >= date('now', '-29 days', 'localtime')"

    cursor.execute(f"""
        SELECT spend_date, ad_spend
        FROM ad_spend
        {ad_where_clause}
    """)
    ad_spend_by_date = {
        row["spend_date"]: row["ad_spend"]
        for row in cursor.fetchall()
    }

    connection.close()

    trend_rows = []

    for row in rows:
        ad_spend = ad_spend_by_date.get(row["order_date"], 0)
        tiktok_fees = row["revenue"] * TIKTOK_FEE_RATE
        postage_cost = row["orders"] * POSTAGE_COST_PER_ORDER
        packaging_cost = row["orders"] * PACKAGING_PER_ORDER

        net_profit = (
            row["revenue"]
            + row["shipping_charged"]
            - row["cogs"]
            - tiktok_fees
            - postage_cost
            - packaging_cost
            - ad_spend
        )

        average_order_value = 0.0
        if row["orders"] > 0:
            average_order_value = row["revenue"] / row["orders"]

        trend_rows.append({
            **row,
            "tiktok_fees": tiktok_fees,
            "postage_cost": postage_cost,
            "packaging_cost": packaging_cost,
            "ad_spend": ad_spend,
            "net_profit": net_profit,
            "average_order_value": average_order_value,
        })

    totals = {
        "orders": sum(row["orders"] for row in trend_rows),
        "revenue": sum(row["revenue"] for row in trend_rows),
        "cogs": sum(row["cogs"] for row in trend_rows),
        "gross_profit": sum(row["gross_profit"] for row in trend_rows),
        "tiktok_fees": sum(row["tiktok_fees"] for row in trend_rows),
        "postage_cost": sum(row["postage_cost"] for row in trend_rows),
        "packaging_cost": sum(row["packaging_cost"] for row in trend_rows),
        "ad_spend": sum(row["ad_spend"] for row in trend_rows),
        "net_profit": sum(row["net_profit"] for row in trend_rows),
    }

    totals["average_order_value"] = 0.0
    if totals["orders"] > 0:
        totals["average_order_value"] = totals["revenue"] / totals["orders"]

    best_revenue_day = max(trend_rows, key=lambda row: row["revenue"], default=None)
    best_profit_day = max(trend_rows, key=lambda row: row["net_profit"], default=None)

    profit_status = "positive" if totals["net_profit"] >= 0 else "negative"
    insight = "No sales data found for this period."

    if trend_rows:
        insight = (
            f"Best revenue day was {best_revenue_day['order_date']} at "
            f"£{best_revenue_day['revenue']:.2f}. "
            f"Best profit day was {best_profit_day['order_date']} at "
            f"£{best_profit_day['net_profit']:.2f}. "
            f"Total net profit is {profit_status} for this period."
        )

    return {
        "period": period,
        "rows": trend_rows,
        "totals": totals,
        "best_revenue_day": best_revenue_day,
        "best_profit_day": best_profit_day,
        "insight": insight,
    }

def get_import_history():
    init_database()
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            imported_at,
            COUNT(*) AS line_count,
            COUNT(DISTINCT order_id) AS order_count,
            MIN(order_date) AS date_from,
            MAX(order_date) AS date_to,
            COALESCE(SUM(revenue), 0) AS revenue,
            COALESCE(SUM(cogs), 0) AS cogs,
            COALESCE(SUM(gross_profit), 0) AS gross_profit
        FROM order_lines
        GROUP BY imported_at
        ORDER BY imported_at DESC
    """)
    batches = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT
            spend_date,
            ad_spend
        FROM ad_spend
        ORDER BY spend_date DESC
    """)
    ad_spend_entries = [dict(row) for row in cursor.fetchall()]

    connection.close()

    totals = {
        "batches": len(batches),
        "line_count": sum(row["line_count"] for row in batches),
        "order_count": sum(row["order_count"] for row in batches),
        "revenue": sum(row["revenue"] for row in batches),
        "cogs": sum(row["cogs"] for row in batches),
        "gross_profit": sum(row["gross_profit"] for row in batches),
        "ad_spend_entries": len(ad_spend_entries),
        "ad_spend": sum(row["ad_spend"] for row in ad_spend_entries),
    }

    return {
        "batches": batches,
        "ad_spend_entries": ad_spend_entries,
        "totals": totals,
    }

def get_business_briefing_summary(order_where_clause="", ad_where_clause=""):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(f"""
        SELECT
            COUNT(DISTINCT order_id) AS orders,
            COALESCE(SUM(revenue), 0) AS revenue,
            COALESCE(SUM(shipping_charged), 0) AS shipping_charged,
            COALESCE(SUM(cogs), 0) AS cogs
        FROM order_lines
        {order_where_clause}
    """)
    totals = dict(cursor.fetchone())

    cursor.execute(f"""
        SELECT COALESCE(SUM(ad_spend), 0) AS ad_spend
        FROM ad_spend
        {ad_where_clause}
    """)
    ad_spend = cursor.fetchone()["ad_spend"]
    connection.close()

    tiktok_fees = totals["revenue"] * TIKTOK_FEE_RATE
    postage_cost = totals["orders"] * POSTAGE_COST_PER_ORDER
    packaging_cost = totals["orders"] * PACKAGING_PER_ORDER

    net_profit = (
        totals["revenue"]
        + totals["shipping_charged"]
        - totals["cogs"]
        - tiktok_fees
        - postage_cost
        - packaging_cost
        - ad_spend
    )

    average_order_value = 0.0
    if totals["orders"] > 0:
        average_order_value = totals["revenue"] / totals["orders"]

    return {
        "orders": totals["orders"],
        "revenue": totals["revenue"],
        "net_profit": net_profit,
        "average_order_value": average_order_value,
    }


def format_change(current, previous, label):
    if previous is None:
        return f"{label} comparison is not available for all-time data."

    if previous == 0 and current == 0:
        return f"{label} is flat at zero versus the previous matching period."

    if previous == 0:
        return f"{label} is up from zero in the previous matching period."

    change = ((current - previous) / abs(previous)) * 100
    direction = "up" if change >= 0 else "down"

    return f"{label} is {direction} {abs(change):.1f}% versus the previous matching period."


def get_briefing_period_clauses(period):
    if period == "7d":
        return {
            "current_order_where": "WHERE order_date >= date('now', '-6 days', 'localtime')",
            "current_ad_where": "WHERE spend_date >= date('now', '-6 days', 'localtime')",
            "previous_order_where": "WHERE order_date >= date('now', '-13 days', 'localtime') AND order_date < date('now', '-6 days', 'localtime')",
            "previous_ad_where": "WHERE spend_date >= date('now', '-13 days', 'localtime') AND spend_date < date('now', '-6 days', 'localtime')",
        }

    if period == "30d":
        return {
            "current_order_where": "WHERE order_date >= date('now', '-29 days', 'localtime')",
            "current_ad_where": "WHERE spend_date >= date('now', '-29 days', 'localtime')",
            "previous_order_where": "WHERE order_date >= date('now', '-59 days', 'localtime') AND order_date < date('now', '-29 days', 'localtime')",
            "previous_ad_where": "WHERE spend_date >= date('now', '-59 days', 'localtime') AND spend_date < date('now', '-29 days', 'localtime')",
        }

    return {
        "current_order_where": "",
        "current_ad_where": "",
        "previous_order_where": None,
        "previous_ad_where": None,
    }


def build_briefing_action(current, previous, best_product, weak_margin_product):
    profit_improving = (
        previous is not None
        and current["net_profit"] > previous["net_profit"]
    )

    if current["net_profit"] < 0:
        return "Reduce ad spend or pause weak campaigns until net profit is back above zero."

    if weak_margin_product and weak_margin_product["margin"] < 30:
        return f"Investigate {weak_margin_product['product']} because its margin is weak."

    if best_product:
        if current["net_profit"] > 0 and profit_improving:
            return "Keep the current strategy because profit is positive and improving."

        return f"Increase content and sales focus on {best_product['product']} because it drove the most gross profit."

    return "Keep current strategy until more imported order data is available."


def get_business_briefing():
    init_database()
    periods = [
        ("7d", "Last 7 Days"),
        ("30d", "Last 30 Days"),
        ("all", "All Time"),
    ]
    briefing_periods = []

    for period, label in periods:
        clauses = get_briefing_period_clauses(period)
        current = get_business_briefing_summary(
            clauses["current_order_where"],
            clauses["current_ad_where"],
        )

        previous = None
        if clauses["previous_order_where"] is not None:
            previous = get_business_briefing_summary(
                clauses["previous_order_where"],
                clauses["previous_ad_where"],
            )

        scoreboard = get_product_scoreboard(period)
        product_rows = [
            row for row in scoreboard["rows"]
            if row["revenue"] > 0
        ]
        best_product = scoreboard["highest_profit"]
        weak_margin_product = min(
            product_rows,
            key=lambda row: row["margin"],
            default=None,
        )

        insights = [
            format_change(
                current["revenue"],
                previous["revenue"] if previous else None,
                "Revenue",
            ),
            format_change(
                current["net_profit"],
                previous["net_profit"] if previous else None,
                "Net profit",
            ),
        ]

        if best_product:
            insights.append(
                f"{best_product['product']} drove the most gross profit at £{best_product['gross_profit']:.2f}."
            )
        else:
            insights.append("No best profit product is available for this period yet.")

        if weak_margin_product and weak_margin_product["margin"] < 30:
            insights.append(
                f"{weak_margin_product['product']} has a weak margin at {weak_margin_product['margin']:.1f}%."
            )
        elif weak_margin_product:
            insights.append("No product has a margin below the weak-margin threshold.")
        else:
            insights.append("No product margin data is available for this period yet.")

        briefing_periods.append({
            "period": period,
            "label": label,
            "current": current,
            "previous": previous,
            "best_product": best_product,
            "weak_margin_product": weak_margin_product,
            "insights": insights,
            "recommended_action": build_briefing_action(
                current,
                previous,
                best_product,
                weak_margin_product,
            ),
        })

    return {
        "periods": briefing_periods,
    }

def get_imported_order_dates():
    init_database()
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            order_date,
            COUNT(*) AS lines,
            COUNT(DISTINCT order_id) AS orders,
            SUM(revenue) AS revenue
        FROM order_lines
        GROUP BY order_date
        ORDER BY order_date DESC
    """)

    rows = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return rows
