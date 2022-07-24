#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 直接使用redis进行协同数据库读取
# V1.0 完备基础数据同步
# V2.0 完备通信数据
# V3.0 完备丢包率，设置过时数据


import time
import redis
import _thread as thread
import socket


selo_dat = ['seq','sec','ns','px','py','pz','vx','vy','vz','ax','ay','az','yaw','yara']
bat_dat  = ['seq','sec','ns','vol','per']
lopo_dat = ['seq','sec','ns','px','py','pz','ox','oy','oz','ow']
imu_dat  = ['seq','sec','ns','ox','oy','oz','ow','ax','ay','az','lx','ly','lz']
img_dat  = ['seq','sec','ns','len','img']
dat_name_list = ['selo', 'bat', 'lopo', 'imu', 'img']
dat_list = [selo_dat, bat_dat, lopo_dat, imu_dat, img_dat]

ping_dat = ['seq','sec','ns','dely','loss','val']   # 延时、丢包、分数（0-100）。其中延时和丢包均乘以偏置100000
# 

class RedisClient():
    def __init__(self, server_addr=('192.168.1.104', 6379), local_redis=('127.0.0.1', 6379), uav_id=0):
        self.redis_expire = 0        # redis数据的保存时间，单位s，为0表示不删除
        self.server_addr = server_addr
        self.local_redis = local_redis
        self.uav_id = uav_id
        self.ping_seq = 1
        self.ping_delay = [0 for i in range(len(dat_list))]     # 为每一个topic的延时
        # 1. 连接服务端redis数据库
        try:
            print('Redis server')
            self.red_s = redis.Redis(host=server_addr[0], port=server_addr[1], db=0)
            self.red_s.get('tst')
            print('Redis OK!')
        except:
            print("Redis connect error!")
            exit()

        # 2. 连接本地redis数据库
        try:
            print('Redis local')
            self.red_l = redis.Redis(host=local_redis[0], port=local_redis[1], db=0)
            self.red_l.get('tst')
            print('Redis OK!')
        except:
            print("Redis connect error!")
            exit()

        # 3. 测试数据库的数据是否正常，仅判断是
        try:
            for dat_name in dat_name_list:
                self.red_s.hmget(str(self.uav_id)+':'+dat_name+':0', 'seq')
            print('Redis data OK')
        except:
            print('Redis server data error!')
            exit()
        pass

        # 4. 测试数据库的数据是否为空
        for dat_name in dat_name_list:
            ret = self.red_s.hmget(str(self.uav_id)+':'+dat_name+':0', 'seq')
            if ret[0] == None:
                print('Redis server data off!')
                print(dat_name+' is not exist')
                # exit()
        print('Redis data ON!')

        # 5. 启动多线程存储数据
        try:
            for i in range(len(dat_name_list)):
                thread.start_new_thread(self.save_dat, (i, ))
                time.sleep(0.01)
            thread.start_new_thread(self.ping_dat, ())
        except Exception as e:
            print(e)
            exit()

        print('UAV ', str(self.uav_id), ' is starting loading~')

    def ping_dat(self):
        # 进行通信测试，包括通信延时、通信丢包、通信
        while True:
            try:
                time_start = time.time()
                # print(time_start)

                # 延时，单位ms
                delay_ave = sum(self.ping_delay) / len(self.ping_delay)
                delay_max = max(self.ping_delay)
                delay_min = min(self.ping_delay)

                # 丢包，单位0-100，有offset的偏置
                loss_ave = 100
                client = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                client.settimeout(0.9)
                #client.bind(("192.168.1.128", 8000))
                msg = 'a' * 1000
                try:
                    client.sendto(msg.encode(),(self.server_addr[0],6380+int(self.uav_id)))
                    data, server_addr = client.recvfrom(1024)   #接收，但是会出现一致卡死在这里
                    loss_ave = int((1000-len(data.decode()))/10)
                except:
                    pass
                # print(len(data.decode()))
                # time.sleep(0.1)
                #print(data.decode('utf-8'))
                client.close()
                

                # 信道评分值，0-100整数，无偏置，根据延时和丢包计算
                val = 100 - loss_ave
                if (delay_ave-5)>0:
                    val = val - (delay_ave-5)*2
                if val<0:
                    val = 0
                val = int(val)

                offset = 100000
                res_dat = {}
                res_dat['seq'] = str(self.ping_seq)
                self.ping_seq += 1
                res_dat['sec'] = 0
                res_dat['ns'] = 0
                res_dat['dely'] = int(delay_ave*offset)     # 通信延时，默认延时的平均值
                res_dat['loss'] = int(loss_ave*offset)     # 通信丢包率，tcp为0，应该用udp进行测试
                res_dat['val'] = int(val)           # 通信质量评分，0-100，基于通信延时和通信丢包进行计算
                # print(res_dat)
                self.red_l.hmset(str(self.uav_id)+':ping:0', res_dat)
                self.red_l.hmset(str(self.uav_id)+':ping:'+str(res_dat['seq']), res_dat)
                if self.redis_expire>0:
                    self.red_l.expire(str(self.uav_id)+':ping:'+str(res_dat['seq']), self.redis_expire)

                # print('Socket udp on~')
                while time.time()-time_start<1:
                    pass
            except Exception as e:
                print(e)
                print('Socket udp error!')
                pass

    def save_dat(self, dat_id=0, seq=0):
        # 存储通用的数据
        while True:
            try:
                time_start = time.time()

                key = str(self.uav_id)+':'+str(dat_name_list[dat_id])+':'
                dat_dat = dat_list[dat_id]

                ret = self.red_s.hmget(key+str(seq), dat_dat)
                self.ping_delay[dat_id] = (time.time() - time_start)*1000       # 计算每个topic的延时

                if ret[0]==None:
                    continue
                res_dat = {}
                for i in range(len(dat_dat)):
                    res_dat[dat_dat[i]] = ret[i]
                

                if seq==0:
                    self.red_l.hmset(key+str(seq), res_dat)
                self.red_l.hmset(key+str(res_dat['seq']), res_dat)
                if self.redis_expire>0:
                    self.red_l.expire(key+str(res_dat['seq']), self.redis_expire)
                
                while time.time()-time_start < 0.1:
                    # 以10Hz的速度进行存储
                    pass
            except Exception as e:
                print(e)
                print('Redis data error!')
                pass
    
    def save_imu(self, seq=0):
        # 专用imu数据读取
        while True:
            try:
                time_start = time.time()

                ret = self.red_s.hmget(str(self.uav_id)+':imu:'+str(seq), imu_dat)
                res_dat = {}
                for i in range(len(imu_dat)):
                    res_dat[imu_dat[i]] = ret[i]
                # print(res_dat)
                if seq==0:
                    self.red_l.hmset(str(self.uav_id)+':imu:'+str(seq), res_dat)
                self.red_l.hmset(str(self.uav_id)+':imu:'+str(res_dat['seq']), res_dat)
                
                while time.time()-time_start < 1:
                    pass
            except Exception as e:
                print(e)
                print('Redis data error!')
                pass

                
   
 
if __name__ == '__main__':
    for i in range(6):
        RedisClient(server_addr=('192.168.1.104', 6379), uav_id=i)
    # RedisClient(server_addr=('192.168.1.104', 6379), uav_id=1)


    while True:
        pass
