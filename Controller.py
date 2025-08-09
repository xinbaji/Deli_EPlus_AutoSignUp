import os
from io import BytesIO
from typing import Optional, Tuple, Dict, Callable, Union, overload  # 导入类型提示相关模块
import time  # 导入时间模块用于等待操作
from subprocess import Popen  # 导入子进程模块用于启动模拟器
import uiautomator2 as u2  # 导入Android设备控制库
from uiautomator2 import Device, ConnectError  # 导入设备类和连接错误类
from PIL import Image  # 导入图像处理库
from Config import Config  # 导入自定义配置模块
from Log import Log  # 导入自定义日志模块
from onnxocr.onnx_paddleocr import ONNXPaddleOcr
from numpy import ndarray  # 导入NumPy数组类型
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
        self.serial: str = self.config.get_value('Emulator', 'serial')  # 设备序列号
        self.launch_with_windows: bool = self.config.get_value('Setting', 'launch_with_windows')
        self.ocr = ONNXPaddleOcr(use_angle_cls=True, use_gpu=False).ocr  # 初始化OCR识别器
        self.log= Log("Controller","d").logger # 初始化日志记录器

        self.device: Device = self.connect()  # 连接设备


    def get_text(self,
                img: Optional[ndarray] = None,
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
        img = img or self.screenshot()  # 如果没有提供图像则截取屏幕
        if not isinstance(img, ndarray):  # 检查图像类型
            self.log.error("Error: img is not a ndarray object")
            raise TypeError("Error: img is not a ndarray object")

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
        self.text_location=()
        img =self.screenshot()  # 如果没有提供图像则截取屏幕
        if not isinstance(img, ndarray):  # 检查图像类型
            self.log.error("Error: img is not a ndarray object")
            raise TypeError("Error: img is not a ndarray object")
        result = self.ocr(img)
        if isinstance(result, list) and len(result) > 0:
            for text in result[0]:
                if target in text[1][0]:
                    x1=text[0][0][0][0]
                    x2=text[0][0][2][0]
                    y1=text[0][0][0][1]
                    y2=text[0][0][2][1]
                    text_location=(x1,y1,x2,y2)
                    self.temp_identify_area = text_location

                    return self
        else:
            return None




    def connect(self) -> Device | None:
        """
        连接到设备

        返回:
            已连接的设备实例

        异常:
            ConnectError: 连接失败时抛出
        """
        while True:  # 持续尝试连接直到成功
            try:
                device = u2.connect(serial=self.serial)  # 尝试连接设备
                self.log.info("Connect to device successfully.")
                return device  # 返回连接成功的设备实例
            except ConnectError:
                continue  # 连接失败则继续尝试
    @overload
    def wait(self,target:int): ...
    @overload  # 方法重载装饰器
    def wait(self, target: str, identify_area: Optional[Tuple[float, float, float, float]] = None,
             timeout: int = 30) -> 'Controller':
        ...

    @overload  # 方法重载装饰器
    def wait(self, targets: Dict[str, Callable], identify_area: Optional[Tuple[float, float, float, float]] = None,
             timeout: int = 30) -> 'Controller':
        ...

    def wait(self,
             target_or_targets: Union[int, str, Dict[str, Callable]],
             identify_area: Optional[Tuple[float, float, float, float]] = None,
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
        try:
            # 记录等待开始
            if isinstance(target_or_targets, int):
                time.sleep(target_or_targets)
                return self
            elif isinstance(target_or_targets, dict):
                targets_str = ", ".join(target_or_targets.keys())
                self.log.info(f"等待目标文本: {targets_str}, 超时时间: {timeout}秒")
            else:
                self.log.info(f"等待目标文本: {target_or_targets}, 超时时间: {timeout}秒")
            
            if identify_area:
                self.log.debug(f"识别区域: {identify_area}")
                
            start_time = time.time()  # 记录开始时间
            attempt_count = 0  # 尝试次数
            
            while time.time() - start_time < timeout:  # 在超时时间内循环
                attempt_count += 1
                try:
                    text = self.get_text(identify_area=identify_area) # 获取识别区域的文本
                    self.log.debug(f"尝试{attempt_count}次, 识别文本: {text}")
                    elapsed = time.time() - start_time
                    
                    if attempt_count % 4 == 0:  # 每4次尝试记录一次日志，避免日志过多
                        self.log.debug(f"第{attempt_count}次尝试, 已用时{elapsed:.1f}秒, 识别文本: {text}")
    
                    # 处理不同类型的target_or_targets参数
                    if isinstance(target_or_targets, dict):  # 如果是字典类型
                        for target, callback in target_or_targets.items():
                            if target in text:  # 如果找到目标文本
                                self.log.info(f"找到目标文本: {target}, 用时{elapsed:.1f}秒")
                                self.temp_identify_area = identify_area  # 存储识别区域
                                try:
                                    callback()  # 执行回调函数
                                    self.log.debug(f"目标 {target} 的回调函数执行成功")
                                except Exception as e:
                                    self.log.error(f"执行回调函数时出错: {str(e)}", exc_info=True)
                                    raise
                                return self  # 返回自身以支持链式调用
                    elif isinstance(target_or_targets, str):  # 如果是字符串类型
                        if target_or_targets in text:  # 如果找到目标文本
                            self.log.info(f"找到目标文本: {target_or_targets}, 用时{elapsed:.1f}秒")
                            self.temp_identify_area = identify_area  # 存储识别区域
                            return self  # 返回自身以支持链式调用
                except Exception as e:
                    self.log.error(f"获取文本时出错: {str(e)}", exc_info=True)
                    # 继续尝试，不中断循环
    
                time.sleep(0.5)  # 避免高频轮询
    
            # 超时处理
            self.log.warning(f"等待超时: 目标文本未在{timeout}秒内找到")
            raise TimeoutError(f"Target not found within {timeout} seconds")  # 超时抛出异常
            
        except Exception as e:
            if not isinstance(e, TimeoutError):
                self.log.error(f"wait方法发生异常: {str(e)}", exc_info=True)
            raise

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

    def send_keys(self, string: str):
        """发送文本到设备"""
        self.device.send_keys(string, clear=True)  # 发送文本并清空原有内容

    def screenshot(self):
        """截取设备屏幕"""
        return self.device.screenshot(format='opencv')  # 返回屏幕截图

    def start_app(self, app_package_name: str):
        """启动指定应用"""
        self.device.app_start(app_package_name, wait=True)  # 启动应用并等待

    def clear_input(self):
        """清空输入框"""
        for i in range(0, 14, 1):  # 循环发送删除键
            self.device.press('del')

    def launch_emulator(self):
        """启动模拟器"""
        Popen(self.emulator_path)  # 启动模拟器进程
        self.connect()  # 连接设备

if __name__ == "__main__":
    controller = Controller().get_text_location("跳过")