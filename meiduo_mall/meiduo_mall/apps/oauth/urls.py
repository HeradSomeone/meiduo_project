from django.conf.urls import url
from . import views


urlpatterns = [

    # 获取QQ登录页面
    url(r'^qq/authorization/$', views.OAuthURLView.as_view()),

    # 获取回调页面
    url(r'^oauth_callback/$', views.OAuthUserView.as_view()),
]