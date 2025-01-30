# Videobox

Videobox is a Python web app that lets you discover and download the latest TV series without annoying ads, tracking scripts, and crypto mining stuff.

![The Videobox home page](screenshot.jpg)

## Prerequisites

Videobox requires the Python 3 programming language to be installed on your machine. If you are not familiar with it please refer to the official Python's [download page][d] for more information. 

To check if you have Python installed type the following after in your terminal prompt (`$`):

```
$ python --version 
Python 3.9.6
```

Any Python version starting from 3.9 should run Videobox just fine. 

**Note**: Videobox is a BitTorrent client so it can download series episodes without any other software. Additionally you can use your favourite BitTorrent client (like [uTorrent](https://www.utorrent.com), [Transmission](https://transmissionbt.com), etc.) with magnet links.

## Installation

You can install Videobox along with the main Python installation of your machine or in so-called "virtual environment", which is the recommended approach, since its dependencies may clash with packages you have already installed. [Learn more about virtual environments][venv]. 

Install or update Videobox from [PyPI][2] via the Python `pip` utility. Again, type the following command in your terminal:

```
$ python -m pip install -U videobox
```

## Quick start

You use Videobox via its web interface. To access it, start the `videobox` command on the terminal and point the web browser to the given URL:

```
$ videobox
Videobox has started, press CTRL+C to quit. Point your browser to http://localhost:8080 to use the web interface.
Finished library sync: added/updated 16 tags, 2770 series, 40998 episodes, and 118434 torrents.
Finished scraping 1000 of the most recently added torrents.
```

At startup Videobox updates its library and will attempt to do it again periodically.

Add `--help` to list all the available options:

```
$ videobox --help 
Usage: videobox [OPTIONS]

Options:
  --host TEXT     Hostname or IP address on which to listen. Default is
                  0.0.0.0, which means "all IP addresses on this host".
  --port INTEGER  TCP port on which to listen, default is 8080
  --help          Show this message and exit.
```

If your are interested in hacking the source code or contribute to the project see the [contributing document][contrib].

## Roadmap

This is a rough plan of what I would like to implement in the upcoming releases:

* **0.8**: Automatic episodes download.
* **0.9**: Support for "complete season" torrents.

## Credits 

[Phosphor Icons][i] created by Helena Zhang and Tobias Fried.


[1]: https://www.funkyspacemonkey.com/how-to-open-applications-from-anywhere-in-macos-sonoma
[2]: https://pypi.org/project/videobox/
[3]: https://brew.sh/
[4]: https://flask.palletsprojects.com/en/2.2.x/cli/
[i]: https://phosphoricons.com
[d]: https://www.python.org/downloads/
[l]: https://github.com/arvidn/libtorrent
[venv]: https://docs.python.org/3/library/venv.html
[contrib]: CONTRIBUTING.md
[cross]: https://github.com/ronaldoussoren/py2app/issues/523#issuecomment-2140630179