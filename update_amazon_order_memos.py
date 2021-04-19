# %%
import os

# selenium for downloading amazon reports
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys

from amazoncaptcha import AmazonCaptcha


import subprocess  # for shell commands to 
from getpass import getpass
import json
import pandas as pd
import numpy as np
import pathlib
import time
import datetime
from distutils import spawn


import pandas as pd
import numpy as np
import json
import os
import requests
from pprint import pprint
from time import strftime, strptime
from datetime import datetime, timedelta


# %%
# make sure program directory has a place to download csvs, 
# then step into that dir
DOWNLOAD_DIR = os.path.join(os.getcwd(), "download")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

os.chdir(DOWNLOAD_DIR)

# Function definitions =======================================================

# 1Password functions: -----------------------------
def get_op_session_token(pw):
    """Generate OnePassword Session Token

    Args:
        pw (str): your onepassword master password

    Returns:
        str: your onepassword session token; works for 30 minutes.
    """
    pw_b = pw.encode('utf-8')
    cmd = "op signin my --raw".split()
    op_token = (
        subprocess.run(cmd, input=pw_b, capture_output=True)
        .stdout
        .decode('utf-8')
        .rstrip()
    )
    return op_token


def get_op_totp(item, session_token):
    cmd = f"op get totp {item} --session {session_token}".split()
    return subprocess.run(cmd, capture_output=True, text=True).stdout.rstrip()


def get_op_field(item, field, session_token):
    cmd = (
        f"op get item {item} --fields {field} --session {session_token}"
        .split()
    )
    return subprocess.run(cmd, capture_output=True, text=True).stdout.rstrip()


# Selenium functions ------------------------------------------------
def download_amz_report(which_report, op_token, download_dir=os.getcwd()):
    """
    Use Selenium to download an Amazon B2B report from 
    https://www.amazon.com/gp/b2b/reports. Saves to CSV.

    Args:
        which_report (str): either "items" or "orders"
        download_dir (str, optional): path to download directory. 
                                      Defaults to os.getcwd().

    Returns:
        None
    """
    assert which_report in ["items", "orders"]

    # set up options for where to download the report
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--verbose")
    prefs = { "download.default_directory" : download_dir }
    chrome_options.add_experimental_option("prefs", prefs)

    # initiate the webdriver
    chromedriver = spawn.find_executable("chromedriver")
    driver = webdriver.Chrome(chromedriver, options=chrome_options)

    driver.get("https://www.amazon.com/gp/b2b/reports")
    driver.find_element_by_id("ap_email").send_keys(get_op_field("Amazon", "username", op_token))
    driver.find_element_by_id("continue").click()
    time.sleep(np.random.random() * 10)
    driver.find_element_by_id("ap_password").send_keys(get_op_field("Amazon", "password", op_token))
    driver.find_element_by_id("signInSubmit").click()
    time.sleep(np.random.random() * 10)
    driver.find_element_by_id("auth-mfa-otpcode").send_keys(get_op_totp("Amazon", op_token))
    driver.find_element_by_id("auth-signin-button").click()
    time.sleep(np.random.random() * 10)
    driver.find_element_by_id("report-type").send_keys([which_report, Keys.RETURN])
    driver.find_element_by_id("report-last30Days").click()
    driver.find_element_by_id("report-type").click()
    driver.find_element_by_id("report-confirm").click()

    time.sleep(np.random.random() * 10)

    def get_latest_csv():
        files = [f for f in os.listdir() if f.endswith(".csv") or f.endswith(".CSV")]
        return max(files, key=os.path.getctime)

    file = get_latest_csv()
    os.rename(file, f"{which_report}.csv")
    print(f"Renamed {file} to {which_report}.csv")
    driver.quit()


# def load_amz_csv_from_disk(csv):



def load_and_process_amz_csv(csv):
    df = pd.read_csv(csv)
    r, c = df.shape
    print(f"Loaded {r} rows and {c} columns from {csv}.")
    
    # cast all colnames to lowercase and replace spaces with underscores
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]

    # identify money related columns based on keywords
    keywords = ["total", "charge", "amount"]
    moneycols = df.columns[
        df.columns.str.contains("|".join(keywords))
    ]

    # format money columns like YNAB: $10.00 charge = -1000
    def reformat_moneycols_like_ynab(c):
        return (
            c.str.replace("$", "", regex=False)
            .astype(float)
            .multiply(-1000)
            .astype(int)
        )

    df[moneycols] = (
        df[moneycols].apply(reformat_moneycols_like_ynab, axis=1)
    )
    print(f"Converted columns {', '.join(moneycols)} to YNAB currency format.")

    # reformat date columns to datetime:
    datecols = df.columns[df.columns.str.contains("date")]
    df[datecols] = df[datecols].apply(lambda x: pd.to_datetime(x))
    print(f"Converted columns {', '.join(datecols)} to pandas datetime format.")

    return df


def summarize_items_report_by_order(items):
    # truncate item descriptions
    items['title_short'] = items.title[:35] + "..."

    # aggregate descriptions and costs
    items_grouped = (
        items.groupby(['order_date', 'order_id'])
        .agg({"title_short": list, "item_total": list})
        .reset_index()
    )

    # add length of item counts
    items_grouped['item_count'] = items_grouped.item_total.apply(len)

    # add description (count): [prices] -- [titles] for multiple item orders
    def create_description(x):
        if x.item_count > 1:
            return f"({x.item_count}): {x.item_total} -- {x.title_short}"
        else:
            return x.title_short[0]

    # create the order descriptions
    items_grouped['description'] = (
        items_grouped.apply(lambda x: create_description(x), axis=1)
    )
    return items_grouped


