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



#%%
# set working directory to Downloads folder

curr_dir = os.path.join(os.environ['USERPROFILE'], "Downloads")
os.chdir(curr_dir)


YNAB_KEYS_DIR = r"C:\users\ryder\keys\YNAB"

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
df.info()

#%%
# reformat Item Total as numeric
df.loc[:, "Item Total"] = df.loc[:, "Item Total"].str.replace("$", "").astype(float)

# reformat Order Date as date
df.loc[:, "Order Date"] = pd.to_datetime(df.loc[:, "Order Date"])

df.loc[:, ["Order Date", "Title", "Item Total"]].info()



#%%
df_recent = df.sort_values("Order Date", ascending = False).head(30).reset_index()


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
    dat = dat[dat[date_col] > n_days_ago].reset_index()
    
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
def get_trans_from_ynab(ynab_keys_dir=YNAB_KEYS_DIR, 
                        since_date=datetime.now() - timedelta(days=30)):

    # since_date = get_last_trns_date()

    ynab_client_key_path = os.path.join(ynab_keys_dir, "ynab_api_key.txt")
    ynab_budget_id_path = os.path.join(ynab_keys_dir, "ynab_budget_id.txt")
    
    with open(ynab_client_key_path, 'r') as y_api_key_txt:
        YNAB_CLIENT_KEY = y_api_key_txt.readline().strip()

    with open(ynab_budget_id_path, 'r') as y_bud_id_txt:
        YNAB_BUDGET_ID = y_bud_id_txt.readline().strip()

    yc = YnabClient(YNAB_CLIENT_KEY)

    all_transactions = yc.get_transaction(budget_id=YNAB_BUDGET_ID)

    column_names = ['date', 'payee_name', 'account_name', 'category_name', 'memo', 'amount']
    listofitems = []

    for item in all_transactions:
        listofitems.append(str(item.date)           + ',,,' + 
                           str(item.payee_name)     + ',,,' +
                           str(item.account_name)   + ',,,' +
                           str(item.category_name)  + ',,,' + 
                           str(item.memo)           + ',,,' +
                           str(item.amount)
                          )

    ynab_df = pd.Series(listofitems).str.split(',,,', expand=True)
    ynab_df.columns = column_names
    ynab_df.date = pd.to_datetime(ynab_df.date)
    ynab_df.amount = ynab_df.amount.astype(int) / -1000

    ynab_df_filter = ynab_df[(ynab_df.date >= since_date)]



    return(ynab_df_filter)
        

#%%
ynab_df = get_trans_from_ynab()
ynab_df = ynab_df.loc[ynab_df.account_name == "RC AMZ 6063 (12th)"]
ynab_df = ynab_df.loc[ynab_df.category_name.isin(["None", ""])]
ynab_df = ynab_df.loc[~ynab_df.payee_name.str.contains("Transfer")]

#%%
indices = find_possible_order_combinations(dat = df, 
                                           max_combo_size = 3,
                                           lookback = 15,
                                           charge = 36.03)
#%%
for index, row in ynab_df.iterrows():
    print()
    
    print("=" * 8)
    
    
    find_possible_order_combinations(dat=df,
                                     max_combo_size=3,
                                     lookback=15,
                                     charge=row["amount"])
