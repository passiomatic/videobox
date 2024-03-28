# Contributing

If you would like to help with the Videobox development these are some essential steps to get you started.

## Setup the environment

Starting from the repo root you might want to create a new virtual environment, to avoid messing up pre-existing Pyhton packages on your machine: 

`$ make venv`

And activate it:

`$ source .venv/bin/activate`

Then, install all project dependencies into the virtual enviroment just created:

`$ make install-deps`

`npm`, the Node Package Manager, is required to install `parcel` to compile CSS styles and JavaScript code:

`$ npm ci && make build-assets`

Finally, run the web interface in debug mode:

`$ make`

When you are done you can exit the virtual enviroment with the `deactivate` command.

## Where to find Videobox data

The Videobox Python package stores local database and configuration settings in `~/.videobox`, while the macOS app uses `~/Library/Application Support/Videobox`. 

## Using the debugger with Visual Studio Code

Debug works just fine under Visual Studio Code once you pick the Python interpreter shown in the `.venv` folder created earlier. 

Place any breakpoint you need, hit F5 and editor will fire up the application.