"""Tests for the abstract AI provider interface."""

from typing import Any

import pytest

from nelson.providers.base import AIProvider, AIResponse, ProviderError


class TestAIResponse:
    """Tests for AIResponse dataclass."""

    def test_create_success_response(self) -> None:
        """Test creating a successful response."""
        response = AIResponse(
            content="Test response",
            raw_output="Raw: Test response",
            metadata={"model": "sonnet", "tokens": 100},
        )

        assert response.content == "Test response"
        assert response.raw_output == "Raw: Test response"
        assert response.metadata["model"] == "sonnet"
        assert response.is_error is False
        assert response.error_message is None

    def test_create_error_response(self) -> None:
        """Test creating an error response."""
        response = AIResponse(
            content="",
            raw_output="Error occurred",
            metadata={},
            is_error=True,
            error_message="API rate limit exceeded",
        )

        assert response.content == ""
        assert response.is_error is True
        assert response.error_message == "API rate limit exceeded"

    def test_metadata_can_be_empty(self) -> None:
        """Test that metadata can be an empty dict."""
        response = AIResponse(content="test", raw_output="test", metadata={})
        assert response.metadata == {}


class TestProviderError:
    """Tests for ProviderError exception."""

    def test_create_retryable_error(self) -> None:
        """Test creating a retryable error."""
        error = ProviderError("Network timeout", is_retryable=True)

        assert str(error) == "Network timeout"
        assert error.message == "Network timeout"
        assert error.is_retryable is True
        assert error.original_error is None

    def test_create_non_retryable_error(self) -> None:
        """Test creating a non-retryable error."""
        error = ProviderError("Invalid API key", is_retryable=False)

        assert str(error) == "Invalid API key"
        assert error.message == "Invalid API key"
        assert error.is_retryable is False

    def test_error_with_original_exception(self) -> None:
        """Test error with underlying exception."""
        original = ValueError("Bad value")
        error = ProviderError("Provider failed", is_retryable=True, original_error=original)

        assert error.message == "Provider failed"
        assert error.original_error is original
        assert isinstance(error.original_error, ValueError)

    def test_default_is_retryable(self) -> None:
        """Test that errors are retryable by default."""
        error = ProviderError("Some error")
        assert error.is_retryable is True


