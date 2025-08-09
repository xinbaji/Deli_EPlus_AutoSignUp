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
* 
### 5.配置运行环境
*  下载源码
*  运行CMD 目录为源码根目录
*  复制命令到命令行中运行：

        pip install -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple -r requirements.txt

### 6.运行deliSignup.py
* 先运行一次deliSignup.py 目录中会生成一个config.toml 在此文件中更改配置
* 修改serial：即模拟器所在的adb端口 格式如下：
        
        [Emulator]
        serial = "127.0.0.1:16384" #地址与端口号写在双引号内
        path = "C:\\Program Files\\NetEase\\MuMu\\nx_main\\MuMuNxMain.exe -v 0" #为模拟器启动路径 但是这个自动启动模拟器的功能没有写
* 输入需要登录的手机号和密码 信息保存在config.toml中 可以通过修改此文件 添加多个手机号远程签到
* 将下面的代码复制到config.toml中 多个用户就复制多次，格式：
  
      [Account.1234]
      username=XXX
      password=XXX
* enjoy！

OCR文字识别支持：OnnxOCR : https://github.com/jingsongliujing/OnnxOCR/tree/main
