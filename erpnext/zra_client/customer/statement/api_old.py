from erpnext.zra_client.custom_frappe_client import CustomFrappeClient
from erpnext.zra_client.tax_calcalator.tax import TaxCaller
from erpnext.zra_client.generic_api import send_response
from erpnext.zra_client.main import ZRAClient
from frappe.utils import nowdate, date_diff, getdate
from frappe import _
import frappe


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_customer_statement():
    customer_id = frappe.form_dict.get("id")
    page = int(frappe.form_dict.get("page", 1))
    page_size = int(frappe.form_dict.get("page_size", 10))
    start = (page - 1) * page_size

    if not customer_id:
        return send_response(
            status="fail",
            message="Customer id must not be null",
            data={},
            status_code=400,
            http_status=400
        )

    try:
        customer = frappe.get_doc("Customer", {"custom_id": customer_id})
    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message=f"Customer with id {customer_id} not found.",
            data={},
            status_code=404,
            http_status=404
        )

    opening_balance = customer.custom_onboard_balance or 0
    opening_date = getdate(customer.creation) if customer.creation else None

    total_invoiced = frappe.db.sql("""
        SELECT COUNT(*)
        FROM `tabSales Invoice`
        WHERE customer=%s AND docstatus=1
    """, (customer.name,))[0][0] or 0

    total_collected = frappe.db.sql("""
        SELECT SUM(ref.allocated_amount)
        FROM `tabPayment Entry Reference` AS ref
        JOIN `tabPayment Entry` AS pe ON pe.name = ref.parent
        WHERE pe.docstatus=1
          AND ref.reference_doctype='Sales Invoice'
          AND ref.reference_name IN (
              SELECT name FROM `tabSales Invoice`
              WHERE customer=%s AND docstatus=1
          )
    """, (customer.name,))[0][0] or 0

    total_invoiced_amount = frappe.db.sql("""
        SELECT SUM(grand_total)
        FROM `tabSales Invoice`
        WHERE customer=%s AND docstatus=1
    """, (customer.name,))[0][0] or 0

    net_outstanding = total_invoiced_amount - total_collected + opening_balance


    aging = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
    invoices = frappe.db.sql("""
        SELECT due_date, outstanding_amount
        FROM `tabSales Invoice`
        WHERE customer=%s AND docstatus=1 AND outstanding_amount > 0
    """, (customer.name,), as_dict=True)

    today = nowdate()
    for inv in invoices:
        due_date = inv.get("due_date") or today
        outstanding = inv.get("outstanding_amount") or 0
        days_overdue = date_diff(today, due_date)
        if days_overdue <= 0:
            aging["current"] += outstanding
        elif 1 <= days_overdue <= 30:
            aging["1_30"] += outstanding
        elif 31 <= days_overdue <= 60:
            aging["31_60"] += outstanding
        elif 61 <= days_overdue <= 90:
            aging["61_90"] += outstanding
        else:
            aging["90_plus"] += outstanding

    gl_rows = frappe.db.sql("""
        SELECT posting_date, voucher_type, voucher_no, debit, credit
        FROM `tabGL Entry`
        WHERE party_type='Customer' AND party=%s AND is_cancelled=0
        ORDER BY posting_date ASC, creation ASC
    """, (customer.name,), as_dict=True)

    total_ledger_entries = len(gl_rows)

    paginated_gl = gl_rows[start:start + page_size]

    ledger = []
    running_balance = opening_balance
    if page == 1:
        ledger.append({
            "date": opening_date,
            "type": "Opening Balance",
            "ref": "BAL-FWD",
            "debit": 0,
            "credit": 0,
            "balance": running_balance,
            "note": ""
        })

    if page > 1:
        for row in gl_rows[:start]:
            debit = row.get("debit") or 0
            credit = row.get("credit") or 0
            running_balance = running_balance + debit - credit

    for row in paginated_gl:
        debit = row.get("debit") or 0
        credit = row.get("credit") or 0
        running_balance = running_balance + debit - credit

        note = ""
        voucher_type = row.get("voucher_type")
        voucher_no = row.get("voucher_no")

        if voucher_type == "Sales Invoice":
            note = frappe.db.get_value("Sales Invoice", voucher_no, "remarks") or ""
        elif voucher_type == "Payment Entry":
            note = frappe.db.get_value("Payment Entry", voucher_no, "remarks") or ""
        elif voucher_type == "Journal Entry":
            note = frappe.db.get_value("Journal Entry", voucher_no, "user_remark") or ""

        ledger.append({
            "date": row.get("posting_date"),
            "type": voucher_type,
            "ref": voucher_no,
            "debit": debit,
            "credit": credit,
            "balance": running_balance,
            "note": note
        })

    total_pages = (total_ledger_entries + page_size - 1) // page_size
    has_next = page < total_pages
    has_prev = page > 1

    statement = {
        "openingBalance": opening_balance,
        "summary": {
            "totalInvoiced": total_invoiced,
            "totalCollected": total_collected,
            "netOutstanding": net_outstanding
        },
        "aging": aging,
        "ledger": ledger,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total_ledger_entries,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev
        }
    }

    return send_response(
        status="success",
        message="Customer statement retrieved successfully",
        data=statement,
        status_code=200,
        http_status=200
    )
