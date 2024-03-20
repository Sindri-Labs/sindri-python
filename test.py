import sys


class A:
    def __init__(self):
        pass

    def foo(self):
        # Do not print if the caller was A.bar()
        print(sys._getframe().f_back.f_code.co_name)
        print("foo()")

    def bar(self):
        print("bar()")

        self.foo()


# print sys._getframe().f_back.f_code.co_name

a = A()
a.foo()
a.bar()
