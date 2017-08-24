# -*- coding:utf-8 -*-
import time
import uuid
import functools
import threading
import logging


class Dict(dict):
    #定义一个新的字典类，继承dict
    def __init__(self, names=(), values=(), **kw):
        #初始化方法，通过SUPER调用dict的初始化方法
        super(Dict, self).__init__(**kw)
        #zip方法会从给定的list中各取一个值，构成一个tuple，组成list返回
        #例zip([1,2,3], [4,5,6]) 返回[(1,4),(2,5),(3,6)]
        for k, v in zip(names, values):
            self[k] = v

    #dict没有getattr和setattr，增加这两个方法之后，支持d.id的方式访问
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

engine = None


def next_id(t=None):
    '''生成一个唯一id，由时间+随机数（伪随机数）拼接得到'''
    if t is None:
        t = time.time()
    return '%015d%s000' % (int(t * 1000), uuid.uuid4().hex)


def _profiling(start, sql=''):
    '''计算sql的执行时间'''
    t = time.time() - start
    if t > 0.1:
        logging.warning('[PROFILING][DB] %s %s' % (t, sql))
    else:
        logging.info('[PROFILING][DB] %s %s' % (t, sql))


#定义两个错误类，后面报错的时候用到
class DBError(Exception):
    pass


class MultiColumnsError(DBError):
    pass


class _Engine(object):
    #定义engine对象，封装了connect方法
    def __init__(self, connect):
        self._connect = connect

    def connect(self):
        return self._connect()


def create_engine(user, password, database, host='127.0.0.1', port=3306, **kw):
    '''
    核心方法，创建一个数据库连接engine对象（全局）
    engine对象持有数据库连接    
    '''
    import mysql.connector
    global engine
    #如果已经连接过数据库了，则报错
    if engine is not None:
        raise DBError('Engine is already initialized.')
    params = dict(user=user, password=password, database=database, host=host, port=port)
    defaults = dict(use_unicode=True, charset='utf8', collation='utf8_general_ci', autocommit=False)
    #比较defaults和传入的字典，如果有重复的key，以传入的为准
    #字典的pop方法，是删除给定的key，并返回key对应的value，如果字典中没有
    #这个key，则返回默认值或者是给定的v
    for k, v in defaults.iteritems():
        #这里一方面删掉了kw中与defaults重复的key
        #另一方面，把params和defaults合并了
        params[k] = kw.pop(k, v)
    #params再合并kw    
    params.update(kw)
    params['buffered'] = True
    #封装数据库连接方法，通过engine.connect()来调用
    engine = _Engine(lambda: mysql.connector.connect(**params))

    logging.info('Init mysql engine <%s> ok' % hex(id(engine)))


class _LasyConnection(object):
    def __init__(self):
        self.connection = None

    def cursor(self):
        global engine
        if self.connection is None:
            #创建链接
            _connection = engine.connect()
            logging.info('[OPEN] connection <%s>...' % hex(id(engine)))
            self.connection = _connection
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def cleanup(self):
        if self.connection:
            connection = self.connection
            self.connection = None
            logging.info('[CLOSE] connection <%s>...' % hex(id(connection)))
            connection.close()


class _DbCtx(threading.local):
    def __init__(self):
        self.connection = None
        self.transactions = 0

    def is_init(self):
        return not self.connection is None

    def init(self):
        logging.info('[OPEN] lazy connection...')
        self.connection = _LasyConnection()
        self.transactions = 0

    def cursor(self):
        return self.connection.cursor()

    def cleanup(self):
        self.connection.cleanup()
        self.connection = None

_db_ctx = _DbCtx()


class _ConnectionCtx(object):
    #自动初始化连接和最后关闭连接
    def __enter__(self):
        global _db_ctx
        self.should_cleanup = False
        if not _db_ctx.is_init():
            _db_ctx.init()
            self.should_cleanup = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _db_ctx
        if self.should_cleanup:
            _db_ctx.cleanup()


def connection():
    return _ConnectionCtx()

