from erpnext.zra_client.generic_api import send_response
import frappe

class CustomFrappeClient():
    
    def GetOrCreateIncoterm(self, incoterm_code):
        if not incoterm_code:
            return None
        if frappe.db.exists("Incoterm", incoterm_code):
            return incoterm_code
        try:
            new_incoterm = frappe.get_doc({
                "doctype": "Incoterm",
                "code": incoterm_code,
                "title": incoterm_code 
            })
            new_incoterm.insert(ignore_permissions=True)
            frappe.db.commit()
            return new_incoterm.name
        except Exception as e:
            frappe.log_error(f"Failed to create Incoterm {incoterm_code}: {str(e)}")
            return None
        
    def GetItemDetails(self, item_code):
        if not item_code:
            return send_response(
                status="fail",
                message="Item code is required.",
                status_code=400,
                http_status=400
            )
        
        try:
            item = frappe.get_doc("Item", item_code)
            return item
        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message=f"Item {item_code} not found",
                status_code=404,
                http_status=404
            )
        except Exception as e:
            return send_response(
                status="fail",
                message=f"Cannot proceed: {str(e)}",
                status_code=400,
                http_status=400
            )
            
    def GetDefaultWareHouse(self):
        WARE_HOUSE = "Finished Goods - Izyane"
        return WARE_HOUSE
    
    
    def getDefaultExpenseAccount(self):
        ACCOUNT = "Stock Difference - Izyane - I"
        return ACCOUNT