import os
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage

load_dotenv()

# Email configuration
sender_email: str = os.getenv("SENDER_EMAIL")
collector_email: str = os.getenv("COLLECTOR_EMAIL")
email_password: str = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "")  # Remove spaces from app password

# SMTP settings - defaults to Gmail, can be overridden
smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
smtp_port: int = int(os.getenv("SMTP_PORT", "465"))


def send_email(sender_address: str, recipient_address: list[str], subject: str = None, content: str = "", is_html: bool = False) -> None:
    """
    Default email send function using SMTP

    :param sender_address: Sender's address
    :type sender_address: str
    :param recipient_address: Send the email to this address(es)
    :type recipient_address: list[str]
    :param subject: Email's subject
    :type subject: str
    :param content: The email body
    :type content: str
    :param is_html: Enable if the content is html content, otherwise it will be treated as plain text
    :type is_html: bool
    """
    # Create email message
    msg = EmailMessage()
    msg["Subject"] = subject or "No Subject"
    msg["From"] = sender_address
    msg["To"] = ", ".join(recipient_address)

    # Set content based on type
    if is_html:
        msg.set_content(content, subtype="html")
    else:
        msg.set_content(content)

    # Send the email
    try:
        # Port 465 uses SSL, port 587 uses STARTTLS
        if smtp_port == 465:
            # Gmail uses direct SSL connection
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                server.login(sender_address, email_password)
                server.send_message(msg)
        else:
            # Outlook (port 587) uses STARTTLS
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_address, email_password)
                server.send_message(msg)

        print("="*10 + "EMAIL SENT" + "="*10)
        print(f"Sender: {sender_address}\nRecipient: {recipient_address}\nSubject: {subject}\nContent: {content}")
        print('=' * (22 + len("EMAIL SENT")))
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        raise



def send_notify_email(content:str="", custom_subject:str="NOTIFICATION") -> None:
    """
    Sends a notification email to the collector email adress
    
    :param content: The content to be sent
    :type content: str
    :param custom_subject: Only change if it the email is not a notification
    :type custom_subject: str
    """

    send_email(sender_email, [collector_email], custom_subject, content)

