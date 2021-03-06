import os
import shutil

from tests import TestEnvironment, mk_config_dir, http, httpbin, HTTP_OK


class SessionTestBase(object):
    def setup_method(self, method):
        """Create and reuse a unique config dir for each test."""
        self.config_dir = mk_config_dir()

    def teardown_method(self, method):
        shutil.rmtree(self.config_dir)

    def env(self):
        """
        Return an environment.

        Each environment created withing a test method
        will share the same config_dir. It is necessary
        for session files being reused.

        """
        return TestEnvironment(config_dir=self.config_dir)


class TestSessionFlow(SessionTestBase):
    """
    These tests start with an existing session created in `setup_method()`.

    """

    def setup_method(self, method):
        """
        Start a full-blown session with a custom request header,
        authorization, and response cookies.

        """
        super(TestSessionFlow, self).setup_method(method)
        r1 = http('--follow', '--session=test', '--auth=username:password',
                  'GET', httpbin('/cookies/set?hello=world'), 'Hello:World',
                  env=self.env())
        assert HTTP_OK in r1

    def test_session_created_and_reused(self):
        # Verify that the session created in setup_method() has been used.
        r2 = http('--session=test', 'GET', httpbin('/get'), env=self.env())
        assert HTTP_OK in r2
        assert r2.json['headers']['Hello'] == 'World'
        assert r2.json['headers']['Cookie'] == 'hello=world'
        assert 'Basic ' in r2.json['headers']['Authorization']

    def test_session_update(self):
        # Get a response to a request from the original session.
        r2 = http('--session=test', 'GET', httpbin('/get'), env=self.env())
        assert HTTP_OK in r2

        # Make a request modifying the session data.
        r3 = http('--follow', '--session=test', '--auth=username:password2',
                  'GET', httpbin('/cookies/set?hello=world2'), 'Hello:World2',
                  env=self.env())
        assert HTTP_OK in r3

        # Get a response to a request from the updated session.
        r4 = http('--session=test', 'GET', httpbin('/get'), env=self.env())
        assert HTTP_OK in r4
        assert r4.json['headers']['Hello'] == 'World2'
        assert r4.json['headers']['Cookie'] == 'hello=world2'
        assert (r2.json['headers']['Authorization'] !=
                r4.json['headers']['Authorization'])

    def test_session_read_only(self):
        # Get a response from the original session.
        r2 = http('--session=test', 'GET', httpbin('/get'), env=self.env())
        assert HTTP_OK in r2

        # Make a request modifying the session data but
        # with --session-read-only.
        r3 = http('--follow', '--session-read-only=test',
                  '--auth=username:password2', 'GET',
                  httpbin('/cookies/set?hello=world2'), 'Hello:World2',
                  env=self.env())
        assert HTTP_OK in r3

        # Get a response from the updated session.
        r4 = http('--session=test', 'GET', httpbin('/get'), env=self.env())
        assert HTTP_OK in r4

        # Origin can differ on Travis.
        del r2.json['origin'], r4.json['origin']
        # Different for each request.
        del r2.json['headers']['X-Request-Id']
        del r4.json['headers']['X-Request-Id']

        # Should be the same as before r3.
        assert r2.json == r4.json


class TestSession(SessionTestBase):
    """Stand-alone session tests."""

    def test_session_ignored_header_prefixes(self):
        r1 = http('--session=test', 'GET', httpbin('/get'),
                  'Content-Type: text/plain',
                  'If-Unmodified-Since: Sat, 29 Oct 1994 19:43:31 GMT',
                  env=self.env())
        assert HTTP_OK in r1

        r2 = http('--session=test', 'GET', httpbin('/get'), env=self.env())
        assert HTTP_OK in r2
        assert 'Content-Type' not in r2.json['headers']
        assert 'If-Unmodified-Since' not in r2.json['headers']

    def test_session_by_path(self):
        session_path = os.path.join(self.config_dir, 'session-by-path.json')
        r1 = http('--session=' + session_path, 'GET', httpbin('/get'),
                  'Foo:Bar', env=self.env())
        assert HTTP_OK in r1

        r2 = http('--session=' + session_path, 'GET', httpbin('/get'),
                  env=self.env())
        assert HTTP_OK in r2
        assert r2.json['headers']['Foo'] == 'Bar'
