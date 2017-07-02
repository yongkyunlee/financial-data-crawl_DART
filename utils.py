#-*- coding:utf-8 -*-
import re
import requests
from statistics import mean
from statistics import median
from statistics import pstdev
from statistics import stdev

def url_exists(url):
    """ This function checks whether the input url exists """
    request = requests.get(url)
    if request.status_code == 200:
        exist = True
    else:
        exist = False
    return exist

def get_quarter(date):
    """ Determines the period of input date
        @param date - "YYYY.MM.DD"
        @return - "YYYY-quarter" where quarter is from 1 to 4
    """
    yr, mth, day = list(map(lambda x: int(x), date.split('.')))
    return "%d-%d" % (yr, (mth-1)/3 + 1)
    
def num_format(inputStr):
    """ This function removes possible elements of string to make it convertible
    to int """
    return inputStr.replace(',', '').replace(' ', '').replace('\n', '').replace("=", '')

def format_page_html(page_html):
    """ This function remove some html tags of old formats that hinder crawling
    """
    page_html = re.sub(r'\s*&nbsp;\s*','', page_html)
    page_html = re.sub(r'<BR/>', '\n', page_html)
    page_html = re.sub(r'<SPAN.*?>', '', page_html)
    page_html = re.sub(r'</SPAN>', '', page_html)
    return page_html

# list of patterns used to search DART data page
page_pattern = {
    "stock_num" : re.compile(r'''[.]\s주식의\s총수\s등".*?viewDoc\(
                             \'(?P<rcpNo>[0-9]+)\W+(?P<dcmNo>[0-9]+)\W+
                             (?P<eleId>[0-9]+)\W+(?P<offset>[0-9]+)\W+
                             (?P<length>[0-9]+)\W+(?P<dtd>[.0-9a-zA-Z]+)\'\);'''
                             , re.MULTILINE | re.DOTALL | re.VERBOSE),
    "conn_fin_state": re.compile(r'''"2\.\s연결재무제표".*?viewDoc\(
                                 \'(?P<rcpNo>[0-9]+)\W+(?P<dcmNo>[0-9]+)\W+
                                 (?P<eleId>[0-9]+)\W+(?P<offset>[0-9]+)\W+
                                 (?P<length>[0-9]+)\W+(?P<dtd>[.0-9a-zA-Z]+)\'\);'''
                                 , re.MULTILINE | re.DOTALL | re.VERBOSE),
    "conn_fin_state_comment": re.compile(r'''"[0-9]\.\s연결재무제표\s주석".*?
                                 viewDoc\(\'(?P<rcpNo>[0-9]+)\W+(?P<dcmNo>[0-9]+)
                                 \W+(?P<eleId>[0-9]+)\W+(?P<offset>[0-9]+)
                                 \W+(?P<length>[0-9]+)\W+(?P<dtd>[.0-9a-zA-Z]+)
                                 \'\);'''
                                 , re.MULTILINE | re.DOTALL | re.VERBOSE),
    "gen_fin_state": re.compile(r'''[.]\s재무제표\s등".*?viewDoc\(
                                 \'(?P<rcpNo>[0-9]+)\W+(?P<dcmNo>[0-9]+)\W+
                                 (?P<eleId>[0-9]+)\W+(?P<offset>[0-9]+)\W+
                                 (?P<length>[0-9]+)\W+(?P<dtd>[.0-9a-zA-Z]+)\'\);'''
                                 , re.MULTILINE | re.DOTALL | re.VERBOSE),
    "gen_fin_state2": re.compile(r'''\s부속명세서".*?viewDoc\(
                                 \'(?P<rcpNo>[0-9]+)\W+(?P<dcmNo>[0-9]+)\W+
                                 (?P<eleId>[0-9]+)\W+(?P<offset>[0-9]+)\W+
                                 (?P<length>[0-9]+)\W+(?P<dtd>[.0-9a-zA-Z]+)\'\);'''
                                 , re.MULTILINE | re.DOTALL | re.VERBOSE),
    "unconn_fin_state": re.compile(r'''"[0-9]\.\s재무제표".*?viewDoc\(
                                 \'(?P<rcpNo>[0-9]+)\W+(?P<dcmNo>[0-9]+)\W+
                                 (?P<eleId>[0-9]+)\W+(?P<offset>[0-9]+)\W+
                                 (?P<length>[0-9]+)\W+(?P<dtd>[.0-9a-zA-Z]+)\'\);'''
                                 , re.MULTILINE | re.DOTALL | re.VERBOSE),
    "unconn_fin_state_comment": re.compile(r'''"[0-9]\.\s재무제표\s주석".*?
                                 viewDoc\(\'(?P<rcpNo>[0-9]+)\W+(?P<dcmNo>[0-9]+)
                                 \W+(?P<eleId>[0-9]+)\W+(?P<offset>[0-9]+)
                                 \W+(?P<length>[0-9]+)\W+(?P<dtd>[.0-9a-zA-Z]+)
                                 \'\);'''
                                 , re.MULTILINE | re.DOTALL | re.VERBOSE),
    "business_content": re.compile(r'''사업의\s내용".*?
                                 viewDoc\(\'(?P<rcpNo>[0-9]+)\W+(?P<dcmNo>[0-9]+)
                                 \W+(?P<eleId>[0-9]+)\W+(?P<offset>[0-9]+)
                                 \W+(?P<length>[0-9]+)\W+(?P<dtd>[.0-9a-zA-Z]+)
                                 \'\);'''
                                 , re.MULTILINE | re.DOTALL | re.VERBOSE),
}

