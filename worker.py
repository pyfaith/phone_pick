# -*- coding: utf-8 -*-
# Author: Faith
# email: pyfaith@foxmail.com
# Date: 2018/8/16

import requests
import json
import re
import time
import threading
from regex_tags import regexTags
from database import getDatabaseConnection

product_list = {
    "腾讯大王卡": ("https://m.10010.com/king/kingNumCard/init?product=0&channel=67",
              "https://m.10010.com/queen/tencent/fill.html?product=0&channel=67"),
    "星粉卡(5元包月)": ("https://m.10010.com/king/kingNumCard/samsunginit?product=0",
            "https://m.10010.com/scaffold-show/fill/new-starcard-fill?product=0&channel=1"),
    "天神卡（3元不限量）": ("https://m.10010.com/king/kingNumCard/wuxianinit?product=0",
                   "https://m.10010.com/queen/xiaomi/infinite-fill.html?product=0"),
    "天神卡（1元日租包）": ("https://m.10010.com/king/kingNumCard/wuxianinit?product=1",
                   "https://m.10010.com/queen/xiaomi/infinite-fill.html?product=1"),
    "微博V+卡": (
    "https://m.10010.com/king/kingNumCard/weiboinit?product=2", "https://m.10010.com/queen/sina/fill.html?product=2"),
    "新米粉卡": ("https://m.10010.com/king/kingNumCard/newmiinit?product=1&channel=1",
             "https://m.10010.com/queen/xiaomi/new-fill.html?product=1&channel=1")
}


def getDistrictCode(init_api):
    r = requests.get(product_list[init_api][0])
    parsed = json.loads(r.text)
    ret = []
    for province in parsed["provinceData"]:
        if province["PROVINCE_CODE"] in parsed["proGroupNum"]:
            tmp = {"code": province["PROVINCE_CODE"], "province": province["PROVINCE_NAME"]}
            tmp["group"] = parsed["proGroupNum"][tmp["code"]]
            tmp["city"] = []
            for city in parsed["cityData"][tmp["code"]]:
                tmp["city"].append({"name": city["CITY_NAME"], "code": city["CITY_CODE"]})
            ret.append(tmp)
    return ret


class Matcher(object):
    def __init__(self, r):
        self.re = re.compile(r[0])
        self.tag = r[1]

    def match(self, s):
        if self.re.search(s):
            return self.tag
        return ""


class Worker(threading.Thread):
    def __init__(self, product, province, provinceCode, city, cityCode, groupKey):
        self.matchers = list(map(Matcher, regexTags))
        self.product = product
        self.province = province
        self.provinceCode = provinceCode
        self.city = city
        self.cityCode = cityCode
        self.groupKey = groupKey
        self.rollingCount = []
        self.running = True
        self.autoTerminate = True
        self.history = []
        super(Worker, self).__init__()

    def getNum(self):
        conn = getDatabaseConnection()
        try:
            r = requests.get("https://m.10010.com/NumApp/NumberCenter/qryNum", params={
                "callback": "jsonp_queryMoreNums",
                "provinceCode": self.provinceCode,
                "cityCode": self.cityCode,
                "groupKey": self.groupKey,
                "searchCategory": "3",
                "net": "01",
                "qryType": "02",
                "goodsNet": "4"
            })
            print(r.url)
            nums = re.findall(r"\d{11}", r.text)
            ret = map(lambda num: (num, self.makeTag(num)), nums)
            cur = conn.cursor()
            cur.executemany("INSERT OR IGNORE INTO tbl_numbers(number, tag) VALUES(?, ?);", ret)
            conn.commit()
            if cur.rowcount > 0:
                self.history.append((time.strftime("%Y-%m-%d %H:%M:%S"), cur.rowcount))
                if len(self.history) == 201:
                    self.history.pop(0)
            return len(nums), cur.rowcount
        except:
            return 0, 0
        finally:
            conn.close()

    def makeTag(self, n):
        return "," + ",".join([i for i in map(lambda r: r.match(n), self.matchers) if i]) + ","

    def run(self):
        self.running = True
        while self.running:
            _, c = self.getNum()
            self.rollingCount.append(c)
            if len(self.rollingCount) == 101:
                self.rollingCount.pop(0)
                if (sum(self.rollingCount) < 10) and (self.autoTerminate):
                    break
            time.sleep(3)

    def stop(self):
        self.running = False
