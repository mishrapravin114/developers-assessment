from pydantic.networks import EmailStr

from app.models import Message
from app.utils import generate_test_email, send_email


class UtilsService:
    @staticmethod
    def test_email(email_to: EmailStr) -> Message:
        """
        Test emails.
        """
        email_data = generate_test_email(email_to=email_to)
        send_email(
            email_to=email_to,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
        return Message(message="Test email sent")

    @staticmethod
    def health_check() -> bool:
        """
        Health check endpoint.
        """
        return True
