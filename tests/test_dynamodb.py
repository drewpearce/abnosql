import os

import boto3  # type: ignore
from moto import mock_aws  # type: ignore
import pytest

import abnosql.exceptions as ex
from abnosql.mocks import mock_dynamodbx
from abnosql import table
from tests import common as cmn


def create_table(name, rk=True):
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    key_schema = [
        {'AttributeName': 'hk', 'KeyType': 'HASH'}
    ]
    attr_defs = [
        {'AttributeName': 'hk', 'AttributeType': 'S'}
    ]
    if rk is True:
        key_schema.append({'AttributeName': 'rk', 'KeyType': 'RANGE'})
        attr_defs.append({'AttributeName': 'rk', 'AttributeType': 'S'})
    params = {
        'TableName': name,
        'KeySchema': key_schema,
        'AttributeDefinitions': attr_defs,
        'ProvisionedThroughput': {
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        }
    }
    dynamodb.create_table(**params)


def setup_dynamodb(set_region=False):
    os.environ['ABNOSQL_KEY_ATTRS'] = 'hk,rk'
    if set_region is True:
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
        os.environ.pop('ABNOSQL_DB', None)
    else:
        os.environ['ABNOSQL_DB'] = 'dynamodb'
    create_table('hash_range', True)
    create_table('hash_only', False)


@mock_aws
def test_exceptions():
    setup_dynamodb(set_region=True)
    tb = table('notfound', {'key_attrs': ['hk']})
    with pytest.raises(ex.NotFoundException) as e:
        tb.get_item(hk='1')
    assert 'not found' in str(e.value)
    assert e.value.to_problem() == {
        'title': 'not found',
        'detail': None,
        'status': 404,
        'type': None
    }


@mock_aws
def test_get_item():
    # test inferring ABNOSQL_DB / database via region env var
    setup_dynamodb(set_region=True)
    cmn.test_get_item()


@mock_aws
def test_check_exists():
    setup_dynamodb()
    cmn.test_check_exists()


@mock_aws
def test_validate_item():
    setup_dynamodb()
    cmn.test_validate_item()


@mock_aws
def test_put_item():
    setup_dynamodb()
    cmn.test_put_item()


@mock_aws
def test_put_item_audit():
    setup_dynamodb()
    cmn.test_put_item_audit()


@mock_aws
def test_update_item():
    setup_dynamodb()
    cmn.test_update_item()


@mock_aws
def test_put_items():
    setup_dynamodb()
    cmn.test_put_items()


@mock_aws
def test_delete_item():
    setup_dynamodb()
    cmn.test_delete_item()


@mock_aws
def test_hooks():
    setup_dynamodb()
    cmn.test_hooks()


@mock_aws
def test_audit_callback():
    setup_dynamodb()
    cmn.test_audit_callback()


@mock_aws
def test_query():
    setup_dynamodb()
    cmn.test_query()


@mock_dynamodbx
@mock_aws
def test_query_sql():
    setup_dynamodb()
    cmn.test_query_sql()


@mock_dynamodbx
@mock_aws
def test_query_scan():
    setup_dynamodb()
    cmn.test_query_scan()


@mock_dynamodbx
@mock_aws
def test_query_pagination():
    setup_dynamodb()
    cmn.test_query_pagination()
