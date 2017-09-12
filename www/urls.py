# -*- coding:utf-8 -*-
from transwarp.web import get, view
from transwarp.tablemodel import User, Blog, Comment


@view('blogs.html')
@get('/')
def index():
    blogs = Blog.find_all()
    users = User.find_first('where email=?', 'test@example.com')
    return dict(blogs=blogs, users=users)
