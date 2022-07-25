#!/usr/bin/env python
# -*- coding:utf-8 -*-

# 使用rospy保存数据到redis
# 测试成功
# 版本：V2.0
# 版本：V3.0 添加图像
# V4.0 添加UDP服务器，用于丢包数据，但是为了同一电脑上进行多开，设置不同的ip端口

import socket
import _thread as thread

import redis
import sys
import rospy
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import PositionTarget
from sensor_msgs.msg import Imu, BatteryState
from sensor_msgs.msg import Image, CompressedImage



class redis_data_save():
    def __init__(self, red_host, uav_name = "", ttl_time=600):
        # 0. 参数
        self.ttl_time = ttl_time
        
        # 1. 启动redis和roslibpy连接
        self.ros_c = None
        self.ros_s = False
        self.red_c = None
        self.red_s = False
        
        self.soc_c = None
        self.soc_s = False
        
        # 2. 定义数据类型
        self.imu_dat = Imu()
        self.lopo_dat = PoseStamped()
        self.glpo_dat = PoseStamped()
        self.bat_dat = BatteryState()
        self.selo_dat = PositionTarget()
        self.img_dat = CompressedImage()
        self.img_seq = 1
        
        # self.uav_name = ''
        # self.uav_name = '/iris_0'
        self.uav_name = uav_name
        if self.uav_name != "" and self.uav_name[0] !="/":
            self.uav_name = '/'+ self.uav_name
        if self.uav_name != "":
            self.uav_id = self.uav_name[-1]
        else:
            self.uav_id = str(0)

        
        self.rostopic_list = [
            self.uav_name+'/mavros/imu/data',
            self.uav_name+'/mavros/local_position/pose',
            self.uav_name+'/mavros/globe_position/pose',
            self.uav_name+'/mavros/battery',
            self.uav_name+'/mavros/setpoint_raw/local',
            self.uav_name+'/stereo_camera/left/image_raw/compressed',
        ]
        
        # 3. 连接rospy和redis
        try:
            rospy.init_node('Redis_data' ,anonymous=True)
            rospy.Subscriber(self.rostopic_list[0], Imu,               self.imu_call)
            rospy.Subscriber(self.rostopic_list[1], PoseStamped,       self.lopo_call)
            # rospy.Subscriber(self.rostopic_list[2], PoseStamped,       self.glpo_call)
            rospy.Subscriber(self.rostopic_list[3], BatteryState,      self.bat_call)
            rospy.Subscriber(self.rostopic_list[4], PositionTarget,    self.selo_call)
            rospy.Subscriber(self.rostopic_list[5], CompressedImage,   self.img_call)
            print('Rospy OK!')
            self.ros_s = True
        except Exception as e:
            print(e)
            print("Rospy error!")
        
        try:
            self.red_c = redis.Redis(host=red_host, port=6379, db=0)
            (self.red_c.get('tst'))
            print('Redis OK!')
            self.red_s = True
        except:
            print("Redis connect error!")

        # 创建socket udp服务器，设置不同的ip
        try:
            self.udp_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_server.bind(('0.0.0.0', 6380+int(self.uav_id)))     # 端口默认随uav_id增加,6380+id
            thread.start_new_thread(self.sock_call, ())
            print("Socket Udp Server OK~")
            # 需要开启多线程，防止占用原有rospy
            # while True:
            #     data, addr = self.udp_server.recvfrom(1024)
            #     self.udp_server.sendto(data.upper(), addr)  # 发送回去
        except Exception as e:
            print(e)
            print("Socket server error!")
            
        # -1：系统处理
        if self.ros_s and self.red_s:
            print('OK')
        else:
            sys.exit()
        pass


    def sock_call(self):
        # socket服务器线程
        try:
            while True:
                data, addr = self.udp_server.recvfrom(1024)
                self.udp_server.sendto(data.upper(), addr)  # 发送回去
        except:
            print('Socket running error!')
            pass
    
    
    # 3. 将数据存储到数据库中，图像数据
    def img_call(self, msg):
        # 存储的数据包括通用：header:seq  stamp: secs  nsecs（都需要自己输入）
        # 专有：img.len, img.data
        # 显示 self.uav_name:img:seq 
        dat = msg
        seq = self.img_seq
        self.img_seq = self.img_seq+1
        stamp_secs = rospy.Time.now().secs
        stamp_nsecs = rospy.Time.now().nsecs
        img = bytes(dat.data)
        length = len(img)
        offset = 100000
        res_dat = {
            'seq':      seq,
            'sec':      stamp_secs,
            'ns':       stamp_nsecs,
            'len':      length,
            'img':      img,
        }
        self.red_c.hmset(self.uav_id+':img:'+str(seq), res_dat)
        if self.ttl_time>0:
            self.red_c.expire(self.uav_id+':img:'+str(seq), self.ttl_time)
        self.red_c.hmset(self.uav_id+':img:'+str(0), res_dat)          # 备份一个到0位置
        if seq%10==0:
            print('img:'+str(seq))
        return
        
        
    # 3. 将数据存储到数据库中
    def selo_call(self, msg):
        # 存储的数据包括通用：header:seq  stamp: secs  nsecs
        # 专有：position velocity acceleration_or_force yaw yaw_rate
        # 显示 self.uav_name:selo:seq 
        dat = msg
        seq = dat.header.seq
        stamp_secs = dat.header.stamp.secs
        stamp_nsecs = dat.header.stamp.nsecs
        position = dat.position
        velocity = dat.velocity
        acceleration = dat.acceleration_or_force
        yaw = dat.yaw
        yaw_rate = dat.yaw_rate
        offset = 100000
        res_dat = {
            'seq':      seq,
            'sec':      stamp_secs,
            'ns':       stamp_nsecs,
            'px':       int(position.x*offset),
            'py':       int(position.y*offset),
            'pz':       int(position.z*offset),
            'vx':       int(velocity.x*offset),
            'vy':       int(velocity.y*offset),
            'vz':       int(velocity.z*offset),
            'ax':       int(acceleration.x*offset),
            'ay':       int(acceleration.y*offset),
            'az':       int(acceleration.z*offset),
            'yaw':      int(yaw*offset),
            'yara':     int(yaw_rate*offset), 
        }
        self.red_c.hmset(self.uav_id+':selo:'+str(seq), res_dat)
        if self.ttl_time>0:
            self.red_c.expire(self.uav_id+':selo:'+str(seq), self.ttl_time)
        self.red_c.hmset(self.uav_id+':selo:'+str(0), res_dat)          # 备份一个到0位置
        if seq%100==0:
            print('selo:'+str(seq))
        return
       
    # 3. 将数据存储到数据库中
    def bat_call(self, msg):
        # 存储的数据包括通用：header:seq  stamp: secs  nsecs
        # 专有：voltage percentage
        # 显示 self.uav_name:bat:seq 
        dat = msg
        seq = dat.header.seq
        stamp_secs = dat.header.stamp.secs
        stamp_nsecs = dat.header.stamp.nsecs
        voltage = dat.voltage
        percentage = dat.percentage
        offset = 100000
        res_dat = {
            'seq':      seq,
            'sec':      stamp_secs,
            'ns':       stamp_nsecs,
            'vol':      int(voltage*offset),
            'per':      int(percentage*offset),
        }
        self.red_c.hmset(self.uav_id+':bat:'+str(seq), res_dat)
        if self.ttl_time>0:
            self.red_c.expire(self.uav_id+':bat:'+str(seq), self.ttl_time)
        self.red_c.hmset(self.uav_id+':bat:'+str(0), res_dat)          # 备份一个到0位置
        if seq%100==0:
            print('bat:'+str(seq))
        return
    
    # 3. 将数据存储到数据库中
    def lopo_call(self, msg):
        # 存储的数据包括通用：header:seq  stamp: secs  nsecs
        # 专有：位置pose position xyz；pose orientation xyzw
        # 显示 self.uav_name:lopo:seq 
        dat = msg
        seq = dat.header.seq
        stamp_secs = dat.header.stamp.secs
        stamp_nsecs = dat.header.stamp.nsecs
        position = dat.pose.position
        orientation = dat.pose.orientation
        offset = 100000
        res_dat = {
            'seq':      seq,
            'sec':      stamp_secs,
            'ns':       stamp_nsecs,
            'px':      int(position.x*offset),
            'py':      int(position.y*offset),
            'pz':      int(position.z*offset),
            'ox':      int(orientation.x*offset),
            'oy':      int(orientation.y*offset),
            'oz':      int(orientation.z*offset),
            'ow':      int(orientation.w*offset),
        }
        self.red_c.hmset(self.uav_id+':lopo:'+str(seq), res_dat)
        if self.ttl_time>0:
            self.red_c.expire(self.uav_id+':lopo:'+str(seq), self.ttl_time)
        self.red_c.hmset(self.uav_id+':lopo:'+str(0), res_dat)          # 备份一个到0位置
        if seq%100==0:
            print('lopo:'+str(seq))
        return
    
    # 3. 将数据存储到数据库中
    def imu_call(self, msg):
        # 存储的数据包括通用：header:seq  stamp: secs  nsecs
        # 专有：四元素：orientation:x y z w; 角速度：angular_velocity：x y z; 线性加速度linear_acceleration: x y z
        # 显示 self.uav_name:imu:seq 
        dat = msg
        seq = dat.header.seq
        stamp_secs = dat.header.stamp.secs
        stamp_nsecs = dat.header.stamp.nsecs
        orientation = dat.orientation
        angular_velocity = dat.angular_velocity
        linear_acceleration = dat.linear_acceleration
        offset = 100000
        res_dat = {
            'seq':      seq,
            'sec':      stamp_secs,
            'ns':       stamp_nsecs,
            'ox':      int(orientation.x*offset),
            'oy':      int(orientation.y*offset),
            'oz':      int(orientation.z*offset),
            'ow':      int(orientation.w*offset),
            'ax':      int(angular_velocity.x*offset),
            'ay':      int(angular_velocity.y*offset),
            'az':      int(angular_velocity.z*offset),
            'lx':      int(linear_acceleration.x*offset),
            'ly':      int(linear_acceleration.y*offset),
            'lz':      int(linear_acceleration.z*offset),
        }       

        self.red_c.hmset(self.uav_id+':imu:'+str(seq), res_dat)
        if self.ttl_time>0:
            self.red_c.expire(self.uav_id+':imu:'+str(seq), self.ttl_time)
        self.red_c.hmset(self.uav_id+':imu:'+str(0), res_dat)          # 备份一个到0位置
        if seq%100==0:
            print('imu:'+str(seq))
        return


if __name__ == "__main__":
    uav_name = sys.argv[1]
    t = redis_data_save('0.0.0.0', uav_name=uav_name, ttl_time=600)
    r = rospy.Rate(10) # 10hz
    while not rospy.is_shutdown():
        r.sleep()

    


