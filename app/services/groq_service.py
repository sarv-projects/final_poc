"""Groq API client for transcript summarization."""

from groq import Groq

from app.core.config import settings


class GroqService:
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)

    def summarize_transcript(self, transcript: str, call_type: str = "inbound") -> str:
        """Generate a concise summary of the call transcript."""
        prompt = f"""Summarize this {call_type} call transcript in 2-3 sentences.
Include: what the customer needed, what was resolved, and any follow-up actions.

Transcript:
{transcript}

Summary:"""

        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes voice call transcripts.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=150,
        )
        return response.choices[0].message.content or "No summary available."


groq_service = GroqService()
