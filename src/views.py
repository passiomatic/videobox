import kivy
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ObjectProperty, NumericProperty
from kivy.uix.image import AsyncImage
from kivy.uix.behaviors import ButtonBehavior
import logging
import model


class Videobox(BoxLayout):

    def show_series_detail(self, id):
        series = model.get_series(id)
        detail_widget = SeriesDetail(id=series.tvdb_id, name=series.name, poster_url=series.poster_url,
                                     network=series.network.upper(), overview=series.overview)
        self.ids.home_nav.add_widget(detail_widget)


class Home(GridLayout):
    featured_series = ObjectProperty()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.featured_series = model.get_featured_series(7)[:12]
        self.update()

    def update(self):
        for series in self.featured_series:
            self.add_widget(SeriesThumbnail(id=series.tvdb_id,
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
