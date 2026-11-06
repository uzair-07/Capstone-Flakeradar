from app.core.security import bearer_token, generate_token, token_matches, token_prefix


def test_generated_token_round_trip():
    token = generate_token()

    assert token.value.startswith(f"fr_{token.prefix}_")
    assert token_prefix(token.value) == token.prefix
    assert token_matches(token.value, token.hash)
    assert not token_matches(token.value + "x", token.hash)
    assert token.hash != token.value  # only the hash is stored


def test_tokens_are_unique():
    assert generate_token().value != generate_token().value


def test_malformed_tokens_have_no_prefix():
    bad_tokens = [
        "",
        "abc",
        "fr__secret",
        "fr_XYZ12345_secret",
        "gh_1234abcd_secret",
        "fr_1234abcd_",
    ]
    for bad in bad_tokens:
        assert token_prefix(bad) is None, bad


def test_bearer_header_parsing():
    assert bearer_token("Bearer fr_1234abcd_s3cret") == "fr_1234abcd_s3cret"
    assert bearer_token("bearer   fr_1234abcd_s3cret ") == "fr_1234abcd_s3cret"
    assert bearer_token("Basic dXNlcjpwYXNz") is None
    assert bearer_token("Bearer ") is None
    assert bearer_token(None) is None
