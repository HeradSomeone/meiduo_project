from django.conf.urls import url

from . import views


urlpatterns = [
    # 注册
    url(r'^register/$', views.RegisterView.as_view(), name='register'),

    # 判断用户名是否已注册
    url(r'^usernames/(?P<username>[a-zA-Z0-9_-]{5,20})/count/$', views.UsernameCountView.as_view()),

    # 判断手机是否已注册
    url(r'^mobiles/(?P<mobile>1[3-9]\d{9})/count/$', views.MobileCountView.as_view()),

    # 用户登录
    url(r'^login/$', views.LoginView.as_view(), name='login'),

    # 用户退出
    url(r'^logout/$', views.LogoutView.as_view(), name='logout'),

    # 用户个人中心
    url(r'^info/$', views.UserInfoView.as_view(), name='info'),

    # 添加邮箱
    url(r'^emails/$', views.EmailView.as_view(), name='emails'),

    # 激活邮箱
    url(r'^emails/verification/$', views.VerifyEmailView.as_view()),

    # 收货地址
    url(r'^addresses/$', views.AddressView.as_view(), name='address'),

    # 创建收货地址
    url(r'^addresses/create/$', views.CreateAddressView.as_view()),

    # 修改及删除收货地址
    url(r'^addresses/(?P<address_id>\d+)/$', views.UpdateDestroyAddressView.as_view()),

    # 设置默认地址
    url(r'^addresses/(?P<address_id>\d+)/default/$', views.DefaultAddressView.as_view()),

    # 修改地址标题
    url(r'^addresses/(?P<address_id>\d+)/title/$', views.UpdateTitleAddressView.as_view()),

    # 修改密码
    url(r'^password/$', views.ChangePasswordView.as_view()),

    # 找回密码页面展示
    url(r'^find_password/$', views.ShowFindPassword.as_view()),

    # 验证用户名
    url(r'^accounts/(?P<username>[a-zA-Z0-9_-]{5,20})/sms/token/$', views.CheckUsername.as_view()),

    # 发送手机验证码
    url(r'^sms_codes/$', views.MobileCode.as_view()),

    # 校验验证码
    url(r'^accounts/(?P<username>[a-zA-Z0-9_-]{5,20})/password/token/$', views.CheckMobile.as_view()),

    # 设置新密码
    url(r'^users/(?P<user_id>\d+)/password/$', views.SetNewPwd.as_view()),

    # 用户浏览记录
    url(r'^browse_histories/$', views.UserBrowseHistory.as_view()),

    # 订单中心
    url(r'^orders/info/(?P<page_num>\d+)/$', views.UserOrderInfoView.as_view()),

]