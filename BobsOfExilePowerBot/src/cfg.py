from typing import Collection
import configparser
from pathlib import Path
from common import CfgMasterOptions, CfgSections, Stringable
from OTHER_SETTINGS import LOGS_SEPARATOR as s, CONFIG_PATH
from logs import ldbg, lwarn


# Setup
class Cfg:
    _MASTER_SECTION: str = CfgSections.MASTER_SECTION.value
    _MASTER_OPTIONS: list[str] = [option.value for option in CfgMasterOptions]
    DEFAULT_VALUE: str = ""
    cfg: configparser.ConfigParser
    path: Path

    def __init__(self, path: Path) -> None:
        ldbg(f"File: {path}{s}Touching")
        path.touch()
        self.path = path

        self.cfg: configparser.ConfigParser = configparser.ConfigParser()
        self.cfg.read(self.path)
        self.ensure_section(self._MASTER_SECTION)
        self.ensure_options(self._MASTER_SECTION, self._MASTER_OPTIONS)

    def save(self) -> None:
        with open(self.path, "w") as f:
            self.cfg.write(f)

    def set_default_value(self, section: str, option: str) -> None:
        logs_infix: str = f"Section: {section}{s}Option: {option}{s}"
        ldbg(f"{logs_infix}Setting default value")
        self.cfg.set(section, option, self.DEFAULT_VALUE)
        self.save()

    def ensure_section(self, section: str) -> None:
        logs_infix: str = f"Section: {section}{s}"
        ldbg(f"{logs_infix}Ensuring it exists")
        if not self.cfg.has_section(section):
            ldbg(f"{logs_infix}Doesn't exist. Creating it now")
            self.cfg.add_section(section)
            self.save()
        else:
            ldbg(f"{logs_infix}Exists!")

    def ensure_option(self, section: str, option: str, fatal: bool) -> bool:
        """
        -> Success
        Assumes section exists
        """
        logs_infix: str = f"Section: {section}{s}Option: {option}{s}"
        ldbg(f"{logs_infix}Ensuring it exists")
        if not self.cfg.has_option(section, option):
            ldbg(f"{logs_infix}Doesn't exist")
            self.set_default_value(section, option)

        if self.cfg.get(section, option) != self.DEFAULT_VALUE:
            ldbg(f"{logs_infix}Exists!")
            return True

        msg: str = (
            f'IMPORTANT! Please fill in the value for the option "{option}"'
            f'In the Section "{section}" In your config file at "{self.path}"'
        )
        if fatal:
            raise RuntimeError(msg)
        lwarn(msg)
        return False

    def ensure_options(self, section: str, options: Collection[str]) -> None:
        """Assumes section exists"""
        fails: int = 0
        for option in options:
            ok: bool = self.ensure_option(section, option, False)
            if not ok:
                fails += 1

        if fails > 0:
            raise RuntimeError(
                "IMPORTANT! Your config has empty values! Please READ THE ABOVE WARNINGS and adjust your config"
            )

    def get_str_data(self, section: str, option: str, expect_non_default: bool) -> str:
        """Assumes both the section and option exist"""
        logs_infix: str = f"Section: {section}{s}Option: {option}{s}"
        ldbg(f"{logs_infix} Getting data")
        data: Stringable = self.cfg.get(section, option)
        if expect_non_default and data == self.DEFAULT_VALUE:
            raise RuntimeError(f"{logs_infix}EXPECTED NOT A DEFAULT VALUE")
        return str(data)  # better safe than sorry

    def get_master_str_data(self, option: str, expect_non_default: bool) -> str:
        return self.get_str_data(self._MASTER_SECTION, option, expect_non_default)


_lazy_loaded_cfg: None | Cfg = None


def get_shared_cfg() -> Cfg:
    global _lazy_loaded_cfg
    if _lazy_loaded_cfg is None:
        _lazy_loaded_cfg = Cfg(CONFIG_PATH)
    return _lazy_loaded_cfg