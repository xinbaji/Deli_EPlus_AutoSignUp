import uiautomator2 as u2
from uiautomator2.exceptions import ConnectError, AdbShellError, LaunchUiAutomationError,XPathElementNotFoundError
from adbutils.errors import AdbError
from Setting import Setting
from Log import Log
from time import time
import subprocess
from threading import Thread
def only_chained_calls(func):
    def wrapper(self, *args, **kwargs):
        if self.temp_element is not None:
            result = func(self, *args, **kwargs)
            self.temp_element = None
            return result
        else:
            raise Exception("被处理的元素不存在")

    return wrapper
class Mumu:
    def __init__(self,):
        self.serial = Setting.serial
        self.path=Setting.emulator_path
        self.manager_exe = self.path+"\\MuMuManager.exe"
        self.emulator_exe = self.path+"\\MuMuNxMain.exe"
        self.adb_path = self.path+"\\adb.exe"
        self.log = Log("mumu").logger
        self.timeout = 60
        self.temp_element = None
        self.device = None
        
    
    def connect(self,timeout=60) -> Device | None:
        start_time=time()
        while True:  # 持续尝试连接直到成功
            if time()-start_time >timeout:
                self.log.error("连接模拟器超时，请检查serial号或先启动模拟器后启动脚本")
                raise TimeoutError
            try:
                self.device = u2.connect(serial=self.serial)  # 尝试连接设备
                self.log.info("设备状态：已连接ADB")
                return # 返回连接成功的设备实例
            except ConnectError:
                continue  # 连接失败则继续尝试
            except AdbShellError:
                continue
            except AdbError as e:
                if "offline" in str(e):
                    continue
            except LaunchUiAutomationError:
                continue
            
    def start_app(self, package_name):
        try:
            self.device.app_start(package_name)
            self.log.info(f"启动应用: {package_name}")
        except Exception as e:
            self.log.error(f"启动应用失败: {str(e)}")
            raise
    
    @only_chained_calls
    def click(self):
        try:
            self.temp_element.click()
        except XPathElementNotFoundError:
            pass

    @only_chained_calls
    def send_keys(self, string: str):
        """发送文本到设备"""
        for i in range(0, 14, 1):  # 循环发送删除键
            self.device.press('del')
        self.device.send_keys(string, clear=True)
        
   
    def start_emulator(self):
        """启动模拟器"""
        Thread(target=subprocess.run,args=([self.emulator_exe,"-v",Setting.emulator_num],)).start() # 启动模拟器进程
        self.connect()
    
    def set_vitual_location(self, latitude: float=Setting.location.get("latitude"), longitude: float=Setting.location.get("longitude")):
        """设置模拟器的虚拟位置"""
        
        command = self.manager_exe+" control -v 0 tool location -lon "+str(longitude)+" -lat "+str(latitude)
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if '"errcode": 0,' in result.stdout:
            self.log.info(f"设置位置: 纬度 {latitude}, 经度 {longitude}")
        else:
            self.log.error(f"设置虚拟位置失败: {result.stderr}")
            raise
        
    def wait(self,xpath,timeout=5):
        """等待元素出现"""
        try:
            self.device.xpath(xpath).wait(timeout=timeout)
            self.log.info(f"元素出现: {xpath}")
            self.temp_element = self.device.xpath(xpath)
            return self
        except Exception as e:
            self.log.error(f"等待元素失败: {str(e)}")
            raise
    @only_chained_calls
    def exists(self):
        """检查元素是否存在"""
        try:
            output=str(self.temp_element).replace('#(XPath("',"").replace('"))','')
            exists = self.device.xpath(self.temp_element).exists
            self.log.info(f"检查元素: {output} - {'存在' if exists else '不存在'}")
            return exists
        except Exception as e:
            self.log.error(f"检查元素存在失败: {str(e)}")
            raise