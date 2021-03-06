from django.contrib.auth.backends import ModelBackend
from django.conf import settings
import re
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer, BadData

from .models import User


def get_user_by_account(account):
    '''
    根据用户名或手机号来查询user
    :param acount: 手机号，用户名
    :return:
    '''
    try:
        if re.match(r'^1[3-9]\d{9}$', account):
            user = User.objects.get(mobile=account)
        else:
            user = User.objects.get(username=account)
    except User.DoesNotExist:
        return None
    else:
        return user # 要返回的是查询出来的user对象，不要写成类了


class UsernameMobileAuthBackend(ModelBackend):
    '''自定义Django的认证后端类'''


    def authenticate(self, request, username=None, password=None, **kwargs):
        '''重写此方法来实现多账号登录'''

        # 根据用户名或手机号来查询user
        user = get_user_by_account(username)

        # 校验密码是否正确
        if user and user.check_password(password):
            return user


def generate_verify_email_url(user):
    """对当前传入的user生成激活邮箱url"""
    serializer = Serializer(secret_key=settings.SECRET_KEY, expires_in=600)
    data = {
        'user_id': user.id,
        'email': user.email

    }

    data_sign = serializer.dumps(data).decode()
    # verify_url = 'http://www.meiduo.site:8000/emails/verification/?token=2'
    verify_url =settings.EMAIL_VERIFY_URL + '?token=' + data_sign
    return verify_url

def check_token_to_user(token):
    '''传入token 返回user'''
    serializer = Serializer(secret_key=settings.SECRET_KEY, expires_in=600)
    try:
        data = serializer.loads(token)
    except BadData:
        return None
    else:
        user_id = data.get('user_id')
        email = data.get('email')
        try:
            user = User.objects.get(id=user_id,email=email)
        except User.DoesNotExist:
            return None
        else:
            return user
