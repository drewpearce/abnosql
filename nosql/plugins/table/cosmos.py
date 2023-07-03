import functools
import os
from traceback import print_exc
import typing as t

import nosql.exceptions as ex
from nosql.plugin import PM
from nosql.table import TableBase
import pluggy  # type: ignore

hookimpl = pluggy.HookimplMarker('nosql.table')

try:
    from azure.cosmos import CosmosClient  # type: ignore
    from azure.cosmos.exceptions import CosmosHttpResponseError  # type: ignore
    from azure.cosmos.exceptions import CosmosResourceNotFoundError  # type: ignore # noqa
except ImportError:
    MISSING_DEPS = True


def cosmos_ex_handler(raise_not_found: t.Optional[bool] = True):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CosmosResourceNotFoundError as e:
                if raise_not_found:
                    raise ex.NotFoundException(e)
                return None
            except CosmosHttpResponseError as e:
                raise ex.ConfigException(e)
            except Exception as e:
                print_exc()
                raise ex.PluginException(e)
        return wrapper
    return decorator


def get_key_kwargs(**kwargs):
    key = dict(kwargs)
    if len(key) > 2 or len(key) == 0:
        raise ValueError('key length must be 1 or 2')
    keys = list(key.keys())
    kwargs = {
        'item': key[keys[0]],
        'partition_key': key[keys[1]] if len(keys) > 1 else key[keys[0]]
    }
    return kwargs


def strip_cosmos_attrs(item):
    for attr in ['_rid', '_self', '_etag', '_attachments', '_ts']:
        item.pop(attr, None)
    return item


class Table(TableBase):

    def __init__(
        self, pm: PM, name: str, config: t.Optional[dict] = None
    ) -> None:
        self.pm = pm
        self.name = name
        if config is None:
            config = {}
        _config = self.pm.hook.config()
        if _config:
            config = t.cast(t.Dict, _config)
        self.database_client = None
        self.config = config

    def _database_client(self):
        _client = self.config.get('database_client', self.database_client)
        if _client is not None:
            return _client
        cf = {}
        required = ['endpoint', 'credential', 'database']
        for attr in ['account'] + required:
            cf[attr] = self.config.get(
                attr, os.environ.get('NOSQL_COSMOS_' + attr.upper())
            )
        if cf['endpoint'] is None and cf['account'] is not None:
            cf['endpoint'] = 'https://%s.documents.azure.com' % cf['account']
        missing = [_ for _ in required if cf[_] is None]
        if len(missing):
            raise ex.ConfigException('missing config: ' + ', '.join(missing))
        self.database_client = CosmosClient(
            url=cf['endpoint'], credential=cf['credential']
        ).get_database_client(cf['database'])
        return self.database_client

    def _container(self, name):
        return self._database_client().get_container_client(name)

    @cosmos_ex_handler(False)
    def get_item(self, **kwargs) -> t.Dict:
        item = strip_cosmos_attrs(
            self._container(self.name).read_item(
                **get_key_kwargs(**kwargs)
            )
        )
        _item = self.pm.hook.get_item_post(table=self.name, item=item)
        if _item:
            item = _item
        return item

    @cosmos_ex_handler()
    def put_item(self, item: t.Dict):
        self._container(self.name).upsert_item(item)
        self.pm.hook.put_item_post(table=self.name, item=item)

    @cosmos_ex_handler()
    def put_items(self, items: t.Iterable[t.Dict]):
        # TODO(batch)
        for item in items:
            self.put_item(item)
        self.pm.hook.put_items_post(table=self.name, items=items)

    @cosmos_ex_handler()
    def delete_item(self, **kwargs):
        self._container(self.name).delete_item(
            **get_key_kwargs(**kwargs)
        )
        self.pm.hook.delete_item_post(table=self.name, key=dict(kwargs))

    def query(self, query: str) -> t.Iterable[t.Dict]:
        print(f'cosmos.query({query})')
        return [{}]
