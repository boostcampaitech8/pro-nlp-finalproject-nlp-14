"""Base classes for MIT Tools

This module defines the base classes for all MIT tools.
Tools are Pydantic models that can be serialized and used with LangChain.
"""

from abc import abstractmethod
from enum import Enum
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model


class ToolCategory(str, Enum):
    """Tool category determines HITL behavior"""

    QUERY = "query"  # Read-only, no HITL required
    MUTATION = "mutation"  # Write operation, requires HITL in Spotlight mode


class ToolParameter(BaseModel):
    """Definition of a tool parameter"""

    name: str = Field(description="Parameter name")
    description: str = Field(description="Human-readable description")
    param_type: str = Field(description="Python type hint (e.g., 'str', 'int', 'uuid')")
    required: bool = Field(default=True, description="Whether this parameter is required")
    default: Any = Field(default=None, description="Default value if not required")

    # HITL 폼 확장 필드
    input_type: str = Field(
        default="text",
        description="Input type for HITL form: text, select, multiselect, checkbox, datetime, number, textarea"
    )
    options_source: str | None = Field(
        default=None,
        description="Dynamic options source (e.g., 'user_teams' for team selection)"
    )
    display_field: str | None = Field(
        default=None,
        description="Field name to display as label (e.g., 'name' for team name instead of team_id)"
    )
    placeholder: str | None = Field(default=None, description="Input placeholder hint")

    model_config = {"frozen": True}


class MITTool(BaseModel):
    """Base class for all MIT tools

    All tools must inherit from this class and implement the execute method.
    Tools are categorized as either QUERY (read-only) or MUTATION (write).

    Example:
        class GetMeetingsTool(MITTool):
            name: str = "get_meetings"
            description: str = "Get list of meetings"
            category: ToolCategory = ToolCategory.QUERY
            parameters: list[ToolParameter] = [
                ToolParameter(name="team_id", description="Team ID", param_type="uuid"),
            ]

            async def execute(self, user_id: str, **kwargs) -> dict:
                # Implementation here
                pass
    """

    name: str = Field(description="Unique tool name")
    description: str = Field(description="Human-readable description for LLM")
    category: ToolCategory = Field(description="Tool category (query or mutation)")
    parameters: list[ToolParameter] = Field(
        default_factory=list, description="List of tool parameters"
    )
    # HITL 표시용 템플릿: 자연어 텍스트에서 {{param_name}} 부분이 input으로 대체됨
    # 예: "{{team_id}} 팀에 '{{title}}' 회의를 {{scheduled_at}}에 만들까요?"
    display_template: str | None = Field(
        default=None,
        description="Natural language template for HITL display. Use {{param_name}} for input placeholders."
    )

    model_config = {"arbitrary_types_allowed": True}

    @abstractmethod
    async def execute(self, user_id: str, **kwargs) -> dict:
        """Execute the tool with provided arguments

        Args:
            user_id: The ID of the user executing the tool
            **kwargs: Tool-specific arguments matching parameters

        Returns:
            dict: Result of the tool execution
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def get_required_params(self) -> list[ToolParameter]:
        """Get list of required parameters"""
        return [p for p in self.parameters if p.required]

    def get_optional_params(self) -> list[ToolParameter]:
        """Get list of optional parameters"""
        return [p for p in self.parameters if not p.required]

    def get_param_names(self) -> list[str]:
        """Get list of all parameter names"""
        return [p.name for p in self.parameters]

    def validate_args(self, args: dict) -> tuple[bool, list[str]]:
        """Validate that all required arguments are provided

        Args:
            args: Dictionary of provided arguments

        Returns:
            tuple: (is_valid, list of missing required parameter names)
        """
        missing = []
        for param in self.get_required_params():
            if param.name not in args or args[param.name] is None:
                missing.append(param.name)
        return len(missing) == 0, missing

    def to_prompt_description(self) -> str:
        """Generate description for LLM prompt

        Returns:
            str: Formatted description including parameters
        """
        params_desc = []
        for p in self.parameters:
            req = "(required)" if p.required else "(optional)"
            params_desc.append(f"    - {p.name}: {p.description} [{p.param_type}] {req}")

        params_str = "\n".join(params_desc) if params_desc else "    (no parameters)"

        return f"""- {self.name}: {self.description}
  Category: {self.category.value}
  Parameters:
{params_str}"""

    def generate_confirmation_message(self, extracted_params: dict) -> str:
        """Generate HITL confirmation message for mutation tools

        Args:
            extracted_params: Parameters extracted from user input

        Returns:
            str: Formatted confirmation message
        """
        if self.category != ToolCategory.MUTATION:
            return ""

        lines = [f"{self.description}을(를) 수행할까요?"]

        # Show extracted parameters if any
        extracted_items = [
            (param, extracted_params[param.name])
            for param in self.parameters
            if param.name in extracted_params and extracted_params[param.name] is not None
        ]

        if extracted_items:
            lines.append("")
            lines.append("입력된 정보:")
            for param, value in extracted_items:
                lines.append(f"  - {param.description}: {value}")

        # Note: Missing fields are handled by frontend via required_fields
        # No longer showing "추가로 필요한 정보" here to avoid UI/message mismatch

        return "\n".join(lines)

    def to_langchain_tool(self) -> StructuredTool:
        """Convert MITTool to LangChain StructuredTool for bind_tools

        Returns:
            StructuredTool: LangChain-compatible tool with dynamic args schema
        """
        # Build dynamic Pydantic schema from parameters
        fields: dict[str, Any] = {}
        type_mapping = {
            "str": str,
            "string": str,
            "int": int,
            "uuid": str,
            "datetime": str,
        }

        for p in self.parameters:
            python_type = type_mapping.get(p.param_type.lower(), str)
            if p.required:
                fields[p.name] = (python_type, Field(description=p.description))
            else:
                fields[p.name] = (
                    python_type | None,
                    Field(default=p.default, description=p.description),
                )

        # Ensure at least one field (StructuredTool requirement)
        if not fields:
            fields["placeholder"] = (str | None, Field(default=None, description="No parameters required"))

        ArgsSchema = create_model(f"{self.name}Input", **fields)

        # Placeholder functions (actual execution happens in tools.py node)
        def placeholder(**kwargs: Any) -> str:
            return f"TOOL:{self.name}"

        async def async_placeholder(**kwargs: Any) -> str:
            return f"TOOL:{self.name}"

        return StructuredTool(
            name=self.name,
            description=self.description,
            args_schema=ArgsSchema,
            func=placeholder,
            coroutine=async_placeholder,
        )
