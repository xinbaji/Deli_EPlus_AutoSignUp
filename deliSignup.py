from emulator.mumu import Mumu
from Setting import Setting
from Log import Log
from time import time

class Deli:
    def __init__(self) -> None:
        try:
            self.emulator = self.select_emulator()()
        except TypeError as e:
            self.log.error(f"初始化模拟器失败:先填写Setting.py {str(e)}")
            raise
        self.log = Log("deli").logger
        self.debugmode=False
        self.deli_package_name = "com.delicloud.app.smartoffice"
        
        self.emulator.connect()
        self.emulator.start_app(self.deli_package_name)
        
        while True:
            if self.emulator.wait("//android.widget.TextView[@text='跳过']",timeout=0.3).exists():
                self.emulator.wait("//android.widget.TextView[@text='跳过']",timeout=0.3).click()
            if self.emulator.wait("//android.widget.TextView[@text='我的']",timeout=0.3).exists():
                self.emulator.wait("//android.widget.TextView[@text='我的']").click()
                self.emulator.wait("//android.widget.TextView[@text='设置']").click()
                self.emulator.wait("//android.widget.TextView[@text='退出登录']").click()
                self.emulator.wait("//android.widget.TextView[@text='确定']").click()
            if self.emulator.wait("//android.widget.TextView[@text='登录']",timeout=0.3).exists():
                break
            
        for user in Setting.users.items():
            self.log.info(f"正在签到: {user[0]}")
            self.login(user[0], user[1])

        self.log.info("签到完成")
    def select_emulator(self):
        if "MuMu" in Setting.emulator_path:
            return Mumu
        
    
    def login(self,username,password):
        
        self.emulator.wait("//android.widget.EditText[@resource-id='com.delicloud.app.smartoffice:id/et_phone']").click()
        self.emulator.wait("//android.widget.EditText[@resource-id='com.delicloud.app.smartoffice:id/et_phone']").send_keys(username)
        self.emulator.wait("//android.widget.EditText[@text='输入密码']").click()
        self.emulator.wait("//android.widget.EditText[@text='输入密码']").send_keys(password)
        self.emulator.wait("//android.widget.TextView[@text='登录']").click()
        self.emulator.wait("//android.widget.TextView[@text='同意并继续']").click()
        self.emulator.wait("//android.widget.TextView[@text='智能考勤']").click()
        self.emulator.set_vitual_location()
        start_time=time()
        while True:
            if time()-start_time > 90:
                self.log.error("签到超时，请检查Setting.py中模拟器定位经纬度")
                raise TimeoutError
            if self.emulator.wait("//android.widget.TextView[@text='已在打卡范围内']",timeout=0.3).exists():
                self.emulator.wait("//android.widget.TextView[@text='打卡']",timeout=0.3)
                time.sleep(1)
                self.emulator.device.press("back")
                
                break
            elif self.emulator.wait("//android.widget.TextView[@text='不在打卡范围内']", timeout=0.3).exists():
                self.emulator.wait("//android.widget.TextView[@text='刷新']", timeout=0.1).click()
        
        self.emulator.wait("//android.widget.TextView[@text='我的']").click()
        self.emulator.wait("//android.widget.TextView[@text='设置']").click()
        self.emulator.wait("//android.widget.TextView[@text='退出登录']").click()
        self.emulator.wait("//android.widget.TextView[@text='确定']").click()

Deli()