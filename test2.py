import inspect
from types import FrameType
from typing import cast


def demo_the_caller_name() -> str:
    """Return the calling function's name."""
    # Ref: https://stackoverflow.com/a/57712700/
    caller_name = cast(FrameType, cast(FrameType, inspect.currentframe()).f_back).f_code.co_name
    print(caller_name)
    return caller_name


if __name__ == "__main__":

    def _test_caller_name() -> None:
        assert demo_the_caller_name() == "_test_caller_name"

    _test_caller_name()
