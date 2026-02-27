from erpnext.zra_client.generic_api import send_response
import frappe
from datetime import datetime
import calendar

@frappe.whitelist(allow_guest=False)
def items_report():
    try:
        sales_item_code = frappe.form_dict.get("sales_item_code")
        stock_item_code = frappe.form_dict.get("stock_item_code")
        from_date = frappe.form_dict.get("from_date")
        to_date = frappe.form_dict.get("to_date")

        # Set default dates if not provided
        if not from_date or not to_date:
            current_year = datetime.now().year
            from_date = f"{current_year}-01-01"
            to_date = f"{current_year}-12-31"

        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")

        response_data = {}

        # Most sold / least sold items across all invoices
        overall_sales = frappe.db.sql("""
            SELECT sii.item_code, ii.item_name
            FROM `tabSales Invoice Item` sii
            JOIN `tabSales Invoice` si ON si.name = sii.parent
            JOIN `tabItem` ii ON ii.item_code = sii.item_code
            WHERE si.docstatus = 1
            GROUP BY sii.item_code, ii.item_name
            ORDER BY SUM(sii.qty) DESC
        """, as_dict=True)

        response_data["most_sold_item"] = overall_sales[0] if overall_sales else None
        response_data["least_sold_item"] = overall_sales[-1] if overall_sales else None

        # Monthly sales graph: number of invoices each item appears in
        sales_month_labels = []
        sales_monthly_data = []

        current_year = from_dt.year
        current_month = from_dt.month

        while current_year < to_dt.year or (current_year == to_dt.year and current_month <= to_dt.month):
            month_start = datetime(current_year, current_month, 1).strftime("%Y-%m-%d 00:00:00")
            last_day = calendar.monthrange(current_year, current_month)[1]
            month_end = datetime(current_year, current_month, last_day, 23, 59, 59).strftime("%Y-%m-%d %H:%M:%S")

            sales_month_labels.append(datetime(current_year, current_month, 1).strftime("%b %Y"))

            if sales_item_code:
                # Count DISTINCT invoices where this item appears
                sale_count = frappe.db.sql("""
                    SELECT COUNT(DISTINCT sii.parent)
                    FROM `tabSales Invoice Item` sii
                    JOIN `tabSales Invoice` si ON si.name = sii.parent
                    WHERE sii.item_code = %s
                    AND si.docstatus = 1
                    AND si.posting_date >= %s
                    AND si.posting_date <= %s
                """, (sales_item_code, month_start, month_end))[0][0] or 0
            else:
                sale_count = 0

            sales_monthly_data.append(sale_count)

            # Move to next month
            if current_month == 12:
                current_month = 1
                current_year += 1
            else:
                current_month += 1

        response_data["monthly_sales_graph"] = {
            "item_code": sales_item_code or "",
            "labels": sales_month_labels,
            "data": sales_monthly_data,
            "from_date": from_date,
            "to_date": to_date
        }

        # Stock graph
        if stock_item_code:
            stock_qty = frappe.db.sql("""
                SELECT SUM(actual_qty)
                FROM `tabBin`
                WHERE item_code=%s
            """, (stock_item_code,))[0][0] or 0
        else:
            stock_qty = 0

        response_data["stock_balance"] = {
            "item_code": stock_item_code or "",
            "data": [stock_qty] if stock_item_code else [],
        }

        return send_response(
            status="success",
            message="Item sales and stock report fetched successfully",
            data=response_data,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Items Report Error")
        return send_response(
            status="fail",
            message="Failed to fetch item sales and stock report",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )