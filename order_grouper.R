library(tidyverse)
library(lubridate)
library(janitor)
library(here)
library(httr)
library(fs)


DOWNLOADS_DIR <- "~/Downloads"



browseURL('https://www.amazon.com/gp/b2b/reports')



get_latest_amz_order_file <- function() {
  ptn <- "\\d{2}-\\w{3}-\\d{4}_to_\\d{2}-\\w{3}-\\d{4}.csv"
  
  latest_amz_csv <- fs::dir_info() %>% 
    filter(str_detect(path, ptn)) %>% 
    arrange(desc(birth_time)) %>% 
    slice(1) %>% 
    pull(path)
  
  read_csv(latest_amz_file) %>% 
    janitor::clean_names() %>% 
    mutate(order_date = lubridate::mdy(order_date))
}


summarize_amz_report <- function(dat) {
  dat %>% 
    # where a variable has the word total, remove dollar sign and cast to numeric
    mutate_at(vars(contains('total')), ~ str_remove(., "\\$") %>% as.numeric()) %>% 
    # trim each title and add ellipsis, call it title_short
    mutate(title_short = substr(title, 1, 35) %>% paste0(., "...")) %>% 
    # group by order date and id and aggregate:
    group_by(order_id, order_date) %>% 
    summarize(
      # create order total value
      order_total = sum(item_total)  
      # order count by that group of items in order
      , item_count = n()  
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
    select(order_date, order_total, items)
}

amz_orderinfo <- 
  get_latest_amz_order_file() %>% 
  summarize_amz_report()



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
  
  query <- list(budget_id=budget_id,
                access_token=token,
                since_date=since_date)
  
  httr::GET(request_url, query=query) %>%
    httr::content("text") %>% 
    jsonlite::fromJSON() %>% 
    .$data %>% 
    .$transactions %>% 
    tibble() %>% 
    mutate(amount = amount / -1000.00)
}

dat_ynab <- get_transactions_from_ynab(budget_id, token, '2021-01-01')

dat_ynab_amz_new <- dat_ynab %>% 
  filter(approved == FALSE) %>% 
  filter(str_detect(account_name, "AMZ")) %>% 
  mutate(max_date = lubridate::ymd(date) %m+% days(5),
         min_date = lubridate::ymd(date) %m-% days(5))


# match transactions --------------------------------------------------------



