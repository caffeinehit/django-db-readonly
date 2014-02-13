#!/usr/bin/env python
import sys
from os.path import dirname, abspath, join

from django.conf import settings

if not settings.configured:
    settings.configure(
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': 'mydatabase',
            }
        },
        
        INSTALLED_APPS=[
            'readonly',
        ],
        ROOT_URLCONF='',
        DEBUG=False,
    )

from django.test.utils import get_runner

def runtests(*test_args, **options):
    if 'south' in settings.INSTALLED_APPS:
        from south.management.commands import patch_for_test_db_setup
        patch_for_test_db_setup()

    if not test_args:
        test_args = ['readonly']
    
    parent = dirname(abspath(__file__))
    sys.path.insert(0, parent)
    
    TestRunner = get_runner(settings)
    
    test_runner = TestRunner(**options)
    test_runner.setup_databases()
    
    # Yeah, we are naughty https://docs.djangoproject.com/en/1.6/topics/settings/#altering-settings-at-runtime
    settings.SITE_READ_ONLY = True
    failures = test_runner.run_tests(test_args)

    if failures:
        sys.exit(bool(failures))

if __name__ == '__main__':
    runtests(*sys.argv[1:])
