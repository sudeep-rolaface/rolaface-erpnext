from erpnext.zra_client.main import ZRAClient
from frappe import throw, _

class Imports(ZRAClient):
    def __init__(self):
        super().__init__()

    def get_tpin(self):
        return self.tpin
    
    def get_bhf_id(self):
        return self.branch_code
    
    def call_update_import(self, payload):
        self.zra_client_update_import(payload)

    def update_import(self, import_data):
        print(import_data)
        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_bhf_id(),
            "taskCd": "4561614",
            "dclDe": "20240426",
            "importItemList": [
                {
                "itemSeq": 2,
                "hsCd": "72149900000",
                "itemClsCd": "5022110801",
                "itemCd": "RW1NTXU0000006",
                "imptItemSttsCd": "3",
                "remark": "remark",
                "modrNm": "Admin",
                "modrId": "Admin"
                },
                {
                "itemSeq": 3,
                "hsCd": "04051000000",
                "itemClsCd": "5022110802",
                "itemCd": "RW1NTXU0000007",
                "imptItemSttsCd": "4",
                "remark": "This is a non-stock item",
                "modrNm": "Admin2",
                "modrId": "Admin2"
                }
            ]
            }


        
        
        self.call_update_import(payload)
        throw(_("🚫 You cannot create a purchase order for an import transaction. Please select a valid supplier."))

    def update_stock():
        pass

    def update_stock_master():
        pass