"""Peewee migrations -- 001_init.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']            # Return model in current state by name
    > Model = migrator.ModelClass                   # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.run(func, *args, **kwargs)           # Run python function with the given args
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""
    
    @migrator.create_model
    class Series(pw.Model):
        id = pw.AutoField()
        tmdb_id = pw.IntegerField(unique=True)
        imdb_id = pw.CharField(default='', max_length=255)
        name = pw.CharField(max_length=255)
        sort_name = pw.CharField(max_length=255)
        tagline = pw.CharField(default='', max_length=255)
        slug = pw.CharField(max_length=255)
        overview = pw.TextField()
        network = pw.CharField(default='', max_length=255)
        poster_url = pw.CharField(default='', max_length=255)
        fanart_url = pw.CharField(default='', max_length=255)
        vote_average = pw.FloatField(default=0.0)
        popularity = pw.FloatField(default=0.0)
        status = pw.FixedCharField()
        language = pw.CharField(max_length=2)
        last_updated_on = pw.DateTimeField()

        class Meta:
            table_name = "series"

    @migrator.create_model
    class Episode(pw.Model):
        id = pw.AutoField()
        tmdb_id = pw.IntegerField()
        series = pw.ForeignKeyField(column_name='series_id', field='id', model=migrator.orm['series'], on_delete='CASCADE')
        name = pw.CharField(max_length=255)
        season = pw.SmallIntegerField()
        number = pw.SmallIntegerField()
        aired_on = pw.DateField(null=True)
        overview = pw.TextField(default='')
        last_updated_on = pw.DateTimeField()
        thumbnail_url = pw.CharField(default='', max_length=255)

        class Meta:
            table_name = "episode"
            indexes = [(('series', 'season', 'number'), True)]

    @migrator.create_model
    class FTS5Model(pw.Model):
        rowid = pw.AutoField()

        class Meta:
            table_name = "fts5model"

    @migrator.create_model
    class Release(pw.Model):
        id = pw.AutoField()
        info_hash = pw.CharField(max_length=64, unique=True)
        episode = pw.ForeignKeyField(column_name='episode_id', field='id', model=migrator.orm['episode'], on_delete='CASCADE', on_update='CASCADE')
        added_on = pw.DateTimeField()
        last_updated_on = pw.DateTimeField()
        size = pw.BigIntegerField()
        magnet_uri = pw.TextField()
        seeders = pw.IntegerField()
        leechers = pw.IntegerField()
        completed = pw.IntegerField()
        name = pw.CharField(max_length=255)
        resolution = pw.SmallIntegerField()

        class Meta:
            table_name = "release"

    @migrator.create_model
    class SeriesIndex(pw.Model):
        rowid = pw.AutoField()
        name = pw.Field(null=True)
        content = pw.Field(null=True)

        class Meta:
            table_name = "seriesindex"

    @migrator.create_model
    class Tag(pw.Model):
        id = pw.AutoField()
        slug = pw.CharField(max_length=255)
        name = pw.CharField(max_length=255)
        type = pw.FixedCharField()

        class Meta:
            table_name = "tag"

    @migrator.create_model
    class SeriesTag(pw.Model):
        series = pw.ForeignKeyField(column_name='series_id', field='id', model=migrator.orm['series'], on_delete='CASCADE')
        tag = pw.ForeignKeyField(column_name='tag_id', field='id', model=migrator.orm['tag'], on_delete='CASCADE')

        class Meta:
            table_name = "seriestag"
            primary_key = pw.CompositeKey('series', 'tag')

    @migrator.create_model
    class SyncLog(pw.Model):
        id = pw.AutoField()
        timestamp = pw.TimestampField()
        status = pw.CharField(default='S', max_length=255)
        description = pw.TextField(default='')

        class Meta:
            table_name = "synclog"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""
    
    migrator.remove_model('synclog')

    migrator.remove_model('seriestag')

    migrator.remove_model('tag')

    migrator.remove_model('seriesindex')

    migrator.remove_model('release')

    migrator.remove_model('fts5model')

    migrator.remove_model('episode')

    migrator.remove_model('series')
