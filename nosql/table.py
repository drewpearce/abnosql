from abc import ABCMeta  # type: ignore
from abc import abstractmethod
from datetime import datetime
import json
import os
import re
import typing as t

from boto3.dynamodb.types import Binary  # type: ignore
from boto3.dynamodb.types import Decimal  # type: ignore
import pluggy  # type: ignore
import sqlparse  # type: ignore

import nosql.exceptions as ex
from nosql import plugin

hookimpl = pluggy.HookimplMarker('nosql.table')
hookspec = pluggy.HookspecMarker('nosql.table')


class TableSpecs(plugin.PluginSpec):

    @hookspec(firstresult=True)
    def set_config(self, table: str) -> t.Dict:  # type: ignore[empty-body] # noqa E501
        pass

    @hookspec(firstresult=True)
    def get_item_post(self, table: str, item: t.Dict) -> t.Dict:  # type: ignore[empty-body] # noqa E501
        pass

    @hookspec
    def put_item_post(self, table: str, item: t.Dict) -> None:  # type: ignore[empty-body] # noqa E501
        pass

    @hookspec
    def put_items_post(self, table: str, items: t.List[t.Dict]) -> None:  # type: ignore[empty-body] # noqa E501
        pass

    @hookspec
    def delete_item_post(self, table: str, key: t.Dict) -> None:  # type: ignore[empty-body] # noqa E501
        pass


class TableBase(metaclass=ABCMeta):
    @abstractmethod
    def __init__(
        self, pm: plugin.PM, name: str, config: t.Optional[dict] = None
    ) -> None:
        pass

    @abstractmethod
    def get_item(self, **kwargs) -> t.Dict:
        pass

    @abstractmethod
    def put_item(self, item: t.Dict):
        pass

    @abstractmethod
    def put_items(self, items: t.Iterable[t.Dict]):
        pass

    @abstractmethod
    def delete_item(self, **kwargs):
        pass

    @abstractmethod
    def query(
        self,
        key: t.Dict[str, t.Any],
        filters: t.Optional[t.Dict[str, t.Any]] = None,
        limit: t.Optional[int] = None,
        next: t.Optional[str] = None
    ) -> t.Dict[str, t.Any]:
        pass

    @abstractmethod
    def query_sql(
        self,
        statement: str,
        parameters: t.Optional[t.Dict[str, t.Any]] = None,
        limit: t.Optional[int] = None,
        next: t.Optional[str] = None
    ) -> t.Dict[str, t.Any]:
        pass


def get_sql_params(
    statement: str,
    parameters: t.Dict[str, t.Any],
    param_val: t.Callable,
    replace: t.Optional[str] = None
) -> t.Tuple[str, t.List]:
    # convert @variable to dynamodb ? placeholders
    vars = list(re.findall(r'\@[a-zA-Z0-9_.-]+', statement))
    params = []
    _missing = {}
    for var in vars:
        if var not in parameters:
            _missing[var] = True
        else:
            val = parameters[var]
            params.append(param_val(var, val))
    for var in parameters.keys():
        if var not in vars:
            _missing[var] = True
    missing = sorted(_missing.keys())
    if len(missing):
        raise ex.ValidationException(
            'missing parameters: ' + ', '.join(missing)
        )
    if isinstance(replace, str):
        for var in parameters.keys():
            statement = statement.replace(var, replace)
    return (statement, params)


# http://stackoverflow.com/questions/11875770/how-to-overcome-datetime-datetime-not-json-serializable-in-python  # noqa
# see https://github.com/Alonreznik/dynamodb-json/blob/master/dynamodb_json/json_util.py  # noqa
def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj) if obj != obj.to_integral_value() else int(obj)
    if isinstance(obj, Binary):
        return obj.value
    if isinstance(obj, set):
        return list(obj)
    raise TypeError('type not serializable')


def quote_str(str):
    return "'" + str.translate(
        str.maketrans({
            "'": "\\'"
        })
    ) + "'"


def deserialize(obj, deserializer=None):
    if deserializer is None:
        deserializer = json_serial
    elif callable(deserializer):
        return deserializer(obj)
    return json.loads(json.dumps(obj, default=deserializer))


def validate_query_attrs(key: t.Dict, filters: t.Dict):
    _name_pat = re.compile(r'^[a-zA-Z09_-]+$')

    def _validate_key_names(obj):
        return [_ for _ in obj.keys() if not _name_pat.match(_)]

    invalid = sorted(set(
        _validate_key_names(key) + _validate_key_names(filters)
    ))
    if len(invalid):
        raise ex.ValidationException(
            'invalid key or filter keys: ' + ', '.join(invalid)
        )


def validate_statement(statement: str):
    parsed = sqlparse.parse(statement)[0]

    def _extract_non_select_tokens(tokens):
        invalid_tokens = []
        for token in tokens:
            name = token.value.upper()
            if token.is_group:
                invalid_tokens.extend(_extract_non_select_tokens(token))
            elif token.ttype is sqlparse.tokens.DML and name != 'SELECT':
                invalid_tokens.append(name)
            elif token.ttype is sqlparse.tokens.DDL:
                invalid_tokens.append(name)
        return invalid_tokens

    # validate that SELECT is only specified
    invalid_tokens = _extract_non_select_tokens(parsed.tokens)
    invalid_tokens = sorted(set(invalid_tokens))
    if len(invalid_tokens) > 0:
        raise ex.ValidationException('only SELECT is allowed')


def table(
    name: str, config:
    t.Optional[dict] = None,
    database: t.Optional[str] = None
) -> TableBase:
    if database is None:
        database = os.environ.get('NOSQL_DB')
    pm = plugin.get_pm('table')
    module = pm.get_plugin(database)
    if module is None:
        raise ex.PluginException(f'table.{database} plugin not found')
    return module.Table(pm, name, config)
