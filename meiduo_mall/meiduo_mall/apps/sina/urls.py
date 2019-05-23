from django.conf.urls import url
from . import views


urlpatterns = [

    # 提供新浪登录连接
    url(r'^sina/authorize/$', views.SinaURLVIew.as_view()),

    # 提供回调连接
    url(r'^sina_callback/$', views.SinaUserView.as_view()),

    # 绑定连接
    # url(r'^oauth/sina/user/$', views.BandUser.as_view()),

]