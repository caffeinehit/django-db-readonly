from django.conf import settings
from django.db import connection
from django.db import transaction
from django.db.backends import util
from django.test import TransactionTestCase

from . import CursorWrapper, CursorDebugWrapper
from .exceptions import DatabaseWriteDenied
from .models import TestModel, OtherTestModel
    
class ReadOnlyCursorTest(TransactionTestCase):
    def setUp(self):
        util.CursorWrapper = CursorWrapper
    
    def test_create(self):
        with self.settings(SITE_READ_ONLY=True):
            # Tests that an empty whitelist prevents writes
            self.assertRaises(DatabaseWriteDenied, TestModel.objects.create, title = 'Test')
        
            # Adds one table to the whitelist
            with self.settings(SITE_READ_ONLY_WHITELISTED_TABLE_PREFIXES=('readonly_testmodel',)):
            
                # Tests that this table can now be written to
                TestModel.objects.create(title='Test')
            
                # Tests that other tables still cannot be written to
                self.assertRaises(DatabaseWriteDenied, OtherTestModel.objects.create, title = 'Test')
    
    def test_update(self):
        instance = TestModel.objects.create(title='Test')
        other_instance = OtherTestModel.objects.create(title='Test')
        
        with self.settings(SITE_READ_ONLY=True):
            # Test to make sure updates are disabled
            instance.title = 'Test2'
            self.assertRaises(DatabaseWriteDenied, instance.save)
        
            # Add one table to the whitelist
            with self.settings(SITE_READ_ONLY_WHITELISTED_TABLE_PREFIXES=('readonly_testmodel',)):
            
                # Test that we can write to the table
                instance.title = 'Test3'
                instance.save()
            
                # Test that other tables are still readonly
                other_instance.title = 'Test2'
                self.assertRaises(DatabaseWriteDenied, other_instance.save)
    
    def test_delete(self):
        instance = TestModel.objects.create(title='Test')
        instance2 = TestModel.objects.create(title='Test')
        other_instance = OtherTestModel.objects.create(title='Test')
        
        with self.settings(SITE_READ_ONLY=True):
            # Test that we can't delete
            self.assertRaises(DatabaseWriteDenied, instance.delete)
        
            # Add one table to the whitelist
            with self.settings(SITE_READ_ONLY_WHITELISTED_TABLE_PREFIXES=('readonly_testmodel',)):
                # Test that we can delete to the whitelisted table
                instance2.delete()
            
                # Test that other tables are still readonly
                self.assertRaises(DatabaseWriteDenied, other_instance.delete)
    
    def test_raw(self):
        with self.settings(SITE_READ_ONLY=True):
            cursor = connection.cursor()
        
            sql = "INSERT INTO readonly_testmodel (title) VALUES (%s)"
            lowercase_sql = "insert into readonly_testmodel (title) values (%s)"
            whitespace_sql = "  insert into    readonly_testmodel    (title) values (%s)   "
        
            # Tests that we can't insert
            self.assertRaises(DatabaseWriteDenied, cursor.execute, sql, ['Test'])
            self.assertRaises(DatabaseWriteDenied, cursor.execute, lowercase_sql, ['Test'])
            self.assertRaises(DatabaseWriteDenied, cursor.execute, whitespace_sql, ['Test'])
        
            with self.settings(SITE_READ_ONLY_WHITELISTED_TABLE_PREFIXES=('readonly_testmodel',)):
            
                # Tests that we can insert
                cursor.execute(sql, ['Test'])
                cursor.execute(lowercase_sql, ['Test'])
                cursor.execute(whitespace_sql, ['Test'])
            
                number_of_pins = TestModel.objects.count()
                self.assertTrue(number_of_pins, 3)
