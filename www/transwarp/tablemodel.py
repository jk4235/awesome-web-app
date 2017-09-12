# -*- coding:utf-8 -*-

import time
from db import next_id
from orm import Model, StringField, FloatField, BooleanField, TextField


class User(Model):
    __table__ = 'user'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(updatable=False, ddl='varchar(50)')
    password = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(updatable=False, default=time.time)


class Blog(Model):
    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(updatable=False, ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(50)')
    content = TextField()
    created_at = FloatField(updatable=False, default=time.time)


class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = StringField(updatable=False, ddl='varchar(50)')
    user_id = StringField(updatable=False, ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(updatable=False, default=time.time)


if __name__ == '__main__':
    import db
    db.create_engine('root', 'qian1205', 'test')
    b = Blog(user_id='001503654986581befb8575ffa14410a5e966e63489bf94000', user_name='Test', user_image='about:blank', name='Test Text', summary='a short text', content='It is a short test text')
    # u = User(name='Test', email='test@example.com', password='1234567890', image='about:blank')
    db.update(b.__sql__())
    b.insert()
    print 'new blog name', b.name