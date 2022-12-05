# Videobox

Video download and playback machine.

The app doesn't allow to download any video material out-of-the-box. You have to provide a valid sync service on your own.

* * *

## Quick start

From the repo root, create a new virtual enviroment: 

`make venv`

Activate it:

`source .venv/bin/activate`

Then install all project dependencies into the virtual enviroment just created:

`make install-deps`

Finally you can run Videobox:

`make`

This will run the Python interpreter using `src/main.py` as application entry point. A few directiores will be created using the repo as root.

When you are done you can exit the virtual enviroment with the `deactivate` command.

## Using the debugger 

Debug works just fine under Visual Studio Code once you pick the Python interpreter shown in the `venv` folder created previously in the `install-deps` task. 

Place any breakpoint you need and hit F5. Editor will fire up `src/main.py` thus starting the application.