def with_connection(func):
    #装饰器，封装with connection()
    def wrapper(*args, **kw):
        with connection():
            return func(*args, **kw)
    return wrapper

class _TransactionCtx(object):
    #封装事务
    def __enter__(self):
        global _db_ctx
        self.should_close_conn = False
        if not _db_ctx.is_init():
            _db_ctx.init()
            self.should_close_conn = True
        _db_ctx.transactions = _db_ctx.transactions + 1
        logging.info('[BEGIN] transaction...')
        if _db_ctx.transactions != 1:
            logging.info('join current transaction')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _db_ctx
        _db_ctx.transactions = _db_ctx.transactions - 1
        try:
            if _db_ctx.transactions == 0:
                if type is None:
                    self.commit()
            else:
                self.rollback()
        finally:
            if self.should_close_conn:
                _db_ctx.cleanup()

    def commit(self):
        global _db_ctx
        logging.info('commit transaction...')
        try:
            _db_ctx.connection.commit()
            logging.info('commit ok')
        except:
            logging.warning('commit failed. try rollback...')
            _db_ctx.connection.rollback()
            logging.info('rollback ok...')

    def rollback(self):
        global _db_ctx
        logging.warning('rollback transaction...')
        _db_ctx.connection.rollback()
        logging.info('rollback ok...')

def transaction():
    return _TransactionCtx()

def with_transaction(func):
    '''装饰器，封装事务with transaction()'''
    @functools.wraps(func)
    def wrapper(*args, **kw):
        _start = time.time()
        with transaction():
            func(*args, **kw)
        _profiling(_start)
    return wrapper

def _select(sql, first, *args):
    #通过first参数来确定是单选，还是多选
    global _db_ctx
    cursor = None
    sql = sql.replace('?', '%s')
    logging.info('SQL:%s, ARGS:%s' % (sql, args))
    try:
        cursor = _db_ctx.cursor()
        # execute第二个参数需要是元组，所以args前面的*去掉了，这里要特别注意
        cursor.execute(sql, args)
        if cursor.description:
            names = [x[0] for x in cursor.description]
            if first:
                values = cursor.fetchone()
                if not values:
                    return None
                return Dict(names, values)
            return [Dict(names, x) for x in cursor.fetchall()]
    finally:
        if cursor:
            cursor.close()

@with_connection
def select_one(sql, *args):
    return _select(sql, True, *args)

@with_connection
def select_int(sql, *args):
    d = _select(sql, True, *args)
    if len(d) != 1:
        raise MultiColumnsError('Expect only one column.')
    return d.values()[0]

@with_connection
def select(sql, *args):
    return _select(sql, False, *args)

@with_connection
def _update(sql, *args):
    global _db_ctx
    cursor = None
    sql = sql.replace('?', '%s')
    logging.info('SQL: %s, ARGS: %s' % (sql, args))
    try:
        cursor = _db_ctx.cursor()
        #execute第二个参数需要是元组，所以args前面的*去掉了，这里要特别注意
        cursor.execute(sql, args)
        r = cursor.rowcount
        if _db_ctx.transactions == 0:
            #update之后，自动提交
            logging.info('Auto commit')
            _db_ctx.connection.commit()
        return r
    finally:
        if cursor:
            cursor.close()

def update(sql, *args):
    return _update(sql, *args)

def insert(table, **kw):
    cols, args = zip(*kw.iteritems())
    #格式化字符串，如果有多个参数，用括号括起来，否则可能会有问题
    sql = 'insert into %s(%s) values(%s)' % (table, ','.join(['%s' % col for col in cols]), ','.join(['?' for i in range(len(cols))]))
    return _update(sql, *args)

if __name__ == '__main__':
    #测试
    logging.basicConfig(level=logging.DEBUG)
    create_engine('root', 'qian1205', 'test')
    update('drop table if exists user')
    update('create table user (id int primary key, name text)')
    insert('user',id=1, name='qian')
    import doctest
    doctest.testmod()
