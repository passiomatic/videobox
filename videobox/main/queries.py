from datetime import datetime, date, timezone, timedelta
from flask import Flask
from peewee import fn, Window
from videobox.models import Series, Episode, Release, Tag, SeriesTag, SeriesIndex, TAG_GENRE

MAX_SEASONS = 2

def get_series_tags(series):
    return (Tag
            .select()
            .join(SeriesTag)
            .join(Series)
            .where((Series.id == series.id) & (Tag.type == TAG_GENRE)))    

def get_library_stats():
    # Make sure we grab series and episodes with at least one release
    return (Series.select(fn.Count(Series.id.distinct()), fn.Count(Episode.id.distinct()), fn.Count(Release.id.distinct()))
            .join(Episode)
            .join(Release).scalar(as_tuple=True))

def get_nav_tags(limit):
    return (Tag.select(Tag, fn.Count(Series.id.distinct()).alias('series_count'))
            .join(SeriesTag)
            .join(Series)
            .where((Tag.type == TAG_GENRE))
            .group_by(Tag.slug)
            .order_by(fn.Count(Series.id.distinct()).desc())
            .having(fn.Count(Series.id.distinct()) > 0)
            .limit(limit)
            )

def get_series_subquery():
    SeriesAlias = Series.alias()
    return (SeriesAlias.select(SeriesAlias.id, fn.Max(Episode.season).alias("max_season"))
            .join(Episode)
            .group_by(SeriesAlias.id))


def get_featured_series(exclude_ids, days_interval):
    series_subquery = get_series_subquery()
    return (Series.select(Series, fn.SUM(Release.completed).alias('total_completed'))
            .join(Episode)
            .join(Release)
            .join(series_subquery, on=(
                series_subquery.c.id == Series.id))
            # Consider episodes from last season only and releases within interval days
            .where(~(Series.id << exclude_ids) & 
                   (Episode.season == series_subquery.c.max_season) &
                   (Release.added_on > (date.today() - timedelta(days=days_interval))))
            .group_by(Series)
            .order_by(fn.SUM(Release.completed).desc())
            )


def get_today_series():
    series_subquery = get_series_subquery()
    return (Series.select(Series, Episode.id, Episode.season, Episode.number, Episode.name, Episode.overview, Episode.aired_on, Episode.thumbnail_url, fn.SUM(Release.completed).alias('total_completed'))
            .join(Episode)
            .join(Release)
            .join(series_subquery, on=(
                series_subquery.c.id == Series.id))
            # Consider episodes from last season only and releases within the past 24h
            .where((Episode.season == series_subquery.c.max_season) &
                   (Episode.thumbnail_url != '') &
                   (Release.added_on > (datetime.utcnow() - timedelta(hours=24))))
            .order_by(fn.SUM(Release.completed).desc())
            .group_by(Series.id)
            .get_or_none()
            )


def get_top_series_for_tags():
    # Grab all tags and associated series with releases for the last two seasons
    subquery = get_series_subquery()
    return (Series.select(Series, Tag.slug.alias('tag_slug'), Tag.name.alias('tag_name'))
            .join(SeriesTag)
            .join(Tag)
            .switch(Series)
            .join(Episode)
            .join(Release)
            .join(subquery, on=(
                subquery.c.id == Series.id))
            .where((Tag.type == TAG_GENRE) & (subquery.c.max_season-Episode.season < MAX_SEASONS))
            .group_by(Tag.name, Series.id)
            .order_by(Tag.name, Series.popularity.desc())
            # Reconstruct objects graph 
            .objects()
            )


def get_series_for_tag(tag):
    subquery = get_series_subquery()
    return (Series.select(Series)
            .join(SeriesTag)
            .switch(Series)
            .join(Episode)
            .join(Release)
            .join(subquery, on=(
                subquery.c.id == Series.id))
            .where((SeriesTag.tag == tag) & (subquery.c.max_season-Episode.season < MAX_SEASONS))
            .order_by(fn.Lower(Series.sort_name))
            .group_by(Series.id)
            )




def release_cte(resolution, size_sorting):
    if size_sorting == "asc":
        aggr_fn = fn.Min(Release.size).alias("size")
    elif size_sorting == "desc":
        aggr_fn= fn.Max(Release.size).alias("size")
    else:
        # Default to sorting by seeders
        aggr_fn = fn.Max(Release.seeders).alias("max_seeders") 

    query = (Release.select(Release.id.alias('release_id'), aggr_fn)
             .join(Episode)
             .where((Release.resolution == resolution) if resolution else True)
             .group_by(Episode.id)
             .cte('best_release'))
    return query


def get_series_with_ids(ids):
    return (Series.select()
            .where(Series.id.in_(ids))
            # .order_by(Series.id)
            )

# ------------
# Search
# ------------

def search_series(query):
    #return SeriesIndex.search(f"{query}*", weights={'name': 1.0, 'content': 0.1}), with_score=True, score_alias='search_score')
    return SeriesIndex.search(f"{query}*", weights={'name': 1.0, 'content': 0.1})


def suggest_series(query):
    query = (SeriesIndex
             .select(SeriesIndex, SeriesIndex.bm25().alias('search_score'))
             .where(SeriesIndex.name.match(f"{query}*"))
             .order_by(SeriesIndex.bm25()))
    return query
