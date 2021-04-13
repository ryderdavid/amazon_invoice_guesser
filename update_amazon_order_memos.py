# %%
import os
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
import subprocess
import getpass
import json
import pandas as pd
import numpy as np
import pathlib
import time
import datetime
from distutils import spawn


import pandas as pd
import json
import os
import requests
from pprint import pprint
from time import strftime, strptime
from datetime import datetime, timedelta


# %%
DOWNLOAD_DIR = os.path.join(os.getcwd(), "download")

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# %%
os.chdir(DOWNLOAD_DIR)

# %%
def op_signin(pw=None):
    if not pw:
        pw = getpass.getpass("Enter OP Password: ")
    session_token = subprocess.run(
        f"echo {pw} | op signin my --raw", 
        shell=True, capture_output=True, text=True
    ).stdout.rstrip()
    return session_token

def get_from_op(account_item, what, session_token):
    # assert what in ["totp", "email", "password"]

    if what == 'totp':
        cmd = f"op get totp {account_item} --session {session_token}"
        return subprocess.run(cmd.split(), capture_output=True, text=True).stdout.rstrip()
    else:
        cmd = f"op get item {account_item} --fields {what} --session {session_token}"
        return subprocess.run(cmd.split(), capture_output=True, text=True).stdout.rstrip()


def download_amz_report(which_report, download_dir=os.getcwd()):
    assert which_report in ["items", "orders"]

    # set up options for where to download the report
    chrome_options = webdriver.ChromeOptions()
    prefs = { "download.default_directory" : download_dir }
    chrome_options.add_experimental_option("prefs", prefs)

    # initiate the webdriver
    chromedriver = spawn.find_executable("chromedriver")
    driver = webdriver.Chrome(chromedriver, options=chrome_options)

    driver.get("https://www.amazon.com/gp/b2b/reports")
    driver.find_element_by_id("ap_email").send_keys(get_from_op("Amazon", "username", op_token))
    driver.find_element_by_id("continue").click()
    time.sleep(0.5)
    driver.find_element_by_id("ap_password").send_keys(get_from_op("Amazon", "password", op_token))
    driver.find_element_by_id("signInSubmit").click()
    time.sleep(0.5)
    driver.find_element_by_id("auth-mfa-otpcode").send_keys(get_from_op("Amazon", "totp", op_token))
    driver.find_element_by_id("auth-signin-button").click()
    time.sleep(0.5)
    driver.find_element_by_id("report-type").send_keys([which_report, Keys.RETURN])
    driver.find_element_by_id("report-last30Days").click()
    driver.find_element_by_id("report-type").click()
    driver.find_element_by_id("report-confirm").click()

    time.sleep(20)
    driver.quit()

def get_latest_csv():
    filedata = pd.DataFrame({"filename": [c for c in os.listdir() if c.endswith(".csv")]})
    filedata['ctime'] = filedata.filename.apply(lambda x: os.path.getctime(x))
    latest_csv = filedata.sort_values("ctime", ascending=False).loc[0, "filename"]
    return latest_csv

def normalize_names(df):
    df.columns = df.columns.str.replace(" ", "_").str.lower()
    return df


# %%
def orders_memoize(items_csv, orders_csv):

    items = normalize_names(pd.read_csv(items_csv))
    orders = normalize_names(pd.read_csv(orders_csv))

    items['title_short'] = items.title[:35] + "..."

    # aggregate descriptions and costs
    items_grouped = (
        items.groupby(['order_date', 'order_id'])
        .agg({"title_short": list, "item_total": list})
        .reset_index()
    )

    # add length of item counts
    items_grouped['item_count'] = items_grouped.item_total.apply(len)

    # add description (count): [prices] -- [titles]
    def create_description(x):
        if x.item_count > 1:
            return f"({x.item_count}): {x.item_total} -- {x.title_short}" # str(x.item_total) + " -- " + str(x.title_short)
        else:
            return x.title_short[0]
        
    items_grouped['description'] = items_grouped.apply(lambda x: create_description(x), axis=1)

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

    op_token = op_signin()

    download_amz_report(which_report="items")

    # %%
    os.rename(get_latest_csv(), "items.csv")

    # %%
    download_amz_report(which_report="orders")

    # %%
    os.rename(get_latest_csv(), "orders.csv")


    # %%
    # items = normalize_names(pd.read_csv(items_csv))
    # orders = normalize_names(pd.read_csv(orders_csv))

    # items['title_short'] = items.title[:35] + "..."

    # # aggregate descriptions and costs
    # items_grouped = (
    #     items.groupby(['order_date', 'order_id'])
    #     .agg({"title_short": list, "item_total": list})
    #     .reset_index()
    # )


    # %%
    orders_memoize(items_csv='items.csv', orders_csv='orders.csv')

    [os.remove(c) for c in os.listdir() if c.endswith('.csv')]