from __future__ import absolute_import, division, print_function, unicode_literals
from pato.local import ctx

class Setup(object):
    def setup(self):
        ctx.db.execute("create table foo (id int)")

    def teardown(self):
        ctx.db.execute("drop table foo")

class Foo(object):
    def __init__(self, other_service):
        self.other_service = other_service

    def list(self):
        return list(ctx.db.execute("select * from foo"))

    def insert(self, id):
        self.other_service(id)

    def insert_twice(self, id):
        self.other_service(id)
        self.other_service(id)
        return list(ctx.db.execute("select count(*) from foo"))

class Bar(object):
    def __call__(self, id):
        ctx.db.execute("insert into foo (id) values (:id)", {"id":id})
