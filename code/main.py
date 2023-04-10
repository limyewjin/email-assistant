import imaplib
import email
import re
import logging

# Define the email account details
email_user = 'yourbotemail@gmail.com'
email_password = 'yourbotpassword'
imap_server = 'imap.gmail.com'
imap_port = 993

# Define the expected sender email address
expected_sender = 'sender@example.com'

# Define a regular expression for extracting the message text
message_regex = r'(?<=Subject: ).*'

# Connect to the email account using IMAP
imap = imaplib.IMAP4_SSL(imap_server, imap_port)
imap.login(email_user, email_password)
imap.select('INBOX')

# Enable the IDLE command to wait for new messages
idle_tag = imap.send('IDLE')
response = imap.readline().decode('utf-8')
if not response.startswith('+'):
    logging.error(f"IDLE command failed: {response}")

# Loop indefinitely and check for new emails as they arrive
while True:
    try:
        # Wait for the server to send an IDLE notification
        response = imap.readline().decode('utf-8')
        if response != 'OK IDLE completed\r\n':
            logging.error(f"IDLE notification failed: {response}")
            continue

        # Process any new messages in the INBOX
        typ, data = imap.search(None, f'(UNSEEN FROM "{expected_sender}")')
        for num in data[0].split():
            typ, data = imap.fetch(num, '(RFC822)')
            email_body = data[0][1]
            email_message = email.message_from_bytes(email_body)

            # Verify the email's legitimacy by checking the sender and DKIM signature
            sender = email_message['From']
            if sender != expected_sender:
                logging.warning(f"Unexpected sender '{sender}', ignoring email")
                continue

            dkim_signature = email_message.get('DKIM-Signature')
            if not dkim_signature:
                logging.warning("Email has no DKIM signature, ignoring email")
                continue

            # Extract the message text and generate a response
            subject = email_message['Subject']
            message_match = re.search(message_regex, subject)
            if not message_match:
                logging.warning(f"Email subject '{subject}' has no message text, ignoring email")
                continue

            message_text = message_match.group(0)
            response_text = generate_response(message_text) # Replace with your own response generation code

            # Send the response back to the sender
            reply_message = email.message.EmailMessage()
            reply_message['From'] = email_user
            reply_message['To'] = sender
            reply_message['Subject'] = 'Re: ' + subject
            reply_message.set_content(response_text)

            imap.append('INBOX', None, None, str(reply_message).encode('utf-8'))
            logging.info(f"Sent response to '{sender}': {response_text}")

            # Mark the email as read
            imap.store(num, '+FLAGS', '\Seen')

        # Send a new IDLE command to wait for the next notification
        idle_tag = imap.send('IDLE')
    except Exception as e:
        logging.error(f"Exception occurred: {e}")
        imap = imaplib.IMAP4_SSL(imap_server, imap_port)
        imap.login(email_user, email_password)
        imap.select('INBOX')
        idle_tag = imap.send('IDLE')

