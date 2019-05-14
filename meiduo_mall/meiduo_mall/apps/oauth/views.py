from django.shortcuts import render,redirect
from django.views import View
from django.conf import settings
from django import http
import logging, re
from django.contrib.auth import login
from django_redis import get_redis_connection

from QQLoginTool.QQtool import OAuthQQ

from carts.utils import merge_cart_cookie_to_redis
from oauth.models import OAuthQQUser
from meiduo_mall.utils.response_code import RETCODE
from oauth.utils import generate_openid_signature, check_openid_sign
from users.models import User

logger = logging.getLogger('django')

class OAuthURLView(View):
    '''提供qq登录链接'''
    def get(self, request):

        # 提取前端用查询参数传入的next参数，记录用户从哪里去到login界面
        next = request.GET.get('next','/')

        # 拼接QQ登录链接
        # oauth = OAuthQQ(client_id='appid', client_secret='appkey', redirect_uri='授权成功回调地址', state='记录来源')
        # https://graph.qq.com/oauth2.0/authorize?response_type=code&client_id=123&redirect_uri=xxx&state=next
        oauth = OAuthQQ(client_id = settings.QQ_CLIENT_ID,
                        client_secret = settings.QQ_CLIENT_SECRET,
                        redirect_uri = settings.QQ_REDIRECT_URI,
                        state = next
                        )

        login_url = oauth.get_qq_url()

        # 响应json数据
        return http.JsonResponse({'login_url':login_url})


class OAuthUserView(View):
    '''QQ回调处理'''
    def get(self, request):
        # 获取查询字符串中的code
        code = request.GET.get('code')
        state = request.GET.get('state')
        # 创建QQ登录SDK对象
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI,
                        state=state
                        )
        try:
            # 调用SDK中的get_access_token(code)得到access_token
            access_token = oauth.get_access_token(code)

            # 调用SDK中的get_openid(access_token)得到openid
            openid = oauth.get_open_id(access_token)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code':RETCODE.SERVERERR,'errmsg':'QQ服务器异常'})

        try:
            # 在OAuthQQUser表中查询openid
            oauth_model = OAuthQQUser.objects.get(openid=openid)

        except OAuthQQUser.DoesNotExist:
            # 如果在OAuthQQUser表中未查询到openid，没绑定 说明是第一次QQ登录，创建一个新的美多用户和QQ的openid绑定
            # 先对openid加密
            openid = generate_openid_signature(openid)

            # 创建一个新的用户和openid进行绑定

            return render(request, 'oauth_callback.html', {'openid':openid})
        else:
            # 如果在OAuthQQUser表中查询到openid，说明是已经绑定过的美多用户的QQ
            # 直接登录成功：状态保持

            user = oauth_model.user
            login(request,user)

            # 存储cookie，再重定向到state参数记录的界面或首页
            next = state
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
        openid = check_openid_sign(openid)
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
        OAuthQQUser.objects.create(
            user=user,
            openid=openid,
        )

        # 重定向
        login(request,user)
        response = redirect(request.GET.get('state'))
        response.set_cookie('username', user.username, max_age=settings.SESSION_COOKIE_AGE)
        # 登录成功时 合并购物车
        merge_cart_cookie_to_redis(request, user, response)
        return response