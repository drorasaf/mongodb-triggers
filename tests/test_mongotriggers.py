import bson
import datetime
import mongotriggers
import pymongo
import pytest
import threading
import time


@pytest.fixture
def connection():
    conn = pymongo.MongoClient(host='localhost', port=27017)

    yield conn
    conn.close()


@pytest.fixture
def trigger(connection):
    mongotrigger = mongotriggers.MongoTrigger(connection)
    return mongotrigger


@pytest.fixture(scope='function')
def database(connection):
    connection.drop_database('test')
    yield connection['test']


def basic_trigger(trigger, func, *argfunc):
    thread = threading.Thread(target=trigger.tail_oplog)
    thread.start()
    func(*argfunc)

    time.sleep(3)
    trigger.stop_tail()
    thread.join()


def test_single_operation(database, trigger):
    result_docs = []

    def append_op(op_doc):
        append_doc = {'op': op_doc['op'], 'ns': op_doc['ns'], }
        result_docs.append(append_doc)

    def operation():
        database['any_trigger'].insert({'a': 1})
        database['any_trigger'].update({}, {'a': 2})
        database['any_trigger'].remove({'a': 2})

    trigger.register_op_trigger(append_op, database.name, 'any_trigger')
    basic_trigger(trigger, operation)
    assert len(result_docs) == 3
    assert result_docs[0]['op'] == 'i'
    assert result_docs[1]['op'] == 'u'
    assert result_docs[2]['op'] == 'd'

    result_docs = []
    trigger.unregister_op_trigger(append_op, database.name, 'any_trigger')
    basic_trigger(trigger, operation)
    assert len(result_docs) == 0


def test_single_insert(database, trigger):
    result_docs = []

    def insert(op_doc):
        append_doc = {'op': op_doc['op'], 'ns': op_doc['ns'], }
        result_docs.append(append_doc)

    trigger.register_insert_trigger(insert, database.name, 'insert_trigger')
    basic_trigger(trigger, database['insert_trigger'].insert, {'a': 1})
    assert len(result_docs) == 1
    assert result_docs[0]['op'] == 'i'
    assert result_docs[0]['ns'] == 'test.insert_trigger'

    result_docs = []
    trigger.unregister_insert_trigger(insert, database.name, 'insert_trigger')
    basic_trigger(trigger, database['insert_trigger'].insert, {'a': 1})
    assert len(result_docs) == 0


def test_single_update(database, trigger):
    result_docs = []

    def update(op_doc):
        append_doc = {'op': op_doc['op'], 'ns': op_doc['ns'], }
        result_docs.append(append_doc)

    def operations(database):
        database['update_trigger'].insert({'a': 1})
        database['update_trigger'].update({}, {'a': 2})

    trigger.register_update_trigger(update, database.name, 'update_trigger')
    basic_trigger(trigger, operations, database)
    assert len(result_docs) == 1
    assert result_docs[0]['op'] == 'u'
    assert result_docs[0]['ns'] == 'test.update_trigger'

    result_docs = []
    trigger.unregister_update_trigger(update, database.name, 'update_trigger')
    basic_trigger(trigger, operations, database)
    assert len(result_docs) == 0


def test_single_delete(database, trigger):
    result_docs = []

    def delete(op_doc):
        append_doc = {'op': op_doc['op'], 'ns': op_doc['ns'], }
        result_docs.append(append_doc)

    def operations(database):
        database['delete_trigger'].insert({'a': 3})
        database['delete_trigger'].remove({'a': 3})

    trigger.register_delete_trigger(delete, database.name, 'delete_trigger')
    basic_trigger(trigger, operations, database)
    assert len(result_docs) == 1
    assert result_docs[0]['op'] == 'd'
    assert result_docs[0]['ns'] == 'test.delete_trigger'

    result_docs = []
    trigger.unregister_delete_trigger(delete, database.name, 'delete_trigger')
    basic_trigger(trigger, operations, database)
    assert len(result_docs) == 0


def test_tailing_from_specific_date(database, connection):
    result_docs = []

    def delete(op_doc):
        append_doc = {'op': op_doc['op'], 'ns': op_doc['ns'], }
        result_docs.append(append_doc)

    def operation():
        pass

    now = bson.timestamp.Timestamp(datetime.datetime.utcnow(), 0)
    database['delete_trigger'].insert({'a': 3})
    database['delete_trigger'].remove({'a': 3})
    trigger = mongotriggers.MongoTrigger(connection, since=now)
    trigger.register_delete_trigger(delete, database.name, 'delete_trigger')
    basic_trigger(trigger, operation)
    assert len(result_docs) == 1
    assert result_docs[0]['op'] == 'd'
    assert result_docs[0]['ns'] == 'test.delete_trigger'


def test_incorrect_database(database, trigger):
    result_docs = []

    def append_result(op_doc):
        append_doc = {'op': op_doc['op'], 'ns': op_doc['ns'], }
        result_docs.append(append_doc)

    def operation():
        database['any_trigger'].insert({'a': 1})
        database['any_trigger'].update({}, {'a': 2})
        database['any_trigger'].remove({'a': 2})

    trigger.register_insert_trigger(append_result, database.name,
                                    'insert_trigger')
    trigger.register_update_trigger(append_result, database.name,
                                    'update_trigger')
    trigger.register_delete_trigger(append_result, database.name,
                                    'delete_trigger')
    basic_trigger(trigger, operation)
    assert len(result_docs) == 0


@pytest.fixture
def mongod_no_replica():
    conn = pymongo.MongoClient(host='localhost', port=27018)

    yield conn
    conn.close()


def test_not_replica(mongod_no_replica):
    with pytest.raises(TypeError):
        mongotriggers.MongoTrigger(mongod_no_replica)


@pytest.fixture
def mongos():
    conn = pymongo.MongoClient(host='localhost', port=27020)

    yield conn
    conn.close()


def test_mongos(mongos):
    with pytest.raises(TypeError):
        mongotriggers.MongoTrigger(mongos)


@pytest.fixture
def mongo_secondary():
    conn = pymongo.MongoClient(host='localhost', port=27019)

    yield conn
    conn.close()


def test_mongo_replica_secondary(mongo_secondary):
    with pytest.raises(TypeError):
        mongotriggers.MongoTrigger(mongo_secondary)
