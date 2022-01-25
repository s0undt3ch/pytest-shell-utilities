# Copyright 2021-2022 VMware, Inc.
# SPDX-License-Identifier: Apache-2.0
#
import os
import pathlib
import sys
from typing import cast

import pytest

from pytestshellutils.customtypes import EnvironDict
from pytestshellutils.exceptions import FactoryTimeout
from pytestshellutils.shell import ScriptSubprocess


@pytest.mark.parametrize("exitcode", [0, 1, 3, 9, 40, 120])
def test_exitcode(exitcode, tempfiles):
    shell = ScriptSubprocess(script_name=sys.executable)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import time
        time.sleep(0.125)
        exit({})
        """.format(
            exitcode
        )
    )
    result = shell.run(script)
    assert result.returncode == exitcode


def test_timeout_defined_on_class_instantiation(tempfiles):
    shell = ScriptSubprocess(script_name=sys.executable, timeout=0.5)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import time
        time.sleep(1)
        exit(0)
        """
    )
    with pytest.raises(FactoryTimeout):
        shell.run(script)


def test_timeout_defined_run(tempfiles):
    shell = ScriptSubprocess(script_name=sys.executable)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import time
        time.sleep(0.5)
        exit(0)
        """
    )
    result = shell.run(script)
    assert result.returncode == 0

    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import time
        time.sleep(0.5)
        exit(0)
        """
    )
    with pytest.raises(FactoryTimeout):
        shell.run(script, _timeout=0.1)


@pytest.mark.parametrize(
    "input_str,expected_object",
    [
        # Good JSON
        ('{"a": "a", "1": 1}', {"a": "a", "1": 1}),
        # Bad JSON
        ("{'a': 'a', '1': 1}", None),
    ],
)
def test_json_output(input_str, expected_object, tempfiles):
    shell = ScriptSubprocess(script_name=sys.executable)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import sys
        sys.stdout.write('''{}''')
        exit(0)
        """.format(
            input_str
        )
    )
    result = shell.run(script)
    assert result.returncode == 0
    if expected_object:
        assert result.data == expected_object
    assert result.stdout == input_str


def test_stderr_output(tempfiles):
    input_str = "Thou shalt not exit cleanly"
    shell = ScriptSubprocess(script_name=sys.executable)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        exit("{}")
        """.format(
            input_str
        )
    )
    result = shell.run(script)
    assert result.returncode == 1
    assert result.stderr == input_str + "\n"


def test_unicode_output(tempfiles):
    shell = ScriptSubprocess(script_name=sys.executable)
    script = tempfiles.makepyfile(
        r"""
        # coding=utf-8
        from __future__ import print_function
        import sys
        sys.stdout.write(u'STDOUT F\xe1tima')
        sys.stdout.flush()
        sys.stderr.write(u'STDERR F\xe1tima')
        sys.stderr.flush()
        exit(0)
        """
    )
    result = shell.run(script)
    assert result.returncode == 0, str(result)
    assert result.stdout == "STDOUT Fátima"
    assert result.stderr == "STDERR Fátima"


def test_process_failed_to_start(tempfiles):
    shell = ScriptSubprocess(script_name=sys.executable)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        1/0
        """
    )
    result = shell.run(script)
    assert result.returncode == 1
    assert "ZeroDivisionError: division by zero" in result.stderr


def test_environ(tempfiles):
    environ = cast(EnvironDict, os.environ.copy())
    environ["FOO"] = "foo"
    shell = ScriptSubprocess(script_name=sys.executable, environ=environ)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import os
        import json
        print(json.dumps(dict(**os.environ)), flush=True)
        exit(0)
        """
    )
    result = shell.run(script)
    assert result.returncode == 0
    assert result.data
    assert "FOO" in result.data
    assert result.data["FOO"] == "foo"


def test_env_in_run_call(tempfiles):
    env = cast(EnvironDict, {"FOO": "bar"})
    environ = cast(EnvironDict, os.environ.copy())
    environ["FOO"] = "foo"
    shell = ScriptSubprocess(script_name=sys.executable, environ=environ)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import os
        import json
        print(json.dumps(dict(**os.environ)), flush=True)
        exit(0)
        """
    )
    result = shell.run(script, env=env)
    assert result.returncode == 0
    assert result.data
    assert "FOO" in result.data
    assert result.data["FOO"] == env["FOO"]


def test_not_started():
    shell = ScriptSubprocess(script_name=sys.executable)
    assert shell.is_running() is False
    assert not shell.pid
    assert shell.terminate() is None


def test_display_name(tempfiles):
    python_binary_name = pathlib.Path(sys.executable).name
    display_name = f"ScriptSubprocess({python_binary_name})"
    shell = ScriptSubprocess(script_name=sys.executable)
    assert shell.get_display_name() == display_name
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import time
        time.sleep(0.125)
        exit(0)
        """
    )
    result = shell.run(script)
    assert result.returncode == 0
    assert shell.get_display_name() == display_name


def test_get_script_path(subtests):
    python_binary_name = pathlib.Path(sys.executable).name
    with subtests.test(script_name=sys.executable):
        shell = ScriptSubprocess(script_name=sys.executable)
        assert shell.get_script_path() == sys.executable
    with subtests.test(script_name=python_binary_name):
        shell = ScriptSubprocess(script_name=python_binary_name)
        assert shell.get_script_path() == sys.executable
    python_binary_name = f"{python_binary_name}3.100"
    with subtests.test(script_name=python_binary_name):
        shell = ScriptSubprocess(script_name=python_binary_name)
        with pytest.raises(FileNotFoundError) as exc:
            shell.get_script_path()
        assert f"The CLI script {python_binary_name!r} does not exist" in str(exc)
