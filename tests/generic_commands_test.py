import asyncio
import time
import math
import os
import unittest
from unittest import mock

from ._testutil import (
    RedisTest, run_until_complete,
    REDIS_VERSION, REDIS_CLUSTER,
    )
from aioredis import ReplyError


@unittest.skipIf(REDIS_CLUSTER, "Skipped on redis cluster")
class GenericCommandsTest(RedisTest):

    @run_until_complete
    def test_delete(self):
        yield from self.add('my-key', 123)
        yield from self.add('other-key', 123)

        res = yield from self.redis.delete('my-key', 'non-existent-key')
        self.assertEqual(res, 1)

        res = yield from self.redis.delete('other-key', 'other-key')
        self.assertEqual(res, 1)

        with self.assertRaises(TypeError):
            yield from self.redis.delete(None)

        with self.assertRaises(TypeError):
            yield from self.redis.delete('my-key', 'my-key', None)

    @run_until_complete
    def test_dump(self):
        yield from self.add('my-key', 123)

        data = yield from self.redis.dump('my-key')
        self.assertEqual(data, mock.ANY)
        self.assertIsInstance(data, (bytes, bytearray))
        self.assertGreater(len(data), 0)

        data = yield from self.redis.dump('non-existent-key')
        self.assertIsNone(data)

        with self.assertRaises(TypeError):
            yield from self.redis.dump(None)

    @run_until_complete
    def test_exists(self):
        yield from self.add('my-key', 123)

        res = yield from self.redis.exists('my-key')
        self.assertIs(res, True)

        res = yield from self.redis.exists('non-existent-key')
        self.assertIs(res, False)

        with self.assertRaises(TypeError):
            yield from self.redis.exists(None)

    @run_until_complete
    def test_expire(self):
        yield from self.add('my-key', 132)

        res = yield from self.redis.expire('my-key', 10)
        self.assertIs(res, True)

        res = yield from self.redis.connection.execute('TTL', 'my-key')
        self.assertGreaterEqual(res, 10)

        yield from self.redis.expire('my-key', -1)
        res = yield from self.redis.exists('my-key')
        self.assertIs(res, False)

        res = yield from self.redis.expire('other-key', 1000)
        self.assertIs(res, False)

        yield from self.add('my-key', 1)
        res = yield from self.redis.expire('my-key', 10.0)
        self.assertIs(res, True)
        res = yield from self.redis.connection.execute('TTL', 'my-key')
        self.assertGreaterEqual(res, 10)

        with self.assertRaises(TypeError):
            yield from self.redis.expire(None, 123)
        with self.assertRaises(TypeError):
            yield from self.redis.expire('my-key', 'timeout')

    # @run_until_complete
    # def test_wait_expire(self):
    #     return
    #     yield from self.add('my-key', 123)
    #     res = yield from self.redis.expire('my-key', 1)
    #     self.assertIs(res, True)

    #     yield from asyncio.sleep(1, loop=self.loop)

    #     res = yield from self.redis.exists('my-key')
    #     self.assertIs(res, False)

    # @run_until_complete
    # def test_wait_expireat(self):
    #     return
    #     yield from self.add('my-key', 123)
    #     ts = int(time.time() + 1)
    #     res = yield from self.redis.expireat('my-key', ts)

    #     yield from asyncio.sleep(ts - time.time(), loop=self.loop)
    #     res = yield from self.redis.exists('my-key')
    #     self.assertIs(res, False)

    @run_until_complete
    def test_expireat(self):
        yield from self.add('my-key', 123)
        now = math.ceil(time.time())

        res = yield from self.redis.expireat('my-key', now + 10)
        self.assertIs(res, True)

        res = yield from self.redis.connection.execute('TTL', 'my-key')
        self.assertGreaterEqual(res, 10)

        res = yield from self.redis.expireat('my-key', -1)
        self.assertIs(res, True)

        res = yield from self.redis.exists('my-key')
        self.assertIs(res, False)

        yield from self.add('my-key', 123)

        res = yield from self.redis.expireat('my-key', 0)
        self.assertIs(res, True)

        res = yield from self.redis.exists('my-key')
        self.assertIs(res, False)

        yield from self.add('my-key', 123)
        res = yield from self.redis.expireat('my-key', time.time() + 10)
        self.assertIs(res, True)

        res = yield from self.redis.connection.execute('TTL', 'my-key')
        self.assertGreaterEqual(res, 10)

        yield from self.add('my-key', 123)
        with self.assertRaises(TypeError):
            yield from self.redis.expireat(None, 123)
        with self.assertRaises(TypeError):
            yield from self.redis.expireat('my-key', 'timestamp')

    @run_until_complete
    def test_keys(self):
        res = yield from self.redis.keys('*pattern*')
        self.assertEqual(res, [])

        yield from self.redis.connection.execute('FLUSHDB')
        res = yield from self.redis.keys('*')
        self.assertEqual(res, [])

        yield from self.add('my-key-1', 1)
        yield from self.add('my-key-ab', 1)

        res = yield from self.redis.keys('my-key-?')
        self.assertEqual(res, [b'my-key-1'])
        res = yield from self.redis.keys('my-key-*')
        self.assertEqual(sorted(res), [b'my-key-1', b'my-key-ab'])

        # test with encoding param
        res = yield from self.redis.keys('my-key-*', encoding='utf-8')
        self.assertEqual(sorted(res), ['my-key-1', 'my-key-ab'])

        with self.assertRaises(TypeError):
            yield from self.redis.keys(None)

    @run_until_complete
    @unittest.skipUnless(os.environ.get('TRAVIS'),
                         "Configured to run on travis")
    def test_migrate(self):
        yield from self.add('my-key', 123)

        conn2 = yield from self.create_redis(('localhost', 6380), db=2,
                                             loop=self.loop)
        yield from conn2.delete('my-key')
        self.assertTrue((yield from self.redis.exists('my-key')))
        self.assertFalse((yield from conn2.exists('my-key')))

        ok = yield from self.redis.migrate('localhost', 6380, 'my-key',
                                           2, 1000)
        self.assertTrue(ok)
        self.assertFalse((yield from self.redis.exists('my-key')))
        self.assertTrue((yield from conn2.exists('my-key')))

        with self.assertRaisesRegex(TypeError, "host .* str"):
            yield from self.redis.migrate(None, 1234, 'key', 1, 23)
        with self.assertRaisesRegex(TypeError, "args .* None"):
            yield from self.redis.migrate('host', '1234',  None, 1, 123)
        with self.assertRaisesRegex(TypeError, "dest_db .* int"):
            yield from self.redis.migrate('host', 123, 'key', 1.0, 123)
        with self.assertRaisesRegex(TypeError, "timeout .* int"):
            yield from self.redis.migrate('host', '1234', 'key', 2, None)
        with self.assertRaisesRegex(ValueError, "Got empty host"):
            yield from self.redis.migrate('', '123', 'key', 1, 123)
        with self.assertRaisesRegex(ValueError, "dest_db .* greater equal 0"):
            yield from self.redis.migrate('host', 6379, 'key', -1, 1000)
        with self.assertRaisesRegex(ValueError, "timeout .* greater equal 0"):
            yield from self.redis.migrate('host', 6379, 'key', 1, -1000)

    @run_until_complete
    def test_move(self):
        yield from self.flushall()
        yield from self.add('my-key', 123)

        self.assertEqual(self.redis.db, 0)
        res = yield from self.redis.move('my-key', 1)
        self.assertIs(res, True)

        with self.assertRaises(TypeError):
            yield from self.redis.move(None, 1)
        with self.assertRaises(TypeError):
            yield from self.redis.move('my-key', None)
        with self.assertRaises(ValueError):
            yield from self.redis.move('my-key', -1)
        with self.assertRaises(TypeError):
            yield from self.redis.move('my-key', 'not db')

    @run_until_complete
    def test_object_refcount(self):
        yield from self.flushall()
        yield from self.add('foo', 'bar')

        res = yield from self.redis.object_refcount('foo')
        self.assertEqual(res, 1)
        res = yield from self.redis.object_refcount('non-existent-key')
        self.assertIsNone(res)

        with self.assertRaises(TypeError):
            yield from self.redis.object_refcount(None)

    @run_until_complete
    def test_object_encoding(self):
        yield from self.flushall()
        yield from self.add('foo', 'bar')

        res = yield from self.redis.object_encoding('foo')
        if REDIS_VERSION < (3, 0, 0):
            self.assertEqual(res, b'raw')
        else:
            self.assertEqual(res, b'embstr')
        res = yield from self.redis.incr('key')
        self.assertEqual(res, 1)
        res = yield from self.redis.object_encoding('key')
        self.assertEqual(res, b'int')
        res = yield from self.redis.object_encoding('non-existent-key')
        self.assertIsNone(res)

        with self.assertRaises(TypeError):
            yield from self.redis.object_encoding(None)

    @run_until_complete
    def test_object_idletime(self):
        yield from self.flushall()
        yield from self.add('foo', 'bar')

        res = yield from self.redis.object_idletime('foo')
        self.assertEqual(res, 0)

        if REDIS_VERSION < (2, 8, 0):
            # Redis at least 2.6.x requires more time to sleep to incr idletime
            yield from asyncio.sleep(10, loop=self.loop)
        else:
            yield from asyncio.sleep(1, loop=self.loop)

        res = yield from self.redis.object_idletime('foo')
        self.assertGreaterEqual(res, 1)

        res = yield from self.redis.object_idletime('non-existent-key')
        self.assertIsNone(res)

        with self.assertRaises(TypeError):
            yield from self.redis.object_idletime(None)

    @run_until_complete
    def test_persist(self):
        yield from self.add('my-key', 123)
        res = yield from self.redis.expire('my-key', 10)
        self.assertTrue(res)

        res = yield from self.redis.persist('my-key')
        self.assertIs(res, True)

        res = yield from self.redis.connection.execute('TTL', 'my-key')
        self.assertEqual(res, -1)

        with self.assertRaises(TypeError):
            yield from self.redis.persist(None)

    @run_until_complete
    def test_pexpire(self):
        yield from self.add('my-key', 123)
        res = yield from self.redis.pexpire('my-key', 100)
        self.assertIs(res, True)

        res = yield from self.redis.connection.execute('TTL', 'my-key')
        self.assertEqual(res, 0)
        res = yield from self.redis.connection.execute('PTTL', 'my-key')
        self.assertGreater(res, 0)

        yield from self.add('my-key', 123)
        res = yield from self.redis.pexpire('my-key', 1)
        self.assertTrue(res)

        yield from asyncio.sleep(.002, loop=self.loop)

        res = yield from self.redis.exists('my-key')
        self.assertFalse(res)

        with self.assertRaises(TypeError):
            yield from self.redis.pexpire(None, 0)
        with self.assertRaises(TypeError):
            yield from self.redis.pexpire('my-key', 1.0)

    @run_until_complete
    def test_pexpireat(self):
        yield from self.add('my-key', 123)
        now = math.ceil(time.time() * 1000)
        res = yield from self.redis.pexpireat('my-key', now + 500)
        self.assertTrue(res)

        res = yield from self.redis.ttl('my-key')
        self.assertAlmostEqual(res, 1)
        res = yield from self.redis.pttl('my-key')
        self.assertAlmostEqual(res, 500, -2)

        with self.assertRaises(TypeError):
            yield from self.redis.pexpireat(None, 1234)
        with self.assertRaises(TypeError):
            yield from self.redis.pexpireat('key', 'timestamp')
        with self.assertRaises(TypeError):
            yield from self.redis.pexpireat('key', 1000.0)

    @run_until_complete
    def test_pttl(self):
        yield from self.add('key', 'val')
        res = yield from self.redis.pttl('key')
        self.assertEqual(res, -1)
        res = yield from self.redis.pttl('non-existent-key')
        if REDIS_VERSION < (2, 8, 0):
            self.assertEqual(res, -1)
        else:
            self.assertEqual(res, -2)

        yield from self.redis.pexpire('key', 500)
        res = yield from self.redis.pttl('key')
        self.assertAlmostEqual(res, 500, -2)

        with self.assertRaises(TypeError):
            yield from self.redis.pttl(None)

    @run_until_complete
    def test_randomkey(self):
        yield from self.flushall()
        yield from self.add('key:1', 123)
        yield from self.add('key:2', 123)
        yield from self.add('key:3', 123)

        res = yield from self.redis.randomkey()
        self.assertIn(res, [b'key:1', b'key:2', b'key:3'])

        # test with encoding param
        res = yield from self.redis.randomkey(encoding='utf-8')
        self.assertIn(res, ['key:1', 'key:2', 'key:3'])

        yield from self.redis.connection.execute('flushdb')
        res = yield from self.redis.randomkey()
        self.assertIsNone(res)

    @run_until_complete
    def test_rename(self):
        yield from self.add('foo', 'bar')
        yield from self.redis.delete('bar')

        res = yield from self.redis.rename('foo', 'bar')
        self.assertTrue(res)

        with self.assertRaisesRegex(ReplyError, 'ERR no such key'):
            yield from self.redis.rename('foo', 'bar')
        with self.assertRaises(TypeError):
            yield from self.redis.rename(None, 'bar')
        with self.assertRaises(TypeError):
            yield from self.redis.rename('foo', None)
        with self.assertRaises(ValueError):
            yield from self.redis.rename('foo', 'foo')

        with self.assertRaisesRegex(ReplyError, '.* objects are the same'):
            yield from self.redis.rename('bar', b'bar')

    @run_until_complete
    def test_renamenx(self):
        yield from self.redis.delete('foo', 'bar')
        yield from self.add('foo', 123)

        res = yield from self.redis.renamenx('foo', 'bar')
        self.assertTrue(res)
        yield from self.add('foo', 123)
        res = yield from self.redis.renamenx('foo', 'bar')
        self.assertFalse(res)

        with self.assertRaisesRegex(ReplyError, 'ERR no such key'):
            yield from self.redis.renamenx('baz', 'foo')
        with self.assertRaises(TypeError):
            yield from self.redis.renamenx(None, 'foo')
        with self.assertRaises(TypeError):
            yield from self.redis.renamenx('foo', None)
        with self.assertRaises(ValueError):
            yield from self.redis.renamenx('foo', 'foo')

        with self.assertRaisesRegex(ReplyError, '.* objects are the same'):
            yield from self.redis.renamenx('foo', b'foo')

    @run_until_complete
    def test_restore(self):
        pass

    @unittest.skipIf(REDIS_VERSION < (2, 8, 0),
                     'SCAN is available since redis>=2.8.0')
    @run_until_complete
    def test_scan(self):
        for i in range(1, 11):
            foo_or_bar = 'bar' if i % 3 else 'foo'
            key = 'key:scan:{}:{}'.format(foo_or_bar, i).encode('utf-8')
            yield from self.add(key, i)

        cursor, values = yield from self.redis.scan()
        # values should be *>=* just in case some other tests left
        # test keys
        self.assertGreaterEqual(len(values), 10)

        cursor, test_values = b'0', []
        while cursor:
            cursor, values = yield from self.redis.scan(
                cursor=cursor, match=b'key:scan:foo*')
            test_values.extend(values)
        self.assertEqual(len(test_values), 3)

        cursor, test_values = b'0', []
        while cursor:
            cursor, values = yield from self.redis.scan(
                cursor=cursor, match=b'key:scan:bar:*')
            test_values.extend(values)
        self.assertEqual(len(test_values), 7)

        # SCAN family functions do not guarantee that the number of
        # elements returned per call are in a given range. So here
        # just dummy test, that *count* argument does not break something
        cursor = b'0'
        test_values = []
        while cursor:
            cursor, values = yield from self.redis.scan(cursor=cursor,
                                                        match=b'key:scan:*',
                                                        count=2)

            test_values.extend(values)
        self.assertEqual(len(test_values), 10)

    @run_until_complete
    def test_sort(self):
        def _make_list(key, items):
            yield from self.redis.delete(key)
            for i in items:
                yield from self.redis.rpush(key, i)

        yield from _make_list('a', '4231')
        res = yield from self.redis.sort('a')
        self.assertEqual(res, [b'1', b'2', b'3', b'4'])

        res = yield from self.redis.sort('a', offset=2, count=2)
        self.assertEqual(res, [b'3', b'4'])

        res = yield from self.redis.sort('a', asc=b'DESC')
        self.assertEqual(res, [b'4', b'3', b'2', b'1'])

        yield from _make_list('a', 'dbca')
        res = yield from self.redis.sort(
            'a', asc=b'DESC', alpha=True, offset=2, count=2
        )
        self.assertEqual(res, [b'b', b'a'])

        yield from self.redis.set('key:1', 10)
        yield from self.redis.set('key:2', 4)
        yield from self.redis.set('key:3', 7)
        yield from _make_list('a', '321')

        res = yield from self.redis.sort('a', by='key:*')
        self.assertEqual(res, [b'2', b'3', b'1'])

        res = yield from self.redis.sort('a', by='nosort')
        self.assertEqual(res, [b'3', b'2', b'1'])

        res = yield from self.redis.sort('a', by='key:*', store='sorted_a')
        self.assertEqual(res, 3)
        res = yield from self.redis.lrange('sorted_a', 0, -1)
        self.assertEqual(res, [b'2', b'3', b'1'])

        yield from self.redis.set('value:1', 20)
        yield from self.redis.set('value:2', 30)
        yield from self.redis.set('value:3', 40)
        res = yield from self.redis.sort('a', 'value:*', by='key:*')
        self.assertEqual(res, [b'30', b'40', b'20'])

        yield from self.redis.hset('data_1', 'weight', 30)
        yield from self.redis.hset('data_2', 'weight', 20)
        yield from self.redis.hset('data_3', 'weight', 10)
        yield from self.redis.hset('hash_1', 'field', 20)
        yield from self.redis.hset('hash_2', 'field', 30)
        yield from self.redis.hset('hash_3', 'field', 10)
        res = yield from self.redis.sort(
            'a', 'hash_*->field', by='data_*->weight'
        )
        self.assertEqual(res, [b'10', b'30', b'20'])

    @run_until_complete
    def test_ttl(self):
        yield from self.add('key', 'val')
        res = yield from self.redis.ttl('key')
        self.assertEqual(res, -1)
        res = yield from self.redis.ttl('non-existent-key')
        if REDIS_VERSION < (2, 8, 0):
            self.assertEqual(res, -1)
        else:
            self.assertEqual(res, -2)

        yield from self.redis.expire('key', 10)
        res = yield from self.redis.ttl('key')
        self.assertGreaterEqual(res, 9)

        with self.assertRaises(TypeError):
            yield from self.redis.ttl(None)

    @run_until_complete
    def test_type(self):
        yield from self.add('key', 'val')
        res = yield from self.redis.type('key')
        self.assertEqual(res, b'string')

        yield from self.redis.delete('key')
        yield from self.redis.incr('key')
        res = yield from self.redis.type('key')
        self.assertEqual(res, b'string')

        yield from self.redis.delete('key')
        yield from self.redis.sadd('key', 'val')
        res = yield from self.redis.type('key')
        self.assertEqual(res, b'set')

        res = yield from self.redis.type('non-existent-key')
        self.assertEqual(res, b'none')

        with self.assertRaises(TypeError):
            yield from self.redis.type(None)
