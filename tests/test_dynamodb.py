import os

import boto3  # type: ignore
from moto import mock_dynamodb  # type: ignore
import pytest

from abnosql import table
import abnosql.exceptions as ex
from abnosql.mocks import mock_dynamodbx
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
    if set_region is True:
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
        os.environ.pop('ABNOSQL_DB', None)
    else:
        os.environ['ABNOSQL_DB'] = 'dynamodb'
    create_table('hash_range', True)
    create_table('hash_only', False)


@mock_dynamodb
def test_exceptions():
    os.environ.pop('ABNOSQL_DB', None)
    tb = table('notfound')
    with pytest.raises(ex.NotFoundException) as e:
        tb.get_item(hk='1')
    assert 'NotFoundException' in str(e.value)


@mock_dynamodb
def test_get_item():
    # test inferring ABNOSQL_DB / database via region env var
    setup_dynamodb(set_region=True)
    cmn.test_get_item()


@mock_dynamodb
def test_put_item():
    setup_dynamodb()
    cmn.test_put_item()


@mock_dynamodb
def test_put_item_audit():
    setup_dynamodb()
    cmn.test_put_item_audit()


@mock_dynamodb
def test_update_item():
    setup_dynamodb()
    cmn.test_update_item()


@mock_dynamodb
def test_put_items():
    setup_dynamodb()
    cmn.test_put_items()


@mock_dynamodb
def test_delete_item():
    setup_dynamodb()
    cmn.test_delete_item()


@mock_dynamodb
def test_hooks():
    setup_dynamodb()
    cmn.test_hooks()


@mock_dynamodb
def test_query():
    setup_dynamodb()
    cmn.test_query()


@mock_dynamodbx
@mock_dynamodb
def test_query_sql():
    setup_dynamodb()
    cmn.test_query_sql()


@mock_dynamodbx
@mock_dynamodb
def test_query_scan():
    setup_dynamodb()
    cmn.test_query_scan()


@mock_dynamodbx
@mock_dynamodb
def test_query_pagination():
    setup_dynamodb()
    cmn.test_query_pagination()
