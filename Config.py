import os
from typing import Any, Optional, Union
from tomlkit import document, table, dump, load
from tomlkit.exceptions import NonExistentKey
from tomlkit.items import Table


class Config:
    def __init__(self, config_path: str = "config.toml") -> None:
        """Initialize config handler

        Args:
            config_path: Path to config file
        """
        self.config_path = config_path
        if not os.path.exists(config_path):
            self.doc = self._generate_default_config()
        else:
            with open(config_path, "r", encoding="utf-8") as f:
                self.doc = load(f)

    def _generate_default_config(self) -> Table:
        """Generate default config file with basic structure"""
        try:
            doc = document()

            # Setting section
            setting = table()
            setting.add("path", os.getcwd())
            doc.add("Setting", setting)

            # Emulator section
            emulator = table()
            emulator.add("serial", "")
            emulator.add("path", "")
            emulator.add("launch_args", "-v")
            emulator.add("launch_emulator_num", "0")
            emulator.add("launch_timeout", 60)
            doc.add("Emulator", emulator)

            position =table()
            
            position.add("不再显示" , [566, 1755, 752, 1822])
            position.add("暂不更新" , [560, 1744, 746, 1819])
            position.add("启动模拟" , [100, 1100, 300, 1190])
            position.add("停止模拟" , [100, 1100, 300, 1190])
            position.add("用户名" , [580, 745, 600, 780])
            position.add("密码" , [580, 910, 600, 955])
            position.add("登录" , [480, 1290, 595, 1350])
            position.add("同意并继续" , [626, 1123, 868, 1195])
            position.add("智能考勤" , [330, 600, 530, 655])
            position.add("刷新" , [830, 975, 920, 1020])
            position.add("不在打卡位置" , [425, 1475, 720, 1530])
            position.add("已在打卡范围" , [425, 1475, 720, 1530])
            position.add("打卡" , [490, 1190, 590, 1255])
            position.add("我的" , [860, 1850, 940, 1895])
            position.add("设置" , [200, 1325, 300, 1380])
            position.add("退出登录" , [425, 1815, 655, 1875])
            position.add("确定" , [710, 1125, 815, 1180])
            position.add("打卡成功" , [352, 612, 718, 718])
            position.add("签退成功" , [352, 612, 718, 718])
            position.add("签到成功" , [352, 612, 718, 718])
            position.add("返回" , [71, 146, 121, 196])
            position.add("账号已失效",[363,901,615,956])
            position.add("登录失效确定" , [474, 1048, 600, 1120])
            doc.add("Position", position)
            # Account section (empty by default)
            doc.add("Account", table())

            self._save_config(doc)
            return doc
        except Exception as e:
            raise RuntimeError(f"Failed to generate config: {str(e)}")

    def _save_config(self, doc: Optional[Table] = None) -> None:
        """Internal method to save config"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                dump(doc or self.doc, f)
        except Exception as e:
            raise IOError(f"Failed to save config: {str(e)}")

    def save(self) -> None:
        """Save current config state"""
        self._save_config()

    def set_value(self, *keys: str, value: Any) -> bool:
        """Set value in config with nested keys

        Args:
            *keys: Nested keys (e.g. 'section', 'subsection', 'key')
            value: Value to set

        Returns:
            True if successful, False if key path doesn't exist
        """
        if not keys:
            return False

        try:
            node = self.doc
            for key in keys[:-1]:
                node = node[key]

            node[keys[-1]] = value
            self.save()
            return True
        except NonExistentKey:
            return False

    def get_value(self, *keys: str, default: Any = None) -> Any:
        """Get value from config with nested keys

        Args:
            *keys: Nested keys to traverse
            default: Default value if key doesn't exist

        Returns:
            Found value or default
        """
        try:
            node = self.doc
            for key in keys:
                node = node[key]
            return node
        except NonExistentKey:
            return default

    def add_user(self, username: str, password: str) -> None:
        """Add or update user credentials"""
        if not self.doc.get("Account"):
            self.doc["Account"] = table()

        user = table()
        user.add("username", username)
        user.add("password", password)
        self.doc["Account"][username] = user
        self.save()
    def get_userlist(self):
        userlist=[]
        for key,value in self.doc["Account"].items():
            userlist.append(value)
        return userlist
    def delete_user(self, username: str) -> bool:
        """Delete user by username

        Returns:
            True if user was deleted, False if not found
        """
        if "Account" not in self.doc or username not in self.doc["Account"]:
            return False

        del self.doc["Account"][username]
        self.save()
        return True

    # Specific property accessors for better type safety
    @property
    def emulator_serial(self) -> str:
        return self.get_value("Emulator", "serial", default="")

    @emulator_serial.setter
    def emulator_serial(self, value: str) -> None:
        self.set_value("Emulator", "serial", value=value)

    @property
    def launch_with_windows(self) -> bool:
        return self.get_value("Setting", "launch_with_windows", default=False)

    @launch_with_windows.setter
    def launch_with_windows(self, value: bool) -> None:
        self.set_value("Setting", "launch_with_windows", value=value)

if __name__ == "__main__":
    config = Config()
    print(config.doc)
    result=config.get_userlist()
    print(result)