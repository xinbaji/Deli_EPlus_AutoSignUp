from emulator.mumu import Mumu
from Setting import Setting
from Log import Log
from time import time, sleep
import threading


class Deli:
    """得力 E+ 自动签到主类，支持在子线程中运行"""

    def __init__(self) -> None:
        self.log = Log("deli").logger
        self.debugmode = True
        self.deli_package_name = "com.delicloud.app.smartoffice"
        self.check_login_invaild_done = False
        self._running = False
        self._stop_flag = False
        self.emulator = None

    def stop(self):
        """请求停止签到流程"""
        self._stop_flag = True
        self.log.info("收到停止请求")

    def _check_stop(self):
        """检查是否被请求停止"""
        if self._stop_flag:
            self.log.info("用户中断签到流程")
            raise InterruptedError("签到已由用户中断")

    def select_emulator(self):
        if "MuMu" in Setting.emulator_path:
            return Mumu
        else:
            self.log.error("未检测到 MuMu 模拟器路径，请在设置中配置")
            raise ValueError("未配置 MuMu 模拟器路径")

    def check_login_invaild(self):
        if not self.check_login_invaild_done and self.emulator.wait(
            "//android.widget.TextView[@text='确定']", timeout=0.1
        ).exists():
            self.emulator.wait("//android.widget.TextView[@text='确定']", timeout=0.1).click()
            self.check_login_invaild_done = True

    def login(self, username, password):
        self._check_stop()

        self.emulator.wait(
            "//android.widget.EditText[@resource-id='com.delicloud.app.smartoffice:id/et_phone']"
        ).click()
        self.emulator.wait(
            "//android.widget.EditText[@resource-id='com.delicloud.app.smartoffice:id/et_phone']"
        ).send_keys(username)
        self.emulator.wait("//android.widget.EditText[@resource-id='com.delicloud.app.smartoffice:id/et_password']").click()
        self.emulator.wait("//android.widget.EditText[@resource-id='com.delicloud.app.smartoffice:id/et_password']").send_keys(password)
        self.emulator.wait("//android.widget.TextView[@text='登录']").click()
        self.emulator.set_vitual_location()
        self.emulator.wait("//android.widget.TextView[@text='同意并继续']").click()
        self.emulator.wait("//android.widget.TextView[@text='智能考勤']").click()
        
        start_time = time()
        flag_success = False
        while True:
            self._check_stop()
            if time() - start_time > 90:
                self.log.error("签到超时，请检查模拟器定位经纬度")
                raise TimeoutError("签到超时")
            if self.emulator.wait(
                "//android.widget.TextView[@text='已在打卡范围内']", timeout=0.3
            ).exists():
                if not self.debugmode:
                    self.emulator.wait(
                        "//android.widget.TextView[@text='打卡']", timeout=0.3
                    ).click()
                    while not flag_success:
                        self._check_stop()
                        for i in ['打卡成功', '签到成功', '签退成功', '迟到', '早退']:
                            if self.emulator.wait(
                                "//android.widget.TextView[@text='" + i + "']", timeout=0.1
                            ).exists():
                                self.emulator.wait(
                                    "//android.widget.ImageView[@resource-id='com.delicloud.app.smartoffice:id/iv_close']",
                                    timeout=0.3,
                                ).click()
                                flag_success = True
                            self.log.info(f"签到结果: {i}")
                            break
                break
            elif self.emulator.wait(
                "//android.widget.TextView[@text='不在打卡范围内']", timeout=0.3
            ).exists():
                self.emulator.wait(
                    "//android.widget.TextView[@text='刷新']", timeout=0.1
                ).click()

        self._check_stop()
        self.emulator.wait("//android.widget.TextView[@text='我的']").click()
        self.emulator.wait("//android.widget.TextView[@text='设置']").click()
        self.emulator.wait("//android.widget.TextView[@text='退出登录']").click()
        self.emulator.wait("//android.widget.TextView[@text='确定']").click()

    def run(self) -> bool:
        """
        执行完整签到流程，返回 True 表示成功，False 表示失败/中断
        """
        self._running = True
        self._stop_flag = False
        try:
            # 重新加载配置
            Setting.reload()

            try:
                self.emulator = self.select_emulator()()
            except (TypeError, ValueError) as e:
                self.log.error(f"初始化模拟器失败: {str(e)}")
                return False

            self._check_stop()
            self.emulator.start_emulator()
            self.emulator.start_app(self.deli_package_name)

            while True:
                self._check_stop()
                if self.emulator.wait(
                    "//android.widget.TextView[@text='跳过']", timeout=0.5
                ).exists():
                    self.emulator.wait(
                        "//android.widget.TextView[@text='跳过']", timeout=0.5
                    ).click()
                    self.check_login_invaild()
                if self.emulator.wait(
                    "//android.widget.TextView[@text='我的']", timeout=0.3
                ).exists():
                    self.check_login_invaild()
                    self.emulator.wait("//android.widget.TextView[@text='我的']").click()
                    self.check_login_invaild()
                    self.emulator.wait("//android.widget.TextView[@text='设置']").click()
                    self.check_login_invaild()
                    self.emulator.wait("//android.widget.TextView[@text='退出登录']").click()
                    self.emulator.wait("//android.widget.TextView[@text='确定']").click()
                if self.emulator.wait(
                    "//android.widget.TextView[@text='登录']", timeout=0.3
                ).exists():
                    break

            users = Setting.users
            if not users:
                self.log.warning("没有配置任何用户，请在设置中添加账号")
                return False

            for user in users.items():
                self._check_stop()
                self.log.info(f"正在签到: {user[0]}")
                self.login(user[0], user[1])

            self.log.info("所有用户签到完成")
            return True

        except InterruptedError:
            self.log.info("签到流程已中断")
            return False
        except Exception as e:
            self.log.error(f"签到流程异常: {str(e)}")
            return False
        finally:
            self._running = False


def run_signup():
    """供 GUI 调用的入口函数，在子线程中执行"""
    d = Deli()
    return d.run()


if __name__ == "__main__":
    # 命令行直接运行时执行签到
    d = Deli()
    d.run()
