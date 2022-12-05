# Videobox

Video download and playback machine.

The app doesn't allow to download any video material out-of-the-box. You have to provide a valid sync service on your own.

* * *

Quick start:

`make install-deps`

This will create a virtual env on the repo root, activate it and install all project dependencies.

Then run:

`make`

This will run the Python interpreter using `src/main.py` as application entry point. A few directiores will be created using the repo as root.

## Using the debugger 

Debug works just fine under Visual Studio Code once you pick the Python interpreter shown in the `venv` folder created previously in the `install-deps` task. 

Place any breakpoint you need and hit F5. Editor will fire up `src/main.py` thus starting the application.
