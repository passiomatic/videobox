from peewee import *
import configuration
from urllib.parse import urljoin, urlparse, parse_qs


DEFAULT_POSTER = "_images/poster-placeholder.png"
DEFAULT_THUMBNAIL = "_images/thumbnail-placeholder.png"

ARTWORK_BASE_URL= 'https://tv.passiomatic.com'

if configuration.DATABASE_FILENAME:
  db = SqliteDatabase(configuration.DATABASE_FILENAME)
else:
  db = MySQLDatabase(
    configuration.DATABASE_NAME 
    , user=configuration.DATABASE_USER
    , password=configuration.DATABASE_PASSWORD
    , host=configuration.DATABASE_HOST
  )

class BaseModel(Model):
  class Meta:
      database = db  

class Series(BaseModel):
    tvdb_id = IntegerField(unique=True)  
    imdb_id = CharField(default="") # E.g. tt123456
    name = CharField()
    sort_name = CharField()
    slug = CharField()
    poster = CharField(default="")
    fanart = CharField(default="")
    language = CharField(max_length=2, default="en") # ISO code for matched series language in TVDb 
    overview = TextField()
    network = CharField(default="")
    status = FixedCharField(max_length=1, default="C")
    status_changed_on = DateTimeField()

    @property
    def poster_filename(self):
      if self.poster:    
        return "/".join([self.slug, 'poster.jpg'])
      else:
        return DEFAULT_POSTER

    @property
    def thumbnail_filename(self):
      if self.poster:    
        return "/".join([self.slug, 'thumbnail.jpg'])
      else:
        return DEFAULT_THUMBNAIL

    @property
    def poster_url(self):
      if self.poster:    
        return "/".join([ARTWORK_BASE_URL, self.slug, 'poster.jpg'])
      else:
        return ""

    @property
    def original_poster_url(self):
      if self.poster:    
        return urljoin(configuration.IMAGE_BASE_URL, self.poster)
      else:
        return ""

    @property
    def thumbnail_url(self):
      if self.poster:    
        return "/".join([ARTWORK_BASE_URL, self.slug, 'thumbnail.jpg'])
      else:
        return ""

    @property
    def fanart_url(self):
      if self.fanart:    
        return "/".join([ARTWORK_BASE_URL, self.slug, 'fanart.jpg'])
      else:
        return ""

    def __str__(self):
      return f"'{self.name}'"   


class Tag(BaseModel):
    name = CharField()
    slug = CharField(unique=True)    

    def __str__(self):
      return f"'{self.name}'"   

class SeriesTag(BaseModel):
    series = ForeignKeyField(Series, on_delete="CASCADE")
    tag = ForeignKeyField(Tag, on_delete="CASCADE")

    class Meta:
        indexes = (
            (('series', 'tag'), True),
        )

class Episode(BaseModel):
    series = ForeignKeyField(Series, backref='episodes', on_delete="CASCADE")
    
    tvdb_id = IntegerField(unique=True)     
    name = CharField()              # TVDb episodeName
    season = SmallIntegerField()    # TVDb airedSeason 
    number = SmallIntegerField()    # TVDb airedEpisodeNumber
    aired_on = DateField(null=True) # TVDB firstAired, can be in the future
    overview = TextField(default="") # TVDB overview
    thumbnail = CharField(default="") # TBDB episode thumbnail

    @property
    def thumbnail_url(self):
      if self.poster:    
        return "/".join([ARTWORK_BASE_URL, self.slug, f'thumbnail-{self.season_episode_id}.jpg'])
      else:
        return ""

    @property
    def season_episode_id(self):
      return f"S{self.season:02}E{self.number:02}"
      
    def __str__(self):
      return f"{self.season_episode_id} '{self.name}'"   

    # TODO
    # class Meta:
    #     indexes = (
    #         (('series', 'season', 'number'), True),
    #     )


class Release(BaseModel):
    episode = ForeignKeyField(Episode, backref='releases', on_delete="CASCADE")
    added_on = DateTimeField()
    tracked_on = DateTimeField()
    size = BigIntegerField()
    magnet_uri = TextField()
    seeds = IntegerField()
    leeches = IntegerField()      
    uploader = CharField()
    original_name = CharField()
    info_hash = CharField(unique=True)    

    def __str__(self):
      return self.original_name 

    @property
    def resolution(self):
        if "2160p" in self.original_name.lower():
          return "2160p"
        elif "1080p" in self.original_name.lower():
          return "1080p"
        elif "720p" in self.original_name.lower():
          return "720p"
        else:
          return ""

    @property
    def trackers(self):
        parsed = urlparse(self.magnet_uri)
        try:
            return parse_qs(parsed.query)['tr']
        except KeyError:
            return []

    # @property
    # def guid(self):
    #     return ("tag:tv.passiomatic.com,2022:/torrent/%s" % self.info_hash.lower())


# class DateTimeTZField(DateTimeField):
#     def python_value(self, value):
#         if value is None: return
#         datetime_str, zone = value.rsplit(' ', 1)  # Expected YYYY-mm-dd HH:MM:SS.ffffff ZZZZ
#         val = datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f')
#         if zone.startswith('-'):
#             mult = -1
#             zone = zone[1:]
#         else:
#             mult = 1
#         zh, zm = int(zone[:2]), int(zone[2:])
#         offset = FixedOffset(mult * (zh * 60 + zm))
#         return val.replace(tzinfo=offset)
# 
#     def db_value(self, value):
#         return value.strftime('%Y-%m-%d %H:%M:%S.%f %z') if value else None


TAGS = [ ("action",  "Action")
,("adventure",  "Adventure"  )
,("animation",      "Animation"  )
,("anime",      "Anime"  )
,("children",      "Children"  )
,("comedy",      "Comedy"  )
,("crime",      "Crime"  )
,("documentary",      "Documentary"  )
,("drama",      "Drama"  )
,("family",      "Family"  )
,("fantasy",      "Fantasy"  )
,("food",      "Food"  )
,("game-show",      "Game Show"  )
,("home-and-garden",      "Home and Garden"  )
,("horror",      "Horror"  )
,("mini-series",      "Mini-Series"  )
,("mystery",      "Mystery"  )
,("news",      "News"  )
,("reality",      "Reality"  )
,("romance",      "Romance"  )
,("science-fiction",      "Science-Fiction"  )
,("soap",      "Soap"  )
,("special-interest",      "Special Interest"  )
,("sport",      "Sport"  )
,("suspense",      "Suspense"  )
,("talk Show",      "Talk Show"  )
,("thriller",      "Thriller"  )
,("travel",      "Travel"  )
,("western",    "Western")
]

def setup():  
  db.create_tables([
    Series, 
    Episode, 
    Release,
    Tag,
    SeriesTag
  ])

def add_tags(series, tags):
  for name in tags:
    try:
      tag = Tag.get(Tag.name == name.strip())
      SeriesTag.create(tag=tag, series=series)
    except DoesNotExist:
      print(f"Tag {name} not found, skipped")
      continue

if __name__ == "__main__":    
    db.connect()
    setup()
    for (slug, name) in TAGS:
        Tag.create(slug=slug, name=name)
    # for series in Series.select():
    #     add_tags(series, series.genre.split(",")) 

    db.close()