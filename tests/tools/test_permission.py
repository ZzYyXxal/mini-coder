"""Tests for PermissionService"""

import pytest
import time
from src.mini_coder.tools.permission import PermissionRequest, PermissionService


class TestPermissionRequest:
    """Tests for PermissionRequest dataclass"""

    def test_create_request(self) -> None:
        """Test creating a permission request"""
        request = PermissionRequest(
            session_id="test-session",
            command="git commit",
            description="Create git commit"
        )

        assert request.session_id == "test-session"
        assert request.command == "git commit"
        assert request.description == "Create git commit"
        assert len(request.id) == 8

    def test_auto_generated_id(self) -> None:
        """Test that request ID is auto-generated"""
        request1 = PermissionRequest(session_id="test", command="cmd1")
        request2 = PermissionRequest(session_id="test", command="cmd2")

        assert request1.id != request2.id

    def test_auto_timestamp(self) -> None:
        """Test that timestamp is auto-generated"""
        before = time.time()
        request = PermissionRequest(session_id="test", command="cmd")
        after = time.time()

        assert before <= request.timestamp <= after


class TestPermissionService:
    """Tests for PermissionService"""

    @pytest.fixture
    def permission_service(self) -> PermissionService:
        """Create PermissionService instance"""
        return PermissionService()

    def test_auto_approve_session(self, permission_service: PermissionService) -> None:
        """Test auto approve session"""
        session_id = "test-session"
        permission_service.auto_approve_session(session_id)

        assert permission_service.is_auto_approved(session_id) is True
        assert permission_service.request(session_id, "any-command") is True

    def test_request_without_callback(self, permission_service: PermissionService) -> None:
        """Test request without callback returns False"""
        result = permission_service.request("session", "command")
        assert result is False

    def test_request_with_callback_approved(self) -> None:
        """Test request with callback that approves"""
        def callback(request: PermissionRequest) -> bool:
            return True

        service = PermissionService(on_request_callback=callback)
        result = service.request("session", "command")

        assert result is True

    def test_request_with_callback_denied(self) -> None:
        """Test request with callback that denies"""
        def callback(request: PermissionRequest) -> bool:
            return False

        service = PermissionService(on_request_callback=callback)
        result = service.request("session", "command")

        assert result is False

    def test_grant_persists(self, permission_service: PermissionService) -> None:
        """Test that granted permissions persist"""
        session_id = "test-session"
        command = "git commit"

        # Manually grant permission
        permission_service.grant_persistent(session_id, command)

        # Should be in granted commands
        assert command in permission_service.get_granted_commands(session_id)

    def test_revoke(self, permission_service: PermissionService) -> None:
        """Test revoking permissions"""
        session_id = "test-session"
        command = "git commit"

        permission_service.grant_persistent(session_id, command)
        assert command in permission_service.get_granted_commands(session_id)

        permission_service.revoke(session_id, command)
        assert command not in permission_service.get_granted_commands(session_id)

    def test_revoke_all(self, permission_service: PermissionService) -> None:
        """Test revoking all permissions for a session"""
        session_id = "test-session"

        permission_service.grant_persistent(session_id, "cmd1")
        permission_service.grant_persistent(session_id, "cmd2")
        permission_service.grant_persistent(session_id, "cmd3")

        permission_service.revoke_all(session_id)

        assert len(permission_service.get_granted_commands(session_id)) == 0

    def test_cache_ttl(self) -> None:
        """Test that permissions expire after TTL"""
        # Create service with 1 second TTL
        service = PermissionService(cache_ttl=1)
        session_id = "test-session"
        command = "git commit"

        service.grant_persistent(session_id, command)
        assert command in service.get_granted_commands(session_id)

        # Wait for TTL to expire
        time.sleep(1.1)

        # Should be expired
        assert command not in service.get_granted_commands(session_id)

    def test_get_pending_requests(self, permission_service: PermissionService) -> None:
        """Test getting pending requests"""
        # Pending requests are only created when callback is provided
        # and the callback doesn't immediately approve/deny
        def pending_callback(request: PermissionRequest) -> bool:
            return False  # Deny, but request stays in pending

        service = PermissionService(on_request_callback=pending_callback)
        service.request("session1", "command1")
        service.request("session1", "command2")
        service.request("session2", "command3")

        # Get all pending
        all_pending = service.get_pending_requests()
        assert len(all_pending) == 3

        # Get pending for specific session
        session1_pending = service.get_pending_requests("session1")
        assert len(session1_pending) == 2

    def test_get_stats(self, permission_service: PermissionService) -> None:
        """Test getting stats"""
        permission_service.grant_persistent("session1", "cmd1")
        permission_service.grant_persistent("session1", "cmd2")
        permission_service.grant_persistent("session2", "cmd3")
        permission_service.auto_approve_session("session3")

        stats = permission_service.get_stats()

        assert stats["total_granted"] == 3
        assert stats["pending_requests"] == 0
        assert stats["auto_approve_sessions"] == 1
        assert stats["active_sessions"] == 2

    def test_remove_auto_approve(self, permission_service: PermissionService) -> None:
        """Test removing auto approve session"""
        session_id = "test-session"
        permission_service.auto_approve_session(session_id)
        assert permission_service.is_auto_approved(session_id) is True

        permission_service.remove_auto_approve(session_id)
        assert permission_service.is_auto_approved(session_id) is False

    def test_callback_exception_handling(self) -> None:
        """Test that callback exceptions are handled"""
        def raising_callback(request: PermissionRequest) -> bool:
            raise Exception("Test exception")

        service = PermissionService(on_request_callback=raising_callback)
        result = service.request("session", "command")

        # Should return False on exception
        assert result is False


class TestPermissionRequestFlow:
    """Integration tests for permission request flow"""

    def test_full_request_flow(self) -> None:
        """Test full permission request flow"""
        approved_requests = []

        def callback(request: PermissionRequest) -> bool:
            approved_requests.append(request)
            return True

        service = PermissionService(on_request_callback=callback, cache_ttl=3600)
        session_id = "test-session"
        command = "git commit -m 'test'"

        # First request - should call callback
        result1 = service.request(session_id, command)
        assert result1 is True
        assert len(approved_requests) == 1

        # Second request - should use cache
        result2 = service.request(session_id, command)
        assert result2 is True
        assert len(approved_requests) == 1  # Callback not called again

    def test_deny_then_grant(self) -> None:
        """Test denying then granting permission"""
        denial_count = [0]

        def callback(request: PermissionRequest) -> bool:
            denial_count[0] += 1
            return False

        service = PermissionService(on_request_callback=callback)

        # First request - denied
        result1 = service.request("session", "command")
        assert result1 is False

        # Manually grant
        service.grant("req1", "session", "command")

        # Second request - should use cache
        result2 = service.request("session", "command")
        assert result2 is True
