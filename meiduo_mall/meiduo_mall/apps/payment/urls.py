from django.conf.urls import url
from . import views


urlpatterns = [

    # 订单支付
    url(r'^payment/(?P<order_id>\d+)/$', views.PaymentView.as_view()),
    # 支付信息
    url(r'^payment/status/$', views.PaymentStatusView.as_view()),
]