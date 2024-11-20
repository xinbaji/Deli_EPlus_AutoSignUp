import os
import sys
import json
import ctypes
import logging
import subprocess

from time import sleep, strftime, localtime
from threading import Thread

import cv2
import numpy as np
import uiautomator2 as u2
import matplotlib.pyplot as plt
from paddleocr import PaddleOCR

# 756/1344->1080/1920 1.408/1.408
click_pos = {
    "启动模拟": (71, 780, 147, 56),
    "停止模拟": (71, 780, 147, 56),
    "用户名": (522, 544, 2, 2),
    "密码": (541, 668, 2, 2),
    "登录": (298, 855, 232, 137),
    "同意并继续": (438, 798, 183, 64),
    "刷新": (571, 572, 90, 60),
    "不在打卡位置": (288, 926, 230, 55),
    "已在打卡范围": (288, 926, 230, 55),
    "打卡": (336, 734, 90, 60),
    "我的": (596, 1310, 90, 38),
    "设置": (136, 932, 107, 75),
    "退出登录": (296, 1279, 196, 73),
    "确定": (488, 794, 113, 58),
    "打卡成功": (238, 428, 287, 90),
    "签退成功": (238, 428, 287, 90),
    "签到成功": (238, 428, 287, 90),
    "返回": (54, 109, 2, 2),
    "手机打卡": (47, 565, 175, 81),
}

Log_level = "i"


class Log:
    def __init__(self, log_name, mode: str = "i") -> None:
        log_level = logging.DEBUG if mode == "d" else logging.INFO
        log_file_name = strftime("%Y-%m-%d", localtime())
        if not os.path.exists("./log/" + log_file_name + ".txt"):
            os.makedirs("log", exist_ok=True)
            with open("./log/" + log_file_name + ".txt", "w") as f:
                f.write("*********deli_AutoSignup log_file************\n")
                f.close()
        handler = logging.FileHandler("./log/" + log_file_name + ".txt")
        handler.setLevel(level=logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(funcName)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        console = logging.StreamHandler()
        console.setLevel(log_level)

        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(level=log_level)
        self.logger.addHandler(handler)


class Ocr:
    def __init__(self) -> None:
        global Log_level
        self.ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        self.log = Log("ocr", Log_level)

    def get_string_in_pic(
        self,
        img_file,
        identify_area: tuple,
    ) -> str:
        """判断指定文字是否在指定区域内

        Arguments:
            target_string {str} -- 目标字符串
            identify_area {list} -- 4 int x1,y1,w,h

        Keyword Arguments:
            picpath {str} -- 被识别图像位置 (default: {"./screenshot/screen.png"})

        Returns:
            string -- 识别的文字
        """
        if isinstance(img_file, str):
            img = cv2.imread(img_file)
        elif isinstance(img_file, np.ndarray):
            img = img_file

        x1, y1, w, h = identify_area
        x1 = int(1.408 * x1)
        y1 = int(1.408 * y1)
        h = int(1.408 * h)
        w = int(1.408 * w)
        img = img[y1 : y1 + h, x1 : x1 + w]
        if Log_level == "d" and click_pos["我的"] == identify_area:
            plt.imshow(img), plt.axis("off")
            plt.show()
            sleep(300)
        result_string = self.ocr.ocr(img)
        if isinstance(result_string[0], list):
            result_string = result_string[0][0][1][0]
            return result_string
        else:
            return None


def admin_start(func):
    def wrapper(*awrgs, **kwargs):
        try:
            result = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            result = False
        finally:
            if result:
                em = func(*awrgs, **kwargs)
                sleep(30)
                return em
            else:
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, __file__, None, 1
                )

    return wrapper


