#-*- coding:utf-8 -*-

import re
import csv
import time
import os
import argparse
from urllib.request import urlopen
from urllib.parse import urlencode
from socket import timeout

from bs4 import BeautifulSoup

import dartData
import finData
import utils

class CompanyData:
    """ This class manages stock and financial statement data of the company """
    
    def __init__(self, stock_code, start_yr=2000, data_target=1):
        """ Initializes CompanyData object
            @param stock_code - stock code of target company
            @param start_yr - initial target year for data collection
            @param data_target - 1 for quarterly data, 2 for yearly data only
        """
        self.stock_code = stock_code
        self.start_yr = start_yr
        self.data_target = data_target
        self.rcp_no_list, self.fin_period_list = dartData.search_dart(self.stock_code,
                                                    self.start_yr, data_target)
        # the first report may be the previous year's data
        if int(self.fin_period_list[0][:4]) < start_yr:
            self.fin_period_list.pop(0)
            self.rcp_no_list.pop(0)
        assert len(self.rcp_no_list) == len(self.fin_period_list)
        
        # creates company directory in ~/workspace/data directory
        HOME_DIR = os.path.join(os.path.expanduser("~"), "workspace")
        DATA_DIR = os.path.join(HOME_DIR, "data")
        self.COMPANY_DIR = os.path.join(DATA_DIR, self.stock_code)
        if not os.path.isdir(self.COMPANY_DIR):
            os.makedirs(self.COMPANY_DIR)
    
    def dart_page_url(self, rcp_no, target=None):
        """ This function sets up crawling for the input target i.e. get url
            @param rcp_no - report number for target company data
            @param target - target to get url for
                'stock_num', 'fin_state', 'gen_finstate', 'gen_finstate2',
                'inc_state', 'cashflow_state',
                'conn_fin_state', 'unconn_fin_state', 'conn_fin_state_comment',
                'unconn_fin_state_comment', 'business_content'
            @return - url if the target page exists
                      None if not
        """
        url = "http://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + rcp_no
        page_html = urlopen(url).read()
        source = BeautifulSoup(page_html, "html.parser")
        pattern = utils.page_pattern[target]
        assert pattern is not None
        
        # url for target datasheet is in script wrapped in certain patterns
        script = source.find("script", text=pattern)
        if script:
            match = pattern.search(script.text)
            if match:
                rcp_no, dcm_no = match.group("rcpNo"), match.group("dcmNo")
                ele_id, offset = match.group("eleId"), match.group("offset")
                length, dtd = match.group("length"), match.group("dtd")
                base_url = "http://dart.fss.or.kr/report/viewer.do?{}"
                url_params = {"rcpNo": rcp_no, "dcmNo": dcm_no, "eleId": ele_id,
                              "offset": offset, "length": length, "dtd": dtd,}
                target_url = base_url.format(urlencode(url_params))
            else:
                target_url = None
        else:
            target_url = None
        return target_url
    
    @staticmethod
    def get_target_table_idx(table_list, pattern=None):
        """ This function obtains indices of table_list for the input pattern
            @param table_list - list of table sources to be analyzed
            @param pattern - pattern to be searched in table_list
            @return table_group_cnt - number of tables in a table group
                                      i.e. one dataset
                    table_head_idx - index of table head (includes '단위')
                                     in a table group
                    table_main_idx - index of main table in a table group
                    table_name_idx - index of table containing the table name
                                     table_head_idx if None
        """
        
        unit_pattern = re.compile(r"\(\s*?단위")
        unit_table_idx_list = []
        for i, table in enumerate(table_list):
            if re.search(unit_pattern, table.text) is not None:
                unit_table_idx_list.append(i)
                
        if len(unit_table_idx_list) >= 2:
            table_group_cnt = unit_table_idx_list[1] - unit_table_idx_list[0]
            group_cnt_diff = []
            for i in range(len(unit_table_idx_list)-1):
                group_cnt_diff.append(unit_table_idx_list[i+1]
                                      - unit_table_idx_list[i])
            if table_group_cnt == 2: # each data set is composed of 2 tables
                table_head_idx, table_main_idx = 0, 1
                table_name_idx = table_head_idx
            elif table_group_cnt == 3: # each data set is composed of 3 tables
                table_head_idx, table_main_idx = 1, 2
                table_name_idx = 0
                if group_cnt_diff[:4] == [3, 3, 2, 2]: # case for 20000515000288
                    table_head_idx, table_main_idx = 0, 1
                    table_name_idx = table_head_idx
            elif table_group_cnt == 4:
                table_head_idx, table_main_idx = 0, 1
                table_name_idx = table_head_idx
        else: # if unit has not been found
            """ TODO: add case when len(table_list) % 6 first """
            if len(table_list) % 2 == 0:
                table_group_cnt, table_head_idx, table_main_idx = 2, 0, 1
                table_name_idx = table_head_idx
            elif len(table_list) % 3 == 0:
                table_group_cnt, table_head_idx, table_main_idx = 3, 1, 2
                table_name_idx = 0
        
        # find the index of the table that contains the input pattern
        table_idx = 0
        if pattern is not None:
            for idx in range(1, int(len(table_list)/table_group_cnt)):
                name_table = table_list[table_group_cnt*idx + table_name_idx]
                pattern_found = False
                name_p = name_table.find_previous_sibling('p')
                name_p_list = [name_p]
                for _ in range(3):
                    name_p = name_p.find_previous('p')
                    name_p_list.append(name_p)
                for name_p in name_p_list:
                    if re.search(pattern, name_p.text) is not None:
                        table_idx = idx
                        pattern_found = True
                        break
                if pattern_found:
                    break
        return table_group_cnt, table_head_idx, table_main_idx, table_name_idx, table_idx
    
    @staticmethod
    def get_table_unit(source, unit_target="money"):
        """ This function obtains the unit of the input table
            @param source - html source of the target table
            @param target - obtains unit for 원 if money, 주 if stock
            @return - unit (in Korean)
        """
        target = r"\(\s*?단위"
        p = source.find("p", text=re.compile(target))
        if unit_target == "money":
            pattern = re.compile(r'\(\s*?단위\s*?:\s*?(?P<unit>\S*?)\s*?원')
        elif unit_target == "stock":
            pattern = re.compile(r'\(\s*?단위\s*?:\s*?(.*?원,)?(?P<unit>\S*?)\s*?주')
        if p is not None: # new table format
            text = p.text
        else: # old table format
            td = source.find("td", text=re.compile(target))
            if td is not None:
                text = td.text
            else:
                head_p = source.find_previous("p")
                text = head_p.text
                
        # some finstate tables do not have unit, so assume their unit to be 1 원
        # for such cases
        unit_match = pattern.search(text)
        if unit_match is not None:
            unit = unit_match.group("unit")
        else:
            unit = ""
        return unit
    
    def dart_page_source(self, rcp_no):
        """ This function obtains the data source of input rcp_no
            @return - dictionary containing sources of financial statements,
                      income statements, cash flow statements, business summary,
                      and the units used in them
        """
        rcp_exist = True
        # stock number source
        url = self.dart_page_url(rcp_no, "stock_num")
        try:
            page_html = urlopen(url).read().decode('utf-8')
        except:
            print("warning : unable to read rcp for stock_num")
            rcp_exist = False
        
        if rcp_exist:
            page_html = utils.format_page_html(page_html)
            stock_num_source = BeautifulSoup(page_html, "html.parser")
        else:
            stock_num_source = None
            
        no_conn = False # when "연결재무제표" has "해당내용 없음" as content
        rcp_exist = True
        url_page_list = ["conn_fin_state", "gen_fin_state", "unconn_fin_state",
                         "gen_fin_state2",] # list of possible urls
        for url_name in url_page_list:
            url = self.dart_page_url(rcp_no, url_name)
            if url is not None:
                break
        try:
            page_html = urlopen(url).read().decode('utf-8')
        except:
            print("warning : unable to read rcp for fin_state")
            rcp_exist = False
        if rcp_exist:
            page_html = utils.format_page_html(page_html)
            fin_page_source = BeautifulSoup(page_html, "html.parser")
            fin_page_tables = fin_page_source.findAll("table")
        else:
            fin_page_source = None
            fin_page_tables = None

        # if "연결재무제표" has no content, move to "재무제표"
        if fin_page_tables is not None:
            if len(fin_page_tables) == 0:
                no_conn = True
                url = self.dart_page_url(rcp_no, "unconn_fin_state")
                page_html = urlopen(url).read().decode('utf-8')
                page_html = utils.format_page_html(page_html)
                fin_page_source = BeautifulSoup(page_html, "html.parser")
                fin_page_tables = fin_page_source.findAll("table")
            if len(fin_page_tables) % 2 != 0:
                print("warning - finstate table: the number of tables is odd")
            # finstate page may have a bordered announcement box at the top
            if ("border" in fin_page_tables[0].attrs) and fin_page_tables[0].attrs["border"] == '1':
                fin_page_tables.pop(0)
            table_indices = self.get_target_table_idx(fin_page_tables)
            table_group_cnt, table_head_idx, table_main_idx, table_name_idx, table_idx = table_indices
            
            # financial statement source is the first table of the page
            fin_state_unit = self.get_table_unit(fin_page_tables[table_group_cnt*0 
                                                                + table_head_idx])
            fin_state_source = fin_page_tables[table_group_cnt*0 + table_main_idx]
    
            # income statement table index is unknown so needs to be fetched
            inc_state_pattern = re.compile(r'손\s*?익\s*?계\s*?산\s*?서')
            table_indices = self.get_target_table_idx(fin_page_tables, inc_state_pattern)
            table_group_cnt, table_head_idx, table_main_idx, table_name_idx, table_idx = table_indices
            inc_state_unit = self.get_table_unit(fin_page_tables[table_group_cnt*table_idx
                                                                + table_head_idx])
            inc_state_source = fin_page_tables[table_group_cnt*table_idx + table_main_idx]
    
            # cash statement table index is unknown so needs to be fetched
            cash_state_pattern = re.compile(r'현.*?금.*?표')
            table_indices = self.get_target_table_idx(fin_page_tables, cash_state_pattern)
            table_group_cnt, table_head_idx, table_main_idx, table_name_idx, table_idx = table_indices
            cash_state_unit = self.get_table_unit(fin_page_tables[table_group_cnt*table_idx
                                                    + table_head_idx])
            cash_state_source = fin_page_tables[table_group_cnt*table_idx
                                                + table_main_idx]
        else:
            fin_state_source = None
            fin_state_unit = None
            inc_state_source = None
            inc_state_unit = None
            cash_state_source = None
            cash_state_unit = None
            
        # financial statement comment source
        rcp_exist = True
        if no_conn:
            url = self.dart_page_url(rcp_no, "unconn_fin_state_comment")
        else:
            url = self.dart_page_url(rcp_no, "conn_fin_state_comment")
        if url is not None:
            try:
                page_html = urlopen(url).read().decode('utf-8')
            except:
                print("warning : unable to read rcp for finstate comment")
                rcp_exist = False
            if rcp_exist:
                page_html = utils.format_page_html(page_html)
                fin_state_comment_source = BeautifulSoup(page_html, "html.parser")
        else:
            # fin_state_comment_source = None
            fin_state_comment_source = fin_page_source

        # fin_state_summary_source (사업의 내용) is used when 
        # depreciation cost is not mentioned in other sections
        # find "재무현황" at p first then move on to the next table
        """ TODO: '재무현황' containing p may be two p's away from the table """
        url = self.dart_page_url(rcp_no, "business_content")
        fin_state_summary_source, fin_state_summary_unit = None, ""
        unit_pattern = re.compile(r'\(단위\s*?:\s*?(?P<unit>\S*?)\s*?원')
        target_pattern = re.compile(r"재무현황")
        unit_in_table = False
        unit_exist = False
        rcp_exist = True
        if url is not None:
            try:
                page_html = urlopen(url).read().decode('utf-8')
            except:
                print("warning - timeout: unable to read rcp for finstate summary")
                rcp_exist = False
            if rcp_exist:
                page_html = utils.format_page_html(page_html)
                summary_source = BeautifulSoup(page_html, "html.parser")
                summary_p = summary_source.find('p', text=target_pattern)
                if summary_p is not None: # if there exists "재무현황" section
                    unit_match = re.search(unit_pattern, summary_p.text)
                    if unit_match is None:
                        unit_p = summary_p.find_next('p')
                        unit_match = re.search(unit_pattern, unit_p.text)
                        if unit_match is None:
                            unit_table = summary_p.find_next('table')
                            unit_td = unit_table.find("td", text=unit_pattern)
                            if unit_td is not None:
                                unit_match = re.search(unit_pattern, unit_td.text)
                                unit_in_table = True
                                unit_exist = True
                            else:
                                unit_exist = False
                        else:
                            unit_exist = True
                    else:
                        unit_exist = True
                        
                    fin_state_summary_source = summary_p.find_next("table")
                    if unit_in_table:
                        # the main table is after the table containing unit
                        fin_state_summary_source = fin_state_summary_source.find_next("table")
                    if unit_exist:
                        unit = unit_match.group("unit")
                        fin_state_summary_unit = unit
                    else:
                        fin_state_summary_source = fin_state_summary_source.find_previous("table")
                        fin_state_summary_unit = ""

        source_dict = {
            "stock_num": stock_num_source,
            "fin_state": fin_state_source,
            "fin_state_unit": fin_state_unit,
            "inc_state": inc_state_source,
            "inc_state_unit": inc_state_unit,
            "cash_state": cash_state_source,
            "cash_state_unit": cash_state_unit,
            "fin_state_comment": fin_state_comment_source,
            "finstate_summary": fin_state_summary_source,
            "finstate_summary_unit": fin_state_summary_unit,
        }
        return source_dict
    
    def parse_stock_num(self, source):
        """ This function parses stock number data from '주식의 총수' page
            @param source - html source to parse stock num from
        """
        pattern_list = utils.target_pattern_list["stock_num"]
        stock_num = None
        stock_num_found = False
        # get the unit of the table
        unit = ""
        unit_td = source.find("td", text=re.compile('단위'))
        if unit_td is not None:
            unit_table = unit_td.parent.parent.parent # html <table> element
            unit = self.get_table_unit(unit_table, unit_target="stock")
        target_pattern = re.compile(r'[0-9]+')
        
        """ TODO
        identiry the type of format first than iterate through possible patterns
        """
        for pattern in pattern_list:
            td = source.find("td", text=re.compile(pattern))
            if td is not None:
                tr = td.parent
                th = source.find("th", text=re.compile("합계"))
                if th is not None:
                    # the column with "합계" is the target, so get index of <th>
                    idx = th.parent.findChildren().index(th)
                    if len(tr.findAll("td")) == 5 or len(tr.findAll("td")) == 4:
                        stock_num = tr.findAll("td")[1+idx].text.replace(',', '')
                        stock_match = re.match(target_pattern, stock_num)
                        if stock_match is not None:
                            stock_num = stock_match.group(0)
                        else:
                            stock_num = utils.num_format(tr.findAll("td")[idx].text)
                            stock_match = re.match(target_pattern, stock_num)
                            stock_num = stock_match.group(0)
                        stock_num += utils.unit_convert[unit]
                        stock_num_found = True
                        break
                else: # if there is no 합계 in the table head
                    # directly find pattern in the table head
                    th = source.find("th", text=re.compile(pattern))
                    idx = th.parent.findChildren().index(th)
                    stock_num_pattern = re.compile(r'(?P<stock_num>[0-9,]+)주?')
                    if th is not None:
                        target_tbody = th.parent.parent.parent.find("tbody")
                        target_text = target_tbody.findAll("td")[idx].text
                        target_match = re.search(stock_num_pattern, target_text).group("stock_num")
                        stock_num = utils.num_format(target_match)
                        stock_num_found = True
                        break

            else: # if there is no <td> containing the pattern
                # find the pattern in th
                th = source.find("th", text=re.compile(pattern))
                if th is not None:
                    tr = th.parent
                    tr_children = tr.findChildren()
                    idx = tr_children.index(th)
                    tr_num = tr.find_next("tr")
                    stock_num = tr_num.findChildren()[idx].text.replace(',', '')
                    stock_num = re.match(target_pattern, stock_num).group(0)
                    stock_num += utils.unit_convert[unit]
                    stock_num_found = True
                    break
        
        # if stock_num is still None, assume that the stock number is written in
        # paragraph form as it is in rcp_no 20090515000326
        if not stock_num_found:
            target_found = False
            target_pattern_list = [re.compile(r'''보통주\s*?
                                    (?P<target>\d+|\d{1,3}(,\d{3})*)
                                    \s*?(?P<unit>\w?)\s*?주'''
                                    , re.MULTILINE | re.DOTALL | re.VERBOSE),
                                   re.compile(r'''유통\s주식의\s총수.*?
                                   (?P<target>\d+|\d{1,3}(,\d{3})*)
                                   \s*?(?P<unit>\w?)\s*?주'''
                                   , re.MULTILINE | re.DOTALL | re.VERBOSE)]
            pattern_list = utils.target_pattern_list["stock_num_p"]
            for pattern in pattern_list:
                p = source.find("p", text=re.compile(pattern))
                if p is not None:
                    for target_pattern in target_pattern_list:
                        p_match = re.search(target_pattern, p.string)
                        if p_match is not None:
                            stock_num = p_match.group("target").replace(',', '')
                            stock_num += utils.unit_convert[p_match.group("unit")]
                            target_found = True
                            break
                    if target_found:
                        break
                
        return stock_num
    
    def parse_finstate(self, source, target_name, row_idx=0):
        """ This function parses target_name data from "대차대조표"
            @param row_idx - the index of target when the target_name appears
                             in the source table multiple times
        """
        pattern_list = utils.target_pattern_list[target_name]
        target_val = None
        target_found = False
        for pattern in pattern_list:
            td_p = source.find("p", text=re.compile(pattern))
            if td_p is not None: # the table is in new format
                tr = td_p.parent.parent
                # for new fomats, number of columns in each row is either 3 or 4
                if len(tr.findAll("td")) in range(3, 5):
                    target_val = utils.num_format(tr.findAll("td")[1].text)
                    break
                else:
                    print("for %s new format, td num is %d" % (target_name,
                                                        len(tr.findAll("td"))))
                                                        
            else: # the table is in old format
                """ TODO - currently, two types of format are both used as 'old
                format' so the two cases need to be divided """
                td = source.find("td", text=re.compile(pattern))
                if td is not None:
                    tr = td.parent
                    td_list = tr.findAll("td")
                    td_idx = 1
                    thead_th_num = 0
                    if source.find("thead") is not None:
                        # there may exist multiple rows consisting <thead>
                        for thead_tr in source.find("thead").findAll("tr"):
                            thead_th_num += len(thead_tr.findAll("th"))
                        
                    mismatch_row_num = False
                    # for financial statement, number of th in thead is equal to
                    # the number of td of data table
                    if thead_th_num <= len(td_list) or thead_th_num == 0:
                        if thead_th_num < len(td_list) and not self.wrong_thead_num:
                            print("warning - finstate: thead num < data td num")
                            self.wrong_thead_num = True
                        for i in range(1, 3): # range has not been verified
                            if len(td_list[i].text.split()) != 0:
                                target_val = utils.num_format(td_list[i].text)
                                target_found = True
                                break
                        if target_found:
                            break
                        
                    elif (len(td_list) in range(3, 6)):
                        # check if the number of <br/> is equal for each column
                        name_list = td_list[0].string.split('\n')
                        value_list = td_list[td_idx].string.split('\n')
                        if len(name_list) < len(value_list):
                            # there exist blank rows in value column (or there 
                            # are rows missing in name column)
                            mismatch_row_num = True
                            if not self.wrong_name_row:
                                print("warning - finstate: name_row < value_row")
                                self.wrong_name_row = True
                            # cause 1: when () for "순이익" exists
                            excp_pattern = re.compile(r'(?P<pre_item>\(.*?순이익.*?\))(?P<item>\w+)')
                            for i, name in enumerate(name_list):
                                regex_result = re.search(excp_pattern, name)
                                if regex_result is not None:
                                    pre_item = regex_result.group("pre_item")
                                    item = regex_result.group("item")
                                    name_list[i] = pre_item
                                    name_list.insert(i+1, item)

                        elif len(name_list) > len(value_list):
                            mismatch_row_num = True
                            # there exist blank rows in name column (or there
                            # are rows missing in value column)
                            if not self.wrong_value_row:
                                print("warning - finstate: name_row > value_row")
                                self.wrong_value_row = True
                        idx_list = [i for i, item in enumerate(name_list)
                                    if re.search(pattern, item)]
                        target_idx = idx_list[row_idx]
                        target_val = value_list[target_idx]
                        target_val = utils.num_format(target_val)
                        if target_val == '' and mismatch_row_num:
                            print("warning - finstate: mismatch in name/value \
                                  row num so choosing different num")
                            target_val = utils.num_format(value_list[target_idx+1])
                        break
                    else:
                        print("for %s old format, td num is %d" % (target_name,
                                                                len(td_list)))
                        if len(td_list) == 7: # some columns (tr) may be empty
                            for i in range(1, len(td_list)):
                                if len(td_list[i].text.split()) != 0:
                                    target_val = utils.num_format(td_list[i].text)
                                    target_found = True
                                    break
                            if target_found:
                                break
                        elif len(td_list) == 2:
                            target_val = utils.num_format(td_list[1].text)
                            break
        if target_val == "-":
            target_val = None
        return target_val
        
    def parse_finstate_comment(self, source, target_name, row_idx=0):
        """ This function parses target_name data from "(연결)재무제표 주석"
            This code adds unit to the return value unlike other parsing functions
            @ return - list of values for target_name
                       (list becasue there may exist multiple deprec_cost types)
        """
        pattern_list = utils.target_pattern_list["cost_type"]
        cost_pattern_list = utils.target_pattern_list["deprec_cost"]
        target_list = []
        target_table_found = False
        acc_pattern = re.compile(r'누\s*?적')

        for pattern in pattern_list:
            head_p = source.find("p", text=re.compile(pattern))
            if head_p is not None:
                cost_table = head_p.find_next("table")
                table_unit = self.get_table_unit(cost_table)
                for cost_pattern in cost_pattern_list:
                    td = cost_table.find("td", text=re.compile(cost_pattern))
                    if td is not None:
                        target_table_found = True
                        break
                if not target_table_found:
                    cost_table = cost_table.find_next("table")
                # check whether the numbers in the table are for current quarter
                # or are accumulated numbers for the year
                if cost_table.find(text=re.compile(acc_pattern)) is not None:
                    acc_col_exist = True
                else:
                    acc_col_exist = False
                if acc_col_exist:
                    td_idx = 2
                else:
                    td_idx = 1
                    
                for cost_pattern in cost_pattern_list:
                    td_list = cost_table.findAll("td", text=re.compile(cost_pattern))
                    if len(td_list) == 0:
                        continue
                    for td in td_list:
                        tr = td.parent
                        target_val = utils.num_format(tr.findAll("td")[td_idx].text)
                        target_val = target_val.replace('(', '-').replace(')', '')
                        target_val += utils.unit_convert[table_unit]
                        target_list.append(target_val)
                break
        return target_list

    def parse_incstate(self, source, target_name, row_idx=0):
        """ This function parses target_name data from '손익계산서' """
        pattern_list = utils.target_pattern_list[target_name]
        target_val = None
        target_found = False
        for pattern in pattern_list:
            # the right pattern found when breaking out from the loop
            valid_pattern = pattern
            td_p = source.find("p", text=re.compile(pattern))
            if td_p is not None: # the table is in new format
                tr = td_p.parent.parent
                table_head = tr.parent.parent.find("thead")
                # check if column for accumulated data exists to decide p_idx
                if table_head.find(text=re.compile(r'누\s*?적')):
                    acc_col_exist = True
                else:
                    acc_col_exist = False
                if acc_col_exist:
                    p_idx = 2
                else:
                    p_idx = 1
                target_val = utils.num_format(tr.findAll("td")[p_idx].text)
                break
            
            else: # the table is in old format
                td = source.find("td", text=re.compile(pattern))
                if td is not None:
                    tr = td.parent
                    td_list = tr.findAll("td")
                    table_head = tr.parent.parent.find("thead")
                    thead_th_num = 0
                    if table_head is not None:
                        for thead_tr in source.find("thead").findAll("tr"):
                            thead_th_num += len(thead_tr.findAll("th"))
                    # for most income statements, number of th in thead is greater
                    # than or equal to the number of td of data table
                    if thead_th_num <= len(td_list) or thead_th_num == 0:
                        if thead_th_num < len(td_list) and not self.wrong_thead_num:
                            print("warning - incstate: thead num < data td num")
                            self.wrong_thead_num = True
                        for i in range(1, len(td_list)):
                            if len(td_list[i].text.split()) != 0:
                                target_val = utils.num_format(td_list[i].text)
                                target_found = True
                                break
                        if target_found:
                            break
                    else:
                        if table_head.find(text=re.compile(r'누\s*?적')):
                            acc_col_exist = True
                        else:
                            acc_col_exist = False
                        if acc_col_exist: # 분기/반기보고서
                            td_index = 2
                        else: # 사업보고서
                            td_index = 1
                        name_list = tr.find("td").string.split('\n')
                        # list of indexs that match the names
                        idx_list = [i for i, item in enumerate(name_list)
                                                if re.search(pattern, item)]
                        target_idx = idx_list[row_idx]
                        value_list = td_list[td_index].string.split('\n')

                        mismatch_row_data = False
                        if len(name_list) < len(value_list):
                            if not self.inc_wrong_name_row:
                                print("warning - inctate: name_row < value_row", end=' ')
                                print("choosing the last row as net_income")
                                self.inc_wrong_name_row = True
                                mismatch_row_data = True
                        if mismatch_row_data and target_name == "net_income":
                            target_val = utils.num_format(value_list.pop())
                            while target_val == '':
                                target_val = utils.num_format(value_list.pop())
                        else:
                            target_val = value_list[target_idx]
                        target_val = utils.num_format(target_val)
                        break
        
        # if pattern is '당기순손실', it means negative income i.e. loss
        if target_val is not None and target_val != "" and valid_pattern == "당\s*?기\s*?순\s*?손\s*?실":
            target_val = "-" + target_val
            
        return target_val
        
    def parse_cashstate(self, source, target_name, row_idx=0):
        """ This function parses cash flow statement (현금흐름표)
            @return - list of target_vals
            cf) for cash statement
            row 0 is the name of the row
            row 1 is the value for the current period and
            row 2 is the value of the last year same period for 분기/반기 보고서
            row 1 is the value for this whole year and 
            row 2 is the value for the last whole year for 사업보고서
        """
        pattern_list = utils.target_pattern_list[target_name]
        target_list = []
        table_tr_num = len(source.findAll("tr"))
        # the number of tr's to decide whether the format is old or new
        tr_threshold = 4

        for pattern in pattern_list:
            td_p_list = source.findAll("p", text=re.compile(pattern))
            if table_tr_num > tr_threshold:
                if len(td_p_list) != 0: # new format (연결재무제표)
                    for td_p in td_p_list:
                        tr = td_p.parent.parent
                        table_head = tr.parent.parent.find("thead")
                        if table_head.find(text=re.compile(r'누\s*?적')):
                            acc_col_exist = True
                        else:
                            acc_col_exist = False
                        if acc_col_exist:
                            p_idx = 2
                        else:
                            p_idx = 1
                        # check whether the td of p_idx is empty
                        td_list = tr.findAll("td")
                        if td_list[p_idx].find("p") is None:
                            target_list.append('0')
                        elif td_list[p_idx].find("p").string == "":
                            target_list.append('0')
                        else:
                            target_list.append(utils.num_format(tr.findAll("p")[p_idx].text))
                    break
                else: # new format but in 재무제표 section
                    td_list = source.findAll("td", text=re.compile(pattern))
                    if len(td_list) != 0: # new format
                        for td in td_list:
                            tr = td.parent
                            table_head = tr.parent.parent.find("thead")
                            if table_head.find(text=re.compile(r'누\s*?적')):
                                acc_col_exist = True
                            else:
                                acc_col_exist = False
                            if acc_col_exist:
                                td_idx = 2
                            else:
                                td_idx = 1
                            td_num = len(tr.findAll("td"))
                            if len(table_head.findAll("th")) < td_num:
                                if not self.cash_wrong_name_row:
                                    print("warning - cashstate: name_row < value_row")
                                    self.cash_wrong_name_row = True
                                # choose the column to select data from
                                if td_num == 13:
                                    # target data is in the third column
                                    print("warning - cashstate: td_num is 13")
                                    td_num = 3
                                else:
                                    td_num = 1 + int((td_num - 1) / 2) * (td_idx - 1)
                                for idx in range(td_num, td_num + td_idx):
                                    target_val = utils.num_format(tr.findAll("td")[idx].text)
                                    if target_val != '':
                                        target_list.append(target_val)
                                        break
                            else:
                                target_list.append(utils.num_format(tr.findAll("td")[td_idx].text))
                        break
            else: # old format that uses td as column
                td = source.find("td", text=re.compile(pattern))
                if td is not None:
                    tr = td.parent
                    td_list = tr.findAll("td")
                    table_head = tr.parent.parent.find("thead")
                    acc_pattern = re.compile(r'누\s*?적')
                    # there exists cash statement with thead components written in tr
                    if table_head is None:
                        print("warning - cash flow statement: no thead")
                        acc_col_exist = False
                        tr_list = tr.parent.parent.findAll("tr")
                        # the last element of tr_list is numerical data
                        for head_idx in range(len(tr_list)-1):
                            tr_head = tr_list[head_idx]
                            if tr_head.find(text=acc_pattern):
                                acc_col_exist = True
                                break
                    else:
                        if table_head.find(text=acc_pattern):
                            acc_col_exist = True
                        else:
                            acc_col_exist = False
                            
                    name_list = tr.find("td").string.split('\n')
                    # list of indexs that match the names
                    idx_list = [i for i, item in enumerate(name_list)
                                            if re.search(pattern, item)]
                    for idx in idx_list:
                        if acc_col_exist:
                            td_idx = 2
                        else:
                            td_idx = 1
                        target_val = td_list[td_idx].string.split('\n')[idx]
                        target_val = utils.num_format(target_val)
                        target_list.append(target_val)
                    break 
        return target_list
    
    @staticmethod
    def parse_finstate_summary(source, target_name):
        """ This function parses finstate summary (사업의 내용)
            @return - list satisfying the target_name
                      list because there exist multiple types of deprec_cost
        """
        pattern_list = utils.target_pattern_list[target_name]
        head_pattern_list = [re.compile(r"당[반분]?기\s*?$"),
                             re.compile(r"[0-9]+\s*?년")]
        target_list = []
        for idx, pattern in enumerate(head_pattern_list):
            head_td = source.find("td", text=pattern)
            if head_td is not None:
                head_p = source.find_previous_sibling('p')
                # obtain the type of data in table
                data_type = idx # 0 if quarter (당기), 1 if year(년)
                head_pattern = pattern
                break
        
        # find the unit of finstate summary table
        unit_pattern = re.compile(r'\(단위\s*?:\s*?(?P<unit>\S*?)\s*?원')
        if head_p is not None:
            unit_match = re.search(unit_pattern, head_p.text)
            if unit_match is not None:
                unit = utils.unit_convert[unit_match.group("unit")]
        
        # obtain the index of the target column
        if head_td is None:
            print("warning - finstate_sumamry: unable to find td num")
        else:
            td_total_num = len(head_td.parent.findAll("td"))
            td_curr_num = len(head_td.parent.findAll("td", text=head_pattern))
            td_idx = int(td_total_num/td_curr_num) * (td_curr_num - 1)
            if data_type == 1:
                print("warning - finstate_summary: data in years")
                td_idx -= 1

        for pattern in pattern_list:
            target_td = source.find("td", text=re.compile(pattern))
            if target_td is not None:
                target_val = target_td.parent.findAll("td")[td_idx+1].string
                target_val = utils.num_format(target_val).replace('(', '-').replace(')', '') + unit
                target_list = [target_val]
                break
        return target_list

    def dart_crawl_target(self, rcp_no, source, unit, target, source_name=None):
        """ This function parses the target data from dart page
            @param source_name - name of source used when there exists multiple
                                 possible sources for one target
        """
        if source is None:
            return None
        
        target_data = None
        if target == "stock_num": # 주식의 총수
            target_data = self.parse_stock_num(source)
            if self.debug:
                print("stock_num: %s" % target_data)
            
        elif target == "asset": # 자산
            curr_asset = self.parse_finstate(source, "curr_asset")
            noncurr_asset = self.parse_finstate(source,
                                                     "noncurr_asset")
            total_asset = self.parse_finstate(source, "total_asset")
            if self.debug:
                print("raw data - curr_asset: %s, noncurr_asset: %s, total_asset: %s" %
                      (curr_asset, noncurr_asset, total_asset))
            
            # remove parenthesis assuming there is no negative asset
            if curr_asset is not None:
                curr_asset = curr_asset.replace('(', '').replace(')', '')
                curr_asset += utils.unit_convert[unit]
            if noncurr_asset is None or noncurr_asset == "":
                noncurr_asset = str(int(total_asset) - int(curr_asset))
            elif noncurr_asset is not None:
                noncurr_asset = noncurr_asset.replace('(', '').replace(')', '')
                noncurr_asset += utils.unit_convert[unit]
            if total_asset is not None:
                total_asset = total_asset.replace('(', '').replace(')', '')
                total_asset += utils.unit_convert[unit]
                
            try:
                if int(total_asset) != int(curr_asset) + int(noncurr_asset):
                    print("warning - asset: total_asset != curr_asset + noncurr_asset")
            except: # if total_asset cannot be converted to int
                if total_asset == "-":
                    total_asset = str(int(curr_asset) + int(noncurr_asset))

            target_data = (curr_asset, noncurr_asset, total_asset)
            
        elif target == "liabilities":
            curr_liabilities = self.parse_finstate(source,
                                                    "curr_liabilities")
            noncurr_liabilities = self.parse_finstate(source,
                                                "noncurr_liabilities")
            total_liabilities = self.parse_finstate(source,
                                                        "total_liabilities")
            if self.debug:
                print("raw data - curr_liab: %s, noncurr_liab: %s, total_liab: %s" % 
                      (curr_liabilities, noncurr_liabilities, total_liabilities))
            
            # remove parenthesis assuming there is no negative liability
            if curr_liabilities is not None:
                curr_liabilities = curr_liabilities.replace('(', '').replace(')', '')
                curr_liabilities += utils.unit_convert[unit]
            if noncurr_liabilities is not None:
                noncurr_liabilities = noncurr_liabilities.replace('(', '').replace(')', '')
                noncurr_liabilities += utils.unit_convert[unit]            
            if total_liabilities is not None:
                total_liabilities = total_liabilities.replace('(', '').replace(')', '')
                total_liabilities += utils.unit_convert[unit]
            
            try:
                if int(total_liabilities) != int(curr_liabilities) + int(noncurr_liabilities):
                    print("warning - asset: total_liab != curr_liab + noncurr_liab")
            except:
                pass
                
            target_data = (curr_liabilities, noncurr_liabilities,
                           total_liabilities)

        elif target == "equity": # 자본
            total_equity = self.parse_finstate(source, "total_equity")
            minor_equity = self.parse_finstate(source, "minor_equity")
            if self.debug:
                print("raw data - total_equity: %s, minor_equity: %s" %
                      (total_equity, minor_equity))
                      
            if total_equity is not None:
                total_equity = total_equity.replace('(', '-').replace(')', '')
                total_equity += utils.unit_convert[unit]
            if minor_equity is not None:
                if minor_equity == "" or minor_equity == "\u3000":
                    minor_equity = '0'
                else:
                    minor_equity = minor_equity.replace('(', '-').replace(')', '')
                    minor_equity += utils.unit_convert[unit]
                target_data = (str(int(total_equity) - int(minor_equity)))
            else:
                target_data = total_equity
        
        elif target == "net_income": # 당기순이익
            total_income = self.parse_incstate(source, "net_income")
            minor_income = self.parse_incstate(source, "minor_income")
            major_income = self.parse_incstate(source, "major_income")
            if self.debug:
                print("raw data - total_income: %s, minor_income: %s, major_income: %s" %
                      (total_income, minor_income, major_income))
                      
            if total_income is not None:
                total_income = total_income.replace('(', '-').replace(')', '').replace('△', '-')
                # for some cases, they use () for positive number, so -- may occur
                total_income = re.sub(r'-+', '-', total_income)
                total_income += utils.unit_convert[unit]
            
            # make sure major_income + minor_income = total_income
            if minor_income is not None:
                if minor_income == "" or minor_income == "\u3000":
                    minor_income = '0'
                else:
                    minor_income = minor_income.replace('(', '-').replace(')', '').replace('△', '-')
                    minor_income = minor_income.replace('--', '-')
                    minor_income += utils.unit_convert[unit]
            if major_income is not None:
                if major_income == "" or major_income == "\u3000":
                    major_income = '0'
                else:
                    major_income = major_income.replace('(', '-').replace(')', '').replace('△', '-')
                    major_income = major_income.replace('--', '-')
                    major_income += utils.unit_convert[unit]
                
            if minor_income is not None and major_income is not None:
                if int(total_income) == int(major_income) + int(minor_income):
                    if major_income != "0":
                        target_data = major_income
                    else:
                        target_data = total_income
                # when minor_income(비지배지분) equals major_income(지배지분) by error
                elif (int(total_income) == int(major_income)) and (int(major_income) == int(minor_income)):
                    print("warning - net_income : major_income == minor_income")
                    target_data = total_income
                elif int(total_income) == int(major_income):
                    print("warning - net_income: total_income == major_income")
                    target_data = total_income
                elif major_income == '0' and minor_income == '0':
                    target_data = total_income
                else:
                    target_data = major_income
            else:
                target_data = total_income

        elif target == "deprec_cost": # 감가상각비
            # parse cash statement (현금흐름표) first
            if source_name is None:
                target_val = 0
                deprec_cost_list = self.parse_cashstate(source, "deprec_cost")
                deprec_none_list = ["", "-", "\n"]
                if self.debug:
                    print("deprec_cost_list(cashstate): ", end='')
                    print(deprec_cost_list)
                if len(deprec_cost_list) != 0:
                    for deprec_cost in deprec_cost_list:
                        if deprec_cost in deprec_none_list:
                            continue
                        deprec_cost = deprec_cost.replace('(', '-').replace(')', '') + utils.unit_convert[unit]
                        target_val += int(deprec_cost)
                    target_data = str(target_val)
            # look at finstate_comment(재무제표 주석) when deprec_cost is not
            # in cash_statement(재무제표)
            elif source_name == "finstate_comment":
                print("searching finstate comment")
                """ TODO: find where and what error happens """
                try:
                    target_val = 0
                    deprec_cost_list = self.parse_finstate_comment(source, "deprec_cost")
                    if self.debug:
                        print("deprec_cost_list(finstate comment): ", end='')
                        print(deprec_cost_list)
                    if len(deprec_cost_list) != 0:
                        for deprec_cost in deprec_cost_list:
                            target_val += int(deprec_cost + utils.unit_convert[unit])
                        target_data = str(target_val)
                except:
                    target_data = None
            # parse finstate_summary(사업의 내용) when
            # finstate_comment(재무제표 주석) does not exist
            elif source_name == "finstate_summary":
                print("searching finstate summary")
                try:
                    deprec_cost_list = self.parse_finstate_summary(source, "deprec_cost")
                # error because target table does not exist in finstate_summary
                except UnboundLocalError:
                    deprec_cost_list = []
                target_val = 0
                if self.debug:
                    print("deprec_cost_list(finstate summary): ", end='')
                    print(deprec_cost_list)
                if len(deprec_cost_list) != 0:
                    for deprec_cost in deprec_cost_list:
                        target_val += int(deprec_cost + utils.unit_convert[unit])
                    target_data = str(target_val)
                else:
                    target_data = '0'
        return target_data
    
    def stock_price_crawl(self, read_data=False, write_data=False, write_raw=False):
        """ This function crawls past stock prices from Naver Finance page
        TODO: add reading raw stock price data csv file and updating data
        """
        url = "http://finance.naver.com/item/sise_day.nhn?code=" + self.stock_code
        page_html = urlopen(url).read()
        source = BeautifulSoup(page_html, "html.parser")
        # find the page number of the last page
        max_pg_href = source.find_all("td", class_="pgRR")[0].a.get("href")
        max_pgnum = int(max_pg_href[max_pg_href.index("page=")+5:])
        price_temp_list = []
        self.stock_price_mean_list = []
        self.stock_price_median_list = []
        self.stock_price_max_list = []
        self.stock_price_min_list = []
        self.stock_price_stdev_list = []
        
        if read_data:
            filename = "stock_data_%s.csv" % self.stock_code
            with open(os.path.join(self.COMPANY_DIR, filename),
                      'r', newline='') as price_file:
                fr = csv.reader(price_file, delimiter=',', quotechar='|')
                next(fr)
                for row in fr:
                    self.stock_price_mean_list.append(row[1])
                    self.stock_price_median_list.append(row[2])
                    self.stock_price_max_list.append(row[3])
                    self.stock_price_min_list.append(row[4])
                    self.stock_price_stdev_list.append(row[5])
                    
        else:
            print("Crawling price for code %s" % self.stock_code)
            if write_raw:
                print("Writing stock price raw data \
                      for code %s" % self.stock_code)
                raw_filename = "raw_stock_data_%s.csv" % self.stock_code
                raw_stock_file = open(os.path.join(self.COMPANY_DIR,
                                      raw_filename), 'w', newline='')
                raw_wr = csv.writer(raw_stock_file, delimiter=',',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            if write_data:
                print("Writing stock price data for code %s" % self.stock_code)
                data_filename = "stock_data_%s.csv" % self.stock_code
                data_file = open(os.path.join(self.COMPANY_DIR, data_filename),
                                 'w', newline='')
                wr = csv.writer(data_file, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
                header_row = ["period", "price_mean", "price_median",
                              "price_max", "price_min", "price_stdev"]
                wr.writerow(header_row)
                  
            data_url = url + "&page=%d" % max_pgnum
            html = urlopen(data_url)
            stock_source = BeautifulSoup(html.read(), "html.parser")
            found_start_yr = False
            start_yr_changed = False
            day_list = stock_source.find_all("tr")
            
            # find the first year of company's stock price and change
            # curr_quarter to the company's first public year if
            # it is after year 2000
            while not found_start_yr:
                for day_data in reversed(day_list):
                    if day_data.span is not None:
                        date = day_data.find_all('td',
                                                 align='center')[0].text
                        company_start_yr = int(date.split('.')[0])
                        if company_start_yr > self.start_yr:
                            curr_quarter = utils.get_quarter(date)
                            start_yr_changed = True
                        elif company_start_yr == self.start_yr:
                            company_start_mth = int(date.split('.')[1])
                            if company_start_mth > 3:
                                curr_quarter = utils.get_quarter(date)
                                start_yr_changed = True
                        found_start_yr = True
                        break
            # if the company's first year for stock price is before year 2000
            if not start_yr_changed:
                curr_quarter = "%d-1" % self.start_yr

            # get stock price info in ascending order of date
            for pgnum in range(max_pgnum, 0, -1):
                data_url = url + "&page=%d" % pgnum
                html = urlopen(data_url)
                stock_source = BeautifulSoup(html.read(), "html.parser")
                day_list = stock_source.find_all("tr")

                for day_data in reversed(day_list):
                    if day_data.span is not None:
                        date = day_data.find_all('td',
                                                 align='center')[0].text
                        # only get data after input start_yr
                        if int(date.split('.')[0]) < self.start_yr:
                            continue
    
                        # data_list = [end, change, start, high, low, volume] 
                        data_list = day_data.find_all('td',
                                                       class_='num')
                        del data_list[1] # remove price_change
                        data_list = list(map(lambda x: x.text.replace(',', ''),
                                             data_list))
                        end_price = int(data_list[0])
                        if write_raw:
                            raw_wr.writerow([date] + data_list)
                        # add price to list unitl the quarter changes
                        if utils.get_quarter(date) == curr_quarter:
                            price_temp_list.append(end_price)
                        # when the quarter changes, write average price for the
                        # quarter on csv
                        else:
                            price_mean = utils.price_mean_list(price_temp_list)
                            self.stock_price_mean_list.append(price_mean)
                            price_median = utils.price_median_list(price_temp_list)
                            self.stock_price_median_list.append(price_median)
                            price_max = utils.price_max_list(price_temp_list)
                            self.stock_price_max_list.append(price_max)
                            price_min = utils.price_min_list(price_temp_list)
                            self.stock_price_min_list.append(price_min)
                            price_stdev = utils.price_stdev_list(price_temp_list)
                            self.stock_price_stdev_list.append(price_stdev)
                            if write_data:
                                wr.writerow([curr_quarter, price_mean,
                                             price_median, price_max,
                                             price_min, price_stdev])
                            # reset price_temp_list and curr_quarter as the
                            # quarter changed in this loop
                            price_temp_list = [end_price]
                            curr_quarter = utils.get_quarter(date)
            
            if write_data:
                data_file.close()
            if write_raw:
                raw_stock_file.close()
                
        
            
        print("Crawled price for code %s" % self.stock_code)

    def dart_crawl(self, update=False, debug=False, debug_list=[]):
        """ This function crawls all the necessary data from DART
            @param debug - whether to turn on debug mode
            @param debug_list - list of rcp_no's to crawl
        TODO: implement updating data on existing file
        """
        debug_rcp_no_list = debug_list

        curr_asset_list, noncurr_asset_list, total_asset_list = [], [], []
        curr_liab_list, noncurr_liab_list, total_liab_list = [], [], []
        equity_list, net_income_list, deprec_cost_list = [], [], []
        stock_num_list = []
        
        stock_data_file = os.path.join(self.COMPANY_DIR,
                                       "stock_data_%s.csv" % self.stock_code)
        if os.path.isfile(stock_data_file):
            price_data_write, read_csv = False, True
        else:
            price_data_write, read_csv = True, False
        stock_data_raw_file = os.path.join(self.COMPANY_DIR,
                                    "raw_stock_data_%s.csv" % self.stock_code)
        if os.path.isfile(stock_data_raw_file):
            price_raw_write = False
        else:
            price_raw_write = True
        self.stock_price_crawl(read_data=read_csv, write_data=price_data_write,
                               write_raw=price_raw_write);
        
        self.debug = debug
        if debug:
            rcp_iter_list = debug_rcp_no_list
        else:
            rcp_iter_list = self.rcp_no_list
            
        for rcp_no in rcp_iter_list:
            # attributes to manage printing of warning messages in parsing
            self.wrong_name_row, self.wrong_value_row = False, False
            self.wrong_thead_num, self.inc_wrong_name_row = False, False
            self.cash_wrong_name_row = False
            print("rcp %s processing" % rcp_no)
            source_dict = self.dart_page_source(rcp_no)
            stock_num_source = source_dict["stock_num"]
            fin_state_source = source_dict["fin_state"]
            inc_state_source = source_dict["inc_state"]
            fin_state_unit = source_dict["fin_state_unit"]
            inc_state_unit = source_dict["inc_state_unit"]
            fin_state_comment_source = source_dict["fin_state_comment"]
            cash_state_source = source_dict["cash_state"]
            cash_state_unit = source_dict["cash_state_unit"]
            fin_state_summary_source = source_dict["finstate_summary"]
            fin_state_summary_unit = source_dict["finstate_summary_unit"]
            
            stock_num = self.dart_crawl_target(rcp_no, stock_num_source,
                                               None, "stock_num")
            stock_num_list.append(stock_num)
            if self.debug:
                print("processed data - stock_num: %s" % stock_num)
    
            asset = self.dart_crawl_target(rcp_no, fin_state_source,
                                           fin_state_unit, "asset")
            if asset is None:
                curr_asset_list.append("")
                noncurr_asset_list.append("")
                total_asset_list.append("")
            else:
                curr_asset_list.append(asset[0])
                noncurr_asset_list.append(asset[1])
                total_asset_list.append(asset[2])
            if self.debug:
                print("processed data - curr_asset: %s, noncurr_asset: %s,\
                      total_asset: %s" % asset)
    
            liabilities = self.dart_crawl_target(rcp_no, fin_state_source,
                                                 fin_state_unit, "liabilities")
            if liabilities is None:
                curr_liab_list.append("")
                noncurr_liab_list.append("")
                total_liab_list.append("")
            else:
                curr_liab_list.append(liabilities[0])
                noncurr_liab_list.append(liabilities[1])
                total_liab_list.append(liabilities[2])
            if self.debug:
                print("processed data - curr_liabilities: %s,\
                noncurr_liabilities: %s, total_liabilities: %s" % liabilities)
            
            equity = self.dart_crawl_target(rcp_no, fin_state_source,
                                            fin_state_unit, "equity")
            if equity is None:
                equity_list.append("")
            else:
                equity_list.append(equity)
            if self.debug:
                print("processed data - equity: %s" % equity)
            
            net_income = self.dart_crawl_target(rcp_no, inc_state_source,
                                            inc_state_unit, "net_income")
            if net_income is None:
                net_income_list.append("")
            else:
                net_income_list.append(net_income)
            if self.debug:
                print("processed data - net_income: %s" % net_income)
            
            deprec_cost = self.dart_crawl_target(rcp_no, cash_state_source,
                                                 cash_state_unit, "deprec_cost")

            if deprec_cost is None:
                # if "재무제표 주석" or "부속명세서" exists
                if fin_state_comment_source is not None:
                    deprec_cost = self.dart_crawl_target(rcp_no,
                                fin_state_comment_source, None, "deprec_cost",
                                source_name="finstate_comment")

                # "사업의 내용" when "주석" or "부속명세서" does not exist
                if deprec_cost is None and fin_state_summary_source is not None:
                    deprec_cost = self.dart_crawl_target(rcp_no,
                                fin_state_summary_source,
                                fin_state_summary_unit, "deprec_cost",
                                source_name="finstate_summary")
            if deprec_cost is None:
                deprec_cost_list.append("")
            else:
                deprec_cost_list.append(deprec_cost)
            if self.debug:
                 print("processed data - deprec_cost: %s" % deprec_cost)
            
        self.fin_dict = {"period": self.fin_period_list,
                         "curr_asset": curr_asset_list,
                         "noncurr_asset": noncurr_asset_list,
                         "total_asset": total_asset_list,
                         "curr_liabilities": curr_liab_list,
                         "noncurr_liabilities": noncurr_liab_list,
                         "total_liabilities": total_liab_list,
                         "equity": equity_list,
                         "net_income": net_income_list,
                         "deprec_cost": deprec_cost_list,
                         "stock_num": stock_num_list,
                         "stock_price_mean": self.stock_price_mean_list,
                         "stock_price_median": self.stock_price_median_list,
                         "stock_price_max": self.stock_price_max_list,
                         "stock_price_min": self.stock_price_min_list,
                         "stock_price_stdev": self.stock_price_stdev_list,
                         }
        
    def set_fin_data(self, read_fin_csv=False, debug=False, debug_list=[]):
        """ This function sets processed financial data using crawled data """
        if not read_fin_csv:
            self.dart_crawl(debug=debug, debug_list=debug_list)
        else:
            self.fin_dict = None
        self.fin_data = finData.FinancialData(self.stock_code, self.fin_dict,
                                              read_csv=read_fin_csv)
        return self.fin_data


if __name__ == "__main__":
    start_time = time.time()
    # add debug mode and read mode
    parser = argparse.ArgumentParser(description="Choose option for the program.")
    parser.add_argument('-debug', action="store_true")
    parser.add_argument('-read', action="store_true")
    debug_mode = vars(parser.parse_args())["debug"]
    read_fin_csv = vars(parser.parse_args())["read"]
    
    company_data = CompanyData("002140")
    debug_list = ['20050812000878']
    company_fin_data = company_data.set_fin_data(read_fin_csv=read_fin_csv,
                                    debug=debug_mode, debug_list=debug_list)
    if not read_fin_csv:
        company_fin_data.write_raw_fin_data()
    company_fin_data.get_fin_data()
    company_fin_data.write_fin_data()

    print("Elapsed time: %s" % (time.time() - start_time))