# list of options of target patterns
target_pattern_list = {
    "stock_num": [r"발행한\s주식의\s총수", r"발행주식의 총수", r"유통\s*?주식수"],
    "stock_num_p": [r"발행한\s주식의\s총수", "발행주식의 총수",
                    r"유통\s*?주식의\s*?총수", r"발행한\s*?주식수"],
    "curr_asset": [r"^\s*?유\s*?동\s*?자\s*?산", "유\s*?동\s*?자\s*?산"],
    "noncurr_asset": [r"^\s*?비\s*?유\s*?동\s*?자\s*?산",
                      r"\s*?비\s*?유\s*?동\s*?자\s*?산", r"고\s*?정\s*?자\s*?산"],
    "total_asset": [r"자\s*?산\s*?총\s*?계"],
    "curr_liabilities": [r"^\s*?유\s*?동\s*?부\s*?채", "유\s*?동\s*?부\s*?채"],
    "noncurr_liabilities": [r"^\s*?비\s*?유\s*?동\s*?부\s*?채",
                            r"비\s*?유\s*?동\s*?부\s*?채",
                            r"고\s*?정\s*?부\s*?채"],
    "total_liabilities": [r"부\s*?채\s*?총\s*?계"],
    "total_equity": [r"자\s*?본\s*?총\s*?계"],
    "minor_equity": ["비지배"],
    "minor_income": ["비지배"],
    "major_income": [r"지배기업\w*?지분", "지배"],
    "net_income": [r"당\s*?기\s*?순\s*?이\s*?익", r"분\s*?기\s*?순\s*?이\s*?익",
                   r"반\s*?기\s*?순\s*?이\s*?익", r"당\s*?기\s*?순\s*?손\s*?실"],
    "deprec_cost": [r".*?상각비.*?"],
    "cost_type": [r"\s비용의\s성격별"],
}

unit_convert = {
    "": "",
    "십": "0",
    "백": "0" * 2,
    "천": "0" * 3,
    "만": "0" * 4,
    "십만": "0" * 5,
    "백만": "0" * 6,
    "천만": "0" * 7,
}

def price_mean_list(price_list):
    """ Calculates the mean of input price_list """
    assert type(price_list[0]) is int
    price_avg = int(mean(price_list))
    return str(price_avg)

def price_median_list(price_list):
    """ Calculates the median of input price_list """
    assert type(price_list[0]) is int
    price_median = int(median(price_list))
    return str(price_median)
    
def price_max_list(price_list):
    """ Returns the maximum price of the input price_list """
    assert type(price_list[0]) is int
    price_max = int(max(price_list))
    return str(price_max)

def price_min_list(price_list):
    """ Returns the minimum price of the input price_list """
    assert type(price_list[0]) is int
    price_min = int(min(price_list))
    return str(price_min)

def price_stdev_list(price_list):
    """ Returns the standard deviation of price of the input price list"""
    assert type(price_list[0]) is int
    price_stdev = pstdev(price_list)
    return "{0:.2f}".format(price_stdev)
    
