import re

from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.views import View
from django.conf import settings
from django import http
import logging

from django_redis import get_redis_connection

from carts.utils import merge_cart_cookie_to_redis
from sina.models import OAuthSINAUser
from sina.utils import generate_uid_signature, check_uid_sign
from users.models import User
from .sinaweibopy3 import APIClient


logger = logging.getLogger('django')


class SinaURLVIew(View):
    '''提供新浪登录连接'''

    def get(self, request):

        next = request.GET.get('next', '/')
        print(next)
        apiclient = APIClient(

            app_key = settings.SINA_CLIENT_ID,
            app_secret = settings.SINA_CLIENT_SECRET,
            redirect_url = settings.SINA_REDIRECT_URI,
            state = next
            )

        login_url = apiclient.get_authorize_url()
        print(login_url)
        return http.JsonResponse({'login_url': login_url})

class SinaUserView(View):
    '''sina回调处理'''
    def get(self, request):


        code = request.GET.get('code')
        state = request.GET.get('state')

        apiclient = APIClient(
            app_key = settings.SINA_CLIENT_ID,
            app_secret = settings.SINA_CLIENT_SECRET,
            redirect_url = settings.SINA_REDIRECT_URI,
            state = state
            )
        try:
            result = apiclient.request_access_token(code)
            access_token = result.access_token
            openid = result.uid
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'message': 'OK'})

        try:

            oauth_model = OAuthSINAUser.objects.get(uid=openid)

        except OAuthSINAUser.DoesNotExist:

            openid = generate_uid_signature(openid)



            return render(request, 'oauth_callback.html', {'openid':openid})
        else:


            user = oauth_model.user
            login(request,user)


            next = state
            print(next)
            response = redirect(next,'/')
            response.set_cookie('username', user.username, max_age=settings.SESSION_COOKIE_AGE)
            # 登录成功时 合并购物车
            merge_cart_cookie_to_redis(request, user, response)
            return response


    def post(self,request):

        # 接收数据
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        sms_code = request.POST.get('sms_code')
        openid = request.POST.get('openid')

        # 校验
        if all([mobile, password, sms_code, openid]) is False:
            return http.HttpResponseForbidden('参数不全')

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('您输入的手机号格式不正确')

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.HttpResponseForbidden('请输入8-20位的密码')

        redis_coon = get_redis_connection('verify_code')
        sms_code_server = redis_coon.get('sms_%s' % mobile)  # 获取redis中的短信验证码

        if sms_code_server is None or sms_code != sms_code_server.decode():
            return http.HttpResponseForbidden('短信验证码有误')

        # 校验openid
        openid = check_uid_sign(openid)
        if openid is None:
            return http.HttpResponseForbidden('openid无效')

        # 绑定用户
        try:
            user = User.objects.get(mobile=mobile)
        except:
            # 绑定的用户是新用户
            user = User.objects.create_user(
                username=mobile,
                password=password,
                mobile=mobile,
            )
        else:
            # 绑定的用户是老用户
            if user.check_password(password) is False:
                return http.HttpResponseForbidden('账号或用户名错误')
        # 用户openid和user绑定一下
        OAuthSINAUser.objects.create(
            user=user,
            uid=openid,
        )

        # 重定向
        login(request,user)
        print(request.GET.get('state'))
        response = redirect(request.GET.get('state'))
        response.set_cookie('username', user.username, max_age=settings.SESSION_COOKIE_AGE)
        # 登录成功时 合并购物车
        merge_cart_cookie_to_redis(request, user, response)
        return response

# class SinaUserView(View):
#     '''sina回调处理'''
#
#     def get(self, request):
#
#         next = request.GET.get('next', '/')
#         code = request.GET.get('code')
#         state = request.GET.get('state')
#
#         apiclient = APIClient(
#
#             app_key=settings.SINA_CLIENT_ID,
#             app_secret=settings.SINA_CLIENT_SECRET,
#             redirect_uri=settings.SINA_REDIRECT_URI,
#             state=next
#         )
#
#         try:
#             result = apiclient.request_access_token(code)
#             access_token = result.access_token
#             uid = result.uid
#         except Exception as e:
#             logger.error(e)
#             return http.JsonResponse({'message':'OK'})
#
#         try:
#             db_uid = OAuthSINAUser.objects.get(uid=uid)
#         except OAuthSINAUser.DoesNotExist:
#
#             uid = generate_uid_signature(uid)
#
#             return render(request, 'sina_callback.html', {'uid':uid})
#         else:
#
#             user = db_uid.user
#             login(request, user)
#
#             next = state
#
#             response = redirect(next, '/')
#             response.set_cookie('username', user.username, max_age=settings.SESSION_COOKIE_AGE)
#
#             merge_cart_cookie_to_redis(request, user, response)
#             return  response
# class BandUser(View):
#     def post(self, request):
#
#         mobile = request.POST.get('mobile')
#         password = request.POST.get('password')
#         sms_code = request.POST.get('sms_code')
#         uid = request.POST.get('uid')
#         access_token = request.POST.get('access_token')
#
#         if all([mobile, password, sms_code, uid,access_token]) is False:
#             return http.HttpResponseForbidden('参数不全')
#
#         if not re.match(r'^1[3-9]\d{9}$', mobile):
#             return http.HttpResponseForbidden('您输入的手机号格式不正确')
#
#         if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
#             return http.HttpResponseForbidden('请输入8-20位的密码')
#
#         redis_coon = get_redis_connection('verify_code')
#         sms_code_redis = redis_coon.get('sms_%s' % mobile)
#
#         if sms_code_redis is None or sms_code != sms_code_redis.decode():
#             return http.HttpResponseForbidden('短信验证码有误')
#
#         # 校验openid
#         openid = check_uid_sign(uid)
#         if openid is None:
#             return http.HttpResponseForbidden('openid无效')
#
#         # 绑定用户
#         try:
#             user = User.objects.get(mobile=mobile)
#         except:
#             # 绑定的用户是新用户
#             user = User.objects.create_user(
#                 username=mobile,
#                 password=password,
#                 mobile=mobile,
#             )
#         else:
#             # 绑定的用户是老用户
#             if user.check_password(password) is False:
#                 return http.HttpResponseForbidden('账号或用户名错误')
#         # 用户openid和user绑定一下
#         OAuthSINAUser.objects.create(
#             user=user,
#             uid=uid,
#         )
#
#         # 重定向
#         login(request,user)
#         response = redirect(request.GET.get('state'))
#         response.set_cookie('username', user.username, max_age=settings.SESSION_COOKIE_AGE)
#         # 登录成功时 合并购物车
#         merge_cart_cookie_to_redis(request, user, response)
#         return response