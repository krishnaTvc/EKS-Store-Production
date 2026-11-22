"""Regression checks for the failures observed in the supplied deployment logs."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock
import pytest
import yaml
from sqlalchemy import make_url

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.fixture
def credentials():
    master = {'host': 'db.example', 'port': 5432, 'master_username': 'postgres', 'master_password': 'master'}
    catalog = {'host': 'db.example', 'port': 5432, 'username': 'catalog_user', 'password': "a:@/%+' b", 'dbname': 'catalog'}
    orders = {'host': 'db.example', 'port': 5432, 'username': 'order_user', 'password': 'other', 'dbname': 'orders'}
    return master, catalog, orders


def test_one_source_passwords_and_distinct_secret_names(credentials):
    prepare = module('prepare_db_secrets')
    objects = prepare.manifests(*credentials)
    assert {o['metadata']['name'] for o in objects} == {
        'eks-store-bootstrap-db-credentials', 'eks-store-catalog-db', 'eks-store-orders-db'}
    master = objects[0]['stringData']
    url = make_url(objects[1]['stringData']['DATABASE_URL'])
    assert url.password == master['CATALOG_DB_PASSWORD'] == credentials[1]['password']
    assert url.query['sslmode'] == 'verify-full'
    assert 'RDS_MASTER_PASSWORD' not in objects[1]['stringData']


def test_stale_url_is_rejected(credentials):
    credentials[1]['DATABASE_URL'] = 'postgresql+psycopg://catalog_user:old@db.example:5432/catalog'
    with pytest.raises(ValueError, match='disagrees'):
        module('prepare_db_secrets').manifests(*credentials)


def test_missing_password_fails_before_secret_creation(credentials):
    credentials[1].pop('password')
    with pytest.raises(ValueError, match='password'):
        module('prepare_db_secrets').manifests(*credentials)


def test_mismatched_endpoint_is_rejected(credentials):
    credentials[2]['host'] = 'other.example'
    with pytest.raises(ValueError, match='endpoints differ'):
        module('prepare_db_secrets').manifests(*credentials)


@pytest.mark.parametrize('existing', [False, True])
def test_bootstrap_uses_safe_role_statements_and_exact_passwords(monkeypatch, existing):
    bootstrap = module('bootstrap_databases')
    env = {'RDS_HOST': 'db.example', 'RDS_PORT': '5432', 'RDS_MASTER_USER': 'postgres',
           'RDS_MASTER_PASSWORD': 'master', 'CATALOG_DB_PASSWORD': "cat'password", 'ORDER_DB_PASSWORD': 'orders'}
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = ([(1,) if existing else None] * 4 +
                                   [('catalog_user', 'catalog'), ('order_user', 'orders')])
    monkeypatch.setattr(bootstrap.psycopg, 'connect', MagicMock(return_value=connection))
    assert bootstrap.bootstrap() == 0
    role_calls = []
    for call in cursor.execute.call_args_list:
        query = call.args[0]
        if hasattr(query, 'as_string'):
            text = query.as_string()
            if 'ROLE' in text and 'PASSWORD' in text:
                role_calls.append(call)
                assert len(call.args) == 1
                assert '%s' not in text and '$1' not in text
    assert len(role_calls) == 2
    assert "cat''password" in role_calls[0].args[0].as_string()


def test_bootstrap_never_defaults_missing_password(monkeypatch):
    monkeypatch.delenv('CATALOG_DB_PASSWORD', raising=False)
    with pytest.raises(ValueError, match='CATALOG_DB_PASSWORD'):
        module('bootstrap_databases').get_app_credentials()


def test_rendered_manifests_have_no_database_csi_dependencies(monkeypatch, tmp_path):
    values = {'ENVIRONMENT': 'lab', 'AWS_REGION': 'eu-north-1', 'ASSETS_BUCKET': 'test-assets',
              'CATALOG_ROLE_ARN': 'arn:aws:iam::123456789012:role/catalog',
              'FRONTEND_IMAGE': 'test/frontend:sha', 'CATALOG_IMAGE': 'test/catalog:sha',
              'ORDERS_IMAGE': 'test/orders:sha', 'SEED_IMAGE': 'test/seed:sha',
              'BOOTSTRAP_JOB': 'bootstrap-123', 'CATALOG_MIGRATION_JOB': 'catalog-migration-123',
              'ORDERS_MIGRATION_JOB': 'orders-migration-123', 'SEED_JOB': 'seed-123'}
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    renderer = module('render_manifests')
    renderer.render(ROOT / 'k8s', tmp_path)
    objects = [o for path in tmp_path.rglob('*.yaml') for o in yaml.safe_load_all(path.read_text()) if o]
    assert len([o for o in objects if o['kind'] == 'Job']) == 4
    assert len([o for o in objects if o['kind'] == 'Deployment']) == 3
    assert not any(o['kind'] == 'SecretProviderClass' for o in objects)
    frontend = next(o for o in objects if o['kind'] == 'Deployment' and o['metadata']['name'] == 'frontend')
    front_spec = frontend['spec']['template']['spec']
    assert any(m['mountPath'] == '/tmp' for m in front_spec['containers'][0]['volumeMounts'])
    assert all('emptyDir' in v for v in front_spec['volumes'])
    for o in objects:
        spec = o.get('spec', {}).get('template', {}).get('spec', {})
        assert not any('csi' in v for v in spec.get('volumes', []))
        for c in spec.get('containers', []):
            assert not any(e['name'] == 'DATABASE_SECRET_DIR' for e in c.get('env', []))
    monkeypatch.delenv('SEED_IMAGE')
    with pytest.raises(ValueError, match='SEED_IMAGE'):
        renderer.render(ROOT / 'k8s', tmp_path)
