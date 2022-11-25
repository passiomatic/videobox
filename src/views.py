from abc import abstractmethod
import kivy
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty, StringProperty, NumericProperty, ListProperty
from kivy.uix.image import AsyncImage
from kivy.uix.behaviors import ButtonBehavior
import model
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.loader import Loader
from kivy.uix.image import Image
import utilities
from datetime import datetime, date
from kivy.logger import Logger
import colors

Window.clearcolor = colors.GRAY_800
Window.size = (1240, 700)

Loader.loading_image = 'loading.png'

class DataWidget(object):

    def __init__(self):
        # Call on next frame when Kivy is ready
        Clock.schedule_once(self.on_ready, 0)

    def on_ready(self, dt):
        raise Exception("DataWidget subclass must override on_ready()")


class Videobox(BoxLayout):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register_event_type('on_show_series')

    def on_show_series(self, id):
        series = model.get_series(id)
        detail_widget = SeriesDetail(id=series.tvdb_id, name=series.name, poster_url=series.poster_url,
                                     network=series.network.upper(), overview=series.overview)
        self.ids.home_nav.add_widget(detail_widget)

    def on_back():
        #self.ids.home_nav.remove_widget()
        pass

class Home(BoxLayout):
    featured_series = ObjectProperty()
    new_series = ObjectProperty()
    running_series = ObjectProperty()

    def on_kv_post(self, base_widget):
        self.featured_series = model.get_featured_series(2)[:12]
        self.new_series = model.get_new_series(7)[:6]
        self.running_series = model.get_updated_series(7)[:12]
        Logger.debug("Home on_kv_post")

    def on_featured_series(self, instance, featured_series):
        self.update_grid(self.featured_grid, featured_series)

    # def on_new_series(self, instance, new_series):
    #     self.update_grid(self.new_grid, new_series)

    # def on_running_series(self, instance, running_series):
    #     self.update_grid(self.running_grid, running_series)

    def update_grid(self, grid, series_list):
        grid.clear_widgets()
        for series in series_list:
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
        relative_pos = self.to_parent(*self.to_widget(*mouse_pos, relative=True), relative=True)
        if self.collide_point(*relative_pos):
            self.color = colors.WHITE
        else: 
            self.color = colors.GRAY_200


class SeriesThumbnail(BoxLayout):
    id = NumericProperty()
    poster_url = StringProperty()
    label = StringProperty()


class EpisodeItem(BoxLayout):
    name = StringProperty()
    on_air = StringProperty()

class SeriesDetail(BoxLayout, DataWidget):
    id = NumericProperty()
    poster_url = StringProperty()
    network = StringProperty()
    name = StringProperty()
    overview = StringProperty()
    episodes = ListProperty()

    def on_kv_post(self, base_widget):
        series = model.get_series(self.id)
        self.poster_url = series.poster_url
        self.network = series.network
        self.name = series.name
        self.episodes = series.episodes

    def on_episodes(self, instance, episodes_list):
        today = date.today()
        self.episode_list.clear_widgets()
        for episode in self.episodes:
            label = ""
            if episode.aired_on and episode.aired_on < today:
                # Past
                label = f"First aired on {utilities.datetime_since(episode.aired_on, today)}"
            elif episode.aired_on and episode.aired_on >= today:
                # Future 
                label = f"Will air on {utilities.format_date(episode.aired_on)}"

            self.episode_list.add_widget(EpisodeItem(name=episode.name, on_air=label))


