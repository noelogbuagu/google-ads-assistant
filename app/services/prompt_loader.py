import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError, meta


def _strip_frontmatter(text: str) -> str:
    """Removes YAML frontmatter (--- ... ---) from the start of a template string."""
    return re.sub(r"^\s*---.*?---\s*", "", text, flags=re.DOTALL)


"""
Prompt Management Module

This module provides functionality for loading and rendering prompt templates with frontmatter.
It uses Jinja2 for template rendering and python-frontmatter for metadata handling,
implementing a singleton pattern for template environment management.
"""


class PromptManager:
    """Manager class for handling prompt templates and their metadata.

    This class provides functionality to load prompt templates from files,
    render them with variables, and extract template metadata and requirements.
    It implements a singleton pattern for the Jinja2 environment to ensure
    consistent template loading across the application.

    Attributes:
        _env: Class-level singleton instance of Jinja2 Environment

    Example:
        # Render a prompt template with variables
        prompt = PromptManager.get_prompt("greeting", name="Alice")

        # Get template metadata and required variables
        info = PromptManager.get_template_info("greeting")
    """

    _env: Environment | None = None

    @classmethod
    def _get_env(cls, templates_dir="prompts") -> Environment:
        """Gets or creates the Jinja2 environment singleton.

        Args:
            templates_dir: Directory name containing prompt templates, relative to app/

        Returns:
            Configured Jinja2 Environment instance

        Note:
            Uses StrictUndefined to raise errors for undefined variables,
            helping catch template issues early.
        """
        templates_dir = Path(__file__).parent.parent / templates_dir
        if cls._env is None:
            cls._env = Environment(
                loader=FileSystemLoader(templates_dir),
                undefined=StrictUndefined,
            )
        return cls._env

    @staticmethod
    def get_prompt(template: str, **kwargs) -> str:
        """Loads and renders a prompt template with provided variables.

        Args:
            template: Name of the template file (without .j2 extension)
            **kwargs: Variables to use in template rendering

        Returns:
            Rendered template string

        Raises:
            ValueError: If template rendering fails
            FileNotFoundError: If template file doesn't exist
        """
        env = PromptManager._get_env()
        template_path = f"{template}.j2"
        assert env.loader is not None
        _, filepath, _ = env.loader.get_source(env, template_path)
        assert filepath is not None, f"Could not resolve path for template: {template_path}"
        with open(filepath) as file:
            raw = file.read()

        content = _strip_frontmatter(raw)
        jinja_template = env.from_string(content)
        try:
            return jinja_template.render(**kwargs)
        except TemplateError as e:
            raise ValueError(f"Error rendering template: {str(e)}")

    @staticmethod
    def get_template_info(template: str) -> dict:
        """Extracts metadata and variable requirements from a template.

        Args:
            template: Name of the template file (without .j2 extension)

        Returns:
            Dictionary containing:
                - name: Template name
                - description: Template description from frontmatter
                - author: Template author from frontmatter
                - variables: List of required template variables
                - frontmatter: Raw frontmatter metadata dictionary

        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        env = PromptManager._get_env()
        template_path = f"{template}.j2"
        assert env.loader is not None
        _, filepath, _ = env.loader.get_source(env, template_path)
        assert filepath is not None, f"Could not resolve path for template: {template_path}"
        with open(filepath) as file:
            raw = file.read()

        content = _strip_frontmatter(raw)
        ast = env.parse(content)
        variables = meta.find_undeclared_variables(ast)

        return {
            "name": template,
            "description": "",
            "author": "",
            "variables": list(variables),
            "frontmatter": {},
        }
