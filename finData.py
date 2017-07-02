#-*- coding:utf-8 -*-

import csv
import os

class FinancialData():
    def __init__(self, stock_code, fin_dict, data_target=1, read_csv=False):
        """ Initializes financial data
            @param fin_dict - dictionary of financial data
                             data_name: list of values
                             None if read_csv is True
            @param data_target - 1 for data every quarter (분기/반기/사업보고서), 
                                 2 for only year data (사업보고서)
        """
        self.stock_code = stock_code
        self.data_target = data_target
        # set directories
        HOME_DIR = os.path.join(os.path.expanduser("~"), "workspace")
        DATA_DIR = os.path.join(HOME_DIR, "data")
        self.COMPANY_DIR = os.path.join(DATA_DIR, self.stock_code)
        if not os.path.isdir(self.COMPANY_DIR):
            os.makedirs(self.COMPANY_DIR)
        
        if read_csv:
            """ TODO: fix the manual order of elements to a scalable form """
            filename = "raw_fin_data_%s.csv" % self.stock_code
            assert os.path.isfile(os.path.join(self.COMPANY_DIR, filename))
            self.period_list, self.stock_price_mean_list = [], []
            self.stock_price_median_list, self.stock_price_stdev_list = [], []
            self.stock_price_max_list, self.stock_price_min_list = [], []
            self.stock_num_list, self.curr_asset_list = [], []
            self.noncurr_asset_list, self.total_asset_list = [], []
            self.curr_liab_list, self.noncurr_liab_list = [], []
            self.total_liab_list, self.equity_list = [], []
            self.net_income_list, self.deprec_cost_list = [], []
            print("Reading raw_fin_data_%s.csv" % self.stock_code)
            with open(os.path.join(self.COMPANY_DIR, filename),
                      'r', newline='') as raw_fin_data_file:
                fr = csv.reader(raw_fin_data_file, delimiter=',', quotechar='|')
                next(fr)
                for row in fr:
                    self.period_list.append(row[0])
                    self.stock_price_mean_list.append(row[1])
                    self.stock_price_median_list.append(row[2])
                    self.stock_price_max_list.append(row[3])
                    self.stock_price_min_list.append(row[4])
                    self.stock_price_stdev_list.append(row[5])
                    self.stock_num_list.append(row[6])
                    self.curr_asset_list.append(row[7])
                    self.noncurr_asset_list.append(row[8])
                    self.total_asset_list.append(row[9])
                    self.curr_liab_list.append(row[10])
                    self.noncurr_liab_list.append(row[11])
                    self.total_liab_list.append(row[12])
                    self.equity_list.append(row[13])
                    self.net_income_list.append(row[14])
                    self.deprec_cost_list.append(row[15])
                    
        else:
            self.period_list = fin_dict["period"] # list of periods for rcp_no
            self.curr_asset_list = fin_dict["curr_asset"]
            self.noncurr_asset_list = fin_dict["noncurr_asset"]
            self.total_asset_list = fin_dict["total_asset"]
            self.curr_liab_list = fin_dict["curr_liabilities"]
            self.noncurr_liab_list = fin_dict["noncurr_liabilities"]
            self.total_liab_list = fin_dict["total_liabilities"]
            self.equity_list = fin_dict["equity"]
            self.stock_num_list = fin_dict["stock_num"]
            self.stock_price_mean_list = fin_dict["stock_price_mean"]
            self.stock_price_median_list = fin_dict["stock_price_median"]
            self.stock_price_max_list = fin_dict["stock_price_max"]
            self.stock_price_min_list = fin_dict["stock_price_min"]
            self.stock_price_stdev_list = fin_dict["stock_price_stdev"]
            # income, deprec_cost is accumulated so they need to be adjusted
            net_income_list_temp = fin_dict["net_income"]
            deprec_cost_list_temp = fin_dict["deprec_cost"]
            self.net_income_list, self.deprec_cost_list = [], []
            
            if self.data_target == 1:
                for idx, period in enumerate(self.period_list):
                    # for net_income, every value is accumulated so they need
                    # to be processed as the value for the quarter
                    if period[-1] == '1':
                        self.net_income_list.append(net_income_list_temp[idx])
                        self.deprec_cost_list.append(deprec_cost_list_temp[idx])
                    else:
                        # if net_income or deprec_cost has not been crawled or
                        # are in wrong format, set to "" and print warning
                        try:
                            quarter_income = str(int(net_income_list_temp[idx])
                                             - int(net_income_list_temp[idx-1]))
                        except ValueError: # cannot be converted to int
                            print("warning : net_income - inappropriate period \
                                   %s data" % period)
                            quarter_income = ""
                        except TypeError:
                            print("warning : net_income - period %s data \
                                   is None" % period)
                            quarter_income = ""
                        self.net_income_list.append(quarter_income)
                        
                        try:
                            quarter_deprec_cost = str(int(deprec_cost_list_temp[idx])
                                                - int(deprec_cost_list_temp[idx-1]))
                        except ValueError:
                            print("warning : deprec_cost - inappropriate \
                                   period %s data" % period)
                            quarter_deprec_cost = ""
                        except TypeError:
                            print("warning : deprec_cost - period %s \
                                   data is None" % period)
                            quarter_deprec_cost = ""
                        
                        # case when quaterly depreciation cost is blank in table
                        if period[-1] == '4':
                            # if deprec_cost exists only in yearly report
                            if idx >= 2:
                                if self.deprec_cost_list[idx-1] == '0' and self.deprec_cost_list[idx-2] == '0':
                                    try:
                                        quarter_deprec_cost = int(float(deprec_cost_list_temp[idx])/4)
                                    except ValueError: # deprec_cost_list_temp[idx] is string
                                        print(deprec_cost_list_temp[idx])
                                        quarter_deprec_cost = 0
                                    self.deprec_cost_list[idx-3] = quarter_deprec_cost
                                    self.deprec_cost_list[idx-2] = quarter_deprec_cost
                                    self.deprec_cost_list[idx-1] = quarter_deprec_cost
                                    print("warning : deprec_cost - quaterly \
                                    data does not exist for yr %s" % period[:4])

                        # if the first period is not "yr-1" i.e. first quarter
                        if idx == 0:
                            # divide the accumulated deprec_cost by quarter_num
                            self.quarter_deprec_cost = int(float(deprec_cost_list_temp[idx])/int(period[-1]))

                        self.deprec_cost_list.append(quarter_deprec_cost)
                        
            elif self.data_target == 2:
                """ TODO: implement data processing for yearly data """
                pass
            # check whether the length of lists are all the same
            list_lens = [len(self.stock_price_mean_list),
                         len(self.stock_price_median_list),
                         len(self.stock_price_max_list),
                         len(self.stock_price_stdev_list),
                         len(self.stock_price_stdev_list),
                         len(self.stock_num_list), len(self.curr_asset_list),
                         len(self.noncurr_asset_list),
                         len(self.total_asset_list),
                         len(self.curr_liab_list), len(self.noncurr_liab_list),
                         len(self.total_liab_list), len(self.equity_list),
                         len(self.net_income_list), len(self.deprec_cost_list)]
            assert all(list_len == len(self.period_list) for list_len in list_lens)
        
    def write_raw_fin_data(self):
        """ This function writes raw fin data (before processing)
            to csv file """
        filename = "raw_fin_data_%s.csv" % self.stock_code
        print("Writing %s" % filename)
        with open(os.path.join(self.COMPANY_DIR, filename),
                  'w', newline='') as data_file:
            wr = csv.writer(data_file, delimiter=',',
                            quotechar='|', quoting=csv.QUOTE_MINIMAL)
            header_row = ["period", "price_mean", "price_median", "price_max",
                          "price_min", "price_stdev",
                          "stock_num", "curr_asset",
                          "noncurr_asset", "total_asset", "curr_liab",
                          "noncurr_liab", "total_liab", "equity",
                          "net_income", "deprec_cost"]
            wr.writerow(header_row)              
            raw_fin_data = zip(self.period_list, self.stock_price_mean_list,
                               self.stock_price_median_list, self.stock_price_max_list,
                               self.stock_price_min_list, self.stock_price_stdev_list,
                               self.stock_num_list, self.curr_asset_list,
                               self.noncurr_asset_list, self.total_asset_list,
                               self.curr_liab_list, self.noncurr_liab_list,
                               self.total_liab_list, self.equity_list,
                               self.net_income_list, self.deprec_cost_list)
            for row in raw_fin_data:
                wr.writerow(row)
                
    def get_fin_data(self):
        """ This function processes raw data to financial ratios """
        self.per_list, self.pbr_list, self.roe_list = [], [], []
        self.peg_list, self.pcr_list, self.curr_ratio_list = [], [], []
        self.debt_equity_list = []
        
        net_income_timespan = 4
        # get list of net_incomes of 4 quarters
        for idx in range(len(self.period_list)):
            if idx <= net_income_timespan:
                net_income_temp_list = self.net_income_list[:idx+1]
            else:
                net_income_temp_list = self.net_income_list[idx-4:idx+1]
            fin_value_dict = {
                "stock_price": self.stock_price_mean_list[idx],
                "stock_num": self.stock_num_list[idx],
                "curr_asset": self.curr_asset_list[idx],
                "noncurr_asset": self.noncurr_asset_list[idx],
                "total_asset": self.total_asset_list[idx],
                "curr_liab": self.curr_liab_list[idx],
                "noncurr_liab": self.noncurr_liab_list[idx],
                "total_liab": self.total_liab_list[idx],
                "equity": self.equity_list[idx],
                "net_income": self.net_income_list[idx],
                "deprec_cost": self.deprec_cost_list[idx],
                "net_income_list": net_income_temp_list,
            }
            
            fin_ratio = FinancialRatio(fin_value_dict,
                                       data_target=self.data_target)
            self.per_list.append(fin_ratio.get_PER())
            self.pbr_list.append(fin_ratio.get_PBR())
            self.roe_list.append(fin_ratio.get_ROE(acc=True))
            self.curr_ratio_list.append(fin_ratio.get_CURR_RATIO())
            self.debt_equity_list.append(fin_ratio.get_DEBT_EQUITY())
            self.pcr_list.append(fin_ratio.get_PCR())
            self.peg_list.append(fin_ratio.get_PEG())
            
    def write_fin_data(self):
        print("Writing fin data")
        filename = "fin_data_%s.csv" % self.stock_code
        with open(os.path.join(self.COMPANY_DIR, filename),
                  'w', newline='') as data_file:
            wr = csv.writer(data_file, delimiter=',',
                            quotechar='|', quoting=csv.QUOTE_MINIMAL)
            header_row = ["period", "per", "pbr", "roe", "curr_ratio",
                          "debt_equity", "pcr", "peg"]
            wr.writerow(header_row)              
            fin_data = zip(self.period_list, self.per_list, self.pbr_list,
                           self.roe_list, self.curr_ratio_list,
                           self.debt_equity_list, self.pcr_list, self.peg_list)
            for row in fin_data:
                wr.writerow(row)

