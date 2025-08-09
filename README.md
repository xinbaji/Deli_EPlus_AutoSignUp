# Deli_EPlus_AutoSignup 

## 一、使用方法
### 1. 下载任意模拟器
* 修改模拟器设置：
  * 性能设置 -> 分辨率 手机版 1080*1920
  
### 2.安装得力e+与Fake Location
### 3.配置Fake Location
* 先设置好需要定位的位置
* 选择 NOROOT模式

### 4.配置得力e+
*  先自己手动输入手机号密码进行登录
*  登录后点击：我的 -> 设置 -> 关闭首页悬浮挂件
  
### 5.运行deliSignup.py
* 输入需要登录的手机号和密码 信息保存在config.toml中 可以通过修改此文件 添加多个手机号远程签到
  * 格式：
  
        [Account.1234]
        username=XXX
        password=XXX
* enjoy！