class Deli:
    def __init__(self) -> None:
        global Log_level
        self.program_path = os.getcwd().replace("\\", "/") + "/"
        self.screenshot_png_path = self.program_path + "screenshot/screen.png"
        self.install_path = "D:\\Softwares\\leidian\\LDPlayer9\\"
        self.deli_package_name = "com.delicloud.app.smartoffice"
        self.fake_location_package_name = "com.lerist.fakelocation"
        self.serial = "127.0.0.1:5555"
        if not os.path.exists("./screenshot"):
            os.makedirs("screenshot")
        if not os.path.exists("userInfo.json"):
            self.add_userinfo()
        else:
            with open("userInfo.json", "r") as f:
                self.user = json.load(f)
                f.close()
        self.focr = Ocr()
        self.log = Log("deli_main", Log_level)
        subprocess.Popen(self.install_path + "dnconsole.exe launch --index 0")
        self.log.logger.info("等待模拟器完全启动中...")
        self.device = u2.connect(self.serial)
        subprocess.Popen(self.install_path + "adb connect " + self.serial)
        self.log.logger.info("ADB已连接模拟器...")

    def click_text(self, target_string: str):
        x1, y1, w, h = click_pos[target_string]
        click_point = (int((x1 + w / 2) * 1.408), int((y1 + h / 2) * 1.408))
        self.device.click(click_point[0], click_point[1])

    def waiting_for_text_to_appear(self, target_string):
        if isinstance(target_string, list):
            target = target_string
        elif isinstance(target_string, str):
            target = []
            target.append(target_string)
        while True:
            img_file = self.device.screenshot(format="opencv")
            result = self.focr.get_string_in_pic(img_file, click_pos[target[0]])
            if result == None:
                continue
            for i in target:
                if i in result:
                    return True

    def wait_for_text_to_appear_and_click(self, target_string: str):
        while True:
            img_file = self.device.screenshot(format="opencv")
            result = self.focr.get_string_in_pic(img_file, click_pos[target_string])
            if result == None:
                continue
            elif target_string in result:
                self.click_text(target_string)
                break
            else:
                continue

    def start_app(self, package_name: str):
        subprocess.Popen(
            self.install_path
            + "dnconsole.exe "
            + "runapp --index 0 --packagename "
            + package_name
        )

    def send_keys(self, text: str):
        command = "action --index 0 --key call.input --value " + text
        subprocess.Popen(self.install_path + "dnconsole.exe " + command)

    def clear_input(self):
        command = 'adb --index 0 --command "' + "shell input keyevent 67" + '"'
        for i in range(0, 14, 1):
            subprocess.Popen(self.install_path + "dnconsole.exe " + command)

    def swipe(self, x1: int, y1: int, x2: int, y2: int):
        command = (
            'adb --index 0 --command "'
            + "shell input swipe "
            + str(x1)
            + " "
            + str(y1)
            + " "
            + str(x2)
            + " "
            + str(y2)
            + '"'
        )
        subprocess.Popen(self.install_path + "dnconsole.exe " + command)

    def init_fake_location(self):
        self.start_app(self.fake_location_package_name)
        while True:
            img_file = self.device.screenshot(format="opencv")
            result = self.focr.get_string_in_pic(img_file, click_pos["停止模拟"])
            if result == None:
                continue
            self.log.logger.debug(result)
            if result == "停止模拟":
                self.log.logger.info("Fake Location启动完成...")
                break
            elif result == "启动模拟":
                self.click_text("启动模拟")
                self.waiting_for_text_to_appear("停止模拟")
                self.log.logger.info("Fake Location启动完成...")
                break
            else:
                continue

    def login(self, info: list):
        username = info[0]
        password = info[1]
        self.start_app(self.deli_package_name)
        while True:
            img_file = self.device.screenshot(format="opencv")
            result = self.focr.get_string_in_pic(img_file, click_pos["登录"])
            if result == None:
                continue
            self.log.logger.debug(result)
            if "已在打卡范围" in result:
                self.log.logger.info("已在打卡范围内")
                self.click_text("打卡")
                self.waiting_for_text_to_appear(["打卡成功", "签退成功", "签到成功"])
                self.click_text("返回")
                break
            elif "不在打卡位置" in result:
                self.click_text("刷新")

            elif result == "登录":
                self.click_text("用户名")
                self.clear_input()
                sleep(1)
                self.send_keys(username)
                sleep(1)
                self.click_text("密码")
                self.clear_input()
                sleep(1)
                self.send_keys(password)
                sleep(1)
                self.click_text("登录")
                self.wait_for_text_to_appear_and_click("同意并继续")
                self.waiting_for_text_to_appear("手机打卡")
        self.waiting_for_text_to_appear("手机打卡")
        self.click_text("我的")
        self.wait_for_text_to_appear_and_click("设置")
        sleep(1)
        self.swipe(388, 782, 384, 183)
        sleep(1)
        self.wait_for_text_to_appear_and_click("退出登录")
        self.wait_for_text_to_appear_and_click("确定")

    def init_userinfo(self):
        user = {}
        if not os.path.exists("userInfo.json"):
            with open("userInfo.json", "w") as f:
                f.write(json.dumps(user))
                f.close()

    def add_userinfo(self):
        if not os.path.exists("userInfo.json"):
            self.init_userinfo()
        with open("userInfo.json", "r") as f:
            user: dict = json.loads(f.read())
            f.close()
        while True:
            infoname = input("请输入用户名称（按回车键结束#键取消输入）：")
            if "#" in infoname:
                break
            username = input("请输入用户手机号（按回车键结束#键取消输入）：")
            if "#" in username:
                break
            password = input("请输入用户密码（按回车键结束#键取消输入）：")
            if "#" in password:
                break
            temp = {infoname: (username, password)}
            user.update(temp)

        with open("userInfo.json", "w") as f:
            f.write(json.dumps(user))
            f.close()
        self.log.logger.info("用户数据保存成功")

    def get_userinfo(self, infoname) -> list:
        return self.user[infoname]


@admin_start
def main():

    deli = Deli()

    deli.init_fake_location()
    # deli.login(info[用户名称])
    # deli.login(info["陈"])
    # deli.login(info["李"])
    # deli.login(info["王"])


if __name__ == "__main__":
    main()
