#!/usr/bin/env python
# -*- coding: utf-8 -*-

# @Filename: calculate_wealth_info_20170417
# @Date: 2017-04-17
# @Author: Mark Wang
# @Email: wangyouan@gmial.com

""" This file based on the 20170413 meeting require """

import os
from dateutil.relativedelta import relativedelta

import pandas as pd

from ChineseStock.constants import Constant as const


class Account(object):
    def __init__(self, p_num, is_reb, i_wealth):
        """
        Init class
        :param p_num: portfolio number 
        :param is_reb: whether this account need to be reblanced or not
        :param i_wealth: initial wealth
        """
        self.account_list = None
        self.free_money = None
        self.free_port = None

        # if not use reblance, we will use account list to count money
        if not is_reb:
            self.account_list = [float(i_wealth) / p_num for _ in range(p_num)]
            self.has_free_port = self._has_free_port_non_reblance
            self.pop_money = self._pop_money_non_reblance
            self.get_total_amount = self._get_total_amount_non_reblance
            self.push_money = self._push_money_non_reblance

        # if reblance, we will use free money and free port count money
        else:
            self.free_money = float(i_wealth)
            self.free_port = p_num
            self.has_free_port = self._has_free_port_reblance
            self.pop_money = self._pop_money_reblance
            self.get_total_amount = self._get_total_amount_reblance
            self.push_money = self._push_money_reblance

    def _has_free_port_reblance(self):
        return self.free_port > 0

    def _pop_money_reblance(self):
        amount = self.free_money / self.free_port
        self.free_money -= amount
        self.free_port -= 1
        return amount

    def _get_total_amount_reblance(self):
        return self.free_money

    def _push_money_reblance(self, money):
        self.free_money += money
        self.free_port += 1

    def _has_free_port_non_reblance(self):
        return len(self.account_list) > 0

    def _pop_money_non_reblance(self):
        return self.account_list.pop(0)

    def _get_total_amount_non_reblance(self):
        return sum(self.account_list)

    def _push_money_non_reblance(self, money):
        self.account_list.append(money)


