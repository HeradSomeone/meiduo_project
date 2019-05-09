from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin


class LoginRequiredView(LoginRequiredMixin,View):
        '''判断类视图是否登录'''
        pass