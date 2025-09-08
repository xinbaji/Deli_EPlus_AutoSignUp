from Controller import Controller
from Config import Config
from Log import Log

class Deli:
    def __init__(self) -> None:
        self.config = Config()
        self.controller = Controller()
        self.log = Log("deli").logger

        self.program_path = self.config.get_value('Program', 'path', default=None)
        self.fake_location_package_name = "com.lerist.fakelocation"
        self.deli_package_name = "com.delicloud.app.smartoffice"

        self.click_pos = self.config.get_value("Position")
        self.init_fake_location()

        for user in self.config.get_userlist():
            self.login(user["username"], user["password"])

        self.log.info("签到完成")




    def init_fake_location(self):
        self.controller.start_app(self.fake_location_package_name)

        def handle_ad_on():
            self.log.info("出现广告，点击不再显示")
            self.controller.click(*self.click_pos["不再显示"])

        def handle_start_emulate():
            self.log.info("点击启动模拟...")
            self.controller.click(*self.click_pos["启动模拟"])

        def handle_stop_emulate():
            self.log.info("Fake Location启动完成...")
            handlers["停止执行"] = None  # 动态添加停止模拟键

        def handle_auto_update():
            self.log.info("暂不更新")
            self.controller.click(*self.click_pos["暂不更新"])


        handlers = {
            "启动模拟": handle_start_emulate,
            "暂不更新": handle_auto_update,
            "不再显示": handle_ad_on,
            "停止模拟": handle_stop_emulate
        }

        while True:
            self.controller.wait(handlers).wait(0.5)
            if "停止执行" in handlers:
                break
    def login(self, username, password):
        """
        登录德力E+并执行签到操作
        
        Args:
            username: 用户名/手机号
            password: 密码
        """
        self.log.info(f"开始执行签到: username={username}, password={'*****' if password else None}")
        if not username or not password:
            error_msg = "用户名或密码不能为空"
            self.log.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            def handle_in_sign_area():
                self.log.info("已在打卡范围内")
                try:
                    self.controller.click(*self.click_pos["打卡"])
                    self.log.info("点击打卡按钮")
                    
                    def handle_sign_success():
                        self.log.info("打卡成功...")
                        try:
                            self.controller.click(*self.click_pos["返回"])
                            self.log.info("点击返回按钮")
                        except Exception as e:
                            self.log.error(f"点击返回按钮失败: {str(e)}")
                            raise
    
                    self.controller.wait(
                        {"打卡成功": handle_sign_success, "签退成功": handle_sign_success, "签到成功": handle_sign_success},
                        )
                except Exception as e:
                    self.log.error(f"处理打卡范围内状态失败: {str(e)}")
                    raise
    
            def handle_not_in_sign_area():
                self.log.info("不在打卡位置，尝试刷新")
                try:
                    self.controller.click(*self.click_pos['刷新'])
                    self.log.info("点击刷新按钮")
                except Exception as e:
                    self.log.error(f"点击刷新按钮失败: {str(e)}")
                    raise
    
            def handle_sign_invaild_confirm():
                self.log.info("检测到登录失效确认对话框")
                try:
                    self.controller.click(*self.click_pos["登录失效确定"])
                    self.log.info("点击登录失效确定按钮")
                except Exception as e:
                    self.log.error(f"点击登录失效确定按钮失败: {str(e)}")
                    raise

                handle_login()
                handle_login_success()
            def handle_login_success():
                    # 等待智能考勤
                self.log.info("等待智能考勤页面...")
                self.controller.wait("智能考勤").wait(2).click(*self.click_pos["智能考勤"])
                self.log.info("登录成功，进入智能考勤页面")
                handlers["停止执行"] = None
            def handle_login():
                self.log.info("检测到登录页面，准备登录")
                try:
                    # 输入用户名
                    self.log.info("准备输入用户手机号...")
                    self.controller.click(*self.click_pos["用户名"])
                    self.log.info("点击用户名输入框")
                    self.controller.clear_input()
                    self.log.info("清除用户名输入框")
                    
                    self.controller.send_keys(username)
                    self.log.info("输入用户名完成")
    
                    # 输入密码
                    self.log.info("准备输入密码...")
                    self.controller.click(*self.click_pos["密码"])
                    self.log.info("点击密码输入框")
                    self.controller.clear_input()
                    self.log.info("清除密码输入框")
                    
                    self.controller.send_keys(password)
                    self.log.info("输入密码完成")
    
                    # 点击登录
                    self.log.info("准备点击登录按钮...")
                    self.controller.click(*self.click_pos["登录"])
                    self.log.info("点击登录按钮完成")
                    
                    # 等待并点击同意并继续
                    self.log.info("等待同意并继续按钮...")
                    self.controller.wait("同意并继续").wait(1).click(*self.click_pos["同意并继续"])
                    self.log.info("点击同意并继续按钮完成")
                    handle_login_success()
                except Exception as e:
                    self.log.error(f"登录过程中发生错误: {str(e)}")
                    raise

            def handle_skip():
                self.controller.get_text_location("跳过").click()
                self.controller.wait({"智能考勤":handle_login_success,"登录":handle_login,"确定":handle_sign_invaild_confirm})


    
            # 启动应用
            self.log.info(f"启动应用: {self.deli_package_name}")
            self.controller.start_app(self.deli_package_name)
            self.log.info("应用启动成功")

            # 等待并点击智能考勤
            handlers={"账号已失效":handle_sign_invaild_confirm,"智能考勤":handle_login_success,"登录":handle_login,"跳过":handle_skip}
            while True:
                self.controller.wait(handlers)
                if "停止执行" in handlers:
                    break

            
            # 等待多种可能的状态
            self.log.info("等待打卡状态...")
            self.controller.wait({
                "已在打卡范围": handle_in_sign_area, 
                "不在打卡位置": handle_not_in_sign_area,
                "确定": handle_sign_invaild_confirm, 
                "登录": handle_login
            })
            self.log.info("打卡操作完成")
    
            # 退出账号
            self.log.info("准备退出账号...")
            self.controller.wait("我的").wait(1).click(*self.click_pos["我的"])
            self.log.info("点击我的按钮")
            self.controller.wait("设置").wait(2).click(*self.click_pos["设置"])
            self.log.info("点击设置按钮")
            self.controller.wait(2).swipe(600, 1600, 900, 500)
            self.log.info("向上滑动屏幕")
            self.controller.wait("退出登录").wait(2).click(*self.click_pos["退出登录"])
            self.log.info("点击退出登录按钮")
            
            self.controller.wait("确定").wait(2).click(*self.click_pos["确定"])
            self.log.info("点击确定按钮，退出登录完成")
            
            return True
        except Exception as e:
            self.log.error(f"登录或签到过程中发生错误: {str(e)}", exc_info=True)
            raise




if __name__ == "__main__":
    Deli()

