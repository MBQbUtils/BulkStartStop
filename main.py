import ctypes
import dataclasses
import distutils.spawn
import os.path
import re
import shlex
import signal
import subprocess
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog
import winreg
from copy import deepcopy

import jsons

import psutil as psutil

from scrframe import ScrollableFrame


class PathsStorage:
    def __init__(self, filename: str = 'apps_to_manage.txt'):
        self._paths = set()
        self.filename = filename

    def load(self):
        try:
            with open(self.filename, 'r', encoding='utf-8-sig') as file:
                self._paths = {path.strip() for path in file.readlines() if path}
        except OSError:
            self._paths = set()

    def save(self):
        with open(self.filename, 'w', encoding='utf-8-sig') as file:
            file.writelines(x + '\n' for x in self._paths)

    @property
    def paths(self):
        if not self._paths:
            self.load()
        return self._paths

    @paths.setter
    def paths(self, value: set[str]):
        if self.paths != value:
            self._paths = set(value)
            self.save()


@dataclasses.dataclass
class Config:
    run_all_at_startup: bool = False
    kill_all_on_close: bool = False


class ConfigStorage:
    def __init__(self, filename: str = 'config.json'):
        self.config = Config()
        self.filename = filename

    def load(self):
        try:
            with open(self.filename, 'r', encoding='utf-8-sig') as file:
                self.config = jsons.loads(file.read(), Config)
        except OSError:
            pass

    def save(self):
        with open(self.filename, 'w', encoding='utf-8-sig') as file:
            file.write(jsons.dumps(self.config,  jdkwargs=dict(indent=2)))


def find_process(name, path, pid):
    for proc in psutil.process_iter():
        try:
            if proc.name() == name or proc.exe() == path or proc.pid == pid:
                return proc
        except:
            return None


def get_program_for_file(filename):
    extension = os.path.splitext(filename)[1]
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, extension, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, '')
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{value}\\shell\\open\\command", 0, winreg.KEY_READ) as key:
            command_line, _ = winreg.QueryValueEx(key, '')
        args = shlex.split(command_line)
        for i, arg in enumerate(args):
            if "%1" in arg or "%l" in arg.lower():
                args[i] = arg.replace("%1", os.path.normpath(filename))\
                             .replace("%l", os.path.normpath(filename))\
                             .replace("%L", os.path.normpath(filename))
        args = [arg for arg in args if not re.search(r'(?<!%)%(\*|[2-9])', arg)]
        return args
    except:
        return None


class ProcessModel:
    def __init__(self, path: str):
        self.path = path
        self.process = None

    @property
    def is_exists(self):
        return os.path.exists(self.path)

    @property
    def is_alive(self):
        if not self.process:
            return False
        return self.process.is_running()

    def kill(self):
        if self.process:
            self.process.send_signal(signal.CTRL_BREAK_EVENT)
            self.process.terminate()
            self.process.kill()

    def run(self):
        if (executable := get_program_for_file(self.path)) is None:
            executable = [self.path]
        process = subprocess.Popen(
            executable,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            start_new_session=True,
            cwd=os.path.dirname(self.path)
        )
        process.is_running = lambda: process.poll() is None
        self.process = process

    @is_alive.setter
    def is_alive(self, value):
        if value == self.is_alive:
            return
        if value:
            self.run()
        else:
            self.kill()

    def toggle(self):
        if self.is_alive:
            self.kill()
        else:
            self.run()


class Model:
    def __init__(self):
        self._paths_storage = PathsStorage()
        self._config_storage = ConfigStorage()
        self._config_storage.load()
        self.paths: list = list(self._paths_storage.paths)
        self._processes = {path: ProcessModel(path) for path in self.paths}

    @property
    def processes(self):
        return [
            self._processes.setdefault(path, ProcessModel(path))
            for path in self.paths
        ]

    @property
    def settings(self):
        return self._config_storage.config

    def save(self):
        self._paths_storage.paths = self.paths  # Save and diffcheck paths
        self.paths = list(self._paths_storage.paths)

    def save_settings(self):
        self._config_storage.save()


