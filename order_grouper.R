library(tidyverse)
library(lubridate)
library(janitor)
library(here)
library(httr)
library(fs)
library(fuzzyjoin)


DOWNLOADS_DIR <- "~/Downloads"



browseURL('https://www.amazon.com/gp/b2b/reports')









# ---------------------------

amz_orderinfo <- 
  read_csv("10-Mar-2021_to_09-Apr-2021 (1).csv") %>% 
  janitor::clean_names()






get_latest_amz_order_file <- function() {
  ptn <- "\\d{2}-\\w{3}-\\d{4}_to_\\d{2}-\\w{3}-\\d{4}.csv"
  
  latest_amz_csv <- fs::dir_info() %>% 
    filter(str_detect(path, ptn)) %>% 
    arrange(desc(birth_time)) %>% 
    slice(1) %>% 
    pull(path)
  
  read_csv(latest_amz_csv) %>% 
    janitor::clean_names() %>% 
    mutate(order_date = lubridate::mdy(order_date))
}







memoize_amz_orders <- function(items, orders) {
  items_summary <- items %>% 
    # trim each title and add ellipsis, call it title_short
    mutate(title_short = substr(title, 1, 35) %>% paste0(., "...")) %>% 
    # group by order date and id and aggregate:
    group_by(order_id, order_date) %>% 
    summarize(
      # # create order total value
      # order_total = sum(item_total)  
      # order count by that group of items in order
      item_count = n()  
      # semicolon delim string list of subtotals for items
      , item_totals = paste(item_total, collapse = "; ")  
      # concatenate short descriptions into semicolon delim string list
      , items = paste(title_short, collapse = "; ")
    ) %>% 
    ungroup() %>% 
    mutate(
      items = ifelse(
        item_count > 1, 
        glue::glue("({item_count}): [{item_totals}]; [{items}]"),
        items
      )
    ) %>% 
    select(order_id, order_date, memo=items)
  
  memoized_orders <- orders %>% 
    left_join(items_summary, by = c('order_date', 'order_id')) %>% 
    mutate(total_charged = str_remove_all(total_charged, "\\$")) %>% 
    mutate(total_charged = as.numeric(total_charged)) %>% 
    select(order_id, order_date, total_charged, memo)
  
  return(memoized_orders)
}

# load and summarize the amazon report, then add min and max fuzzy join targets
amz_orderinfo <- read_csv('orders.csv') %>% 
  janitor::clean_names() %>% 
  mutate(order_date = lubridate::mdy(order_date))
  
amz_iteminfo <- read_csv('items.csv') %>% 
  janitor::clean_names() %>% 
  mutate(order_date = lubridate::mdy(order_date))
  
amz_order_summary <- 
  memoize_amz_orders(amz_iteminfo, amz_orderinfo) %>% 
  mutate(max_date = order_date %m+% days(5),
         min_date = order_date %m-% days(5))

# get from ynab -------------------------------------------------------------
budget_id <- "155b5ff2-d41d-45e1-8386-8c95b9f7bba7"
token <- "69018301c972a0e44a3e9865909fe608970d8f9aec237d74f5ff22afd4a8887f"

#' Get transactions from YNAB
#'
#' @param budget_id your budget id from YNAB app
#' @param token your YNAB API token
#' @param since_date (optional) %Y-%m-%d 
#'
#' @return
#' @export
#'
#' @examples
get_transactions_from_ynab <- function(budget_id, token, since_date=NULL) {
  base_url = "https://api.youneedabudget.com/v1"
  request_url = fs::path(base_url, 'budgets', budget_id, 'transactions')
  
  query <- list(access_token=token,
                since_date=since_date)
  
  httr::GET(request_url, query=query) %>%
    httr::content("text") %>% 
    jsonlite::fromJSON() %>% 
    .$data %>% 
    .$transactions %>% 
    tibble() %>% 
    mutate(amount = amount / -1000.00) %>% 
    mutate(date = ymd(date))
}

# get all ynab transactions since 10 days before the earliest AMZ order -----
ten_days_before_amz_orders <- 
  min(amz_order_summary$order_date) %m-% 
  days(10) %>% 
  as.character()

# new Amz transactions in ynab are within 30 days of earliest tx in 30 day
# window, unapproved, and with AMZ in the account name
dat_ynab_amz_new <- 
  get_transactions_from_ynab(budget_id, token, ten_days_before_amz_orders) %>% 
  filter(approved == FALSE) %>% 
  filter(str_detect(account_name, "AMZ"))


# match transactions --------------------------------------------------------
left_is_missing <- function(x, y) {
  is.na(x) & !is.na(y)
}

matches <- dat_ynab_amz_new %>%
  fuzzyjoin::fuzzy_left_join(
    amz_order_summary,
    by = c(
      'amount' = 'total_charged',
      'date' = 'max_date',
      'date' = 'min_date'
    ),
    match_fun = list(`==`, `<=`, `>=`)
  ) %>% 
  select(id, date, amount, memo=memo.y, everything()) %>% 
  select(!c(order_id, order_date, total_charged, max_date, min_date, memo.x)) %>% 
  mutate(flag_color = ifelse(is.na(memo), 'red', NA)) %>% 
  mutate(category_id = NA, category_name = NA) %>% 
  mutate(amount = amount * -1000.00)



matches_j <- list(transactions = matches)


update_transactions_in_ynab <- function(dat, budget_id, token) {
  base_url = "https://api.youneedabudget.com/v1"
  request_url = fs::path(base_url, 'budgets', budget_id, 'transactions')
  
  j <- list(transactions = dat) %>% jsonlite::toJSON(pretty = TRUE)
  
  # query <- list(access_token=token)
  body <- list(data=j)
  
  b <- list(transactions = matches) %>% toJSON(pretty=F)
  
  res <- httr::PATCH(request_url, 
                     body = list(
                       data = b
                     ),
                     encode='json',
                     add_headers(Authorization = glue::glue("Bearer {token}"), 
                                 `Content-Type` = "application/json")
                     )
  
  return(res)
  
}

r <- update_transactions_in_ynab(matches, budget_id, token)

httr::content(r, "text")

write_json(matches, path = 'matches.json')
