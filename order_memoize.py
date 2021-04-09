# %%
import pandas as pd
import json
import os
import requests
from pprint import pprint
from time import strftime, strptime
from datetime import datetime, timedelta
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", help="Path to CSV of Amazon Items Report")
    parser.add_argument("--orders", help="Path to CSV of Amazon Orders Report")

    args = parser.parse_args()

    def normalize_names(df):
        df.columns = df.columns.str.replace(" ", "_").str.lower()
        return df

    items = normalize_names(pd.read_csv(args.items))
    orders = normalize_names(pd.read_csv(args.orders))


    # process items
    items['title_short'] = items.title.apply(lambda x: x[:35] + "...")
    items['item_total'] = items.item_total.str.replace("$", "", regex=False).astype(float)

    # aggregate descriptions and costs
    items_grouped = (
        items.groupby(['order_date', 'order_id'])
        .agg({"title_short": list, 
            "item_total": list})
        .reset_index()
    )

    # add length of item counts
    items_grouped['item_count'] = items_grouped.item_total.apply(len)

    # add memo (count): [prices] -- [titles]
    def create_memo(x):
        if x.item_count > 1:
            return f"({x.item_count}): {x.item_total} -- {x.title_short}" # str(x.item_total) + " -- " + str(x.title_short)
        else:
            return x.title_short[0]
        
    items_grouped['description'] = items_grouped.apply(lambda x: create_memo(x), axis=1)

    # merge both
    orders_memoized = pd.merge(
        orders, 
        items_grouped
    )

    orders_memoized.order_date = pd.to_datetime(orders_memoized.order_date)

    orders_memoized.total_charged = (
        orders_memoized.total_charged
            .str.replace("$", "", regex=False)
            .astype(float)
            .multiply(-1000)
            .astype(int)
    )

    ynab_since_date = (
        ( min(orders_memoized.order_date) - timedelta(days=7) )
        .strftime("%Y-%m-%d")
    )

    # YNAB transactions -------------------------------------------------------
    budget_id = os.environ["YNAB_BUDGET_ID"]
    token = os.environ["YNAB_KEY"]

    base_url = "https://api.youneedabudget.com/v1"
    request_url = f"{base_url}/budgets/{budget_id}/transactions"
    request_url



    r = requests.get(request_url, params = {"access_token": token, "since_date": ynab_since_date})
    j = json.loads(r.text)

    ynab_tx = pd.json_normalize(j['data']['transactions'])


    ynab_amz_tx = (
        ynab_tx
        .query("account_name.str.contains('AMZ')")
        .query("approved == False")
    )

    matches = pd.merge(
        ynab_amz_tx, 
        orders_memoized, 
        left_on='amount', 
        right_on='total_charged'
    )

    matches.memo = matches.description

    matched_ynab_tx = matches[ynab_amz_tx.columns]

    if matched_ynab_tx.shape[0] == 0:
        print("No transactions found to memo; nothing to do!")
        return

    ynab_tx_js = matched_ynab_tx.to_json(orient='records')
    ynab_j = json.loads(ynab_tx_js)

    j = json.dumps({
        "transactions": ynab_j
    })

    js = json.loads(j)

    print(js)

    r = requests.patch(
        request_url, 
        data=js, 
        headers={
            "Authorization": f"Bearer {token}", 
            'Content-Type':'application/json'
        }
    )

    if r.reason == 'OK':
        print(f"Updated memos for {len(js['transactions'])} transactions. They are:")
        print(matched_ynab_tx.memo)
    else:
        print("Could not run program.")
        print(r.reason)


if __name__ == "__main__":
    main()