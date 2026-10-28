from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import api_router
from app.core import auth
from app.core.auth import AuthenticatedUser
from app.core.config import settings
from app.core.upload_limits import UploadBodyLimitMiddleware
from app.db.base import Base
from app.db.session import get_db
from app.llm.provider import (
    DeterministicDemoProvider,
    OpenAILLMProvider,
    get_llm_provider,
)
import app.models
from app.schemas.retrieval import RetrievedPassage


@pytest.fixture
def api_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autoflush=False, bind=engine)()
    app = FastAPI()
    app.add_middleware(UploadBodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://testserver"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _passage() -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id="chunk-1",
        document_id="doc-1",
        document_number="SOP-1",
        document_title="Test SOP",
        revision="Rev A",
        approval_status="Approved",
        is_authoritative=True,
        page_number=1,
        section_title="Operation",
        content="Use the documented operating procedure.",
        score=0.9,
    )


def _authenticate_upload_user(monkeypatch, api_client, roles):
    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://issuer.example/")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "manufacturing-assistant")
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", "https://issuer.example/keys")
    api_client.app.dependency_overrides[auth.get_optional_user] = lambda: AuthenticatedUser(
        subject="trusted-uploader",
        roles=frozenset(roles),
    )


def test_oidc_role_dependency_uses_verified_claims(monkeypatch):
    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://issuer.example/")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "manufacturing-assistant")
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", "https://issuer.example/keys")

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class SigningKey:
        key = private_key.public_key()

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, token):
            assert token
            return SigningKey()

    monkeypatch.setattr(auth, "_get_jwks_client", lambda _url: FakeJwksClient())
    token = auth.jwt.encode(
        {
            "sub": "trusted-user",
            "roles": ["document_approver"],
            "iss": "https://issuer.example/",
            "aud": "manufacturing-assistant",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user = auth.require_roles("document_approver")(credentials)
    assert user == AuthenticatedUser(subject="trusted-user", roles=frozenset({"document_approver"}))

    with pytest.raises(HTTPException) as error:
        auth.require_roles("expert_reviewer")(credentials)
    assert error.value.status_code == 403

    invalid_token = auth.jwt.encode(
        {
            "sub": "untrusted-user",
            "roles": ["document_approver"],
            "iss": "https://issuer.example/",
            "aud": "another-audience",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )
    with pytest.raises(HTTPException) as error:
        auth.require_roles("document_approver")(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=invalid_token)
        )
    assert error.value.status_code == 401

    token_without_expiration = auth.jwt.encode(
        {
            "sub": "untrusted-user",
            "roles": ["document_approver"],
            "iss": "https://issuer.example/",
            "aud": "manufacturing-assistant",
        },
        private_key,
        algorithm="RS256",
    )
    with pytest.raises(HTTPException) as error:
        auth.require_roles("document_approver")(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=token_without_expiration,
            )
        )
    assert error.value.status_code == 401


def test_oidc_rejects_insecure_issuer_or_jwks_url(monkeypatch):
    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://issuer.example/")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "manufacturing-assistant")
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", "http://issuer.example/keys")

    with pytest.raises(HTTPException) as error:
        auth.require_roles("admin")(None)

    assert error.value.status_code == 503


def test_health_reports_oidc_unconfigured_when_urls_are_insecure(monkeypatch, api_client):
    from app import main

    monkeypatch.setattr(settings, "OIDC_ISSUER", "http://issuer.example/")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "manufacturing-assistant")
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", "https://issuer.example/keys")
    db = next(api_client.app.dependency_overrides[get_db]())

    assert main.health_check(db)["authentication_configured"] is False


