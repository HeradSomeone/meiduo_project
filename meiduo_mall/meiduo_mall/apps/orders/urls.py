from django.conf.urls import url
from . import views


urlpatterns = [

    # 结算订单
    url(r'^orders/settlement/$', views.OrderSettlementView.as_view()),

    # 提交订单
    url(r'^orders/commit/$', views.OrderCommitView.as_view()),

    # 提交成功展示
    url(r'^orders/success/$', views.OrderSuccessView.as_view()),
]