# YNAB FUNCTIONS ==================================================
budget_id = os.environ["YNAB_BUDGET_ID"]
token = os.environ["YNAB_KEY"]

def get_ynab_transactions(budget_id, token, since_date=None):
    base_url = "https://api.youneedabudget.com/v1"
    request_url = f"{base_url}/budgets/{budget_id}/transactions"
    r = requests.get(request_url, params = {"access_token": token, "since_date": since_date})
    if since_date:
        print(f"Downloading transactions from YNAB API since {since_date}...")
    else:
        print(f"Downloading all transactions from YNAB API...")

    print(r)
    j = json.loads(r.text)
    ynab_tx = pd.json_normalize(j['data']['transactions'])
    return ynab_tx


def memoize_ynab_transactions_from_amz_data(ynab_tx, amz_memoized_orders):

    # just get the amazon ones that haven't been approved yet
    ynab_amz_tx = (
        ynab_tx
        .query("account_name.str.contains('AMZ')")
        .query("approved == False")
    )

    # match the ynab transactions with their amazon order counterparts
    matches = pd.merge(
        ynab_amz_tx, 
        amz_memoized_orders,
        how="left",
        left_on='amount', 
        right_on='total_charged'
    )

    # if there was no match on a ynab transaction (not found in amz report),
    # then give it a no match found memo
    matches.memo = (
        matches.description.apply(
            lambda x: "No match found" if pd.isnull(x) else x
        )
    )
    # then flag it red
    matches.flag_color = (
        matches.description.apply(
            lambda x: "Red" if pd.isnull(x) else None
        )
    )
    
    # only keep the ynab relevant columns now that 
    # description has been copied into memo
    matched_ynab_tx = matches[ynab_amz_tx.columns]

    # if the final match dataframe has no matches just print that 
    # there's nothing to do and move on
    if matched_ynab_tx.shape[0] == 0:
        raise("No transactions found to memo; nothing to do!")

    return matched_ynab_tx


def upload_tx_to_ynab(ynab_tx, budget_id, token):
    base_url = "https://api.youneedabudget.com/v1"
    request_url = f"{base_url}/budgets/{budget_id}/transactions"

    ynab_tx_js = ynab_tx.to_json(orient='records')
    ynab_j = json.loads(ynab_tx_js)

    j = json.dumps({
        "transactions": ynab_j
    })

    js = json.loads(j)

    print(js)

    r = requests.patch(
        request_url, 
        data=j, 
        headers={
            "Authorization": f"Bearer {token}", 
            'Content-Type':'application/json'
        }
    )

    print("YNAB API Response:")
    print(r)

# %%


def main(cleanup=False):
    op_token = get_op_session_token(pw=getpass("Enter OP Master Password: "))

    # download the items and orders csvs -- only if necessary
    if not os.path.exists('items.csv'):
        print("Getting Amazon Items Report... This might take a bit...")
        download_amz_report(which_report="items", op_token=op_token)
    else:
        print("Items CSV exists, skipping download")
    if not os.path.exists('orders.csv'):
        print("Getting Amazon Orders Report... This might take a bit...")
        download_amz_report(which_report="orders", op_token=op_token)
    else:
        print("Orders CSV exists, skipping download")
    
    orders = load_and_process_amz_csv('orders.csv')
    items = load_and_process_amz_csv('items.csv')

    items_grouped = summarize_items_report_by_order(items=items)

    # add on the items_grouped (containing the order description field) 
    # to the orders dataframe (so we get the order total that includes 
    # shipping costs
    orders_memoized = pd.merge(
        orders, 
        items_grouped
    )

    # set a date 7 days before the earliest transaction in the amazon
    # reports to make sure we get all the relevant YNAB transactions
    ynab_since_date = (
        ( min(orders_memoized.order_date) - timedelta(days=7) )
        .strftime("%Y-%m-%d")
    )

    # YNAB transactions -------------------------------------------------------

    ynab_tx = get_ynab_transactions(
        budget_id=os.environ["YNAB_BUDGET_ID"],
        since_date=ynab_since_date,
        token=os.environ["YNAB_KEY"]
    )

    matched_ynab_tx = memoize_ynab_transactions_from_amz_data(
        ynab_tx=ynab_tx, 
        amz_memoized_orders=orders_memoized
    )

    print("New Transactions in YNAB AMZ Account: ")
    print(
        matched_ynab_tx[['date', 'amount', 'memo']].apply(
            lambda x: x / -1000 if x.name == 'amount' else x
        )
    )

    print("Updating the memos in YNAB...")
    upload_tx_to_ynab(
        ynab_tx=matched_ynab_tx, 
        budget_id=os.environ["YNAB_BUDGET_ID"], 
        token=os.environ["YNAB_KEY"]
    )

    if cleanup:
        print("Cleaning up download directory...")
        [os.remove(c) for c in os.listdir() if c.endswith('.csv')]

    print("Done.")

if __name__ == "__main__":
    main()