class View(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.controller: 'Controller' = None
        self.common_status = ttk.Label(text='...')
        self.common_status.pack(padx=8, pady=8)
        self.apps = ScrollableFrame(self, width=540)
        self.apps.pack(padx=8, pady=8)
        bulk_controls = ttk.Frame(self)
        bulk_controls.pack()
        ttk.Button(master=bulk_controls, text="Add apps", command=self.add_apps_callback).pack(padx=4, pady=8, side=tk.LEFT)
        ttk.Button(master=bulk_controls, text="Delete all apps",
                   command=self.delete_all_apps_callback).pack(padx=4, pady=8, side=tk.LEFT)
        ttk.Button(master=bulk_controls, text="Kill all apps",
                   command=lambda: self.controller.set_all_apps_alive(False)
                   ).pack(padx=4, pady=8, side=tk.LEFT)
        ttk.Button(master=bulk_controls, text="Run all apps",
                   command=lambda: self.controller.set_all_apps_alive(True)
                   ).pack(padx=4, pady=8, side=tk.LEFT)
        bottom_bar = ttk.Frame()
        bottom_bar.pack(side=tk.BOTTOM, padx=16, pady=16)
        self.run_at_startup = tk.IntVar()
        self.kill_on_close = tk.IntVar()
        ttk.Checkbutton(master=bottom_bar, text="Run all apps when program started",
                        variable=self.run_at_startup, command=lambda: self.controller.set_run_at_startup(bool(self.run_at_startup.get()))).pack(anchor="w")
        ttk.Checkbutton(master=bottom_bar, text="Kill all apps when program closed",
                        variable=self.kill_on_close, command=lambda: self.controller.set_kill_on_close(bool(self.kill_on_close.get()))).pack(anchor="w")

    def set_settings(self, settings: Config):
        self.run_at_startup.set(settings.run_all_at_startup)
        self.kill_on_close.set(settings.kill_all_on_close)

    def set_apps(self, apps: list[ProcessModel]):
        for child in self.apps.winfo_children():
            child.destroy()
        for i, app in enumerate(apps):
            ttk.Label(master=self.apps, text=self.format_app_name(app.path)).grid(column=0, row=i, padx=8)
            state = ttk.Label(master=self.apps, text=self.get_state(app))
            state.grid(column=1, row=i, padx=16)
            state.after(1000, lambda state=state, app=app: state.config(text=self.get_state(app)))
            if app.is_exists:
                ttk.Button(
                    master=self.apps, text="Kill" if app.is_alive else "Run",
                    command=lambda app=app: self.toggle_app_callback(app)
                ).grid(column=2, row=i, padx=4, pady=8)
            ttk.Button(
                master=self.apps, text="Delete",
                command=lambda app=app.path: self.delete_app_callback(app)
            ).grid(column=3, row=i, padx=4, pady=8)
            ttk.Button(
                master=self.apps, text="Open folder",
                command=lambda path=app.path: self.open_app_path(path)
            ).grid(column=4, row=i, padx=4, pady=8)
        self.common_status.config(text=f"Common status: {self.get_common_state(apps)}")

    @staticmethod
    def get_state(app: ProcessModel):
        if not app.is_exists:
            return "NOT FOUND"
        if app.is_alive:
            return "ACTIVE"
        return "NOT ACTIVE"

    @staticmethod
    def get_common_state(apps: list[ProcessModel]):
        if all(not app.is_exists for app in apps):
            return "NOTHING FOUND"
        alive_states = [app.is_alive for app in apps]
        if all(alive_states):
            return "ALL ACTIVE"
        if not any(alive_states):
            return "ALL INACTIVE"
        return f"PARTIAL ACTIVE ({alive_states.count(True)}/{len(alive_states)})"

    @staticmethod
    def format_app_name(app_path):
        app_name = os.path.basename(app_path)
        app_name = app_name.strip()
        max_len = 30
        if len(app_name) > max_len:
            app_name = app_name[:max_len] + '…'
        return app_name

    def add_apps_callback(self):
        self.controller.add_apps(self.get_apps_paths())

    def toggle_app_callback(self, app):
        self.controller.toggle_app(app)

    def get_apps_paths(self) -> tuple[str]:
        return tk.filedialog.askopenfilenames(
            title='Select some executables',
            filetypes=(("Executable", ".exe .bat .cmd"), ("Other", "*.*"))
        ) or tuple()

    def delete_app_callback(self, app):
        self.controller.delete_app(app)

    def delete_all_apps_callback(self):
        self.controller.delete_all_apps()

    def open_app_path(self, path):
        os.system(f'explorer /select,"{os.path.normpath(path)}"')


class Controller:
    def __init__(self, model: 'Model', view: 'View'):
        self.model = model
        self.view = view

    def add_apps(self, apps):
        self.model.paths += apps
        self.model.save()
        self.view.set_apps(self.model.processes)

    def delete_app(self, app: str):
        self.model.paths.remove(app)
        self.model.save()
        self.view.set_apps(self.model.processes)

    def delete_all_apps(self):
        self.model.paths.clear()
        self.model.save()
        self.view.set_apps(self.model.processes)

    def setup(self):
        self.view.set_apps(self.model.processes)
        self.view.set_settings(self.model.settings)
        if self.model.settings.run_all_at_startup:
            self.set_all_apps_alive(True)
        if not self.model.paths:
            self.view.add_apps_callback()

    def on_close(self, root):
        if self.model.settings.kill_all_on_close:
            self.set_all_apps_alive(False)
        root.destroy()

    def toggle_app(self, app: ProcessModel):
        app.toggle()
        self.view.set_apps(self.model.processes)

    def set_all_apps_alive(self, is_alive: bool):
        for app in self.model.processes:
            app.is_alive = is_alive
        self.view.set_apps(self.model.processes)

    def set_run_at_startup(self, value: bool):
        self.model.settings.run_all_at_startup = value
        self.model.save_settings()

    def set_kill_on_close(self, value: bool):
        self.model.settings.kill_all_on_close = value
        self.model.save_settings()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Apps bulk start/stop')
        self.geometry('640x480')
        self.apply_theme()
        model = Model()
        view = View(self)
        view.pack(fill=tk.X, padx=8, pady=8)
        controller = Controller(model, view)
        view.controller = controller
        controller.setup()
        self.protocol("WM_DELETE_WINDOW", lambda: controller.on_close(self))

    def apply_theme(self):
        ctypes.windll['uxtheme.dll'][135](1)
        self.tk.call('source', 'forest-dark.tcl')
        style = ttk.Style()
        style.theme_use('forest-dark')


def main():
    App().mainloop()


if __name__ == '__main__':
    main()
