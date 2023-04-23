from imap_tools import MailBox, A
import email

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
import os
load_dotenv()

import datetime
import logging

# Define the email account details
email_user = os.environ["EMAIL_USER"]
email_password = os.environ["EMAIL_PASSWORD"]
imap_server = 'imap.gmail.com'
imap_port = 993

# Define the expected sender email address
expected_senders = os.environ["EXPECTED_SENDERS"].strip().split(',')

# Timeout to use around connections and requests.
TIMEOUT = 60 * 10

def send_email(subject, body, original_msg, recipient, sender=email_user, password=email_password):
    #msg = MIMEText(body)
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    # quote the original email
    quoted_body = f"{body}\n\n----- Original Message -----\n"
    for line in original_msg.split('\n'):
        quoted_body += f"> {line}\n"

    # attach the quoted body to the MIME message
    msg.attach(MIMEText(quoted_body, 'plain'))

    smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    smtp_server.login(sender, password)
    smtp_server.sendmail(sender, [recipient], msg.as_string())
    smtp_server.quit()

def check_email_login():
    with MailBox(imap_server).login(email_user, email_password, 'INBOX') as mailbox:
        logging.info("Login to email confirmed")

def inner_loop_check():
    sixty_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=60)
    date_gte_criteria = sixty_minutes_ago.date()

    try:
        # waiting for updates TIMEOUT sec, print unseen immediately if any update
        with MailBox(imap_server).login(email_user, email_password, 'INBOX') as mailbox:
            msgs = [msg for msg in mailbox.fetch(A(seen=False, date_gte=date_gte_criteria))]
            if len(msgs) == 0:
                    responses = mailbox.idle.wait(timeout=TIMEOUT)
                    if responses:
                        msgs = [msg for msg in mailbox.fetch(A(seen=False, date_gte=date_gte_criteria))]
            if len(msgs) > 0:
                for msg in msgs:
                    if msg.from_ not in expected_senders: continue

                    # Check the "Received" headers for additional security
                    received_headers = msg.headers.get('received', [])
                    is_valid_email = False
                    for received_header in received_headers:
                        # check if the header contains a trusted domain
                        if 'google.com' in received_header:
                            is_valid_email = True
                            break

                    # Skip if the email is not valid based on the "Received" headers
                    if not is_valid_email:
                        continue

                    return msg
    except Exception as e:
        logging.error(f"Exception {e}")

    return None
