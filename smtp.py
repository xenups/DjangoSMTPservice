import os
import email
import smtplib
from time import sleep
from django.conf import settings
from email.mime.text import MIMEText
from django.utils.encoding import force_text
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication


class SMTPService(object):
    MAX_RETRY = 2
    AUTHENTICATION_FAILED_CODE = 454
    required_config_fields = ['username', 'password', 'host', 'port']

    def __init__(self, from_email=settings.DEFAULT_FROM_EMAIL, reply_email=None, config=settings.DEFAULT_EMAIL_CONFIG):

        self._provider = config.get('provider')
        self._from_email = from_email
        self._reply_email = reply_email

        self._username = config['username']
        self._password = config['password']

        self._set_tls(config.get('tls'))
        self._smtp_service = smtplib.SMTP(config['host'], config['port'])
        self._smtp_service.login(self._username, self._password)

    def send_mail(self, subject: str, receiver: [], html_msg, filepath=None, filename=None, quite=True):
        for _, address in enumerate(receiver):
            mail = self._create_mail_body(subject, address, html_msg)
            mail = self._add_mail_attachment(filepath, filename, mail)
            self._process_mail(mail, quite)

    def _create_mail_body(self, subject: str, address: str, html_msg) -> MIMEMultipart:
        message = MIMEMultipart()
        message['Subject'] = email.header.Header(force_text(subject), 'utf-8')
        message['From'] = self._from_email
        message['To'] = address
        message = self._add_aws_headers(message)
        body = MIMEText(html_msg.encode('utf-8'), 'html', 'utf-8')
        message.attach(body)
        return message

    @staticmethod
    def _add_mail_attachment(message: MIMEMultipart, filepath=None, filename=None) -> MIMEMultipart:
        if filepath:
            if os.path.isfile(filepath) and os.access(filepath, os.R_OK):
                with open(filepath, "rb") as fp:
                    attachment = MIMEApplication(fp.read(), _subtype="csv")
                    fp.close()
                    attachment.add_header(
                        'Content-Disposition',
                        'attachment',
                        filename=filename
                    )
                message.attach(attachment)
            else:
                raise TypeError("File doesn't exist, and no data given.")
        return message

    def _process_mail(self, mails: [], quite: bool):
        sent_mail_count: int = 0
        current_retry: int = 0
        while sent_mail_count < len(mails):
            mail = mails[sent_mail_count]
            try:
                self._smtp_service.sendmail(mail['From'], [mail['To']], mail.as_string())
                current_retry = 0
                sent_mail_count += 1
            except smtplib.SMTPResponseException as e:
                if e.smtp_code == self.AUTHENTICATION_FAILED_CODE and current_retry < self.MAX_RETRY:
                    current_retry += 1
                    sleep(1)
                    continue
                raise e
            finally:
                if quite:
                    self._smtp_service.quit()

    def _set_tls(self, tls):
        if tls:
            self._smtp_service.starttls()

    def _add_aws_headers(self, message):
        if self._provider == 'AWS':
            if settings.SES_CONFIGURATION_SET:
                message['X-SES-CONFIGURATION-SET'] = settings.SES_CONFIGURATION_SET
        return message
