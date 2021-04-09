# %%
import os
import requests
import json

budget_id = os.environ["YNAB_BUDGET_ID"]
token = os.environ["YNAB_KEY"]

base_url = "https://api.youneedabudget.com/v1"
request_url = f"{base_url}/budgets/{budget_id}/transactions"
request_url



r = requests.get(request_url, params = {"access_token": token, "since_date": ynab_since_date})
j = json.loads(r.text)

print(j)