class TestAIProvider:
    """Tests for AIProvider abstract base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that AIProvider cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            AIProvider()  # type: ignore[abstract]

    def test_must_implement_execute(self) -> None:
        """Test that subclasses must implement execute()."""

        class IncompleteProvider(AIProvider):
            def validate_response(self, response: AIResponse) -> bool:
                return True

            def extract_status_block(self, response: AIResponse) -> dict[str, Any]:
                return {}

            def is_available(self) -> bool:
                return True

            def get_cost(self, response: AIResponse) -> float:
                return 0.0

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteProvider()  # type: ignore[abstract]

    def test_must_implement_all_abstract_methods(self) -> None:
        """Test that subclasses must implement all abstract methods."""

        class CompleteProvider(AIProvider):
            def execute(
                self,
                system_prompt: str,
                user_prompt: str,
                model: str,
                max_retries: int = 3,
                retry_delay: float = 3.0,
            ) -> AIResponse:
                return AIResponse(content="test", raw_output="test", metadata={})

            def validate_response(self, response: AIResponse) -> bool:
                return True

            def extract_status_block(self, response: AIResponse) -> dict[str, Any]:
                return {}

            def is_available(self) -> bool:
                return True

            def get_cost(self, response: AIResponse) -> float:
                return 0.0

        # Should not raise - all methods implemented
        provider = CompleteProvider()
        assert isinstance(provider, AIProvider)

    def test_execute_signature(self) -> None:
        """Test execute method signature requirements."""

        class TestProvider(AIProvider):
            def execute(
                self,
                system_prompt: str,
                user_prompt: str,
                model: str,
                max_retries: int = 3,
                retry_delay: float = 3.0,
            ) -> AIResponse:
                return AIResponse(
                    content=f"Model: {model}",
                    raw_output=f"System: {system_prompt}\nUser: {user_prompt}",
                    metadata={"retries": max_retries, "delay": retry_delay},
                )

            def validate_response(self, response: AIResponse) -> bool:
                return bool(response.content)

            def extract_status_block(self, response: AIResponse) -> dict[str, Any]:
                return {"exit_signal": False}

            def is_available(self) -> bool:
                return True

            def get_cost(self, response: AIResponse) -> float:
                return 0.01

        provider = TestProvider()
        response = provider.execute(system_prompt="System", user_prompt="User", model="test-model")

        assert response.content == "Model: test-model"
        assert response.metadata["retries"] == 3
        assert response.metadata["delay"] == 3.0

    def test_validate_response_signature(self) -> None:
        """Test validate_response method signature."""

        class TestProvider(AIProvider):
            def execute(
                self,
                system_prompt: str,
                user_prompt: str,
                model: str,
                max_retries: int = 3,
                retry_delay: float = 3.0,
            ) -> AIResponse:
                return AIResponse(content="test", raw_output="test", metadata={})

            def validate_response(self, response: AIResponse) -> bool:
                return "---NELSON_STATUS---" in response.content

            def extract_status_block(self, response: AIResponse) -> dict[str, Any]:
                return {}

            def is_available(self) -> bool:
                return True

            def get_cost(self, response: AIResponse) -> float:
                return 0.0

        provider = TestProvider()

        valid_response = AIResponse(
            content="---NELSON_STATUS---\nSTATUS: COMPLETE\n---END_NELSON_STATUS---",
            raw_output="",
            metadata={},
        )
        invalid_response = AIResponse(content="No status", raw_output="", metadata={})

        assert provider.validate_response(valid_response) is True
        assert provider.validate_response(invalid_response) is False

    def test_extract_status_block_signature(self) -> None:
        """Test extract_status_block method returns dict."""

        class TestProvider(AIProvider):
            def execute(
                self,
                system_prompt: str,
                user_prompt: str,
                model: str,
                max_retries: int = 3,
                retry_delay: float = 3.0,
            ) -> AIResponse:
                return AIResponse(content="test", raw_output="test", metadata={})

            def validate_response(self, response: AIResponse) -> bool:
                return True

            def extract_status_block(self, response: AIResponse) -> dict[str, Any]:
                return {
                    "status": "COMPLETE",
                    "exit_signal": True,
                    "tasks_completed": 1,
                }

            def is_available(self) -> bool:
                return True

            def get_cost(self, response: AIResponse) -> float:
                return 0.0

        provider = TestProvider()
        response = AIResponse(content="test", raw_output="test", metadata={})
        status = provider.extract_status_block(response)

        assert isinstance(status, dict)
        assert status["status"] == "COMPLETE"
        assert status["exit_signal"] is True

    def test_is_available_signature(self) -> None:
        """Test is_available method returns bool."""

        class TestProvider(AIProvider):
            def __init__(self, available: bool) -> None:
                self._available = available

            def execute(
                self,
                system_prompt: str,
                user_prompt: str,
                model: str,
                max_retries: int = 3,
                retry_delay: float = 3.0,
            ) -> AIResponse:
                return AIResponse(content="test", raw_output="test", metadata={})

            def validate_response(self, response: AIResponse) -> bool:
                return True

            def extract_status_block(self, response: AIResponse) -> dict[str, Any]:
                return {}

            def is_available(self) -> bool:
                return self._available

            def get_cost(self, response: AIResponse) -> float:
                return 0.0

        available_provider = TestProvider(available=True)
        unavailable_provider = TestProvider(available=False)

        assert available_provider.is_available() is True
        assert unavailable_provider.is_available() is False

    def test_get_cost_signature(self) -> None:
        """Test get_cost method returns float."""

        class TestProvider(AIProvider):
            def execute(
                self,
                system_prompt: str,
                user_prompt: str,
                model: str,
                max_retries: int = 3,
                retry_delay: float = 3.0,
            ) -> AIResponse:
                return AIResponse(content="test", raw_output="test", metadata={"cost": 0.05})

            def validate_response(self, response: AIResponse) -> bool:
                return True

            def extract_status_block(self, response: AIResponse) -> dict[str, Any]:
                return {}

            def is_available(self) -> bool:
                return True

            def get_cost(self, response: AIResponse) -> float:
                cost: float = response.metadata.get("cost", 0.0)
                return cost

        provider = TestProvider()
        response = provider.execute(system_prompt="", user_prompt="", model="test-model")
        cost = provider.get_cost(response)

        assert isinstance(cost, float)
        assert cost == 0.05
