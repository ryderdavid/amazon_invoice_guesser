# -*- coding: utf-8 -*-

"""
Created on Mon Jun 15 00:49:29 2020

@author: ryder
"""
#%%
import pandas as pd
from itertools import combinations
from datetime import date, datetime, timedelta
import os
import re
from pynabapi import YnabClient
import json
import requests

# import credentials in better way
with open('/Users/ryder/.credentials/ynab.json', 'r') as file:
    ynab_creds = json.loads(file.read())
    
YNAB_API_KEY = ynab_creds['api_key']
YNAB_BUDGET_ID = ynab_creds['budget_id']


#%%
# set working directory to Downloads folder
if os.name == "posix":
    curr_dir = os.path.join(os.path.expanduser('~'), "Downloads")
else:
    curr_dir = os.path.join(os.environ['USERPROFILE'], "Downloads")

os.chdir(curr_dir)

YNAB_KEYS_DIR = os.path.join("~", "keys", "YNAB")

#%%
files = filter(os.path.isfile, os.listdir(curr_dir))
files = [os.path.join(curr_dir, f) for f in files]  # add path to each file

def find_newest_amazon_report( path_to_dir=os.getcwd() ):
    filenames = os.listdir(path_to_dir)
    csv_files = [ filename for filename in filenames if filename.endswith( ".csv" ) ]
    
    ptn = re.compile("\d{2}-\w{3}-\d{4}_to_\d{2}-\w{3}-\d{4}")
    
    amazon_files = [csv for csv in csv_files if ptn.match(csv)]
    
    newest_amzfile = max(amazon_files, key=os.path.getctime)
    
    return(newest_amzfile)

newest_amzfile = find_newest_amazon_report()


#%%
df = pd.read_csv(newest_amzfile)
df.columns = df.columns.str.replace('\W+', '_').str.lower()

df.item_total = df.item_total.str.replace("$", "", regex=False).astype(float)
df.order_date = pd.to_datetime(df.order_date)

df_recent = (
    df.sort_values("order_date", ascending=False)
    .head(30)
    .reset_index(drop=True)
)

#%%
earliest_amz_tx_dt = df_recent['Order Date'].min().date()

#%%
def find_possible_order_combinations(dat, 
                                     names_col="Title", 
                                     prices_col="Item Total", 
                                     date_col="Order Date",
                                     charge=0, 
                                     max_combo_size=5,
                                     lookback=7):
    
    # filter the dataframe by how many days you want to look back
    n_days_ago = datetime.now() - timedelta(days=lookback)
    # dat = dat[dat[date_col] > n_days_ago].reset_index()

    
    index_combinations = []
    prices = dat[prices_col]
    
    # iterate over each number of possible combination sizes 
    for combo_size in range(1, max_combo_size + 1):
        
        index_combinations.extend(list(combinations(range(len(prices)), combo_size)))
        
    
    combo_matches = []
    for index_combo in index_combinations:
        combo_total = sum(dat.loc[index_combo, prices_col])
        # print(combo_total)
        if combo_total == charge:
            # print(combo_total)
            # print(index_combo)
            items = dat.loc[index_combo, names_col]
            combo_matches.append(items)
            
            print(f"{len(items)} items add up to {charge}: ")
            
            print(dat.loc[index_combo, ["Order Date", names_col, prices_col]])

    if len(combo_matches) == 0:
        print(f"No matches for {charge}")
        
        
        
#%%
def get_trans_from_ynab(creds, since_date):

    url = (
      f"https://api.youneedabudget.com/v1/budgets/" \
      f"{YNAB_BUDGET_ID}/transactions?since_date={since_date}" \
      "&type=unapproved"
    )
    
    resp = requests.get(url, headers = {"Authorization": f"bearer {YNAB_API_KEY}"})

    j = json.loads(resp.text)
    
    ynab_df = pd.json_normalize(j['data']['transactions'])
    
    ynab_df = ynab_df[[
      'date', 
      'payee_name', 
      'account_name', 
      'category_name', 
      'memo', 
      'amount'
    ]]
    
    ynab_df.date = pd.to_datetime(ynab_df.date)
    ynab_df.amount = ynab_df.amount.astype(int) / -1000

    return ynab_df
        

#%%

forty_days_ago = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")

ynab_df = get_trans_from_ynab(creds=ynab_creds, since_date=forty_days_ago)


# %%
ynab_df = ynab_df.loc[ynab_df.account_name == "RC AMZ 6063 (12th)"]

# %%
ynab_df = ynab_df.loc[~ynab_df.payee_name.str.contains("Transfer")]




# %%
for index, row in ynab_df.iterrows():
    print()
    
    print("=" * 8)
    
    
    find_possible_order_combinations(dat=ynab_df,
                                     max_combo_size=3,
                                     lookback=15,
                                     charge=ynab_df["amount"])

# %%
find_possible_order_combinations(dat=df,
                                    max_combo_size=3,
                                    lookback=15,
                                    charge=105.99)
# %%
