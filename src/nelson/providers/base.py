"""Abstract base class for AI provider implementations.

This module defines the interface that all AI providers (Claude, OpenAI Codex, etc.)
must implement to work with Nelson's workflow engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AIResponse:
    """Response from an AI provider call.

    Attributes:
        content: The text response from the AI
        raw_output: Raw output from the provider (for debugging/logging)
        metadata: Additional metadata (model used, tokens, cost, etc.)
        is_error: Whether this response represents an error
        error_message: Error message if is_error is True
    """

    content: str
    raw_output: str
    metadata: dict[str, Any]
    is_error: bool = False
    error_message: str | None = None


class ProviderError(Exception):
    """Base exception for AI provider errors.

    Attributes:
        message: Human-readable error message
        is_retryable: Whether this error is transient and should be retried
        original_error: The underlying exception if any
    """

    def __init__(
        self,
        message: str,
        is_retryable: bool = True,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize provider error.

        Args:
            message: Human-readable error message
            is_retryable: Whether this error should trigger retry logic
            original_error: The underlying exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.is_retryable = is_retryable
        self.original_error = original_error


class AIProvider(ABC):
    """Abstract base class for AI provider implementations.

    Each provider (Claude, OpenAI Codex, etc.) must implement this interface
    to integrate with Nelson's workflow engine. The provider is responsible for:

    - Executing AI calls with system and user prompts
    - Parsing provider-specific output formats
    - Handling retries for transient errors
    - Extracting cost/token metadata
    - Validating responses

    Example:
        class MyProvider(AIProvider):
            def execute(self, system_prompt, user_prompt, model):
                # Call provider API
                # Parse response
                # Return AIResponse
                pass
    """

    @abstractmethod
    def execute(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_retries: int = 3,
        retry_delay: float = 3.0,
    ) -> AIResponse:
        """Execute an AI call with the given prompts.

        This method should:
        1. Call the provider's API with the given prompts
        2. Handle retries for transient errors
        3. Parse the response into an AIResponse object
        4. Extract metadata (cost, tokens, model used)
        5. Validate the response format

        Args:
            system_prompt: The system-level prompt (Nelson's instructions)
            user_prompt: The user/task-specific prompt
            model: Model identifier (e.g., "sonnet", "opus", "gpt-4")
            max_retries: Maximum number of retry attempts for transient errors
            retry_delay: Delay in seconds between retry attempts

        Returns:
            AIResponse object containing the provider's response

        Raises:
            ProviderError: If the call fails after all retries
        """
        pass

    @abstractmethod
    def validate_response(self, response: AIResponse) -> bool:
        """Validate that the response contains required elements.

        Different providers may have different validation requirements.
        For Nelson, this typically means checking for the status block.

        Args:
            response: The AIResponse to validate

        Returns:
            True if response is valid, False otherwise
        """
        pass

    @abstractmethod
    def extract_status_block(self, response: AIResponse) -> dict[str, Any]:
        """Extract the NELSON_STATUS block from the response.

        Parses the response content to find and extract the status block
        delimited by ---NELSON_STATUS--- and ---END_NELSON_STATUS---.

        Expected format:
            ---NELSON_STATUS---
            STATUS: IN_PROGRESS|COMPLETE|BLOCKED
            TASKS_COMPLETED_THIS_LOOP: N
            FILES_MODIFIED: N
            TESTS_STATUS: PASSING|FAILING|NOT_RUN
            WORK_TYPE: IMPLEMENTATION|TESTING|DOCUMENTATION|REFACTORING
            EXIT_SIGNAL: true|false
            RECOMMENDATION: one-line text
            ---END_NELSON_STATUS---

        Args:
            response: The AIResponse containing the status block

        Returns:
            Dictionary with parsed status fields:
                - status: str (IN_PROGRESS|COMPLETE|BLOCKED)
                - tasks_completed: int
                - files_modified: int
                - tests_status: str (PASSING|FAILING|NOT_RUN)
                - work_type: str
                - exit_signal: bool
                - recommendation: str

        Raises:
            ProviderError: If status block is missing or malformed
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and configured correctly.

        This should verify:
        - Required command/executable exists
        - API credentials are configured (if applicable)
        - Any required dependencies are available

        Returns:
            True if provider is ready to use, False otherwise
        """
        pass

    @abstractmethod
    def get_cost(self, response: AIResponse) -> float:
        """Extract cost information from the response metadata.

        Args:
            response: The AIResponse containing cost metadata

        Returns:
            Cost in USD, or 0.0 if cost cannot be determined
        """
        pass
