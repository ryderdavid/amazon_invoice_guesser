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

op_token = op_signin(pw="sandy pace chile dawn rift pause meier")


# %%
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
    filedata['mtime'] = filedata.filename.apply(lambda x: os.path.getmtime(x))
    latest_csv = filedata.sort_values("mtime", ascending=False).loc[0, "filename"]
    return latest_csv

download_amz_report(which_report="items")


os.rename(get_latest_csv(), "items.csv")

download_amz_report(which_report="orders")

os.rename(get_latest_csv(), "orders.csv")


