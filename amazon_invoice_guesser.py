# -*- coding: utf-8 -*-
"""
Created on Mon Jun 15 00:49:29 2020

@author: ryder
"""

import pandas as pd
from itertools import combinations
from datetime import date, datetime, timedelta


#%%
df = pd.read_csv("~/Downloads/29-May-2020_to_28-Jun-2020.csv")
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
    for index in range(1, max_combo_size + 1):
        
        index_combinations.extend(list(combinations(range(len(prices)), index)))
        
    
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
        print("No matches")

#%%
indices = find_possible_order_combinations(dat = df, 
                                           max_combo_size = 3,
                                           lookback = 15,
                                           charge = 31.22)


