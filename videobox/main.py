import os
import sys
import logging
from pathlib import Path
from datetime import date, datetime, timedelta
from optparse import OptionParser, OptionGroup, Option, make_option
import configparser
import uuid
import subprocess
import itertools
import textwrap
from termcolor import cprint, colored
import videobox
import videobox.sync as sync
import videobox.model as model
import videobox.utilities as utilities


MIN_SEEDERS = 5
SERIES_RUNNING_DAYS = 30

package_dir = Path(__file__).parent


def running_command(args, options):
    results = model.get_running_series(options.days)
    print(
        f"Found {len(results)} series updated in the last {options.days} days:")
    initials_series = itertools.groupby(results, key=get_initial)
    for initial, series in initials_series:
        cprint(f"\n{initial}", attrs=["bold"])
        for s in series:
            print(f" · {s.sort_name}  {colored(s.network,  'light_grey')}")
    # print(f"Use {colored('videobox search name', 'light_grey')} to found out more")


def get_initial(series):
    value = (series.sort_name[0]).upper()
    if value.isalpha():
        return value
    elif value.isdigit():
        return "#"
    else:
        return "?"


def update_command(config):
    worker = sync.SyncWorker(
        config.get("api", "client_id"), progress_callback=on_update_progress, done_callback=on_update_done)
    worker.run()


