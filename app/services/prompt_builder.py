"""Template rendering engine for system prompts and welcome messages."""


class PromptBuilder:
    def render(self, template: str, variables: dict) -> str:
        """Replace {{variable}} and {variable} placeholders with values."""
        result = template
        for key, value in variables.items():
            rendered_value = str(value or "")
            double_placeholder = f"{{{{{key}}}}}"
            single_placeholder = f"{{{key}}}"
            result = result.replace(double_placeholder, rendered_value)
            result = result.replace(single_placeholder, rendered_value)
        return result

    def build_system_prompt(
        self,
        shared_template: str,
        business: dict,
        is_outbound: bool = False,
        extra_vars: dict | None = None,
    ) -> str:
        """Build the final system prompt for a call.

        extra_vars: optional dict of additional variables (e.g. customerName, chatSummary)
        that should be substituted into the shared_template when rendering server-side.
        """
        variables = {
            "agentName": "Ananya",
            "businessName": business.get("display_name", ""),
            "city": business.get("city", "Bengaluru"),
            "hours": business.get("hours", "business hours"),
            "services": business.get("services", "our services"),
            "fallbackNumber": business.get("fallback_number", ""),
            "chatContext": " (from chat context)" if is_outbound else "",
        }

        # Merge any extra variables provided by the caller. This lets callers
        # inject runtime values like customerName or chatSummary so server-side
        # rendering includes them (avoids asking the caller to repeat).
        if extra_vars:
            for k, v in extra_vars.items():
                variables[k] = v

        return self.render(shared_template, variables)

    def build_welcome_message(
        self,
        template: str,
        variables: dict,
    ) -> str:
        """Build the first message for the assistant."""
        return self.render(template, variables)


prompt_builder = PromptBuilder()
