import os

from alipay import AliPay
from django.conf import settings
from django.shortcuts import render
from django.views import View
from django import http

from meiduo_mall.utils.response_code import RETCODE
from meiduo_mall.utils.views import LoginRequiredView
from orders.models import OrderInfo
from payment.models import Payment


class PaymentView(LoginRequiredView):
    '''订单支付功能'''

    def get(self, request, order_id):
        '''查询支付的订单信息'''
        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, status=OrderInfo.ORDER_STATUS_ENUM['UNPAID'])
        except OrderInfo.DoesNotExist:
            return http.HttpResponseForbidden('订单信息有误')

        # 创建支付宝支付对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),"keys/alipay_public_key.pem"),
            sign_type="RSA2",
            debug=settings.ALIPAY_DEBUG
        )

        # 生成登录支付宝连接
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(order.total_amount),
            subject="美多商城%s" % order_id,
            return_url=settings.ALIPAY_RETURN_URL,
        )

        # 响应登录支付宝连接
        # 真实环境电脑网站支付网关：https://openapi.alipay.com/gateway.do? + order_string
        # 沙箱环境电脑网站支付网关：https://openapi.alipaydev.com/gateway.do? + order_string
        alipay_url = settings.ALIPAY_URL + "?" + order_string
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'alipay_url': alipay_url})


class PaymentStatusView(LoginRequiredView):
    '''校验支付结果，及修改保存订单'''
    def get(self,request):
        # 获取查询参数
        query_dict = request.GET
        # 将QueryDict类型转换成字典
        data = query_dict.dict()
        # 将字典中的sign移除
        sign = data.pop('sign')

        # 创建alipay对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys/app_private_key.pem'),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),'keys/alipay_public_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )

        # 调用它的verify方法校验支付结果
        success = alipay.verify(data, sign)
        if success:
            # 保存支付宝交易号和美多订单号
            order_id = data.get('out_trade_no')
            trade_id = data.get('trade_no')
            try:
                Payment.objects.get(order_id=order_id, trade_id=trade_id)
            except Payment.DoesNotExist:
                # 保存支付结果
                Payment.objects.create(
                    order_id=order_id,
                    trade_id=trade_id
                )

                # 修改美多订单状态
                OrderInfo.objects.filter(user=request.user, order_id=order_id,
                                         status=OrderInfo.ORDER_STATUS_ENUM['UNPAID']).update(
                                         status=OrderInfo.ORDER_STATUS_ENUM['UNCOMMENT']
                                        )
            # 响应
            return render(request, 'pay_success.html', {'trade_id': trade_id})
        else:
            return http.HttpResponseForbidden('非法请求')