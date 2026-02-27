import frappe
from erpnext.zra_client.generic_api import send_response
from datetime import datetime

@frappe.whitelist(allow_guest=False, methods=["GET"])
def procurement():
    """Return aggregated counts and grouped data for Purchase Invoices, Purchase Orders, and Suppliers,
    with monthly breakdowns covering all months of a given year (or current year)."""
    args = frappe.request.args
    from_date = args.get("from_date")
    to_date = args.get("to_date")
    supplier_filter = args.get("supplier")
    year = args.get("year")

    # Determine target year for month filling
    if not year:
        if from_date:
            year = from_date.split("-")[0]
        else:
            year = str(datetime.now().year)

    # Helper to fill missing months in a dictionary with zero counts
    def fill_missing_months(data_dict):
        all_months = [f"{year}-{str(m).zfill(2)}" for m in range(1, 13)]
        filled = {}
        for month in all_months:
            filled[month] = data_dict.get(month, 0)
        return filled

    # Helper to build date conditions
    def date_condition(field):
        cond = ""
        if from_date and to_date:
            cond = f" AND {field} BETWEEN %(from_date)s AND %(to_date)s"
        elif from_date:
            cond = f" AND {field} >= %(from_date)s"
        elif to_date:
            cond = f" AND {field} <= %(to_date)s"
        return cond

    # Helper to add supplier filter for invoices/orders (uses 'supplier' link field)
    def supplier_condition(field="supplier"):
        if supplier_filter:
            return f" AND {field} LIKE %(supplier)s"
        return ""

    params = {}
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date
    if supplier_filter:
        params["supplier"] = f"%{supplier_filter}%"

    # ----- Purchase Invoice aggregates -----
    invoice_queries = {
        "total": "SELECT COUNT(*) FROM `tabPurchase Invoice` WHERE 1=1",
        "by_status": "SELECT status, COUNT(*) as count FROM `tabPurchase Invoice` WHERE 1=1 GROUP BY status",
        "by_tax_category": "SELECT tax_category, COUNT(*) as count FROM `tabPurchase Invoice` WHERE 1=1 GROUP BY tax_category",
        "by_sync_status": "SELECT custom_sync_status, COUNT(*) as count FROM `tabPurchase Invoice` WHERE 1=1 GROUP BY custom_sync_status",
        "by_registration_type": "SELECT custom_registration_type, COUNT(*) as count FROM `tabPurchase Invoice` WHERE 1=1 GROUP BY custom_registration_type",
        "by_payment_method": "SELECT custom_payment_method, COUNT(*) as count FROM `tabPurchase Invoice` WHERE 1=1 GROUP BY custom_payment_method",
        "by_month": f"SELECT DATE_FORMAT(posting_date, '%%Y-%%m') as month, COUNT(*) as count FROM `tabPurchase Invoice` WHERE 1=1 {date_condition('posting_date')} {supplier_condition()} GROUP BY month ORDER BY month"
    }

    invoice_data = {}
    for key, sql in invoice_queries.items():
        full_sql = sql + date_condition("posting_date") + supplier_condition()
        if key == "total":
            invoice_data[key] = frappe.db.sql(full_sql, params)[0][0]
        else:
            rows = frappe.db.sql(full_sql, params, as_dict=True)
            invoice_data[key] = {row.get(list(row.keys())[0]): row["count"] for row in rows}

    # Fill missing months for invoices
    invoice_data["by_month"] = fill_missing_months(invoice_data.get("by_month", {}))

    # ----- Purchase Order aggregates -----
    order_queries = {
        "total": "SELECT COUNT(*) FROM `tabPurchase Order` WHERE 1=1",
        "by_status": "SELECT status, COUNT(*) as count FROM `tabPurchase Order` WHERE 1=1 GROUP BY status",
        "by_tax_category": "SELECT tax_category, COUNT(*) as count FROM `tabPurchase Order` WHERE 1=1 GROUP BY tax_category",
        "by_month": f"SELECT DATE_FORMAT(transaction_date, '%%Y-%%m') as month, COUNT(*) as count FROM `tabPurchase Order` WHERE 1=1 {date_condition('transaction_date')} {supplier_condition()} GROUP BY month ORDER BY month"
    }

    order_data = {}
    for key, sql in order_queries.items():
        full_sql = sql + date_condition("transaction_date") + supplier_condition()
        if key == "total":
            order_data[key] = frappe.db.sql(full_sql, params)[0][0]
        else:
            rows = frappe.db.sql(full_sql, params, as_dict=True)
            order_data[key] = {row.get(list(row.keys())[0]): row["count"] for row in rows}

    # Fill missing months for orders
    order_data["by_month"] = fill_missing_months(order_data.get("by_month", {}))

    # ----- Supplier aggregates -----
    supplier_queries = {
        "total": "SELECT COUNT(*) FROM `tabSupplier` WHERE 1=1",
        "by_status": "SELECT custom_status, COUNT(*) as count FROM `tabSupplier` WHERE 1=1 GROUP BY custom_status",
        "by_tax_category": "SELECT tax_category, COUNT(*) as count FROM `tabSupplier` WHERE 1=1 GROUP BY tax_category",
        "by_month": f"SELECT DATE_FORMAT(creation, '%%Y-%%m') as month, COUNT(*) as count FROM `tabSupplier` WHERE 1=1 {date_condition('creation')} GROUP BY month ORDER BY month"
    }

    # For suppliers, the supplier filter applies to the actual supplier_name field
    supplier_name_condition = ""
    if supplier_filter:
        supplier_name_condition = " AND supplier_name LIKE %(supplier)s"

    supplier_data = {}
    for key, sql in supplier_queries.items():
        full_sql = sql + date_condition("creation") + supplier_name_condition
        if key == "total":
            supplier_data[key] = frappe.db.sql(full_sql, params)[0][0]
        else:
            rows = frappe.db.sql(full_sql, params, as_dict=True)
            supplier_data[key] = {row.get(list(row.keys())[0]): row["count"] for row in rows}

    # Fill missing months for suppliers
    supplier_data["by_month"] = fill_missing_months(supplier_data.get("by_month", {}))

    # ----- Ratios -----
    invoice_count = invoice_data.get("total", 0)
    order_count = order_data.get("total", 0)
    invoice_to_order = invoice_count / order_count if order_count else 0

    synced = invoice_data.get("by_sync_status", {}).get("1", 0)
    sync_rate = synced / invoice_count if invoice_count else 0

    # ----- Structure the response -----
    response_data = {
        "totals": {
            "purchase_invoices": invoice_data.get("total", 0),
            "purchase_orders": order_data.get("total", 0),
            "suppliers": supplier_data.get("total", 0)
        },
        "purchase_invoices": {
            "by_status": invoice_data.get("by_status", {}),
            "by_tax_category": invoice_data.get("by_tax_category", {}),
            "by_sync_status": invoice_data.get("by_sync_status", {}),
            "by_registration_type": invoice_data.get("by_registration_type", {}),
            "by_payment_method": invoice_data.get("by_payment_method", {}),
            "by_month": invoice_data.get("by_month", {})
        },
        "purchase_orders": {
            "by_status": order_data.get("by_status", {}),
            "by_tax_category": order_data.get("by_tax_category", {}),
            "by_month": order_data.get("by_month", {})
        },
        "suppliers": {
            "by_status": supplier_data.get("by_status", {}),
            "by_tax_category": supplier_data.get("by_tax_category", {}),
            "by_month": supplier_data.get("by_month", {})
        },
        "ratios": {
            "invoice_to_order": round(invoice_to_order, 2),
            "sync_rate": round(sync_rate, 4)
        }
    }

    return send_response(
        status="success",
        message="Report retrieved successfully",
        data=response_data,
        status_code=200,
        http_status=200
    )