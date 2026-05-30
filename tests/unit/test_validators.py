"""Unit tests for app.validators.

These tests are the executable form of the project's hard ethics rules.
If any of them go red, do not relax the test — fix the code.
"""

import pytest

from app.validators import (
    assert_no_credential_payload,
    is_allowed_event_type,
    is_landing_link_local,
    is_sender_fictional,
    is_template_safe,
    is_valid_subject_code,
)


# --- is_sender_fictional ----------------------------------------------------


class TestIsSenderFictional:
    @pytest.mark.parametrize(
        "name",
        [
            "Bank of America",
            "Chase Customer Care",
            "Microsoft Account Team",
            "PayPal Support",
            "Bank Leumi",
            "Visa Notifications",
            "The IRS",
        ],
    )
    def test_rejects_real_brands(self, name):
        assert is_sender_fictional(name) is False

    @pytest.mark.parametrize(
        "name",
        [
            "Demo Co.",
            "FictionalCorp HR",
            "Acme Internal IT",
            "Lab Account Services",
            "Demo Sender",
        ],
    )
    def test_accepts_fictional_names(self, name):
        assert is_sender_fictional(name) is True

    def test_empty_string_is_rejected(self):
        assert is_sender_fictional("") is False
        assert is_sender_fictional("   ") is False

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            is_sender_fictional(123)  # type: ignore[arg-type]


# --- is_template_safe -------------------------------------------------------


class TestIsTemplateSafe:
    def test_rejects_body_with_brand(self):
        body = "Your Google account has been suspended."
        assert is_template_safe(body) is False

    def test_accepts_neutral_body(self):
        body = "Please confirm your account details with Demo Co."
        assert is_template_safe(body) is True

    def test_empty_body_is_safe(self):
        # No risk in an empty body; the campaign service requires non-empty
        # bodies separately.
        assert is_template_safe("") is True


# --- is_landing_link_local --------------------------------------------------


class TestIsLandingLinkLocal:
    @pytest.mark.parametrize(
        "url",
        [
            "/landing/1",
            "/landing/42?subject=subject-01&variant=A",
            "http://127.0.0.1:5000/landing/1",
            "http://localhost:5000/landing/1",
        ],
    )
    def test_accepts_local(self, url):
        assert is_landing_link_local(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://evil.example.com/landing/1",
            "http://10.0.0.5/landing/1",
            "/admin/campaigns",  # local but not landing
            "/static/logo.png",
            "",
            "javascript:alert(1)",
        ],
    )
    def test_rejects_non_local(self, url):
        assert is_landing_link_local(url) is False

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            is_landing_link_local(None)  # type: ignore[arg-type]


# --- assert_no_credential_payload -------------------------------------------


class TestAssertNoCredentialPayload:
    def test_none_is_noop(self):
        assert assert_no_credential_payload(None) is None

    def test_empty_dict_is_noop(self):
        assert assert_no_credential_payload({}) is None

    def test_safe_payload_passes(self):
        assert assert_no_credential_payload(
            {"field_count": 2, "time_on_page_ms": 1234, "variant": "A"}
        ) is None

    @pytest.mark.parametrize(
        "key",
        [
            "password", "Password", "PWD",
            "user_password", "passwd", "pwd",
            "secret", "api_token", "auth_token",
            "pin", "card_number", "cvv", "ssn",
        ],
    )
    def test_rejects_sensitive_keys(self, key):
        with pytest.raises(ValueError):
            assert_no_credential_payload({key: "anything"})

    def test_rejects_nested_sensitive_key(self):
        with pytest.raises(ValueError):
            assert_no_credential_payload(
                {"outer": {"inner": {"password": "x"}}}
            )

    def test_rejects_sensitive_key_inside_list_of_dicts(self):
        with pytest.raises(ValueError):
            assert_no_credential_payload({"items": [{"password": "x"}]})

    def test_non_dict_raises_typeerror(self):
        with pytest.raises(TypeError):
            assert_no_credential_payload("string-payload")  # type: ignore[arg-type]


# --- is_allowed_event_type --------------------------------------------------


class TestIsAllowedEventType:
    @pytest.mark.parametrize(
        "event_type",
        [
            "message_opened",
            "link_clicked",
            "landing_visited",
            "form_interaction_started",
            "fake_submit_attempted",
            "landing_exited",
        ],
    )
    def test_accepts_known(self, event_type):
        assert is_allowed_event_type(event_type) is True

    @pytest.mark.parametrize(
        "event_type",
        [
            "MESSAGE_OPENED",      # wrong case
            "message-opened",      # wrong separator
            "password_submitted",  # not in allow-list
            "",
            "random_string",
        ],
    )
    def test_rejects_unknown(self, event_type):
        assert is_allowed_event_type(event_type) is False


# --- is_valid_subject_code --------------------------------------------------


class TestIsValidSubjectCode:
    @pytest.mark.parametrize(
        "code",
        [
            "subject-01",
            "subject_alpha",
            "lab1",
            "A",
            "noy-laptop-test",
        ],
    )
    def test_accepts_pseudonymous(self, code):
        assert is_valid_subject_code(code) is True

    @pytest.mark.parametrize(
        "code",
        [
            "",
            "1subject",          # starts with digit
            "subject 01",        # contains space
            "subject@01",        # contains @
            "x" * 100,           # too long
        ],
    )
    def test_rejects_invalid(self, code):
        assert is_valid_subject_code(code) is False


class TestIsValidEmail:
    @pytest.mark.parametrize(
        "addr",
        [
            "a@b.co",
            "alice@example.test",
            "x.y+z@sub.example.org",
            "  trimmed@example.test  ",
        ],
    )
    def test_accepts_plain_addresses(self, addr):
        from app.validators import is_valid_email
        assert is_valid_email(addr) is True

    @pytest.mark.parametrize(
        "addr",
        [
            "",
            "   ",
            "foo",
            "foo@",
            "@bar.com",
            "a b@c.com",
            "a@b",        # no dot in host
            "a@@b.com",
            123,
            None,
        ],
    )
    def test_rejects_malformed(self, addr):
        from app.validators import is_valid_email
        assert is_valid_email(addr) is False
