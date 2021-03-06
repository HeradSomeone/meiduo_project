from django.core.mail import send_mail
from celery_tasks.main import celery_app
from django.conf import settings
#   给函数添加 @ celery_app.task()装饰器
@celery_app.task(name='send_verify_email')
def send_verify_email(to_email,verify_url):
    '''
        发送验证邮箱邮件
    :param to_email: 收件人邮箱
    :param verify_url: 验证链接
    :return:None
    '''

    subject = "美多商城邮箱验证"
    html_message = '<p>尊敬的用户您好！</p>' \
                   '<p>感谢您使用美多商城。</p>' \
                   '<p>您的邮箱为：%s 。请点击此链接激活您的邮箱：</p>' \
                   '<p><a href="%s">%s<a></p>' % (to_email, verify_url, verify_url)
    # send_mail(邮件主题, 普通邮件正文, 发件人邮箱, [收件人邮件], html_message='超文本邮件内容')
    send_mail(subject, '', settings.EMAIL_FROM, [to_email], html_message=html_message )
