# Videobox

Videobox is a Python program that lets you download latest TV series via a quick and simple command-line interface.

If you would like to hack the source code read the _Contributing_ section below.

## Install 

You can install Videobox from [PyPI][2] via the `pip` utility:

```
python -m pip install videobox
```

The install procedure will also create a `videobox` command, available in your terminal. For example, if you installed Python on macOS via [homebrew][3] the command will live in `/opt/homebrew/bin/videobox`.

Currently Videobox requires [aria2][1] to download contents. Please check aria2 documentation to install it on your machine.

## Quick guide

First, tell Videobox to update its local database:

```
$ videobox update
First run: import running series... 
(...)
```

**Note**: Videobox will auto-update itself if local database hasn't been refreshed for a while.

Find out what series are running:

```
$ videobox running -y7
Found 84 series updated in the last 7 days:
(...)
N
 · NCIS  CBS
 · NCIS: Hawai'i  CBS
 · NCIS: Los Angeles  CBS
```

Find out more about a specific series:

```
$ videobox search ncis los angeles
------------------------------
NCIS: Los Angeles  CBS
------------------------------
NCIS: Los Angeles is a drama about the high stakes world of
undercover surveillance at the Office of Special Projects
(...)
#Action #Adventure #Crime #Drama

Found 1 season with a total of 15 episodes and 92 releases:

Season 14
  1 Game of Drones  Aired 3 months ago, with 8 releases
  2 Of Value  Aired 2 months ago, with 11 releases
  3 The Body Stitchers  Aired 2 months ago, with 9 releases
(...)
 15 TBA  Will air on Mar. 05, 2023

More series info at <https://thetvdb.com/series/ncis-los-angeles>
```

Download a whole series season without headaches:

```
$ videobox download ncis los angeles -s14 --dry-run
Ready to download 10 releases for series 'NCIS: Los Angeles':

Seeds  Res. Size   Name
--------------------------------------------------------------------------------
  128 1080p 2.15GB ncis.los.angeles.s14e01.1080p.web.h264-glhf[eztv.re].mkv
  198 1080p 2.15GB NCIS.Los.Angeles.S14E02.1080p.WEB.h264-GOSSIP[eztv.re].mkv
  209 1080p 2.15GB NCIS.Los.Angeles.S14E03.1080p.WEB.h264-GOSSIP[eztv.re].mkv
(...)
   90  720p 1.41GB NCIS.Los.Angeles.S14E10.720p.WEB.h264-KOGi[eztv.re].mkv
```

## Motivation 

I've seen too many torrent web sites full of tracking scripts, pop-ups windows and crypto mining to remember. In the past years I've built a number of scripts to scrape such sites and now it's time to put all together in a coherent way. 

## Contributing

### Setup the environment

Starting from the repo root you might want to create a new virtual environment, to avoid messing up pre-existing Pyhton packages on your machine: 

`make venv`

And activate it:

`source .venv/bin/activate`

Then, install all project dependencies into the virtual enviroment just created:

`make install-deps`

When you are done you can exit the virtual enviroment with the `deactivate` command.

### Where to find Videobox data

Videobox stores local database and settings in `~/.videobox`. The directory will look something like this:

```
.videobox/
  library.db
  logs/
    2023-01-24.log
    2023-01-25.log
    ...
  videobox.ini
```

### Using the debugger with Visual Studio Code

Debug works just fine under Visual Studio Code once you pick the Python interpreter shown in the `.venv` folder created earlier. 

Place any breakpoint you need, hit F5 and editor will fire up the application.


[1]: https://aria2.github.io
[2]: https://pypi.org/project/videobox/
[3]: https://brew.sh/