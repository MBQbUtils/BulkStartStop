import argparse
import ctypes
import dataclasses
import os.path
import re
import shlex
import sys
import textwrap
import tkinter as tk
import tkinter.filedialog
import tkinter.ttk as ttk
import winreg

import WinJobster
import jsons

from scrframe import ScrollableFrame


class PathsStorage:
    def __init__(self, filename: str = 'apps_to_manage.txt'):
        self._paths = tuple()
        self.filename = filename

    def load(self):
        try:
            mkdir(self.filename)
            with open(self.filename, 'r', encoding='utf-8-sig') as file:
                self._paths = tuple(path.strip() for path in file.readlines() if path)
        except OSError:
            self._paths = tuple()

    def save(self):
        with open(self.filename, 'w', encoding='utf-8-sig') as file:
            file.writelines(x + '\n' for x in self._paths)

    @property
    def paths(self):
        if not self._paths:
            self.load()
        return self._paths

    @paths.setter
    def paths(self, value: tuple[str, ...]):
        self._paths = value
        self.save()


@dataclasses.dataclass
class Config:
    run_all_at_startup: bool = False
    kill_all_on_close: bool = False
    rules_path: str = 'apps_to_manage.txt'


def mkdir(path):
    dirname = os.path.dirname(path)
    if dirname and not (os.path.exists(dirname) and os.path.isdir(dirname)):
        os.mkdir(dirname)


class ConfigStorage:
    def __init__(self, filename: str = 'config.json'):
        self.config = Config()
        self.filename = filename

    def load(self):
        try:
            mkdir(self.filename)
            with open(self.filename, 'r', encoding='utf-8-sig') as file:
                self.config = jsons.loads(file.read(), Config)
        except OSError:
            self.save()
        except jsons.DeserializationError:
            self.save()

    def save(self):
        with open(self.filename, 'w', encoding='utf-8-sig') as file:
            file.write(jsons.dumps(self.config,  jdkwargs=dict(indent=2)))


def get_program_for_file(filename):
    extension = os.path.splitext(filename)[1]
    app_path = os.path.normpath(filename)
    if extension in ('.lnk', '.url'):
        return f'cmd.exe /C start "" "{app_path}"'
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, extension, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, '')
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{value}\\shell\\open\\command", 0, winreg.KEY_READ) as key:
            command_line, _ = winreg.QueryValueEx(key, '')
        args = shlex.split(command_line)
        for i, arg in enumerate(args):
            if "%1" in arg or "%l" in arg.lower():
                args[i] = arg.replace("%1", app_path)\
                             .replace("%l", app_path)\
                             .replace("%L", app_path)
        args = [arg for arg in args if not re.search(r'(?<!%)%(\*|[2-9])', arg)]
        return ' '.join(args)
    except:
        return None


class ProcessModel:
    def __init__(self, path: str):
        self.path = path
        self.process: WinJobster.Job = None

    @property
    def is_exists(self):
        return os.path.exists(self.path)

    @property
    def is_alive(self):
        if not self.process:
            return False
        return self.process.is_alive

    def kill(self):
        if self.process:
            self.process.terminate()

    def run(self):
        executable = get_program_for_file(self.path) or self.path
        self.process = WinJobster.Job()
        self.process.start_process(executable, working_directory=os.path.dirname(self.path))

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
    def __init__(self, args):
        self._config_storage = ConfigStorage(args.config)
        self._config_storage.load()
        self._paths_storage = PathsStorage(self.settings.rules_path)
        self.paths = list(self._paths_storage.paths)
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
        self._paths_storage.paths = tuple(self.paths)
        self.paths = list(self._paths_storage.paths)

    def save_settings(self):
        self._config_storage.save()


def open_path(path):
    os.system(f'explorer /select,"{os.path.normpath(path)}"')


class AppView(ttk.Frame):
    def __init__(self, parent, app: ProcessModel,
                 toggle_callback, delete_callback):
        super().__init__(parent)
        self.app_name = tk.StringVar()
        self.app_state = tk.StringVar()
        self.app = None
        ttk.Label(master=self, textvariable=self.app_name, width=20).pack(side=tk.LEFT, padx=8)
        ttk.Label(master=self, textvariable=self.app_state,width=12).pack(side=tk.LEFT, padx=8)
        self.live_controller_btn = ttk.Button(
            master=self, command=lambda: toggle_callback(self.app)
        )
        self.live_controller_btn.pack(side=tk.LEFT, padx=4, pady=8)
        ttk.Button(
            master=self, text="Delete",
            command=lambda: delete_callback(self.app.path)
        ).pack(side=tk.LEFT, padx=4, pady=8)
        self.open_folder_btn = ttk.Button(
            master=self, text="Open folder",
            command=lambda: open_path(self.app.path)
        )
        self.open_folder_btn.pack(side=tk.LEFT, padx=4, pady=8)
        self.set_app(app)

    def set_app(self, app: ProcessModel):
        self.app = app
        self.app_name.set(os.path.basename(app.path).strip())
        self.app_state.set(self.get_state(app))
        exists_state = tk.DISABLED if not self.app.is_exists else tk.NORMAL
        self.live_controller_btn.config(state=exists_state, text="Kill" if app.is_alive else "Run")
        self.open_folder_btn.config(state=exists_state)

    def refresh(self):
        self.set_app(self.app)

    @staticmethod
    def get_state(app: ProcessModel):
        if not app.is_exists:
            return "NOT FOUND"
        if app.is_alive:
            return "ACTIVE"
        return "NOT ACTIVE"


