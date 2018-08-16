# -*- coding: utf-8 -*-
# Author: Faith
# email: pyfaith@foxmail.com
# Date: 2018/8/16

import json
import tornado.web
import tornado.ioloop
import requests
from worker import Worker, product_list, getDistrictCode
from database import getDatabaseConnection
from regex_tags import regexTags

_worker = None

class MainHandler(tornado.web.RequestHandler):
    '''首页'''
    def get(self):
        self.render('index.html')

class ApiBaseHandler(tornado.web.RequestHandler):
    '''api基类'''
    def set_default_headers(self):
        self.set_header('Accept',
                        'application/json, text/javascript, */*; q=0.01')
    def write_json(self, data):
        return self.write(json.dumps(data))


class ApiStartHandler(ApiBaseHandler):
    '''
    启动爬虫,抓取号码
    '''
    global _worker
    def get(self):
        global _worker
        _worker = Worker(
            product=self.get_argument("product", "腾讯大王卡"),
            province=self.get_argument("province", "上海"),
            provinceCode=self.get_argument("provinceCode", "31"),
            city=self.get_argument("city", "上海"),
            cityCode=self.get_argument("cityCode", "310"),
            groupKey=self.get_argument("groupKey", "34236498")
        )
        _worker.start()
        result_data = {}
        self.write_json(result_data)

class ApiStopHandler(ApiBaseHandler):
    '''
    停止抓取号码
    '''
    global _worker
    def get(self):
        if _worker:
            _worker.stop()
        result_data = {}
        self.write_json(result_data)


class ApiStatusHandler(ApiBaseHandler):
    '''查看当前获取到的号码'''
    global _worker
    def get(self):
        conn = getDatabaseConnection()
        #获取游标
        db_cursor = conn.cursor()
        try:
            db_cursor.execute("SELECT COUNT(*) FROM tbl_numbers;")
        except Exception as e:
            print(e)
        else:
            result_count = db_cursor.fetchone()[0]
        finally:
            conn.close()

        if _worker:
            result_data = {
                "running": _worker.is_alive(),
                "count": result_count,
                "product": _worker.product,
                "city": _worker.city,
                "cityCode": _worker.cityCode,
                "province": _worker.province,
                "provinceCode": _worker.provinceCode,
                "groupKey": _worker.groupKey,
                "autoTerminate": _worker.autoTerminate,
                "history": _worker.history
            }
        else:
            result_data = {
                "running": False,
                "count": result_count
            }
        self.write_json(result_data)

class ApiProductsHandler(ApiBaseHandler):
    '''获取联通互联网卡套餐信息'''
    def get(self):
        result_data = list(product_list.keys())
        self.write_json(result_data)


class ApiDistrictHandler(ApiBaseHandler):
    def get(self):
        result_data = getDistrictCode(self.get_argument("product"))
        self.write_json(result_data)

class ApiLinkHandler(ApiBaseHandler):
    '''获取申请链接'''
    def get(self):
        result_data = {
            'link': product_list[self.get_argument("product")][1]
        }
        self.write_json(result_data)

class ApiFiltersHandler(ApiBaseHandler):
    '''查询正则'''
    def get(self):
        result_data = list(map(lambda i: i[1], regexTags))
        self.write_json(result_data)

class ApiEmptyHandler(ApiBaseHandler):
    '''清空数据库'''
    global _worker
    def get(self):
        if _worker:
            if _worker.is_alive():
                result_data = {}
        conn = getDatabaseConnection()
        db_cursor = conn.cursor()
        try:
            db_cursor.execute("DELETE FROM tbl_numbers;")
        except Exception as e:
            print(e)
        else:
            conn.commit()
            result_data = {}
        finally:
            conn.close()
        self.write_json(result_data)


class ApiNumsHandler(ApiBaseHandler):
    '''获取数据库号码'''
    def get(self):
        query = []
        if self.get_argument("filter", None):
            filters = self.get_argument("filter").split("|")
            for f in filters:
                query.append("tag LIKE '%,{},%'".format(f))
        if self.get_argument("custom", None):
            query.append("number REGEXP '{}'".format(self.get_argument("custom")))
        conn = getDatabaseConnection()
        db_cursor = conn.cursor()
        try:
            if query:
                db_cursor.execute("SELECT number,tag FROM tbl_numbers WHERE {};".format(" OR ".join(query)))
            else:
                db_cursor.execute("SELECT number,tag FROM tbl_numbers;")
        except Exception as e:
            print(e)
        else:
            retsult_count = db_cursor.fetchall()
        finally:
            conn.close()
        result_data = list(map(lambda i: {"number": i[0], "tag": i[1].strip(",")}, retsult_count))
        self.write_json(result_data)


class ApiAutoTerminateHandler(ApiBaseHandler):
    global _worker
    def get(self):
        _worker.autoTerminate =  True if self.get_argument("autoTerminate", "true") == "true" else False
        result_data = {}
        self.write_json(result_data)



handlers = [
    (r'/', MainHandler),
    (r'/api/start', ApiStartHandler),
    (r'/api/stop', ApiStopHandler ),
    (r'/api/status', ApiStatusHandler ),
    (r'/api/products', ApiProductsHandler ),
    (r'/api/district', ApiDistrictHandler ),
    (r'/api/link', ApiLinkHandler ),
    (r'/api/filters', ApiFiltersHandler ),
    (r'/api/empty', ApiEmptyHandler ),
    (r'/api/nums', ApiNumsHandler ),
    (r'/api/autoTerminate', ApiAutoTerminateHandler ),
    ]



settings = {
    'template_path': 'template',
    'debug': True,
}
application = tornado.web.Application(
    handlers=handlers,
    **settings,
)

if __name__ == '__main__':
    application.listen(8000, address='0.0.0.0')
    tornado.ioloop.IOLoop.instance().start()