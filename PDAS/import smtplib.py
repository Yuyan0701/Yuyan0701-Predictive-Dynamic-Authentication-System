import smtplib

server = 'sandbox.smtp.mailtrap.io'
port = 2525

try:
    with smtplib.SMTP(server, port) as smtp:
        smtp.ehlo()  # 发送 EHLO 命令
        print("Connection successful!")
except Exception as e:
    print(f"Failed to connect: {e}")
