import requests

# -------------------------------
# Configuration
# -------------------------------
API_KEY = "sandbox_sk_1446c0d02f3e20570f47a6c9297a3c149fc635c5946a"

BASE_URL = "https://sandbox-api-d.squadco.com/virtual-account/webhook/logs"
PER_PAGE = 100  # Number of records per page
import requests

# Temporary in-memory store for processed transactions (use a database in production)
processed_transactions = set()

# -------------------------------
# Helper Functions
# -------------------------------

def fetch_missed_webhooks(page=1):
    """Fetch missed webhook notifications from error log"""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    params = {"page": page, "perPage": PER_PAGE}
    
    response = requests.get(BASE_URL, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json().get('data', {})
    else:
        print(f"Failed to fetch logs: {response.status_code} - {response.text}")
        return None

def delete_webhook(transaction_ref):
    """Delete a processed transaction from the error log"""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    delete_url = f"{BASE_URL}/{transaction_ref}"
    
    response = requests.delete(delete_url, headers=headers)
    
    if response.status_code == 200:
        print(f"Deleted transaction {transaction_ref} successfully.")
    else:
        print(f"Failed to delete transaction {transaction_ref}: {response.status_code} - {response.text}")


# -------------------------------
# Main Workflow
# -------------------------------

def prefetch_webhooks(merchant_reference):

    page = 1
    while True:

        data = fetch_missed_webhooks(page)
        if not data or not data.get("rows"):
            print("No more missed transactions to process.")
            break

        rows_data = data.get('rows', []).copy()
        print("rows: ", rows_data)
        success_txn = next(
            (
                row for row in rows_data 
                if row.get('payload', {}).get('merchant_reference', '').lower() == merchant_reference.lower() 
                and row.get('payload', {}).get('transaction_status', '').lower() == 'success'
            ),
            None
        )

        if not success_txn:
            print("no success message")
            return 
        
        if success_txn:
            print("success_txn: ", success_txn)
            return success_txn

        rows = [row for row in rows_data if row['payload']['merchant_reference'].lower() == merchant_reference.lower()]
        print()
        print("rows: ", rows)
        lastest_txn = max(rows, key=lambda x: x['payload']['date'])

        if lastest_txn:
            print("lastest: ", lastest_txn)
            return lastest_txn
        
        # If fewer rows than PER_PAGE, we are at the last page
        if len(data["rows"]) < PER_PAGE:
            break
        page += 1

if __name__ == "__main__":
    prefetch_webhooks(merchant_reference='REF-3ea99af5a5c3481ba9e4abe6ad38b6e1-5680916028')
