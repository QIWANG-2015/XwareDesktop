#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../"))

if __name__ == "__main__":
    import faulthandler, logging
    from utils import misc
    misc.tryMkdir(os.path.expanduser("~/.xware-desktop"))

    logging.basicConfig(filename = os.path.expanduser("~/.xware-desktop/log.txt"))

    faultLogFd = open(os.path.expanduser('~/.xware-desktop/frontend.fault.log'), 'a')
    faulthandler.enable(faultLogFd)

    from CrashReport import CrashAwareThreading
    CrashAwareThreading.installCrashReport()
    CrashAwareThreading.installThreadExceptionHandler()

from PyQt5.QtCore import pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QApplication

import fcntl

from shared import __version__

import constants
__all__ = ['app']


class XwareDesktop(QApplication):
    mainWin = None
    monitorWin = None
    sigMainWinLoaded = pyqtSignal()

    def __init__(self, *args):
        super().__init__(*args)

        import main
        from Settings import SettingsAccessor, DEFAULT_SETTINGS
        from xwaredpy import XwaredPy
        from etmpy import EtmPy
        from systray import Systray
        import mounts
        from Notify import Notifier
        from frontendpy import FrontendPy
        from Schedule import Scheduler

        logging.info("XWARE DESKTOP STARTS")
        self.setApplicationName("XwareDesktop")
        self.setApplicationVersion(__version__)

        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        self.checkOneInstance()

        self.settings = SettingsAccessor(self,
                                         configFilePath = constants.CONFIG_FILE,
                                         defaultDict = DEFAULT_SETTINGS)

        # components
        self.xwaredpy = XwaredPy(self)
        self.etmpy = EtmPy(self)
        self.mountsFaker = mounts.MountsFaker()
        self.dbusNotify = Notifier(self)
        self.frontendpy = FrontendPy(self)
        self.scheduler = Scheduler(self)

        self.settings.applySettings.connect(self.slotCreateCloseMonitorWindow)

        self.mainWin = main.MainWindow(None)
        self.mainWin.show()
        self.sigMainWinLoaded.emit()

        self.systray = Systray(self)

        self.settings.applySettings.emit()

        if self.settings.get("internal", "previousversion") == "0.8":
            # upgraded or fresh installed
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl("https://github.com/Xinkai/XwareDesktop/wiki/使用说明"))
            self.settings.set("internal", "previousversion", __version__)

    @staticmethod
    def checkOneInstance():
        fd = os.open(constants.FRONTEND_LOCK, os.O_RDWR | os.O_CREAT)

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            def showStartErrorAndExit():
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(None, "Xware Desktop 启动失败",
                                    "Xware Desktop已经运行，或其没有正常退出。\n"
                                    "请检查：\n"
                                    "    1. 没有Xware Desktop正在运行\n"
                                    "    2. 上次运行的Xware Desktop没有残留"
                                    "（使用进程管理器查看名为python3或xware-desktop或launcher.py的进程）\n",
                                    QMessageBox.Ok, QMessageBox.Ok)
                sys.exit(-1)

            tasks = sys.argv[1:]
            if len(tasks) == 0:
                showStartErrorAndExit()
            else:
                from Tasks import CommandlineClient
                try:
                    CommandlineClient(tasks)
                except FileNotFoundError:
                    showStartErrorAndExit()
                except ConnectionRefusedError:
                    showStartErrorAndExit()
                sys.exit(0)

    @pyqtSlot()
    def slotCreateCloseMonitorWindow(self):
        logging.debug("slotCreateCloseMonitorWindow")
        show = self.settings.getbool("frontend", "showmonitorwindow")
        import monitor
        if show:
            if self.monitorWin:
                pass  # already shown, do nothing
            else:
                self.monitorWin = monitor.MonitorWindow(None)
                self.monitorWin.show()
        else:
            if self.monitorWin:
                logging.debug("close monitorwin")
                self.monitorWin.close()
                del self.monitorWin
                self.monitorWin = None
            else:
                pass  # not shown, do nothing

    @property
    def autoStart(self):
        return os.path.lexists(constants.DESKTOP_AUTOSTART_FILE)

    @autoStart.setter
    def autoStart(self, on):
        if on:
            # mkdir if autostart dir doesn't exist
            misc.tryMkdir(os.path.dirname(constants.DESKTOP_AUTOSTART_FILE))

            misc.trySymlink(constants.DESKTOP_FILE,
                            constants.DESKTOP_AUTOSTART_FILE)
        else:
            misc.tryRemove(constants.DESKTOP_AUTOSTART_FILE)


app = None
if __name__ == "__main__":
    from shared.profile import profileBootstrap
    profileBootstrap(constants.PROFILE_DIR)
    app = XwareDesktop(sys.argv)
    sys.exit(app.exec())
else:
    app = QApplication.instance()
