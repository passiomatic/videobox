# Videobox

Videobox is a Python web app that lets you discover and download the latest TV series.

![Videobox detail page](https://videobox.passiomatic.com/screenshot-0.5.jpg?1)

## Prerequisites

Videobox requires the Python 3 programming language to be installed on your machine. If you are not familiar with it please refer to the official Python's [download page][d] for more information. 

To check if you have Python installed type the following after in your terminal prompt (`$`):

```
$ python --version 
Python 3.9.6
```

Any Python version starting from 3.9 should run Videobox just fine. 

**Note**: currently Videobox requires an external BitTorrent client ([uTorrent](https://www.utorrent.com), [Transmission](https://transmissionbt.com), etc.) to download video files.


## Install 

You can install Videobox from [PyPI][2] via the Python `pip` utility. Again, type the following command in your terminal:

```
$ python -m pip install videobox
```

The install procedure will also create a `videobox` command, available in your terminal. 

## Quick start

You use Videobox via its web interface. To access it you start the `videobox` command on the terminal and point your web browser to the given URL:

```
$ videobox
Server started. Point your browser to http://0.0.0.0:8080 to use the web interface.
```

Once the page is loaded Videobox will ask you to update your library by clicking the update button 🔄.

## Additional command-line options

Add `--help` to list all the available options:

```
$ videobox --help 
Usage: videobox [OPTIONS]

Options:
  --host TEXT     Hostname or IP address on which to listen, default is
                  0.0.0.0, which means "all IP addresses on this host".
  --port INTEGER  TCP port on which to listen, default is 8080
  --help          Show this message and exit.
```

## Roadmap

This is a rough plan of what I would like to implement in the upcoming releases:

* **0.6**: Ability to "follow" series.
* **0.7**: [libtorrent][l] integration.

## Motivation 

I've seen too many torrent web sites full of tracking scripts, pop-ups windows and crypto mining to remember. In the past years I've built a number of scripts to scrape such sites and now it's time to put all together in a coherent way. 

## Credits 

[Phosphor Icons][i] created by Helena Zhang and Tobias Fried.

## Contributing

If you would like to help with the Videobox development these are some essential steps to get you started.

### Setup the environment

Starting from the repo root you might want to create a new virtual environment, to avoid messing up pre-existing Pyhton packages on your machine: 

`make venv`

And activate it:

`source .venv/bin/activate`

Then, install all project dependencies into the virtual enviroment just created:

`make install-deps`

Finally, run the web interface in debug mode:

`make`

When you are done you can exit the virtual enviroment with the `deactivate` command.

### Where to find Videobox data

Videobox stores local database and settings in `~/.videobox`. The directory will look something like this:

```
.videobox/
  library.db
  config.toml
```

### Using the debugger with Visual Studio Code

Debug works just fine under Visual Studio Code once you pick the Python interpreter shown in the `.venv` folder created earlier. 

Place any breakpoint you need, hit F5 and editor will fire up the application.


[1]: https://aria2.github.io
[2]: https://pypi.org/project/videobox/
[3]: https://brew.sh/
[4]: https://flask.palletsprojects.com/en/2.2.x/cli/
[i]: https://phosphoricons.com
[d]: https://www.python.org/downloads/
[l]: https://github.com/arvidn/libtorrent