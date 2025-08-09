from Controller import Controller
from Config import Config
from Log import Log

class Deli:
    def __init__(self) -> None:
        self.config = Config()
        self.controller = Controller()
        self.log = Log("deli").logger

        self.program_path = self.config.get_value('Program', 'path', default=None)
        self.fake_location_package_name = self.config.get_value('Fake_location', 'package_name')
        self.deli_package_name = self.config.get_value('Deli', 'package_name')

        self.click_pos = {
            "启动模拟": (100, 1100, 300, 1190),
            "停止模拟": (100, 1100, 300, 1190),
            "用户名": (580, 745, 600, 780),
            "密码": (580, 910, 600, 955),
            "登录": (480, 1290, 595, 1350),
            "同意并继续": (630, 1130, 860, 1190),
            "智能考勤": (330, 600, 530, 655),
            "刷新": (830, 975, 920, 1020),
            "不在打卡位置": (425, 1475, 720, 1530),
            "已在打卡范围": (425, 1475, 720, 1530),
            "打卡": (490, 1190, 590, 1255),
            "我的": (860, 1850, 940, 1895),
            "设置": (200, 1325, 300, 1380),
            "退出登录": (425, 1815, 655, 1875),
            "确定": (710, 1125, 815, 1180),
            "打卡成功": (238, 428, 287, 90),
            "签退成功": (238, 428, 287, 90),
            "签到成功": (238, 428, 287, 90),
            "返回": (54, 109, 2, 2),
            "手机打卡": (47, 565, 175, 81),
            "登录失效确定": (183, 763, 2, 2),
        }

        self.init_fake_location()

        for user in self.config.get_userlist():
            self.login(user["username"], user["password"])

        self.log.info("签到完成")




    def init_fake_location(self):
        self.controller.start_app(self.fake_location_package_name)

        def handle_start_emulate():
            self.log.info("点击启动模拟...")
            self.controller.click(*self.click_pos["启动模拟"])

        def handle_stop_emulate():
            self.log.info("Fake Location启动完成...")

        self.controller.wait({"启动模拟": handle_start_emulate, "停止模拟": handle_stop_emulate},
                             self.click_pos["启动模拟"])
        self.controller.wait({ "停止模拟": handle_stop_emulate},
                             self.click_pos["启动模拟"])
    def login(self, username, password):
        """
        登录德力E+并执行签到操作
        
        Args:
            username: 用户名/手机号
            password: 密码
        """
        self.log.info(f"开始执行签到操作: username={username}, password={'*****' if password else None}")
        if not username or not password:
            error_msg = "用户名或密码不能为空"
            self.log.error(error_msg)
            raise ValueError(error_msg)
            
        self.log.info(f"开始为用户 {username} 执行登录和签到操作")
        
        try:
            def handle_in_sign_area():
                self.log.info("已在打卡范围内")
                try:
                    self.controller.wait("打卡", self.click_pos["打卡"]).click()
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
                        self.click_pos["打卡成功"])
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
            def handle_login_success():
                    # 等待智能考勤
                self.log.info("等待智能考勤页面...")
                self.controller.wait("智能考勤", self.click_pos["智能考勤"])
                self.log.info("登录成功，进入智能考勤页面")

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
                    self.controller.wait("同意并继续", self.click_pos["同意并继续"]).click()
                    self.log.info("点击同意并继续按钮完成")
                    handle_login_success()
                except Exception as e:
                    self.log.error(f"登录过程中发生错误: {str(e)}")
                    raise

            def handle_skip():
                self.controller.get_text_location("跳过").click()
                self.controller.wait({"智能考勤":handle_login_success,"登录":handle_login}).click()


    
            # 启动应用
            self.log.info(f"启动应用: {self.deli_package_name}")
            self.controller.start_app(self.deli_package_name)
            self.log.info("应用启动成功")

            # 等待并点击智能考勤

            self.controller.wait({"智能考勤":handle_login_success,"登录":handle_login,"跳过":handle_skip}).click()

            
            # 等待多种可能的状态
            '''self.log.info("等待打卡状态...")
            self.controller.wait({
                "已在打卡范围": handle_in_sign_area, 
                "不在打卡位置": handle_not_in_sign_area,
                "确定": handle_sign_invaild_confirm, 
                "登录": handle_login
            })'''
            self.log.info("打卡操作完成")
    
            # 退出账号
            self.log.info("准备退出账号...")
            self.controller.wait("我的", self.click_pos["我的"]).click()
            self.log.info("点击我的按钮")
            
            self.controller.wait("设置", self.click_pos["设置"]).click()
            self.log.info("点击设置按钮")
            self.controller.wait(2)
            self.controller.swipe(600, 1600, 900, 500)
            self.log.info("向上滑动屏幕")
            self.controller.wait(1)
            self.controller.wait("退出登录", self.click_pos["退出登录"]).click()
            self.log.info("点击退出登录按钮")
            
            self.controller.wait("确定", self.click_pos["确定"]).click()
            self.log.info("点击确定按钮，退出登录完成")
            
            return True
        except Exception as e:
            self.log.error(f"登录或签到过程中发生错误: {str(e)}", exc_info=True)
            raise




if __name__ == "__main__":
    Deli()