def test_oidc_protected_routes_fail_closed_and_public_reads_remain_available(
    monkeypatch, api_client
):
    monkeypatch.setattr(settings, "OIDC_ISSUER", None)
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", None)
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", None)

    assert api_client.get("/api/documents").status_code == 200
    protected_requests = [
        ("patch", "/api/documents/missing/status", {"approval_status": "Approved"}),
        ("post", "/api/review/missing/action", {
            "action": "approved",
            "expert_notes": "Reviewed",
        }),
        ("post", "/api/instructions/missing/approve", {
            "reviewer_name": "untrusted-name",
            "comments": "Reviewed",
        }),
        ("post", "/api/governance/conflicts/resolve", {
            "conflict_id": "conflict-1",
            "resolution_notes": "Reviewed",
            "action_taken": "approve_exception",
            "resolver": "untrusted-name",
        }),
        ("delete", "/api/documents/missing", None),
    ]
    for method, url, payload in protected_requests:
        response = (
            getattr(api_client, method)(url, json=payload)
            if payload
            else getattr(api_client, method)(url)
        )
        assert response.status_code == 503, (method, url, response.text)


def test_configured_oidc_rejects_unauthenticated_protected_action(monkeypatch, api_client):
    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://issuer.example/")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "manufacturing-assistant")
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", "https://issuer.example/keys")

    protected_requests = [
        ("post", "/api/documents/upload", {
            "data": {
                "document_number": "SOP-TEST",
                "title": "Test",
                "revision": "Rev A",
                "approval_status": "Draft",
            },
            "files": {"file": ("document.pdf", b"test", "application/pdf")},
        }),
        ("patch", "/api/documents/missing/status", {
            "json": {"approval_status": "Approved"},
        }),
        ("post", "/api/review/missing/action", {
            "json": {"action": "approved", "expert_notes": "Reviewed"},
        }),
        ("post", "/api/instructions/missing/approve", {
            "json": {"comments": "Reviewed"},
        }),
        ("post", "/api/governance/conflicts/resolve", {
            "json": {
                "conflict_id": "conflict-1",
                "resolution_notes": "Reviewed",
                "action_taken": "approve_exception",
            },
        }),
        ("delete", "/api/documents/missing", {}),
    ]
    for method, url, kwargs in protected_requests:
        response = getattr(api_client, method)(url, **kwargs)
        assert response.status_code == 401, (method, url, response.text)
        assert response.headers["www-authenticate"] == "Bearer"


def test_upload_rejects_oversized_file_before_unbounded_write(monkeypatch, tmp_path, api_client):
    _authenticate_upload_user(monkeypatch, api_client, {"document_uploader"})
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 1)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)

    response = api_client.post(
        "/api/documents/upload",
        data={
            "document_number": "SOP-TEST",
            "title": "Test",
            "revision": "Rev A",
            "approval_status": "Draft",
        },
        files={"file": ("oversized.pdf", b"x" * (1024 * 1024 + 1), "application/pdf")},
    )

    assert response.status_code == 413
    assert list(tmp_path.iterdir()) == []


def test_upload_body_limit_rejects_large_request_before_multipart_handling(
    monkeypatch, tmp_path, api_client
):
    _authenticate_upload_user(monkeypatch, api_client, {"document_uploader"})
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 1)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)

    response = api_client.post(
        "/api/documents/upload",
        data={
            "document_number": "SOP-TEST",
            "title": "Test",
            "revision": "Rev A",
            "approval_status": "Draft",
        },
        files={"file": ("oversized.pdf", b"x" * (1024 * 1024 + 64 * 1024 + 1), "application/pdf")},
    )

    assert response.status_code == 413
    assert list(tmp_path.iterdir()) == []


def test_upload_cleans_temporary_file_after_parse_failure(monkeypatch, tmp_path, api_client):
    from app.api.routes import documents

    _authenticate_upload_user(monkeypatch, api_client, {"document_uploader"})
    def fail_parse(*args, **kwargs):
        raise ValueError("invalid test document")

    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        documents.document_parser,
        "parse_document",
        fail_parse,
    )

    response = api_client.post(
        "/api/documents/upload",
        data={
            "document_number": "SOP-TEST",
            "title": "Test",
            "revision": "Rev A",
            "approval_status": "Draft",
        },
        files={"file": ("invalid.pdf", b"%PDF-1.7\ninvalid content", "application/pdf")},
    )

    assert response.status_code == 422
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("approval_status", "supersedes_id"),
    [("Draft", None), ("Approved", None), ("Draft", "previous-document")],
)
def test_all_uploads_require_authentication_and_protected_changes_require_approver(
    monkeypatch, tmp_path, api_client, approval_status, supersedes_id
):
    monkeypatch.setattr(settings, "OIDC_ISSUER", None)
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", None)
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", None)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)

    data = {
        "document_number": "SOP-TEST",
        "title": "Test",
        "revision": "Rev A",
        "approval_status": approval_status,
    }
    if supersedes_id:
        data["supersedes_id"] = supersedes_id

    response = api_client.post(
        "/api/documents/upload",
        data=data,
        files={"file": ("document.pdf", b"test", "application/pdf")},
    )

    assert response.status_code == 503
    assert list(tmp_path.iterdir()) == []


