"""AI engine for log analysis and intelligent suggestions."""

import os
from typing import Optional

from litellm import completion
from rich.console import Console

from nanoship.config import settings

console = Console()


class AIEngine:
    """AI-powered analysis and suggestion engine."""

    def __init__(self):
        self.provider = settings.llm_provider
        self.api_key = settings.llm_api_key or os.getenv("LLM_API_KEY")
        self.model = settings.llm_model
        self.base_url = settings.llm_base_url

    def _get_completion(self, messages: list, temperature: float = 0.3) -> str:
        """Get completion from LLM."""
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }

            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.base_url:
                kwargs["base_url"] = self.base_url

            response = completion(**kwargs)
            return response.choices[0].message.content

        except Exception as e:
            console.print(f"[red]AI analysis failed: {e}[/red]")
            return f"Error: {e}"

    def analyze_logs(self, logs: str, service_name: str) -> dict:
        """Analyze application logs and identify issues."""
        system_prompt = """You are an expert DevOps engineer and system administrator.
Your task is to analyze application logs and identify:
1. The root cause of any errors or issues
2. Severity level (critical, warning, info)
3. Suggested fixes or remediation steps
4. Whether the issue requires immediate attention

Respond in JSON format:
{
    "issue_detected": true/false,
    "severity": "critical/warning/info",
    "root_cause": "description of the problem",
    "suggested_fix": "specific commands or steps to fix",
    "requires_attention": true/false
}"""

        user_prompt = f"""Analyze the following logs from service '{service_name}':

```
{logs[-4000:]}  # Last 4000 chars to stay within token limits
```

Provide your analysis in the requested JSON format."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self._get_completion(messages)

        # Try to parse JSON response
        try:
            import json
            # Extract JSON from response if wrapped in markdown
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            return json.loads(response.strip())
        except json.JSONDecodeError:
            return {
                "issue_detected": True,
                "severity": "warning",
                "root_cause": response,
                "suggested_fix": "Please review the logs manually",
                "requires_attention": True,
            }

    def analyze_project(self, project_info: dict) -> dict:
        """Analyze project structure and provide deployment recommendations."""
        system_prompt = """You are an expert DevOps engineer specializing in Docker and containerization.
Analyze the project information and provide:
1. Deployment best practices
2. Security recommendations
3. Performance optimizations
4. Potential issues to watch for

Respond in JSON format:
{
    "recommendations": ["list of recommendations"],
    "security_concerns": ["list of security issues"],
    "optimizations": ["list of performance optimizations"],
    "warnings": ["list of potential issues"]
}"""

        user_prompt = f"""Analyze this project for deployment:

```json
{project_info}
```

Provide your analysis in the requested JSON format."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self._get_completion(messages, temperature=0.2)

        try:
            import json
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except json.JSONDecodeError:
            return {
                "recommendations": [response],
                "security_concerns": [],
                "optimizations": [],
                "warnings": [],
            }

    def generate_nginx_config(self, domain: str, port: int, ssl: bool = True) -> str:
        """Generate optimized Nginx configuration."""
        system_prompt = """You are an expert Nginx administrator.
Generate a production-ready Nginx configuration with best practices for security and performance."""

        user_prompt = f"""Generate an Nginx configuration for:
- Domain: {domain}
- Backend port: {port}
- SSL: {'enabled' if ssl else 'disabled'}

Include:
- Security headers
- Gzip compression
- Rate limiting
- Proxy headers for proper forwarding
- WebSocket support if needed"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return self._get_completion(messages, temperature=0.2)

    def suggest_fix(self, error_message: str, context: str) -> str:
        """Suggest a fix for a deployment error."""
        system_prompt = """You are an expert DevOps engineer.
Given an error message and context, provide a specific, actionable fix.
Be concise and provide exact commands when possible."""

        user_prompt = f"""Error: {error_message}

Context: {context}

What is the fix?"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return self._get_completion(messages, temperature=0.2)

    def audit_server(self, server_info: dict) -> dict:
        """Audit server configuration and provide security recommendations."""
        system_prompt = """You are a security expert and system administrator.
Audit the server configuration and identify:
1. Security vulnerabilities
2. Performance bottlenecks
3. Best practice violations
4. Recommended hardening steps

Respond in JSON format:
{
    "security_score": 0-100,
    "critical_issues": ["list of critical issues"],
    "warnings": ["list of warnings"],
    "recommendations": ["list of recommendations"],
    "hardening_commands": ["specific commands to run"]
}"""

        user_prompt = f"""Audit this server configuration:

```json
{server_info}
```

Provide your audit in the requested JSON format."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self._get_completion(messages)

        try:
            import json
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except json.JSONDecodeError:
            return {
                "security_score": 50,
                "critical_issues": ["Could not parse audit results"],
                "warnings": [],
                "recommendations": [response],
                "hardening_commands": [],
            }
