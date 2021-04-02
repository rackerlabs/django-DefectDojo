from django_test_migrations.contrib.unittest_case import MigratorTestCase
from django_test_migrations.migrator import Migrator
from django.test import TransactionTestCase
from django.core.exceptions import FieldError


class TestEndpointMigrationBroken(TransactionTestCase):
    migrate_from = ('dojo', '0086_endpoint_userinfo_creation')
    migrate_to = ('dojo', '0087_endpoint_host_migration')

    def setUp(self):
        super().setUp()
        self.migrator = Migrator()

        self.old_state = self.migrator.apply_initial_migration(self.migrate_from)

        Endpoint = self.old_state.apps.get_model('dojo', 'Endpoint')
        self.endpoints = {
            'empty': Endpoint.objects.create().pk,
            'empty_host': Endpoint.objects.create(host='').pk,
            'invalid_host': Endpoint.objects.create(host='foo bar').pk,
            'invalid_ip': Endpoint.objects.create(host='127.0.1').pk,
            'invalid_port_high': Endpoint.objects.create(host='127.0.0.1:66666').pk,
            'invalid_port_low': Endpoint.objects.create(host='127.0.0.1:-1').pk,
            'invalid_port_word': Endpoint.objects.create(host='127.0.0.1:port').pk,
            'protocol_mismatch': Endpoint.objects.create(protocol='http', host='https://foo.bar').pk,
            'port_mismatch': Endpoint.objects.create(host='https://foo.bar', port=80).pk,
            'path_mismatch': Endpoint.objects.create(host='https://foo.bar/path1', path='/path1').pk,
            'query_mismatch': Endpoint.objects.create(host='https://foo.bar/?key1=value&key2', query='?key1=value&'
                                                                                                     'key2=None').pk,
            'fragment_mismatch': Endpoint.objects.create(host='https://foo.bar/#fragment', fragment='#fragment').pk,
            'missing_host': Endpoint.objects.create(host='file:///etc/passwd').pk,
        }

    def tearDown(self):
        try:
            self.migrator.reset()
        except FieldError:
            pass
        super().tearDown()

    def test_migration_0087_endpoint_broken(self):
        with self.assertRaisesRegex(FieldError, r'^It is not possible to migrate database because there is\/are {} brok'
                                                r'en endpoint\(s\)\. Please check logs\.$'.format(len(self.endpoints))):
            self.migrator.apply_tested_migration(self.migrate_to)


class TestEndpointMigration(MigratorTestCase):
    migrate_from = ('dojo', '0086_endpoint_userinfo_creation')
    migrate_to = ('dojo', '0087_endpoint_host_migration')

    def prepare(self):
        Endpoint = self.old_state.apps.get_model('dojo', 'Endpoint')
        self.endpoints = {
            'valid_host': Endpoint.objects.create(host='foo.bar').pk,
            'valid_ip': Endpoint.objects.create(host='127.0.0.1').pk,
            'host_port': Endpoint.objects.create(host='foo.bar:22').pk,
            'ip_port': Endpoint.objects.create(host='127.0.0.1:22').pk,
            'url': Endpoint.objects.create(host='http://foo.bar/').pk,
            'url_existing_port': Endpoint.objects.create(host='https://foo.bar:4433/', port=4433).pk,
            'full_url': Endpoint.objects.create(host='https://alice@foo.bar:4433/path1/path2/?key1=value1&no_value_key'
                                                     '#fragmentX').pk,
        }

    def test_migration_0087_endpoint(self):
        Endpoint = self.new_state.apps.get_model('dojo', 'Endpoint')

        endpoint = Endpoint.objects.get(pk=self.endpoints['valid_host'])
        self.assertEqual(endpoint.host, 'foo.bar')

        endpoint = Endpoint.objects.get(pk=self.endpoints['valid_ip'])
        self.assertEqual(endpoint.host, '127.0.0.1')

        endpoint = Endpoint.objects.get(pk=self.endpoints['host_port'])
        self.assertEqual(endpoint.host, 'foo.bar')
        self.assertEqual(endpoint.port, 22)

        endpoint = Endpoint.objects.get(pk=self.endpoints['ip_port'])
        self.assertEqual(endpoint.host, '127.0.0.1')
        self.assertEqual(endpoint.port, 22)

        endpoint = Endpoint.objects.get(pk=self.endpoints['url'])
        self.assertEqual(endpoint.protocol, 'http')
        self.assertEqual(endpoint.host, 'foo.bar')
        self.assertEqual(endpoint.port, 80)
        self.assertIsNone(endpoint.path)

        endpoint = Endpoint.objects.get(pk=self.endpoints['url_existing_port'])
        self.assertEqual(endpoint.port, 4433)

        endpoint = Endpoint.objects.get(pk=self.endpoints['full_url'])
        self.assertEqual(endpoint.protocol, 'https')
        self.assertEqual(endpoint.userinfo, 'alice')
        self.assertEqual(endpoint.host, 'foo.bar')
        self.assertEqual(endpoint.port, 4433)
        self.assertEqual(endpoint.path, 'path1/path2/')
        self.assertEqual(endpoint.query, 'key1=value1&no_value_key')
        self.assertEqual(endpoint.fragment, 'fragmentX')
