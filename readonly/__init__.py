"""
Django DB Readonly
~~~~~~~~~~~~~~~~~~
"""

import pkg_resources
import re

try:
    VERSION = tuple(map(int, pkg_resources.get_distribution('django-db-readonly').version.split('.')))
    __version__ = VERSION
except pkg_resources.DistributionNotFound:
    pass

from time import time

from django.conf import settings
from django.db.backends import util
from django.db.models import signals
from django.dispatch import receiver
from django.utils.log import getLogger

from .exceptions import DatabaseWriteDenied


logger = getLogger('django.db.backends')


def _readonly():
    return getattr(settings, 'SITE_READ_ONLY', False)

def _whitelisted_table_prefixes():
    return getattr(settings, 'SITE_READ_ONLY_WHITELISTED_TABLE_PREFIXES', ())

class ReadOnlyCursorWrapper(object):
    """
    This is a wrapper for a database cursor.

    This sits between django's own wrapper at
    `django.db.backends.util.CursorWrapper` and the database specific cursor at
    `django.db.backends.*.base.*CursorWrapper`. It overrides two specific
    methods: `execute` and `executemany`. If the site is in read-only mode,
    then the SQL is examined to see if it contains any write actions. If a
    write is detected, an exception is raised.

    A site is in read only mode by setting the SITE_READ_ONLY setting. For
    obvious reasons, this is False by default.

    Raises a DatabaseWriteDenied exception if writes are disabled.
    """

    SQL_WRITE_BLACKLIST = (
        # Data Definition
        'CREATE', 'ALTER', 'RENAME', 'DROP', 'TRUNCATE',
        # Data Manipulation
        'INSERT INTO', 'UPDATE', 'REPLACE', 'DELETE FROM',
    )

    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, sql, params=()):
        # Check the SQL
        if _readonly() and self._write_sql(sql) and not self._whitelisted(sql):
            raise DatabaseWriteDenied
        return self.cursor.execute(sql, params)

    def executemany(self, sql, param_list):
        # Check the SQL
        if _readonly() and self._write_sql(sql) and not self._whitelisted(sql):
            raise DatabaseWriteDenied
        return self.cursor.executemany(sql, param_list)

    def __getattr__(self, attr):
        return getattr(self.cursor, attr)

    def __iter__(self):
        return iter(self.cursor)

    def _write_sql(self, sql):
        return sql.strip().upper().startswith(self.SQL_WRITE_BLACKLIST)
    
    def _whitelisted(self, sql):
        whitelist_exists = len(_whitelisted_table_prefixes()) > 0
        
        base_regex = r'\s*?{0}"?\s*?({1})[^"\s]*?"?'
        
        whitelisted_tables = "".join(['{0}|'.format(s) for s in _whitelisted_table_prefixes()])[:-1]
        table_modification_regex = base_regex.format("(CREATE|ALTER|RENAME|DROP|TRUNCATE) TABLE", whitelisted_tables)
        row_modification_regex = base_regex.format("(INSERT INTO|UPDATE|DELETE FROM) ", whitelisted_tables)
        
        return whitelist_exists and (
            re.match(table_modification_regex, sql, re.IGNORECASE) or 
            re.match(row_modification_regex, sql, re.IGNORECASE)
        )


class CursorWrapper(util.CursorWrapper):
    def __init__(self, cursor, db):
        self.cursor = ReadOnlyCursorWrapper(cursor)
        self.db = db


# Redefine CursorDebugWrapper because we want it to inherit from *our*
# CursorWrapper instead of django.db.backends.util.CursorWrapper
class CursorDebugWrapper(CursorWrapper):

    def execute(self, sql, params=()):
        start = time()
        try:
            return self.cursor.execute(sql, params)
        finally:
            stop = time()
            duration = stop - start
            sql = self.db.ops.last_executed_query(self.cursor, sql, params)
            self.db.queries.append({
                'sql': sql,
                'time': "%.3f" % duration,
            })
            logger.debug('(%.3f) %s; args=%s' % (duration, sql, params),
                extra={'duration': duration, 'sql': sql, 'params': params}
            )

    def executemany(self, sql, param_list):
        start = time()
        try:
            return self.cursor.executemany(sql, param_list)
        finally:
            stop = time()
            duration = stop - start
            self.db.queries.append({
                'sql': '%s times: %s' % (len(param_list), sql),
                'time': "%.3f" % duration,
            })
            logger.debug('(%.3f) %s; args=%s' % (duration, sql, param_list),
                extra={'duration': duration, 'sql': sql, 'params': param_list}
            )

if _readonly():
    # Monkey Patching!
    util.CursorWrapper = CursorWrapper
    util.CursorDebugWrapper = CursorDebugWrapper
    
    # While the database is being synced, it's pretty safe to assume
    # we want to enable writing
    @receiver(signals.pre_syncdb)
    def disable_read_only_when_syncing_database(**kwargs):
        settings.SITE_READ_ONLY = False
    
    try:
        import south
        # While the database is being migrated, it's pretty safe to assume
        # we want to enable writing
        @receiver(south.signals.pre_migrate)
        def disable_read_only_when_migrating_database(**kwargs):
            settings.SITE_READ_ONLY = False
    except ImportError:
        pass
