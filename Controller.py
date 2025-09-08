import subprocess
from typing import Optional, Tuple, Dict, Callable, Union, overload  # 导入类型提示相关模块
import time  # 导入时间模块用于等待操作

import adbutils
import uiautomator2 as u2  # 导入Android设备控制库
from uiautomator2 import Device, ConnectError
from uiautomator2.exceptions import LaunchUiAutomationError,AdbShellError
from adbutils.errors import AdbError
from Config import Config  # 导入自定义配置模块
from Log import Log  # 导入自定义日志模块
from onnxocr.onnx_paddleocr import ONNXPaddleOcr
from numpy import ndarray  # 导入NumPy数组类型
from threading import Thread
class Controller:
    def __init__(self) -> None:
        """
        初始化控制器，连接设备并加载配置

        属性:
            temp_identify_area: 临时存储的识别区域坐标
            config: 配置管理器实例
            emulator_path: 模拟器可执行文件路径
            serial: 设备序列号
            launch_with_windows: 是否随Windows启动
            ocr: OCR识别器实例
            log: 日志记录器
            device: 连接的设备实例
        """

        self.temp_identify_area: Optional[Tuple[float, float, float, float]] = None  # 临时存储识别区域
        self.config: Config = Config()  # 初始化配置管理器

        # 从配置文件中获取相关设置
        self.emulator_path: str = self.config.get_value('Emulator', 'path')  # 模拟器路径
        self.serial: str = self.config.get_value('Emulator', 'serial')
        # 设备序列号
        self.ocr = ONNXPaddleOcr(use_angle_cls=True, use_gpu=False).ocr  # 初始化OCR识别器
        self.log= Log("Controller","d").logger # 初始化日志记录器
        self.click_pos:dict=dict(self.config.get_value("Position"))
        self.text_location = ()
        self.launch_emulator()
        self.device: Device
    def reconnect(self,func):
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs) # 返回连接成功的设备实例
            except ConnectError:
                self.connect()  # 连接失败则继续尝试
            except AdbShellError:
                self.connect()
            except AdbError as e:
                if "offline" in str(e):
                    self.connect()
            except LaunchUiAutomationError:
                self.connect()
        return wrapper
    def get_screenshot(self):
        return self.screenshot()
    def get_text(self,
                img: ndarray,
                identify_area: Optional[Tuple[float, float, float, float]] = None
               ) -> str:
        """
        从图像或屏幕截图中识别文本

        参数:
            img: 要识别的PIL图像，如果为None则自动截图
            identify_area: 识别区域坐标 (x1, y1, x2, y2)

        返回:
            识别到的文本字符串

        异常:
            TypeError: 当img参数不是PIL.Image.Image类型时抛出
        """
        textlist=""
        if identify_area:
            x1,y1,x2,y2=identify_area# 如果有指定识别区域则裁剪图像
            img = img[int(y1):int(y2), int(x1):int(x2)]

        result = self.ocr(img)
        if isinstance(result, list) and len(result) > 0:
            for text in result[0]:
                textlist+=str(text[1][0]) # 使用OCR识别文本
         # 使用OCR识别文本
        return textlist

    def get_text_location(self,target:str):
        """
        从图像或屏幕截图中识别文本
        """

        img =self.screenshot()  # 如果没有提供图像则截取屏幕
        if not isinstance(img, ndarray):  # 检查图像类型
            self.log.error("Error: img is not a ndarray object")
            raise TypeError("Error: img is not a ndarray object")
        result = self.ocr(img)
        self.log.debug("target: "+target+"  result: "+str(result))
        if isinstance(result, list) and len(result) > 0:
            try:
                for text in result[0]:
                    if target in str(text[1][0]):
                        x1=text[0][0][0]
                        x2=text[0][2][0]
                        y1=text[0][0][1]
                        y2=text[0][2][1]
                        text_location=(x1,y1,x2,y2)
                        self.temp_identify_area = text_location
            except TypeError as e:
                if "float" in str(e):
                    self.log.error(e)


            return self
        else:
            return None




    def connect(self,timeout=60) -> Device | None:
        """
        连接到设备

        返回:
            已连接的设备实例

        异常:
            ConnectError: 连接失败时抛出
        """


        start_time=time.time()
        self.log.info("Connecting")
        while True:  # 持续尝试连接直到成功
            if time.time()-start_time >timeout:
                self.log.error("连接模拟器超时，请检查serial号或先启动模拟器后启动脚本")
                raise TimeoutError
            try:
                device = u2.connect(serial=self.serial)  # 尝试连接设备
                self.log.info("Connect to device successfully.")
                self.device = device
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

    @overload
    def wait(self,target:int):...

    @overload
    def wait(self,target:float): ...
    @overload
    def wait(self,target:str):...

    @overload
    def wait(self, targets: Dict[str, Callable]):
        ...

    def wait(self,
             target_or_targets: Union[int,float, str, Dict[str, Callable]],
             timeout: int = 30) -> 'Controller':
        """
        等待直到检测到目标文本或任一目标文本

        参数:
            target_or_targets: 单个目标字符串或目标字典 {目标字符串: 回调函数}
            identify_area: 识别区域坐标 (x1, y1, x2, y2)
            timeout: 超时时间(秒)

        返回:
            self (支持链式调用)

        异常:
            TimeoutError: 超时未找到目标
        """
        if isinstance(target_or_targets, int):
            time.sleep(target_or_targets)
            return self
        elif isinstance(target_or_targets, float):
            time.sleep(target_or_targets)
            return self
        elif isinstance(target_or_targets, str):
            target_or_targets = {target_or_targets: "str"}

        else:
            targets_str = ", ".join(target_or_targets.keys())
            self.log.info(f"等待目标文本: {targets_str}, 超时时间: {timeout}秒")
        start_time = time.time()  # 记录开始时间
        attempt_count = 0  # 尝试次数
            
        while time.time() - start_time < timeout:  # 在超时时间内循环
            attempt_count += 1
            try:
                img = self.get_screenshot()# 如果是字典类型
                for target, callback in target_or_targets.items():
                    if target not in self.click_pos.keys():
                        text = self.get_text(img)
                    else:
                        text=self.get_text(img,identify_area=self.click_pos[target])

                    elapsed = time.time() - start_time

                    if attempt_count % 5 == 0:  # 每4次尝试记录一次日志，避免日志过多
                        self.log.debug(f"第{attempt_count}次尝试, 已用时{elapsed:.1f}秒, 识别文本: {text}")
                    if target in text:  # 如果找到目标文本
                        self.log.info(f"找到目标文本: {target}, 用时{elapsed:.1f}秒")
                        try:
                            if not isinstance(callback,str):
                                callback()  # 执行回调函数
                            self.log.debug(f"目标 {target} 的回调函数执行成功")
                        except Exception as e:
                            self.log.error(f"执行回调函数时出错: {str(e)}", exc_info=True)
                            raise
                        return self  # 返回自身以支持链式调用

            except Exception as e:
                self.log.error(f"获取文本时出错: {str(e)}", exc_info=True)
                # 继续尝试，不中断循环

            # 超时处理
        self.log.error(f"等待超时: 目标文本未在{timeout}秒内找到")
        raise TimeoutError # 超时抛出异常



    @overload  # 方法重载装饰器
    def click(self) -> None:
        ...

    @overload  # 方法重载装饰器
    def click(self, x1: int, y1: int, x2: int, y2: int) -> None:
        ...

    @overload  # 方法重载装饰器
    def click(self, x: int, y: int) -> None:
        ...

    def click(self, *args: Union[int, float]) -> None:
        """
        执行点击操作

        参数:
            *args: 支持以下格式:
                - x, y (两个参数)
                - x1, y1, x2, y2 (四个参数，自动计算中心点)
                - 无参数 (使用temp_identify_area)

        异常:
            ValueError: 当参数不匹配任何支持的格式时抛出
        """
        if len(args) == 2:  # 如果是x,y坐标
            self.device.click(int(args[0]), int(args[1]))  # 直接点击坐标点
        elif len(args) == 4:  # 如果是矩形区域
            x = int((args[0] + args[2]) / 2)  # 计算中心点x坐标
            y = int((args[1] + args[3]) / 2)  # 计算中心点y坐标
            self.device.click(x, y)  # 点击中心点
        elif not args and hasattr(self, 'temp_identify_area'):  # 如果没有参数但有临时区域
            if isinstance(self.temp_identify_area, tuple):  # 检查临时区域类型
                self.click(*self.temp_identify_area)  # 递归调用click方法
            self.temp_identify_area = None  # 清空临时区域
        else:
            raise ValueError("不支持的参数组合")  # 参数不匹配抛出异常
        self.wait(0.5)
    def swipe(self,
              x1: Union[int, float],
              y1: Union[int, float],
              x2: Union[int, float],
              y2: Union[int, float]
             ) -> None:
        """
        执行滑动操作

        参数:
            x1: 起始点x坐标
            y1: 起始点y坐标
            x2: 结束点x坐标
            y2: 结束点y坐标
        """

        self.device.drag(int(x1), int(y1), int(x2), int(y2),duration=0.05)# 执行滑动操作
        self.wait(0.1)
    def send_keys(self, string: str):
        """发送文本到设备"""
        self.device.send_keys(string, clear=True)  # 发送文本并清空原有内容

    def screenshot(self):
        """截取设备屏幕"""
        return self.device.screenshot(format='opencv')  # 返回屏幕截图


    def start_app(self, app_package_name: str):
        """启动指定应用"""
        self.device.app_start(app_package_name)  # 启动应用并等待

    def clear_input(self):
        """清空输入框"""
        for i in range(0, 14, 1):  # 循环发送删除键
            self.device.press('del')

    def launch_emulator(self):
        """启动模拟器"""
        launch_timeout=self.config.get_value("Emulator","launch_timeout")
        launch_args=self.config.get_value("Emulator","launch_args")
        launch_emulator_num=self.config.get_value("Emulator","launch_emulator_num")
        Thread(target=subprocess.run,args=([self.emulator_path,launch_args,launch_emulator_num],)).start() # 启动模拟器进程
        self.connect(timeout=launch_timeout)
        self.wait("得力")

if __name__ == "__main__":
    controller = Controller()