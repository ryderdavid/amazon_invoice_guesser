import pandas as pd
import os
import string
import re
import datetime

amz = pd.read_csv(os.path.join("~", "Downloads", "26-Feb-2021_to_28-Mar-2021.csv"))
amz.columns = [re.sub(r'[^\w\d]', '_', c).lower() for c in amz.columns]
# amz.order_date = pd.to_datetime(amz.order_date)
moneycols = [c for c in amz.columns if "total" in c]
amz[moneycols] = (
  amz[moneycols].apply(lambda x: x.str.replace("$", "", regex=False).astype(float))
)
amz['title_short'] = amz.title.str.slice(0, 50) + "..."


# aggregate to create summary --------------------------------------------------
key = ['order_id', 'order_date']

amz_orderinfo = (
  amz.assign(item_count = 1)
    .groupby(key)
    .agg({
       "item_total": list 
      , "title_short": list
      , "item_count": sum
    })
)

amz_orderinfo['order_total'] = amz_orderinfo.item_total.apply(sum)

amz_orderinfo = amz_orderinfo.reset_index()
amz_orderinfo = amz_orderinfo.rename(columns = {"item_total": "item_amounts"})

amz_orderinfo['memo'] = amz_orderinfo.item_amounts + amz_orderinfo.title_short
amz_orderinfo.memo = amz_orderinfo.memo.apply(lambda x: [str(i) for i in x])
amz_orderinfo.memo = amz_orderinfo.memo.apply(lambda x: "; ".join(x))

amz_orderinfo.memo = (
  "(" + amz_orderinfo.item_count.astype(str) + ") " + amz_orderinfo.memo
)


amz_orderinfo = amz_orderinfo[['order_date', 'order_total', 'memo']]

# get amazon transactions from YNAB --------------------------------------------
import requests
import json
token = "69018301c972a0e44a3e9865909fe608970d8f9aec237d74f5ff22afd4a8887f"
budget_id = "155b5ff2-d41d-45e1-8386-8c95b9f7bba7"

def get_transactions_from_ynab(budget_id, token, since_date):
  base_url = "https://api.youneedabudget.com/v1"
  request_url = os.path.join(base_url, 'budgets', budget_id, 'transactions')
  params = {
    "since_date": since_date,
    "access_token": token
  }
  res = requests.get(request_url, params=params)
  resj = json.loads(res.content)
  df = pd.json_normalize(resj['data']['transactions'])
  df.amount = df.amount / -1000.00
  return df

base_url = "https://api.youneedabudget.com/v1"
request_url = os.path.join(base_url, 'budgets', budget_id, 'transactions')
params = {
  "since_date": '2021-01-01',
  "access_token": token
}
res = requests.get(request_url, params=params)
resj = json.loads(res.content)
df = pd.json_normalize(resj['data']['transactions'])
df.amount = df.amount / -1000.00
ynab_tx = get_transactions_from_ynab(budget_id=budget_id, token=token, since_date="2021-01-01")

ynab_amz = (
  ynab_tx
    .query("account_name == 'RC AMZ 6063 (12th)'")
    .query("payee_name != 'Audible'")
    .query("approved == False")
)

strftime(strptime(amz_orderinfo.order_date.loc[0], "%m/%d/%y"), "%Y-%m-%d")
