"""
Unit tests for InsightFace engine model path resolution.

Feature: cloud-deployment
Validates: Requirements 6.1, 6.2, 6.3, 6.4
"""

import os
import sys
import pytest
from unittest.mock import patch

# Ensure backend/ is on the path so we can import model.insightface_engine
sys.path.insert(0, os.path.dirname(__file__))


class TestResolveModelRoot:
    """Tests for _resolve_model_root() function."""

    def test_model_root_env_var_used_when_set(self, tmp_path):
        """(a) When MODEL_ROOT points to an existing directory, return that path."""
        with patch.dict(os.environ, {'MODEL_ROOT': str(tmp_path)}, clear=False):
            # Re-import to pick up fresh env state
            from model.insightface_engine import _resolve_model_root
            result = _resolve_model_root()
            assert result == str(tmp_path)

    def test_model_root_default_resolves_to_repo_root(self):
        """(b) When MODEL_ROOT is unset, default resolves to repo root (parent of backend/)."""
        env = {k: v for k, v in os.environ.items() if k != 'MODEL_ROOT'}
        with patch.dict(os.environ, env, clear=True):
            from model.insightface_engine import _resolve_model_root
            result = _resolve_model_root()
            # The repo root should be a valid directory
            assert os.path.isdir(result)
            # Verify it's the repo root by checking buffalo_l/ exists there
            assert os.path.isdir(os.path.join(result, 'buffalo_l')), \
                f"Expected buffalo_l/ at repo root {result}"

    def test_model_root_raises_runtime_error_when_missing(self, tmp_path):
        """(c) When the resolved path does not exist, raise RuntimeError with the path."""
        nonexistent = str(tmp_path / "does_not_exist")
        with patch.dict(os.environ, {'MODEL_ROOT': nonexistent}, clear=False):
            from model.insightface_engine import _resolve_model_root
            with pytest.raises(RuntimeError) as exc_info:
                _resolve_model_root()
            assert nonexistent in str(exc_info.value)

    def test_model_root_error_message_is_descriptive(self, tmp_path):
        """RuntimeError message should mention MODEL_ROOT and buffalo_l."""
        nonexistent = str(tmp_path / "missing_dir")
        with patch.dict(os.environ, {'MODEL_ROOT': nonexistent}, clear=False):
            from model.insightface_engine import _resolve_model_root
            with pytest.raises(RuntimeError) as exc_info:
                _resolve_model_root()
            error_msg = str(exc_info.value)
            assert 'MODEL_ROOT' in error_msg or 'buffalo_l' in error_msg

    def test_model_root_logs_resolved_path(self, tmp_path, caplog):
        """_resolve_model_root() should log the resolved path at INFO level."""
        import logging
        with patch.dict(os.environ, {'MODEL_ROOT': str(tmp_path)}, clear=False):
            with caplog.at_level(logging.INFO, logger='model.insightface_engine'):
                from model.insightface_engine import _resolve_model_root
                _resolve_model_root()
            assert any(
                'InsightFace' in record.message or str(tmp_path) in record.message
                for record in caplog.records
            )