def test_authenticated_read_only_user_cannot_upload_draft(monkeypatch, tmp_path, api_client):
    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://issuer.example/")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "manufacturing-assistant")
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", "https://issuer.example/keys")
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)

    class SigningKey:
        key = "verified-key"

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _token):
            return SigningKey()

    monkeypatch.setattr(auth, "_get_jwks_client", lambda _url: FakeJwksClient())
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_args, **_kwargs: {"sub": "readonly-user", "roles": ["reader"]},
    )

    response = api_client.post(
        "/api/documents/upload",
        headers={"Authorization": "Bearer verified-token"},
        data={
            "document_number": "SOP-TEST",
            "title": "Test",
            "revision": "Rev A",
            "approval_status": "Draft",
        },
        files={"file": ("document.pdf", b"test", "application/pdf")},
    )

    assert response.status_code == 403
    assert list(tmp_path.iterdir()) == []


def test_document_uploader_cannot_upload_approved_document(monkeypatch, tmp_path, api_client):
    _authenticate_upload_user(monkeypatch, api_client, {"document_uploader"})
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)

    response = api_client.post(
        "/api/documents/upload",
        data={
            "document_number": "SOP-TEST",
            "title": "Test",
            "revision": "Rev A",
            "approval_status": "Approved",
        },
        files={"file": ("document.pdf", b"test", "application/pdf")},
    )

    assert response.status_code == 403
    assert list(tmp_path.iterdir()) == []


def test_openai_missing_or_placeholder_key_uses_labeled_demo_provider(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    for key in (None, "", "******", "your-openai-api-key", "sk-..."):
        monkeypatch.setattr(settings, "OPENAI_API_KEY", key)
        provider = get_llm_provider()
        assert isinstance(provider, DeterministicDemoProvider)
        assert "OpenAI unavailable" in provider.provider_name


def test_health_check_reports_selected_fallback_provider(monkeypatch, api_client):
    from app import main

    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(
        main,
        "llm_provider",
        DeterministicDemoProvider(
            display_name="deterministic_demo_engine (OpenAI unavailable: missing or placeholder API key)"
        ),
    )

    db = next(api_client.app.dependency_overrides[get_db]())
    response = main.health_check(db)

    assert "OpenAI unavailable" in response["llm_provider"]


def test_openai_uses_bearer_key_and_reports_fallback_on_failure(monkeypatch):
    import httpx

    provider = OpenAILLMProvider(api_key="sk-test-key")
    calls = []

    class Response:
        status_code = 401

    def fake_post(url, headers, **kwargs):
        calls.append((url, headers))
        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    provider.generate_grounded_answer(
        "How should this machine operate?",
        [_passage()],
        [],
        False,
    )

    assert calls[0][1]["Authorization"] == "Bearer sk-test-key"
    assert provider.provider_name.startswith("deterministic_demo_engine")
    assert "request failed" in provider.provider_name


def test_openai_reports_success_only_after_valid_response(monkeypatch):
    import httpx

    provider = OpenAILLMProvider(api_key="sk-test-key")

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "Use the documented procedure."}}]}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: Response())
    result = provider.generate_grounded_answer(
        "How should this machine operate?",
        [_passage()],
        [],
        False,
    )

    assert result[0] == "Use the documented procedure."
    assert provider.provider_name == "openai (gpt-4o-mini)"
