import operator
from functools import reduce
from datetime import datetime, date, timedelta, timezone
from peewee import fn
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

def get_top_tags(limit):
    return (Episode.select(Episode, Tag.name.alias('tag_name'), Tag.slug.alias("tag_slug"))
            .join(Series)
            .join(SeriesTag)
            .join(Tag)
            .where((Tag.type == TAG_GENRE) & (Episode.thumbnail_url != ''))
            .group_by(Tag.slug)
            .order_by(fn.Count(Series.id.distinct()).desc())
            # Do not show empty tags
            .having(fn.Count(Series.id.distinct()) > 0)
            .limit(limit)
            .objects()
            )

def get_series_subquery():
    SeriesAlias = Series.alias()
    return (SeriesAlias.select(SeriesAlias.id, fn.Max(Episode.season).alias("max_season"))
            .join(Episode)
            .group_by(SeriesAlias.id))


def get_featured_series(exclude_ids, days_interval):
    series_subquery = get_series_subquery()
    return (Series.select(Series, fn.Sum(Release.completed).alias('total_completed'))
            .join(Episode)
            .join(Release)
            .join(series_subquery, on=(
                series_subquery.c.id == Series.id))
            # Consider episodes from last season only and releases within interval days
            .where(~(Series.id << exclude_ids) & 
                   (Episode.season == series_subquery.c.max_season) &
                   (Release.added_on > (date.today() - timedelta(days=days_interval))))
            .group_by(Series)
            .order_by(fn.Sum(Release.completed).desc())
            )


def get_today_series(limit):
    series_subquery = get_series_subquery()
    return (Series.select(Series, Episode, fn.SUM(Release.completed).alias('total_completed'))
            .join(Episode)
            .join(Release)
            .join(series_subquery, on=(
                series_subquery.c.id == Series.id))
            # Consider episodes from last season only and releases within the past 24h
            .where((Episode.season == series_subquery.c.max_season) &
                   (Episode.thumbnail_url != '') &
                   # @@TODO do not user current time, figure out max added_on and compute from it
                   (Release.added_on > (datetime.now(timezone.utc) - timedelta(hours=24))))
            .order_by(fn.Sum(Release.completed).desc())
            .group_by(Series.id)
            #.get_or_none()
            .limit(limit)
            )

def get_followed_series(days=None):
    series_subquery = get_series_subquery()
    where_clauses = [
        # Only episodes from the last season        
        (Episode.season == series_subquery.c.max_season),
        (fn.strftime('%Y-%m-%d', Release.added_on) >= Series.followed_since)
    ]
    if days:
        min_date = date.today() - timedelta(days=days)
        where_clauses.append((fn.strftime('%Y-%m-%d', Release.added_on) > min_date))
    q = (Series.select(Series, Episode, fn.strftime('%Y-%m-%d', Release.added_on).alias("added_on_date"), fn.Count(Release.id).alias("release_count"))
         .join(Episode)
         .join(Release)
         .join(series_subquery, on=(
             series_subquery.c.id == Series.id))
         # Chain all conditions together AND'ing them 
         #  https://github.com/coleifer/peewee/issues/391#issuecomment-468042229
         .where(reduce(operator.and_, where_clauses))
         .group_by(Episode.id)
         # Make sure series' releases are one after another when listing
         .order_by(fn.strftime('%Y-%m-%d', Release.added_on).desc(), Series.id)
         )    
    return q

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


def get_series_for_tag(tag, sorting):
    # TODO https://michaelsoolee.com/case-insensitive-sorting-sqlite/
    # https://stackoverflow.com/questions/27051013/using-collate-on-peewee-queries
    # https://github.com/coleifer/peewee/issues/1111
    #sort_name_collated = Clause(Series.sort_name, SQL('COLLATE NOCASE'))
    sorting_expr = Series.sort_name
    if sorting == 'popularity':
        sorting_expr = Series.popularity.desc()
    elif sorting == 'desc':
        sorting_expr = Series.sort_name.desc()

    subquery = get_series_subquery()
    return (Series.select(Series)
            .join(SeriesTag)
            .switch(Series)
            .join(Episode)
            .join(Release)
            .join(subquery, on=(
                subquery.c.id == Series.id))
            .where((SeriesTag.tag == tag) & (subquery.c.max_season-Episode.season < MAX_SEASONS))
            .order_by(sorting_expr)
            .group_by(Series.id)
            )


def get_series_for_language(language):
    subquery = get_series_subquery()
    return (Series.select(Series)
            .switch(Series)
            .join(Episode)
            .join(Release)
            .join(subquery, on=(
                subquery.c.id == Series.id))
            .where((Series.language == language) & (subquery.c.max_season-Episode.season < MAX_SEASONS))
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
    return SeriesIndex.search(f"{query}*", 
                              weights={SeriesIndex.name: 2.0, SeriesIndex.content: 1.0})


def suggest_series(query):
    query = (SeriesIndex
             .select(SeriesIndex, SeriesIndex.bm25().alias('search_score'))
             .where(SeriesIndex.name.match(f"{query}*"))
             .order_by(SeriesIndex.bm25()))
    return query
