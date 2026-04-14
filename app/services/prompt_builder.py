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
    ) -> str:
        """Build the final system prompt for a call."""
        variables = {
            "agentName": "Ananya",
            "businessName": business.get("display_name", ""),
            "city": business.get("city", "Bengaluru"),
            "hours": business.get("hours", "business hours"),
            "services": business.get("services", "our services"),
            "fallbackNumber": business.get("fallback_number", ""),
            "chatContext": " (from chat context)" if is_outbound else "",
        }
        return self.render(shared_template, variables)

    def build_welcome_message(
        self,
        template: str,
        variables: dict,
    ) -> str:
        """Build the first message for the assistant."""
        return self.render(template, variables)


prompt_builder = PromptBuilder()
