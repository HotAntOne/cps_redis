# cps_redis

#### 介绍
1. 存放cps redis的服务端和客户端的代码，用于云端协同数据库。
2. 其中server运行在运行无人机或者仿真的电脑上，client运行在同局域网的地面站上。无人机端运行之后，会存放多个类型的数据到本地redis数据库中，地点站基于redis通信进行数据备份，同时测试通信增加通信数据。
3. 所有存放在redis中的数据类型均为hashmap，通过hmget进行获取。数据key为(uav_id):(data):(seq)，例如读取1号无人机的实时imu数据，其key为1:iu:0。
4. redis的每份数据会保存在两个地方，一个是seq=0的地方，一个是seq=n的地方，这样通过seq=0就可以获得最新的数据，而获得当前seq后，得到之前的一些数据。

#### 软件架构
1. 包含server端和client端


#### 安装教程

1.  均需要安装redis，ubuntu使用`sudo apt install redis`进行安装
2.  client端如果使用redis_img_show.py进行实时图像显示，则需要额外安装opencv，使用`pip install opencv-python`进行安装
3.  代码运行在python2上，使用python3也可以。

#### 使用说明

1.  server端运行无人机仿真之后，运行server文件夹中的redis_data.py，需要给入参数iris_0等指明当前无人机名称，如`python redis_data.py iris_0`。如果server端运行仿真多个无人机，则多开几个命令窗口进行运行。观察输出，是否有ros、redis和socket的报错。
2.  client端需要在代码中修改ip地址为server端ip，在redis_save_data.py的main函数中修改即可。默认main函数启动了6架无人机，根据需要进行修改即可。同样运行后观察是否有ros、redis和socket的报错。
3.  由于redis的数据存放在内存中，server端默认保存10分钟数据，client端同样保存10分钟数据。地面站client如果需要长期保存数据，可以根据代码备注，修改类中第一行的存放时间。