def calculate_raw_alpha_wealth_series_record(hday, sr, irrp, rp, ap, bp, tag, p, is_reb):
    """
    Generate wealth series not reblance
    :param hday: holding days
    :param sr: stop loss rate
    :param irrp: event report path
    :param rp: raw series result path
    :param ap: alpha series result path
    :param bp: buy and sell record path
    :param tag: name tag
    :param p: portfolio num
    :param is_reb: is reblance, need reblance or not
    :return: raw_series or alpha_series in this test
    """
    if isinstance(sr, float):
        sr = int(100 * abs(sr))

    series_name = '{}_{}p_{}d_2cost_{}sr'.format(tag, p, hday, sr)
    report_file_name = 'hday{}_sr{}.p'.format(hday, sr)

    # read some prepared information
    event_report_df = pd.read_pickle(os.path.join(irrp, report_file_name))
    stock_df = pd.read_pickle(const.STOCK_PRICE_20170408_FILE_13_2)
    index_data_df = pd.read_pickle(const.SZ_399300_PATH)

    # This two account are used
    raw_free_account = Account(p_num=p, is_reb=is_reb, i_wealth=const.initial_wealth)
    alpha_free_account = Account(p_num=p, is_reb=is_reb, i_wealth=const.initial_wealth)

    # holding_tic_dict: This dict saves all the holding tickers info, include the following information
    # {sell_date: [{tic, a_amount, r_amount, buy_date, buy_price, buy_index_price, sell_type, sell_price}]}
    holding_tic_dict = {}

    # trading days list
    tday_list = pd.read_pickle(const.TRADING_DAYS_20170408_FILE)

    # initialize two series to save wealth data and set first date to initial wealth
    raw_series = pd.Series()
    alpha_series = pd.Series()
    raw_series.loc[tday_list[0] - relativedelta(days=1)] = raw_free_account.get_total_amount()
    alpha_series.loc[tday_list[0] - relativedelta(days=1)] = alpha_free_account.get_total_amount()

    # these variables are used to save transaction record information
    keys = list(event_report_df.keys())
    keys.append('amount')
    transaction_df = pd.DataFrame(columns=event_report_df.keys())
    transaction_index = 0

    # this set is used to save holding tickers info. We will neglect some trading signals if we hold those stocks.
    holding_tics = set()

    # start to calculate wealth data
    for current_date in tday_list:

        ################################################################################
        # first buy some stocks
        ################################################################################
        today_report = event_report_df[event_report_df[const.REPORT_BUY_DATE] == current_date]
        today_index_data = index_data_df.loc[current_date]

        if raw_free_account.has_free_port() and not today_report.empty:
            for i in today_report.index:
                # get some useful info
                transaction_df.loc[transaction_index] = today_report.loc[i]
                # if np.isnan(today_report.loc[i, const.REPORT_SELL_PRICE]):
                #     continue
                trading_info = {const.REPORT_BUY_PRICE: today_report.loc[i, const.REPORT_BUY_PRICE],
                                const.REPORT_SELL_PRICE: today_report.loc[i, const.REPORT_SELL_PRICE],
                                const.REPORT_SELL_TYPE: today_report.loc[i, const.REPORT_SELL_TYPE],
                                const.TICKER: today_report.loc[i, const.TICKER],
                                # const.REPORT_BUY_DATE: current_date,
                                'last_price': today_report.loc[i, const.REPORT_BUY_PRICE],
                                }

                if trading_info[const.TICKER] in holding_tics:
                    continue

                sell_date = today_report.loc[i, const.REPORT_SELL_DATE]
                buy_type = today_report.loc[i, const.REPORT_BUY_TYPE]

                # buy raw
                raw_amount = raw_free_account.pop_money()
                trading_info['raw_amount'] = raw_amount * (1 - const.transaction_cost)
                transaction_df.loc[transaction_index, 'amount'] = trading_info['raw_amount']

                # buy alpha
                alpha_amount = alpha_free_account.pop_money()
                trading_info['alpha_amount'] = alpha_amount * (1 - const.transaction_cost)
                trading_info['index_price'] = today_index_data[buy_type]

                if sell_date in holding_tic_dict:
                    holding_tic_dict[sell_date].append(trading_info)

                else:
                    holding_tic_dict[sell_date] = [trading_info]
                transaction_index += 1
                holding_tics.add(trading_info[const.TICKER])

                if not raw_free_account.has_free_port():
                    break

        ################################################################################
        # second sell some stocks
        ################################################################################
        if current_date in holding_tic_dict:

            # sell holding accounts
            for sell_info in holding_tic_dict[current_date]:
                buy_price = sell_info[const.REPORT_BUY_PRICE]
                sell_price = sell_info[const.REPORT_SELL_PRICE]
                raw_amount = sell_info['raw_amount']
                alpha_amount = sell_info['alpha_amount']
                ibuy_price = sell_info['index_price']  # index buy price

                # handle raw account
                raw_amount *= sell_price / buy_price * (1 - const.transaction_cost)
                raw_free_account.push_money(raw_amount)

                # handle alpha account
                isell_price = today_index_data[sell_info[const.REPORT_SELL_TYPE]]  # index sell price
                alpha_amount *= (sell_price / buy_price * (1 - const.transaction_cost) - isell_price / ibuy_price + 1)
                alpha_free_account.push_money(alpha_amount)

                holding_tics.remove(sell_info[const.TICKER])

            # today's sell info handled finished, remove those info
            del holding_tic_dict[current_date]

        ################################################################################
        # The following code is used to calculate today wealth
        ################################################################################
        raw_wealth = raw_free_account.get_total_amount()
        alpha_wealth = alpha_free_account.get_total_amount()

        # get todays index close price
        ic_price = today_index_data[const.STOCK_CLOSE_PRICE]

        for i_date in holding_tic_dict:
            for sell_info in holding_tic_dict[i_date]:
                tic = sell_info[const.TICKER]
                buy_price = sell_info[const.REPORT_BUY_PRICE]
                ibuy_price = sell_info['index_price']
                a_amount = sell_info['alpha_amount']
                r_amount = sell_info['raw_amount']

                # get stock price. If today has no such info, use yesterday's price
                if (current_date, tic) not in stock_df.index:
                    tc_price = sell_info['last_price']
                else:
                    tc_price = sell_info['last_price'] = stock_df.ix[(current_date, tic), const.STOCK_CLOSE_PRICE]

                # handle raw wealth
                raw_wealth += r_amount * tc_price / buy_price

                # handle alpha wealth
                alpha_wealth += a_amount * (tc_price / buy_price - ic_price / ibuy_price + 1)

        raw_series.loc[current_date] = raw_wealth
        alpha_series.loc[current_date] = alpha_wealth

    # save result
    raw_series.to_pickle(os.path.join(rp, '{}.p'.format(series_name)))
    alpha_series.to_pickle(os.path.join(ap, '{}.p'.format(series_name)))
    transaction_df.to_csv(os.path.join(bp, '{}.csv'.format(series_name)))
    return raw_series, alpha_series
