#!/usr/bin/env python
import sys
from os.path import dirname, abspath, join

from django.conf import settings

if not settings.configured:
    settings.configure(
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': 'testdb.sqlite',
            }
        },
        
        INSTALLED_APPS=[
            'readonly.test',
        ],
        ROOT_URLCONF='',
        DEBUG=False,
        SITE_READ_ONLY=True,
    )

from django.test.utils import get_runner

def runtests(*test_args, **options):
    if 'south' in settings.INSTALLED_APPS:
        from south.management.commands import patch_for_test_db_setup
        patch_for_test_db_setup()

    if not test_args:
        test_args = ['readonly.test']
    
    parent = dirname(abspath(__file__))
    sys.path.insert(0, parent)
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(**options)
    failures = test_runner.run_tests(test_args)

    if failures:
        sys.exit(bool(failures))

if __name__ == '__main__':
    runtests(*sys.argv[1:])
