class Setting:
    serial = "127.0.0.1:16384" #ADB连接的模拟器序列号
    emulator_path = "" #MuMu模拟器安装路径 例：C:\\Program Files\\NetEase\\MuMu\\nx_main
    emulator_num="0" #模拟器编号
    location={"latitude": 111, "longitude": 111} #模拟器虚拟位置，纬度和经度
    users={
        "XXX":"XXX",
        } #用户账号和密码