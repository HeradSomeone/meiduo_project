from django.shortcuts import render
from django.views import View
from QQLoginTool.QQtool import OAuthQQ
from django.conf import settings
from django import http
from oauth.models import OAuthQQUser
import logging
from meiduo_mall.utils.response_code import RETCODE
from django.contrib.auth import login
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


            return render(request, 'oauth_callback.html')
        else:
            # 如果在OAuthQQUser表中查询到openid，说明是已经绑定过的美多用户的QQ
            # 直接登录成功：状态保持

            user = oauth_model.user
            login(request,user)

        return http.JsonResponse({'openid':openid})
