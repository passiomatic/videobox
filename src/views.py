from abc import abstractmethod
import kivy
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty, StringProperty, NumericProperty, ListProperty
from kivy.uix.image import AsyncImage
from kivy.uix.behaviors import ButtonBehavior
import logging
import model
from kivy.lang import Builder
from kivy.core.window  import Window
from kivy.clock import Clock

Window.clearcolor = (.2, .2, .2, 1) # Dark gray
Window.size = (1240, 700)

class Videobox(BoxLayout):

    def show_series_detail(self, id):
        series = model.get_series(id)
        detail_widget = SeriesDetail(id=series.tvdb_id, name=series.name, poster_url=series.poster_url,
                                     network=series.network.upper(), overview=series.overview)
        self.ids.home_nav.add_widget(detail_widget)

class DataWidget(object):

    def __init__(self):
        # Call on next frame
        Clock.schedule_once(self.on_ready, 0)        

    #@abstractmethod
    def on_ready(self):
        raise Exception("DataWidget subclass must override on_ready()")

class Home(BoxLayout):
    featured_series = ObjectProperty()
    new_series = ObjectProperty()
    running_series = ObjectProperty()

    featured_grid = ObjectProperty(None)
    new_grid = ObjectProperty(None)
    running_grid = ObjectProperty(None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)        
        # Call on next frame
        Clock.schedule_once(self.on_ready, 0)
        
    def on_ready(self, dt):
        self.featured_series = model.get_featured_series(2)[:12]
        self.new_series = model.get_new_series(7)[:6]
        self.running_series = model.get_updated_series(7)[:12]

    def on_featured_series(self, instance, featured_series):
        self.update_grid(self.featured_grid, featured_series)

    def on_new_series(self, instance, new_series):
        self.update_grid(self.new_grid, new_series)

    def on_running_series(self, instance, running_series):
        self.update_grid(self.running_grid, running_series)

    def update_grid(self, grid, series_list):
        grid.clear_widgets()
        for series in series_list:
            grid.add_widget(SeriesThumbnail(id=series.tvdb_id,
                            poster_url=series.poster_url, label=series.name))

class Imagebutton(ButtonBehavior, AsyncImage):
    """
    A clickable image loaded via HTTP
    """
    pass


class SeriesThumbnail(BoxLayout):
    id = NumericProperty()
    poster_url = StringProperty()
    label = StringProperty()

    def show_series_detail(self):
        logging.info(f"Clicked show_series_detail {self.id}")


class SeriesDetail(BoxLayout):
    id = NumericProperty()
    poster_url = StringProperty()
    network = StringProperty()
    name = StringProperty()
    overview = StringProperty()

    # def show_episode_detail(self):
    #     logging.info(f"Clicked show_episode_detail {self.id}")