class FinancialRatio():
    """ This class calculates financial ratios based on the input financial data
        Receives final number as input i.e. the inputs are already processed
        before being pushed in formulas. All the outputs are string.
    """
    def __init__(self, fin_value_dict, data_target=1):
        """ Initializes FinancialRatio object
            @param fin_value_dict - dictionary of financial value
                                    data_name: value
            @param data_target - 1 for data every quarter (분기/반기/사업보고서), 
                                 2 for only year data (사업보고서)
        """
        self.round_pt = 4
        self.output_format = "{0:.4f}"
        
        self.data_target = data_target
        self.stock_price = int(fin_value_dict["stock_price"])
        self.stock_num = int(fin_value_dict["stock_num"])
        self.curr_asset = int(fin_value_dict["curr_asset"])
        self.noncurr_asset = int(fin_value_dict["noncurr_asset"])
        self.total_asset = int(fin_value_dict["total_asset"])
        self.curr_liab = int(fin_value_dict["curr_liab"])
        self.noncurr_liab = int(fin_value_dict["noncurr_liab"])
        self.total_liab = int(fin_value_dict["total_liab"])
        self.equity = int(fin_value_dict["equity"])
        self.net_income = int(fin_value_dict["net_income"])
        self.deprec_cost = int(fin_value_dict["deprec_cost"])
        self.net_income_list = fin_value_dict["net_income_list"]
        net_income_int_list = list(map(int, self.net_income_list))
        if data_target == 1:
            # obtain sum of net_incomes for 4 quarters
            if len(net_income_int_list) >=4:
                self.net_income_acc = sum(net_income_int_list[-4:])
            else:
                self.net_income_acc = sum(net_income_int_list)
                for _ in range(4 - len(net_income_int_list)):
                    self.net_income_acc += net_income_int_list[0]
        elif data_target == 2:
            self.net_income_acc = self.net_income
        self.market_cap = self.stock_num * self.stock_price
    
    def get_EPS(self, acc=False):
        """ This function calculates the value of EPS (Earnings Per Share)
            @param acc - uses accumulated net income if True
                         uses net income for the period if False
        """
        if self.net_income is None or self.stock_num is None:
            self.eps = None
            return None
        else:
            if acc:
                self.eps = float(self.net_income_acc) / self.stock_num
            else:
                self.eps = float(self.net_income) / self.stock_num
            return self.output_format.format(round(self.eps, self.round_pt))
    
    def get_EPS_list(self, acc=False):
        """ This function obtains the list of EPS of 4 quarters
            @param acc - uses accumulated net income if True
                         uses net income for the period if False
        """
        self.eps_list = []
        for net_income in self.net_income_list:
            eps = float(net_income) / self.stock_num
            self.eps_list.append(eps)
        return self.eps_list

    def get_PER(self, acc=True):
        """ This function calculates PER (P/E ratio)
            For quaterly data, sum of net_income over the last 4 quarters
            is used
            @param acc - uses accumulated net income if True
                         uses net income for the period if False
        """
        if self.market_cap is None or self.net_income_acc is None:
            self.per = None
            return None
        else:
            if acc:
                self.per = float(self.market_cap) / self.net_income_acc
            else:
                self.per = float(self.market_cap) / self.net_income
            return self.output_format.format(round(self.per, self.round_pt))
        
    def get_PBR(self):
        """ This function calculates PBR (Price-to-Book Ratio)
            @param acc - uses accumulated net income if True
                         uses net income for the period if False
        """
        if self.market_cap is None or self.equity is None:
            self.pbr = None
            return None
        else:
            self.pbr = float(self.market_cap) / self.equity
            return self.output_format.format(round(self.pbr, self.round_pt))

    def get_ROE(self, acc=False):
        """ This function calculates ROE (Return On Equity)
            @param acc - uses accumulated net income if True
                         uses net income for the period if False
        """
        if self.net_income is None or self.equity is None:
            self.roe = None
            return None
        else:
            if acc:
                self.roe = float(self.net_income_acc) / self.equity
            else:
                self.roe = float(self.net_income) / self.equity
            return self.output_format.format(round(self.roe, self.round_pt))

    def get_CPS(self, acc=False):
        """ This function calculates CPS (Cash Per Share)
            @param acc - uses accumulated net income if True
                         uses net income for the period if False
        """
        if self.net_income is None or self.deprec_cost is None or self.stock_num is None:
            self.cps = None
            return None
        else:
            if acc:
                self.cps = float(self.net_income_acc + self.deprec_cost) / self.stock_num
            else:
                self.cps = float(self.net_income + self.deprec_cost) / self.stock_num
            return self.output_format.format(round(self.cps, self.round_pt))
        
    def get_PCR(self, acc=False):
        """ This function calculates PCR (Price-to-Cashflow Ratio)
            @param acc - uses accumulated net income if True
                         uses net income for the period if False
        """
        self.get_CPS(acc=acc)
        if self.cps is None or self.stock_price is None:
            self.pcr = None
            return None
        else:
            self.pcr = float(self.stock_price) / self.cps
            return self.output_format.format(round(self.pcr, self.round_pt))
    
    def get_PEG(self):
        """ This function calculates PEG (Price/Earnings To Growth)
            TODO: needs large timespan to be an effective ratio
        """
        self.get_EPS_list()
        self.get_PER()
        if self.per is None or len(self.eps_list) <= 1:
            self.peg = None
            return None
        else:
            eps_growth_list = []
            for idx in range(1, len(self.eps_list)):
                eps_growth = ((float(self.eps_list[idx]) / self.eps_list[idx-1]) - 1) * 100
                eps_growth_list.append(eps_growth)
            avg_eps_growth = sum(eps_growth_list) / len(eps_growth_list)
            self.peg = float(self.per) / avg_eps_growth
            return self.output_format.format(round(self.peg, self.round_pt))
    
    def get_DEBT_EQUITY(self):
        """ This function calculates Debt-to-Equity ratio """
        if self.total_liab is None or self.equity is None:
            self.debt_equity = None
            return None
        else:
            self.debt_equity = float(self.total_liab) / self.equity
            return self.output_format.format(round(self.debt_equity, self.round_pt))

    def get_CURR_RATIO(self):
        """ This function calculates Current Ratio """
        if self.curr_asset is None or self.curr_liab is None:
            self.current_ratio = None
            return None
        else:
            self.current_ratio = float(self.curr_asset) / self.curr_liab
            return self.output_format.format(round(self.current_ratio, self.round_pt))


