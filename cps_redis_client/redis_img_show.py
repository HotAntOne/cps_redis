#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 直接使用redis进行协同数据库读取
# 


import time
import redis
import cv2
import numpy as np
import sys


class RedisClient():
    def __init__(self, local_redis=('127.0.0.1', 6379), uav_id='0'):
        # 连接本地redis数据库
        try:
            print('Redis local')
            self.red_l = redis.Redis(host=local_redis[0], port=local_redis[1], db=0)
            self.red_l.get('tst')
            print('Redis OK!')
        except:
            print("Redis connect error!")
            exit()

        # 读取并显示图片
        while True:
            ret = self.red_l.hmget(uav_id+':img:0', 'img')
            if ret[0] != None:
                img_np = np.frombuffer(ret[0], np.uint8)
                img_cv = cv2.imdecode(img_np, cv2.IMREAD_ANYCOLOR)
                cv2.imshow('test', img_cv)
                # time.sleep(10)
                cv2.waitKey(1)
                pass

if __name__ == '__main__':
    uav_id = sys.argv[1]
    RedisClient(uav_id=uav_id)
