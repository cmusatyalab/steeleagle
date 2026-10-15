"""No fixtures needed: the FSM-builder routes reach eaglec through
EaglecClient, which tests replace with tests.fake_eaglec's fakes rather
than running the real compiler (see tests/test_eaglec_integration.py for
the opt-in end-to-end test)."""
