from django.contrib.auth.backends import ModelBackend
import re
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