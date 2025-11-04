from erpnext.zra_client.main import ZRAClient
import frappe
from frappe.utils import flt

class Stock(ZRAClient):
    def __init__(self):
        super().__init__()

    def get_tpin(self):
        return self.tpin

    def get_branch_code(self):
        return self.branch_code

    def create_stock(self, stock_data):
        if not isinstance(stock_data, dict):
            frappe.throw("Invalid input: stock_data must be a dictionary")

        total_taxable = 0
        total_tax = 0
        total_amount = 0

        items = stock_data.get("items", [])
        if not items:
            frappe.throw("No items found in stock_data")

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "sarNo": 1,
            "orgSarNo": 0,
            "regTyCd": "M",
            "custTpin": None,
            "custNm": None,
            "custBhfId": None,
            "sarTyCd": "02",
            "ocrnDt": stock_data.get("posting_date", "").replace("-", "") if stock_data.get("posting_date") else None,
            "totItemCnt": len(items),
            "remark": stock_data.get("remarks"),
            "regrId": stock_data.get("owner"),
            "regrNm": stock_data.get("owner"),
            "modrNm": stock_data.get("owner"),
            "modrId": stock_data.get("owner"),
            "itemList": []
        }

        vat_code_map = {
            "StandardRated": "A",
            "MinimumTaxableValue": "B",
            "Exports": "C1",
            "ZeroRatingLocalPurchases": "C2",
            "ZeroRatedByNature": "C3",
            "Exempt": "D",
            "Disbursement": "E",
            "ReverseVAT": "RVAT"
        }

        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                frappe.log_error(f"Invalid item format. Expected dict, got {type(item)}")
                continue

            item_code = item.get("item_code")
            if not item_code:
                frappe.log_error("Missing item_code in Stock Entry items")
                continue

            try:
                item_doc = frappe.get_doc("Item", item_code)
            except frappe.DoesNotExistError:
                frappe.log_error(f"Item not found: {item_code}")
                continue

            qty = flt(item.get("qty", 0))
            valuation_rate = flt(item.get("valuation_rate", 0))

            if not valuation_rate:
                valuation_rate = flt(item_doc.get("custom_default_unit_price", 0))

            if valuation_rate == 0:
                if not item.get("allow_zero_valuation_rate", False):
                    frappe.throw(f"Valuation Rate missing for item: {item_code}. "
                                 "Set valuation rate or enable 'Allow Zero Valuation Rate'.")
                else:
                    frappe.log_error(f"Zero valuation rate allowed for item: {item_code}")

            custom_vat = (item_doc.get("custom_vat") or "").replace(" ", "").strip()
            vatCatCd = vat_code_map.get(custom_vat, "A")
            vat_rate = 0.16 if vatCatCd == "A" else 0

            supply_amount = round(qty * valuation_rate, 2)
            taxable_amount = supply_amount if vatCatCd == "A" else 0
            tax_amount = round(taxable_amount * vat_rate, 2)
            total_item_amount = supply_amount + tax_amount

            total_taxable += taxable_amount
            total_tax += tax_amount
            total_amount += total_item_amount

            payload["itemList"].append({
                "itemSeq": idx,
                "itemCd": item_code,
                "itemClsCd": item_doc.get("item_class_code") or "NA",
                "itemNm": item_doc.item_name,
                "pkgUnitCd": item_doc.get("custom_packaging_unit_code") or "PKG",
                "qtyUnitCd": item_doc.get("custom_units_of_measure") or "EA",
                "vatCatCd": vatCatCd,
                "qty": qty,
                "prc": valuation_rate,
                "splyAmt": supply_amount,
                "taxblAmt": taxable_amount,
                "taxAmt": tax_amount,
                "totAmt": total_item_amount,
                "totDcAmt": 0,
                "pkg": 1
            })

        payload.update({
            "totTaxblAmt": total_taxable,
            "totTaxAmt": total_tax,
            "totAmt": total_amount
        })



        try:
            response = self.save_stock(payload)
            if isinstance(response, dict) and response.get("resultCd") == "000":
                update_stock_master_payload = {
                    "tpin": payload.get("tpin"),
                    "regrId": payload.get("regrId"),
                    "regrNm": payload.get("regrNm"),
                    "bhfId": payload.get("bhfId"),
                    "modrId": payload.get("modrId"),
                    "modrNm": payload.get("modrNm"),
                    "stockItemList": [
                        {
                            "itemCd": payload["itemList"][0]["itemCd"],
                            "rsdQty": 12
                        }
                    ]
                }

        
                print("Update stock master payload: ", update_stock_master_payload)
          

                update_stock_master_response = self.update_stock_master(update_stock_master_payload)

            else:
                frappe.throw(f"ZRA returned error: {response.get('resultMsg') if isinstance(response, dict) else response}")

        except Exception as e:
            frappe.log_error(title="❌ ZRA Save Stock Failed", message=str(e))
            frappe.throw(f"ZRA Error: {e}")

    def update_stock_master(self, update_stock_master_payload):
  
        try:
            save_stock_master = self.save_stock_master(update_stock_master_payload)
            return save_stock_master
        except Exception as e:
            frappe.log_error(title="❌ Failed to update stock master", message=str(e))
            print(f"Exception in update_stock_master: {e}")
            return None