def on_update_progress(message, percent=0):
    bar_remaining = "." * (int(100 - percent) // 5)
    bar_done = "#" * (int(percent) // 5)
    print(f"{bar_done}{bar_remaining} {message:40}\r", end="")


def on_update_done(message, alert):
    print(f"{message:60}")
    if alert:
        cprint(alert, "yellow")


def download_command(parser, args, options):
    query = sanitize_query(" ".join(args))
    if not query:
        parser.error("missing download query.")

    try:
        max_resolution = int(options.max_resolution.replace("p", "", 1))
    except ValueError:
        parser.error(f"unrecognized resolution {options.max_resolution}")

    download_dir = options.output_dir
    logging.debug(f"Download dir is {download_dir}")
    results = model.search_series(query)
    if len(results) == 1:
        # Single match
        series = results[0]
        releases = model.get_releases_for_series(
            series.rowid, options.season, max_resolution)
        best_releases = find_best_releases(releases)
        if options.dry_run:
            print(
                f"Ready to download {len(best_releases)} releases for {f'season {options.season} of ' if options.season else ''}series '{series.name}' into {download_dir}:\n")
        else:
            print(
                f"Start downloading {len(best_releases)} releases for {f'season {options.season} of ' if options.season else ''}series '{series.name}' into {download_dir} via aria2c...\n")

        print("Seeds  Res.   Size Name")
        cprint("-" * 80, "dark_grey")
        for _, r in best_releases:
            print_release(r)

        if not options.dry_run:
            completed_process = run_aria2(
                download_dir, [r.magnet_uri for _, r in best_releases])
    elif results:
        # Multiple matches
        print(
            f"Found {len(results)} series matching query '{query}':\n")
        for r in results:
            print(
                f" · {r.name}")
        print("\nPlease restrict your query.")
    else:
        print(
            f"No series to download matching '{query}'.")


def run_aria2(download_dir, magnet_uris):
    try:
        with open(package_dir.joinpath("trackers.txt")) as f:
            trackers = f.read()
    except FileNotFoundError as ex:
        logging.warning(
            "Could not open trackers file, using magnet URI's metadata only")
        trackers = ""

    args = [
        "aria2c",
        "--seed-time=0",
        "--allow-overwrite=false",
        f"-d {download_dir}"
    ]
    args.extend(magnet_uris)
    # Move tracker list on tail to avoid messing up things
    args.append(f"--bt-tracker={trackers}")
    # process = subprocess.run(args, capture_output=False, text=True)
    logging.debug(f"Run {' '.join(args)}")
    completed_process = subprocess.run(args)
    return completed_process


def find_best_releases(releases):
    grouped = itertools.groupby(
        releases, lambda r: r.episode.season_episode_id)
    best_releases = []
    for key, episode_releases in grouped:
        release = find_best_release_for_episode(episode_releases)
        best_releases.append((key, release))
    return best_releases


def find_best_release_for_episode(releases):
    # The higher resolution the best
    releases = sorted(releases, key=lambda r: (
        r.resolution, r.size, r.seeders), reverse=True)
    return releases[0]


def print_release(r):
    if r.seeders < MIN_SEEDERS:
        cprint(f"{r.seeders:5} {print_resolution(r.resolution, False)} {utilities.format_size(r.size)} {r.name}", "dark_grey")
    else:
        print(f"{r.seeders:5} {print_resolution(r.resolution)} {utilities.format_size(r.size)} {colored(r.name, 'light_grey')}")


def print_resolution(resolution, use_color=True):
    if use_color:
        colored_ = colored
    else:
        def colored_(x, _): return x  # Uncolored
    if resolution == 2160:
        return colored_(f"{resolution:4}p", "magenta")
    elif resolution == 1080:
        return colored_(f"{resolution:4}p", "yellow")
    elif resolution == 720:
        return colored_(f"{resolution:4}p", "cyan")
    elif resolution == 480:
        return f"{resolution:4}p"
    else:
        return "-"*5


def search_command(parser, args, options):
    query = sanitize_query(" ".join(args))
    if not query:
        parser.error("missing search query.")
    results = model.search_series(query)
    if len(results) == 1:
        today = date.today()
        # Single match
        series = model.get_series(results[0].rowid)
        tags = model.get_tags_for_series(series)
        episodes = model.get_episodes_for_series(series)
        episode_count = len(episodes)
        seasons = set([episode.season for episode in episodes])
        release_count = sum([episode.release_count for episode in episodes])
        cprint("-" * 30, "dark_grey")
        cprint(
            f"{colored(f'{series.name}', attrs=['bold'])}  {colored(series.network, 'light_grey')}")
        cprint("-" * 30, "dark_grey")
        if series.overview:
            print("\n".join(textwrap.wrap(series.overview, 60)))
        print(" ".join([colored(f"#{t.name}", "light_grey") for t in tags]))
        print(f"\nFound {len(seasons)} {plural('season', len(seasons))} with a total of {episode_count} {plural('episode', episode_count)} and {release_count} {plural('release', release_count)}:")
        for season, episodes in itertools.groupby(episodes, key=lambda e: e.season):
            cprint(f"\nSeason {season}", attrs=["bold"])
            for e in episodes:
                print_episode(e, today)
        print(f"\nMore info:")
        print(f" · {series.tvdb_url}")
        if series.imdb_url:
            print(f" · {series.imdb_url}")
    elif results:
        # Multiple matches
        print(
            f"Found {len(results)} series matching query '{query}':\n")
        for search_result in results:
            print(
                f" · {search_result.name}")
    else:
        print(
            f"No series found matching '{query}'. Perhaps try to relax the search query a little?")


def print_episode(e, today):
    aired = ""
    if e.aired_on and e.aired_on < today:
        # Past
        aired = f"Aired {utilities.datetime_since(e.aired_on, today)}"
    elif e.aired_on and e.aired_on >= today:
        # Future
        aired = f"Will air on {utilities.format_date(e.aired_on)}"
    label = f" {e.number:2} {e.name}  {colored(aired, 'light_grey')}{colored(f' with {e.release_count} releases' if e.release_count > 0 else '', 'light_grey')}"
    cprint(label)


def plural(prefix, value):
    return f"{prefix}{'s' if value > 1 else ''}"


def sanitize_query(query):
    # https://www.sqlite.org/fts5.html
    sanitized_query = ""
    for c in query:
        if c.isalpha() or c.isdigit() or ord(c) > 127 or ord(c) == 96 or ord(c) == 26:
            # Allowed in FTS queries
            sanitized_query += c
        else:
            sanitized_query += " "
    return sanitized_query


def auto_update_if_stale(config):
    last_log = model.get_last_log()
    if (not last_log) or (datetime.utcnow() - last_log.timestamp) > timedelta(days=1):
        print("Local database is stale, performing auto-update...")
        update_command(config)


def run_command(config, parser, name, args, options):
    if name == "update":
        update_command(config)
    elif name == "search":
        auto_update_if_stale(config)
        search_command(parser, args, options)
    elif name == "download":
        auto_update_if_stale(config)
        download_command(parser, args, options)
    elif name == "running":
        auto_update_if_stale(config)
        running_command(args, options)
    else:
        raise CommandNotFound()

#############
# Configuration
#############


INI_FILENAME = 'videobox.ini'


def save_config(app_dir, config):
    with open(os.path.join(app_dir, INI_FILENAME), 'w') as out:
        config.write(out)


def load_config(app_dir):
    config = configparser.ConfigParser()
    config.read(os.path.join(app_dir, INI_FILENAME))
    return config


#############
# CLI
#############

class CommandNotFound(RuntimeError):
    pass


COMMANDS = [
    ('download',    'Download all available series releases or a single season'),
    ('running',     'List all series with new releases in the last 30 days'),
    ('search',      'Search for a series by name'),
    ('update',      'Update local database')
]

EPILOG = ""
USAGE = '%prog command [options] [query]\n\n\
Available commands are:\n\n' + "\n".join(f"  {c}\t{help}" for c, help in COMMANDS)


def make_parser():
    parser = OptionParser(prog="videobox",
                          version=videobox.__version__, usage=USAGE, epilog=EPILOG)

    parser.add_option('-v', '--verbose', dest='verbose',
                      help='set logging to DEBUG level', action="store_true", default=False)

    download_options = OptionGroup(parser, "Download options")
    download_options.add_option('-s', '--season',
                                dest='season', type='int', help='download only the given season number')
    download_options.add_option('-d', '--dir',
                                dest='output_dir', help='directory to save downloaded files (default: current working directory)', default=os.getcwd())
    download_options.add_option('--dry-run',
                                dest='dry_run', help='do not download anything, just list what would be', action="store_true")
    download_options.add_option('-r', '--max-resolution',
                                dest='max_resolution', help='limit downloads to 1080p, 720p, or 480p videos (default: 2160p or highest found)', default="2160p")
    parser.add_option_group(download_options)

    search_options = OptionGroup(parser, "Search options")
    search_options.add_option('-y', '--days',
                              dest='days', type='int', help=f'show series updated since number of days (default: {SERIES_RUNNING_DAYS})', default=SERIES_RUNNING_DAYS)
    parser.add_option_group(search_options)

    return parser


def run():

    parser = make_parser()
    command_options, args = parser.parse_args()
    if not args:
        parser.error("no command given, use '-h' for full help")

    command_name, command_args = args[0].lower(), args[1:]

    app_dir = Path.home().joinpath(".videobox")
    os.makedirs(app_dir, exist_ok=True)
    log_dir = app_dir.joinpath("logs")
    os.makedirs(log_dir, exist_ok=True)

    today = date.today()
    log_filename = today.strftime("%Y-%m-%d.log")
    logging.basicConfig(filename=log_dir.joinpath(
        log_filename), level=logging.INFO)
    if videobox.DEBUG or command_options.verbose:
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        for module in ['peewee', 'requests', 'urllib3']:
            # Set higher log level for deps
            logging.getLogger(module).setLevel(logging.INFO)

    config = load_config(app_dir)
    if config.has_option("api", "client_id"):
        client_id = config.get("api", "client_id")
    else:
        # Save client ID for later use
        client_id = uuid.uuid1().hex
        config.add_section("api")
        config.set("api", "client_id", client_id)
        save_config(app_dir, config)

    model.connect(app_dir, should_setup=True)

    try:
        run_command(config, parser, command_name,
                    command_args, command_options)
    except CommandNotFound as ex:
        parser.error(
            f"unrecognized command {command_name}, use '-h' for full help")
    finally:
        model.close()
        logging.shutdown()
