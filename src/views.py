import kivy
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.videoplayer import VideoPlayer
from kivy.properties import ObjectProperty, StringProperty, NumericProperty, ListProperty
from kivy.uix.image import AsyncImage
from kivy.uix.behaviors import ButtonBehavior
import model
#from kivy.lang import Builder
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.loader import Loader
#from kivy.uix.image import Image
import utilities
from datetime import datetime, date
from kivy.logger import Logger
import colors
from pubsub import pub
import torrenter

Window.clearcolor = colors.GRAY_900
Window.size = (1366, 768)


Loader.loading_image = 'loading.png'

MSG_SERIES_CLICKED = 'series.clicked'
MSG_EPISODE_CLICKED = 'episode.clicked'
MSG_RELEASE_CLICKED = 'release.clicked'
MSG_BACK_CLICKED = 'back.clicked'

VIEW_PLAYER = object()
VIEW_LIBRARY = object()
VIEW_SETTINGS = object()

class CardLayout(FloatLayout):

    card = NumericProperty(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        trigger = self._trigger_layout
        fbind = self.fbind
        fbind('card', trigger)
    
    def do_layout(self, *largs, **kwargs):
        super().do_layout(*largs, **kwargs)
        for index, c in enumerate(self.children):
            if index == self.card:
                c.opacity = 1
                c.disabled = False
            else:
                c.opacity = 0
                c.disabled = True


class Videobox(CardLayout):

    #current_view = ObjectProperty()

    def on_kv_post(self, base_widget):
        # @@FIXME Set library view as default for now
        #self.current_view = VIEW_LIBRARY

        #self.add_widget(VideoPlayer())
        self.add_widget(Library())

    # def on_current_view(self, instance, new_value):
    #     self.clear_widgets()
    #     if new_value is VIEW_LIBRARY:
    #         self.add_widget(Library())
    #     elif new_value is VIEW_PLAYER:
    #         self.add_widget(VideoPlayer())
    #     elif new_value is VIEW_SETTINGS:
    #         # @@TODO add settings panel
    #         pass
    #     else:
    #         pass


class Library(BoxLayout):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pub.subscribe(self.on_show_series, MSG_SERIES_CLICKED)
        pub.subscribe(self.on_show_episode, MSG_EPISODE_CLICKED)
        #pub.subscribe(self.on_start_download, MSG_RELEASE_CLICKED)
        pub.subscribe(self.on_back, MSG_BACK_CLICKED)

    def on_show_series(self, tvdb_id):
        detail_widget = SeriesDetail(id=tvdb_id)
        self.ids.home_nav.add_widget(detail_widget)
        self.ids.home_nav.page += 1

    def on_show_episode(self, tvdb_id):
        detail_widget = EpisodeDetail(id=tvdb_id)
        self.ids.home_nav.add_widget(detail_widget)
        self.ids.home_nav.page += 1

    # def on_start_download(self, id):
    #     release = model.get_release(id)
    #     self.app.torrenter.add_torrent(release.magnet_uri)

    # def on_back_completed(self, animation, widget):
    #     # Throw away current widget
    #     Logger.debug(f"on_complete {widget}!")

    def on_back(self):
        index = self.ids.home_nav.page
        nav = self.ids.home_nav
        if index:
            # current_widget = nav.children[0]
            # current_widget.bind(on_complete=self.on_back_completed)
            nav.page -= 1


class Home(GridLayout):
    featured_series = ObjectProperty()
    new_series = ObjectProperty()
    running_series = ObjectProperty()

    def on_kv_post(self, base_widget):
        self.featured_series = model.get_featured_series(2)[:12]
        self.new_series = model.get_new_series(7)[:6]
        self.running_series = model.get_updated_series(7)[:12]

    def on_featured_series(self, instance, new_list):
        self.update_grid(self.featured_grid, new_list)

    def on_new_series(self, instance, new_list):
        self.update_grid(self.new_grid, new_list)

    def on_running_series(self, instance, new_list):
        self.update_grid(self.running_grid, new_list)

    def update_grid(self, grid, new_list):
        grid.clear_widgets()
        for series in new_list:
            grid.add_widget(SeriesThumbnail(id=series.tvdb_id,
                            poster_url=series.poster_url, label=series.name))


class ImageButton(ButtonBehavior, AsyncImage):
    """
    A clickable image loaded via HTTP
    """
    pass


class LabelButton(Button):
    """
    Button with a simple label
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(mouse_pos=self.on_hover)

    def on_hover(self, window, mouse_pos):
        relative_pos = self.to_parent(
            *self.to_widget(*mouse_pos, relative=True), relative=True)
        if self.collide_point(*relative_pos):
            self.color = colors.WHITE
        else:
            self.color = colors.GRAY_200


class SeriesThumbnail(GridLayout):
    id = NumericProperty()
    poster_url = StringProperty()
    label = StringProperty()

    def on_series_clicked(self):
        pub.sendMessage(MSG_SERIES_CLICKED, tvdb_id=self.id)


class EpisodeListItem(BoxLayout):
    id = NumericProperty()
    name = StringProperty()
    aired_on = StringProperty()

    def on_episode_clicked(self):
        pub.sendMessage(MSG_EPISODE_CLICKED, tvdb_id=self.id)


class SeriesDetail(BoxLayout):
    id = NumericProperty()
    name = StringProperty()
    network = StringProperty()
    overview = StringProperty()
    poster_url = StringProperty()
    episodes = ListProperty()

    def on_kv_post(self, base_widget):
        series = model.get_series(self.id)
        self.poster_url = series.poster_url
        self.network = series.network.upper()
        self.name = series.name
        self.overview = series.overview
        self.episodes = series.episodes

    def on_back_clicked(self):
        pub.sendMessage(MSG_BACK_CLICKED)

    def on_episodes(self, instance, new_list):
        today = date.today()
        self.episode_list.clear_widgets()
        for episode in new_list:
            label = ""
            if episode.aired_on and episode.aired_on < today:
                # Past
                label = f"First aired on {utilities.datetime_since(episode.aired_on, today)}"
            elif episode.aired_on and episode.aired_on >= today:
                # Future
                label = f"[i]Will air on {utilities.format_date(episode.aired_on)}[/i]"

            self.episode_list.add_widget(
                EpisodeListItem(id=episode.tvdb_id, name=episode.name, aired_on=label))


class EpisodeDetail(BoxLayout):
    id = NumericProperty()
    name = StringProperty()
    overview = StringProperty()
    thumbnail_url = StringProperty()
    releases = ListProperty()

    def on_kv_post(self, base_widget):
        episode = model.get_episode(self.id)
        self.thumbnail_url = episode.thumbnail_url
        self.name = f"{episode.season_episode_id} {episode.name}"
        self.overview = episode.overview
        self.releases = episode.releases

    def on_back_clicked(self):
        pub.sendMessage(MSG_BACK_CLICKED)

    def on_releases(self, instance, new_list):
        now = datetime.now()
        self.release_list.clear_widgets()

        for release in new_list:
            self.release_list.add_widget(
                ReleaseListItem(id=release.id, name=release.name,
                                torrent_size=release.size, seeds=release.seeds,  added_on=release.added_on))


class ReleaseListItem(BoxLayout):
    id = NumericProperty()
    name = StringProperty()
    seeds = NumericProperty()
    added_on = StringProperty()
    torrent_size = NumericProperty()


class Transfers(BoxLayout):
    transfers = ListProperty()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pub.subscribe(self.on_torrent_update, torrenter.MSG_TORRENT_UPDATE)

    def on_torrent_update(self, torrents):
        self.transfers = torrents

    def on_kv_post(self, base_widget):
        self.transfers = []

    def on_transfers(self, instance, new_list):
        self.transfer_list.clear_widgets()
        for transfer in new_list:
            self.transfer_list.add_widget(
                TransferListItem(name=transfer.name, progress=transfer.progress, stats=transfer.stats))


class TransferListItem(BoxLayout):
    name = StringProperty()
    progress = NumericProperty()
    stats = StringProperty()
