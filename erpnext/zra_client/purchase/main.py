
import frappe
import requests
from datetime import datetime
from frappe.utils import flt
from erpnext.zra_client.main import ZRAClient


class zraPurchase(ZRAClient):
    def __init__(self):
        super().__init__()


    def get_tpin_number(self):
        return self.tpin
    

    def get_branch_code(self):
        return self.branch_code
    

    def update_stock_after_purchase(self, payload):

        self.update_stock_after_purchase_view(payload)

    
    def update_stock_master_after_purchase(self, payload):
        self.save_stock_master(payload)


    def create_purchase(self, purchase_data):
       
        payload = {
            "tpin": self.get_tpin_number(),
            "bhfId": self.get_branch_code(),
            "cisInvcNo": purchase_data.get("name"),
            "regTyCd": "M",
            "pchsTyCd": "N",
            "rcptTyCd": "P",
            "pmtTyCd": "01",
            "pchsSttsCd": "02",
            "cfmDt": frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S"),
            "pchsDt": frappe.utils.now_datetime().strftime("%Y%m%d"),
            "cnclReqDt": "",
            "cnclDt": "",
            "totItemCnt": len(purchase_data.get("items", [])),
            "totTaxblAmt": float(purchase_data.get("total") or 0),
            "totTaxAmt": 0.0,
            "totAmt": float(purchase_data.get("grand_total") or 0),
            "remark": "Auto from ERP",
            "regrNm": purchase_data.get("owner"),
            "regrId": purchase_data.get("owner"),
            "modrNm": purchase_data.get("owner"),
            "modrId": purchase_data.get("owner"),
            "itemList": []
        }
        toUseData = payload



        for idx, item in enumerate(purchase_data.get("items", [])):
            item_code = item.get("item_code")
            item_name = item.get("item_name")
            requested_qty = flt(item.get("qty") or 0)

            bins = frappe.db.get_all("Bin", filters={"item_code": item_code}, fields=["actual_qty", "projected_qty", "name"])
            available_qty = sum(flt(b.get("actual_qty", 0)) for b in bins)


            remaining_qty = requested_qty
            for b in bins:
                if remaining_qty == 0:
                    break
                projected_qty = flt(b.get("projected_qty", 0))
                actual_qty = flt(b.get("actual_qty", 0))
                if projected_qty <= 0:
                    continue
                consume = min(projected_qty, remaining_qty)
                frappe.db.set_value("Bin", b["name"], "projected_qty", projected_qty - consume)
                frappe.db.set_value("Bin", b["name"], "actual_qty", actual_qty - consume)
                remaining_qty -= consume

            item_doc = frappe.get_doc("Item", item_code)

            get_packaging_unit = item_doc.custom_packaging_unit_code or "PCS"
            r = requests.get(f"http://0.0.0.0:7000/packaging-unit-code/{get_packaging_unit}/", timeout=5)
            r.raise_for_status()
            packaging_unit_code = r.json().get("code")

            get_qty_unit = item_doc.custom_units_of_measure or "PCS"
            r = requests.get(f"http://0.0.0.0:7000/unitofmeasure/{get_qty_unit}/", timeout=5)
            r.raise_for_status()
            qty_unit_code = r.json().get("code")

            item_cls_cd = item_doc.get("unspsc_code") or "50102517"

            payload["itemList"].append({
                "itemSeq": idx + 1,
                "itemCd": item_code,
                "itemClsCd": item_cls_cd,
                "itemNm": item_name,
                "bcd": "",
                "pkgUnitCd": packaging_unit_code,
                "pkg": 1,
                "qtyUnitCd": qty_unit_code,
                "qty": float(item.get("qty") or 0),
                "prc": float(item.get("rate") or 0),
                "splyAmt": float(item.get("amount") or 0),
                "dcRt": 0.0,
                "dcAmt": 0.0,
                "taxTyCd": "A",
                "iplCatCd": "",
                "tlCatCd": "",
                "exciseCatCd": "",
                "taxblAmt": float(item.get("amount") or 0),
                "vatCatCd": "A",
                "iplTaxblAmt": float(purchase_data.get("total") or 0),
                "tlTaxblAmt": float(purchase_data.get("total") or 0),
                "exciseTaxblAmt": float(purchase_data.get("total") or 0),
                "taxAmt": float(purchase_data.get("total") or 0),
                "iplAmt": float(purchase_data.get("total") or 0),
                "tlAmt": float(purchase_data.get("total") or 0),
                "exciseTxAmt": float(purchase_data.get("total") or 0),
                "totAmt": float(item.get("amount") or 0)
            })

    


        response_data = self.save_purchase_manually(payload)

        if response_data.get("resultCd") == "000":
            frappe.msgprint(f"Purchase saved successfully: {response_data.get('resultMsg')}")

            ocrnDt = datetime.now().strftime("%Y%m%d")

            update_stock_master_items  = []
            update_stock_items = []
            
            itemsListInToUseData = toUseData.get("itemList", [])
            for item in itemsListInToUseData:
                itemSeq = item.get("itemSeq")
                itemCd = item.get("itemCd") 
                itemClsCd = item.get("itemClsCd")
                itemNm = item.get("itemNm") 
                pkgUnitCd = item.get("pkgUnitCd")
                qtyUnitCd = item.get("qtyUnitCd")
                qty = item.get("qty")
                prc = item.get("prc")
                splyAmt = item.get("splyAmt")
                taxblAmt = item.get("taxblAmt")
                vatCatCd = item.get("vatCatCd")
                taxAmt = item.get("taxAmt")
                totAmt = item.get("totAmt")
                update_stock_items.append({
                    "itemSeq": itemSeq,
                    "itemCd": itemCd,
                    "itemClsCd": itemClsCd,
                    "itemNm": itemNm,
                    "pkgUnitCd": pkgUnitCd,
                    "qtyUnitCd": qtyUnitCd,
                    "qty": qty,
                    "prc": prc,
                    "splyAmt": splyAmt,
                    "taxblAmt": taxblAmt,
                    "vatCatCd": vatCatCd,
                    "taxAmt": taxAmt,
                    "totAmt": totAmt,
                    "pkg": 1,
                    "totDcAmt": 0,
                })
                update_stock_master_items.append({
                    "itemCd": itemCd,
                    "rsdQty": 12
                })
               



            create_update_stock_payload =  {
                "tpin": self.get_tpin_number(),
                "bhfId": self.get_branch_code(),
                "sarNo":1,
                "orgSarNo":0,
                "regTyCd":"M",  
                "sarTyCd":"02",
                "ocrnDt":ocrnDt ,
                "totItemCnt":toUseData['totItemCnt'],
                "totTaxblAmt":toUseData['totTaxblAmt'],
                "totTaxAmt": toUseData['totTaxAmt'],
                "totAmt": toUseData['totAmt'],
                "regrId": purchase_data.get("owner"),
                "regrNm": purchase_data.get("owner"),
                "modrNm": purchase_data.get("owner"),
                "modrId": purchase_data.get("owner"),
                "itemList":update_stock_items
                    
            }

            call_update_stock_after_purchase = self.update_stock_after_purchase(create_update_stock_payload)
            create_update_stock_master_payload = {
                            "tpin": self.get_tpin_number(),
                            "bhfId": self.get_branch_code(),
                            "regrId": purchase_data.get("owner"),
                            "regrNm": purchase_data.get("owner"),
                            "modrNm": purchase_data.get("owner"),
                            "modrId": purchase_data.get("owner"),
                            "stockItemList":update_stock_master_items 

                            }
            print("Preparing stock master update data:", create_update_stock_master_payload)
            call_update_stock_master_after_purchase = self.update_stock_master_after_purchase(create_update_stock_master_payload)
     

        if response_data.get("resultCd") != "000":
            frappe.throw(f"Purchase save failed: {response_data.get('resultMsg')}")

        purchase_data["purchase_payload"] = frappe.as_json(payload)