def make_shortcut(app_path: str, args: str, shortcut_path: str):
    workdir = os.path.dirname(app_path)
    command = textwrap.dedent(f"""
    Set objWS = WScript.CreateObject("WScript.Shell")
    Set objLink = objWS.CreateShortcut("{shortcut_path}")

    objLink.TargetPath = "{app_path}"
    objLink.Arguments = "{args}"
    objLink.IconLocation = "{app_path}"
    objLink.WorkingDirectory = "{workdir}"
    objLink.Save
    """).strip()
    with open("make_shortcut.vbs", 'w') as f:
        f.write(command)
    os.system("CSCRIPT .\\make_shortcut.vbs")
    os.remove(".\\make_shortcut.vbs")


class View(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.controller: 'Controller' = None
        self.common_status = ttk.Label(text='...')
        self.common_status.pack(padx=8, pady=8)
        self.apps = ScrollableFrame(self, width=580)
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
        ttk.Button(master=bottom_bar, text="Make new config", command=self.make_new_config_callback)\
            .pack(anchor="w", pady=8)
        self._apps_stored = []
        self._apps_views = []
        self.refresh()

    def refresh(self):
        self.refresh_apps()
        self.after(1000, self.refresh)

    def set_settings(self, settings: Config):
        self.run_at_startup.set(settings.run_all_at_startup)
        self.kill_on_close.set(settings.kill_all_on_close)

    def set_apps(self, apps: list[ProcessModel]):
        self._apps_stored = apps
        self._apps_views = []
        for child in self.apps.winfo_children():
            child.destroy()
        for app in apps:
            app_view = AppView(self.apps, app, self.toggle_app_callback, self.delete_app_callback)
            self._apps_views.append(app_view)
            app_view.pack()
        self.refresh_common_state()

    def refresh_apps(self):
        for app_view in self._apps_views:
            app_view.refresh()
        self.refresh_common_state()

    def refresh_common_state(self):
        self.common_status.config(text=f"Common status: {self.get_common_state(self._apps_stored)}")

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

    def add_apps_callback(self):
        self.controller.add_apps(self.get_apps_paths())

    def toggle_app_callback(self, app):
        self.controller.toggle_app(app)

    def get_apps_paths(self) -> tuple[str]:
        return tk.filedialog.askopenfilenames(
            title='Select some executables',
            filetypes=(("Executable", ".exe .bat .cmd .url .lnk"), ("Other", "*.*"))
        ) or tuple()

    def make_new_config_callback(self):
        new_config = self.get_new_config_path()
        if not new_config:
            return
        new_config = os.path.normpath(new_config)
        config_dir = os.path.dirname(new_config)
        app_name = os.path.basename(sys.argv[0]).split(".")[0]
        config_name = os.path.basename(new_config).split(".")[0]
        config_storage = ConfigStorage(new_config)
        config_storage.config.rules_path = os.path.join(config_dir, config_storage.config.rules_path)
        config_storage.save()
        link_path = os.path.join(config_dir, f"New {app_name} for {config_name}.lnk")
        make_shortcut(
            sys.argv[0],
            f'-c ""{new_config}""',
            link_path
        )
        open_path(link_path)

    def get_new_config_path(self) -> str:
        return tk.filedialog.asksaveasfilename(
            defaultextension="json",
            initialfile="config",
            filetypes=(("json", ".json",),),
            title='Save new config to',
        ) or None

    def delete_app_callback(self, app):
        self.controller.delete_app(app)

    def delete_all_apps_callback(self):
        self.controller.delete_all_apps()


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
        self.view.refresh_apps()

    def set_all_apps_alive(self, is_alive: bool):
        for app in self.model.processes:
            app.is_alive = is_alive
        self.view.refresh_apps()

    def set_run_at_startup(self, value: bool):
        self.model.settings.run_all_at_startup = value
        self.model.save_settings()

    def set_kill_on_close(self, value: bool):
        self.model.settings.kill_all_on_close = value
        self.model.save_settings()



class App(tk.Tk):
    def __init__(self, args):
        super().__init__()
        self.title('Apps bulk start/stop')
        self.geometry('640x520')
        self.apply_theme()
        model = Model(args)
        view = View(self)
        view.pack(fill=tk.X, padx=8, pady=8)
        controller = Controller(model, view)
        view.controller = controller
        controller.setup()
        self.protocol("WM_DELETE_WINDOW", lambda: controller.on_close(self))

    def apply_theme(self):
        ctypes.windll['uxtheme.dll'][135](1) # Win Dark Theme hack
        self.tk.call('source', 'data/theme/forest-dark.tcl')
        style = ttk.Style()
        style.theme_use('forest-dark')


def get_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--config', '-c', default='config.json')
    return parser.parse_args(sys.argv[1:])


def main():
    args = get_args()
    App(args).mainloop()


if __name__ == '__main__':
    main()
