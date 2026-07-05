# Deli_EPlus_AutoSignup 

## 一、使用方法
### 1. 下载Mumu模拟器
* 修改模拟器设置：
  * 性能设置 -> 选择高性能
### 2.安装得力e+
### 3.配置运行环境
*  下载Python 推荐3.14.2版本
*  下载源码
*  运行CMD 目录为源码根目录
*  复制命令到命令行中运行：

        pip install -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple -r requirements.txt
### 4.填写Setting.py
    serial = "127.0.0.1:16384" #ADB连接的模拟器序列号
    emulator_path = "" #MuMu模拟器安装路径 例：C:\\Program Files\\NetEase\\MuMu\\nx_main
    emulator_num="0" #模拟器编号
    location={"latitude": 111, "longitude": 111} #模拟器虚拟位置，纬度和经度
    users={
        "XXX":"XXX",
        }  #“你的账号”：“你的密码”,
  
可以在users添加多个账号签到
### 5.运行deliSignup.py
  enjoy！
