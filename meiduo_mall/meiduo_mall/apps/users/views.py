import re
from . models import User
from django.shortcuts import render, redirect
from django import http
from django.views import View
from django.db import DatabaseError
import logging
from django.contrib.auth import login
from meiduo_mall.utils.response_code import RETCODE

logger = logging.getLogger('django') # 创建日志输出器
class RegisterView(View):
    "注册"

    def get(self, request):
        '''提供注册界面'''

        return render(request, 'register.html')


    def post(self, request):
        '''用户注册功能'''

        # 接收前端传入的表单数据：username， password， password2， sms_code， mobile， allow
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        sms_code = request.POST.get('sms_code')
        mobile = request.POST.get('mobile')
        allow = request.POST.get('allow')
        # 校验数据前端传入数据是否符合要求 [ ]中数据任一为 None, False, '' all返回False
        if all([username, password, password2, sms_code, mobile, allow]) is False:

            return http.HttpResponseForbidden('缺少必传参数')

        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return http.HttpResponseForbidden('请输入5-20个字符的用户名')

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.HttpResponseForbidden('请输入8-20位的密码')

        if password != password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        if not re.match(r'^1[345789]\d{9}$', mobile):
            return http.HttpResponseForbidden('您输入的手机号格式不正确')

        # TODO 短信验证码校验

        # 创建一个user

        # create_user 可以自动对password进行加密
        try:
            user = User.objects.create_user(
                username = username,
                password = password,
                mobile = mobile,

            )
        except DatabaseError as e:

            logger.error(e)
            return render(request, 'register.html', {'register_errmsg': '用户注册失败'})


        # 状态保持, 注册成功直接登录

        login(request, user)    # 存储用户的ID到session中记录它到登录状态



        # 重定向到首页

        return redirect('/')


class UsernameCountView(View):
    '''判断用户名是否已注册'''

    def get(self, request, username):

        # 查询当前用户名的个数 要么0要么1 1代表重复
        count = User.objects.filter(username=username).count()
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK','count': count})


class MobileCountView(View):
    '''判断手机号是否已注册'''

    def get(self, request, mobile):
        # 查询当前用户名的个数 要么0要么1 1代表重复
        count = User.objects.filter(mobile=mobile).count()
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'count': count})
