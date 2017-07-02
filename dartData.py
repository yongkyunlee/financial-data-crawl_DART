#-*- coding:utf-8 -*-

import requests
import json
import datetime
import os
import re

def get_rcp_period(rcp_nm_list):
    """ This function obtains the period rcp belongs to using 
        the input rcp_nm_list
    """
    pattern = re.compile(r'''(\[기재정정\])?(\[첨부추가\])?(\[첨부정정\])?
                         (?P<rcp_nm>.*?)\s*?
                         \((?P<rcp_yr>[0-9]+)\.(?P<rcp_mth>[0-9]+)\)'''
                         , re.MULTILINE | re.DOTALL | re.VERBOSE)
    rcp_period_list = []
    for rcp_nm in rcp_nm_list:
        match = pattern.search(rcp_nm)
        rcp_nm, rcp_yr, rcp_mth = match.group("rcp_nm"), match.group("rcp_yr"), match.group("rcp_mth")
        rcp_quarter = int(rcp_mth) / 3
        assert rcp_quarter in range(1, 5)
        if rcp_quarter == 1 or rcp_quarter == 3:
            assert rcp_nm == "분기보고서"
        elif rcp_quarter == 2:
            assert rcp_nm == "반기보고서"
        elif rcp_quarter == 4:
            assert rcp_nm == "사업보고서"
        # period format is "year-quarter"
        rcp_period = "%s-%d" % (rcp_yr, rcp_quarter)
        rcp_period_list.append(rcp_period)
    return rcp_period_list

def search_dart(stock_code, start_yr=2000, data_target = 1):
    """ This function returns the list of rcp_no and rpt_nm uploaded at DART
        for the input stock_code
        @param start_yr - starting year of data
        @param data_target - 1 for data every quarter (분기/반기/사업보고서), 
                             2 for only year data (사업보고서)
        TODO:
        - implement code for data_target == 2
    """
    now = datetime.datetime.now()
    curr_yr, curr_month = now.year, now.month
    # maximum number of reports to request
    data_num = (curr_yr - 2000 + 1)*4 + int(curr_month / 4)
    rcp_no_list, rcp_dt_list, rpt_nm_list, crp_cd_list = [], [], [], []
    
    # choose type of reports to request
    if data_target == 1:
        dsn_tp_cnt = 3 # include A001 ~ A003
    elif data_target == 2:
        dsn_tp_cnt = 1 # include only A001
    else:
        raise TypeError("data_target parameter is invalid")
        
    for idx in range(1, dsn_tp_cnt + 1):
        # A001 - 사업보고서, A002 - 반기보고서, A003 - 분기보고서
        bsn_tp = "A00" + str(idx)
        params = {
            "crp_cd": stock_code,
            "start_dt": str(start_yr) + "0101",
            "bsn_tp": bsn_tp,
            "page_no": "1",
            "fin_rpt": "Y",
            "page_set": str(data_num),
        }
        response = requests.get("http://dart.fss.or.kr/api/search.json?auth="
                                + os.environ["DART_API_KEY"], params=params)
        content = response.content
        result_list = json.loads(content.decode('UTF-8'))["list"]
        rcp_no_list += list(map(lambda x: x['rcp_no'], result_list)) # 접수번호
        rcp_dt_list += list(map(lambda x: x['rcp_dt'], result_list)) # 공시접수일자
        rpt_nm_list += list(map(lambda x: x['rpt_nm'], result_list)) # 공시구분
        crp_cd_list += list(map(lambda x: x['crp_cd'], result_list)) # 종목코드
        for crp_cd in crp_cd_list:
            assert crp_cd == stock_code
    print("Dart data retrieved for the stock_code %s" % stock_code)
    
    # rcp_no may not be in the order of time
    # need to order the rcp_no_list and rpt_nm_list from oldest to newest
    # sort based on the period in rpt_nm and apply the order to rcp_no_list
    rcp_no_list, rcp_nm_list = zip(*sorted(zip(rcp_no_list, rpt_nm_list),
                                key=lambda x: x[1][len(x[1])-8 : len(x[1])-1]))
    rcp_no_list = list(rcp_no_list)
    rcp_nm_list = list(rcp_nm_list)
    rcp_period_list = get_rcp_period(rcp_nm_list)
    return rcp_no_list, rcp_period_list
    
if __name__ == "__main__":
    # test case
    search_data = search_dart("002140")
    print(search_data)
    