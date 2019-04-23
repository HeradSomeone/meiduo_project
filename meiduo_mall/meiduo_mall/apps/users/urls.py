from django.conf.urls import url

from . import views


urlpatterns = [
    # 注册
    url(r'^register/$', views.RegisterView.as_view()),

    # 判断用户名是否已注册
    url(r'^usernames/(?P<username>[a-zA-Z0-9_-]{5,20})/count/$', views.UsernameCountView.as_view()),

    # 判断手机是否已注册
    url(r'^mobiles/(?P<mobile>1[3-9]\d{9})/count/$', views.MobileCountView.as_view()),

]