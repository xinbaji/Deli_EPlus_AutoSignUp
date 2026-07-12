from tkinter import N
import uiautomator2 as u2
from uiautomator2.exceptions import ConnectError, AdbShellError, LaunchUiAutomationError,XPathElementNotFoundError
from adbutils.errors import AdbError
from Setting import Setting
from Log import Log
from time import time, sleep
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
            
    def start_app(self, package_name, timeout=120):
        
        start_time = time()
        attempt = 0
        # 常见启动失败关键字，出现任一则视为启动失败
        _FAIL_KEYWORDS = [
            "error", "failed", "unable", "cannot", "not found",
            "shell output invalid", "exception", "timeout",
            "refused", "denied", "killed",
        ]
        while True:
            attempt += 1
            elapsed = time() - start_time
            if elapsed > timeout:
                self.log.error(f"启动应用超时（{timeout}秒），已尝试 {attempt} 次")
                raise TimeoutError(f"启动应用超时：{package_name}")

            try:
                # 使用 uiautomator2 内置方式启动（内部通过 shell 执行 am start）
                output = self.device.app_start(package_name)
                # 检查返回输出中是否包含失败关键字
                output_str = str(output or "").lower()
                fail_reason = None
                for kw in _FAIL_KEYWORDS:
                    if kw in output_str:
                        fail_reason = kw
                        break

                if fail_reason:
                    self.log.warning(
                        f"app_start 输出包含失败关键字 '{fail_reason}'（第 {attempt} 次尝试），"
                        f"继续重试..."
                    )
                else:
                    self.log.info(f"启动应用成功: {package_name}（第 {attempt} 次尝试）")
                    return
            except Exception as e:
                err_str = str(e).lower()
                self.log.warning(
                    f"启动应用异常（第 {attempt} 次尝试）: {err_str}，继续重试..."
                )

            # 等待 2 秒后重试
            sleep(2)
    
    @only_chained_calls
    def click(self):
        try:
            self.temp_element.click()
        except XPathElementNotFoundError:
            pass

    @only_chained_calls
    def send_keys(self, string: str):
        """发送文本到设备"""
        sleep(0.1)
        for i in range(0, 14, 1):  # 循环发送删除键
            self.device.press('del')
        self.device.send_keys(string, clear=True)
        
   
    def start_emulator(self):
        """启动模拟器"""
        Thread(target=subprocess.run,args=([self.emulator_exe,"-v",Setting.emulator_num],)).start() # 启动模拟器进程
        self.connect()
    
    def set_vitual_location(self, latitude: float=None, longitude: float=None):
        """设置模拟器的虚拟位置"""
        if latitude is None:
            latitude = Setting.location.get("latitude", 111)
        if longitude is None:
            longitude = Setting.location.get("longitude", 111)

        command = [
            self.manager_exe, "control", "-v", str(Setting.emulator_num),
            "tool", "location", "-lon", str(longitude), "-lat", str(latitude)
        ]
        self.log.info(f"执行定位命令: {' '.join(command)}")

        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=15)
        except subprocess.TimeoutExpired:
            self.log.error("设置虚拟位置超时")
            raise RuntimeError("设置虚拟位置超时，请检查 MuMuManager.exe 是否可正常执行")

        output = (result.stdout or "") + (result.stderr or "")
        if '"errcode": 0' in output or '"errcode":0' in output:
            self.log.info(f"设置位置成功: 纬度 {latitude}, 经度 {longitude}")
        else:
            err_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
            if not err_msg:
                err_msg = f"返回码 {result.returncode}，输出为空"
            self.log.error(f"设置虚拟位置失败: {err_msg}")
            raise RuntimeError(f"设置虚拟位置失败: {err_msg}")
        
    def wait(self,xpath,timeout=5):
        """等待元素出现"""
        try:
            self.device.xpath(xpath).wait(timeout=timeout)
            
        except Exception as e:
            self.log.error(f"等待元素失败: {str(e)}")
            raise
        else:
            self.log.info(f"元素出现: {xpath}")
            self.temp_element = self.device.xpath(xpath)
            return self
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