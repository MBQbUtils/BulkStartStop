# Bulk Start Stop or Bulk App Launcher
App to start / stop multiple apps in batch

Features:
- Add/Remove app to list
- Open app folder
- Run app
- Run all apps
- Kill app
- Kill all apps
- Start all aps with program start
- Kill all apps when program closed

# Preview
![image](https://user-images.githubusercontent.com/27343275/223377875-6372e719-6b8d-4c9b-88bc-af7f7827d750.png)
![image](https://user-images.githubusercontent.com/27343275/223378776-80b98933-0377-43b3-b1fd-bc1adecfe1ae.png)

# Download: [![Latest](https://img.shields.io/github/v/tag/MBQbUtils/BulkStartStop?sort=date&label=&style=for-the-badge&color=424242)](https://github.com/MBQbUtils/BulkStartStop/releases/latest/)
### [ [Portable](https://github.com/MBQbUtils/BulkStartStop/releases/latest/download/BulkStartStop_portable.zip) ] [ [Installer](https://github.com/MBQbUtils/BulkStartStop/releases/latest/download/BulkStartStop_setup.exe) ]
### Or
```
winget install BulkStartStop
```
## Theme used: [forest-dark](https://github.com/rdbende/Forest-ttk-theme) with minor changes
## Main lib used: [WinJobster](https://github.com/SemperSolus0x3d/WinJobster) with minor changes

# Multiple configs and rules lists
Path to config can be configured with `-c`/`--config` params on start
```cmd
BulkStartStop.exe --config path/to/config.json
```

Path to rules list file can be set with config.

Use `Make new config` button for that purpose.