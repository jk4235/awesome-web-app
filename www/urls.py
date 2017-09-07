# -*- coding:utf-8 -*-
from transwarp.web import get, view
from transwarp.tablemodel import User


@view('test.html')
@get('/')
def test_users():
    users = User.find_all()
    return dict(users=users)
