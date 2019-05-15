import json
from decimal import Decimal

from django import http
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django_redis import get_redis_connection
from django.db import transaction

from meiduo_mall.utils.response_code import RETCODE
from goods.models import SKU
from users.models import Address
from .models import OrderInfo,OrderGoods
from meiduo_mall.utils.views import LoginRequiredView


class OrderSettlementView(View):
    '''订单结算'''
    def get(self, request):
        '''提供订单结算界面'''

        # 获取当前登录用户的所有收货地址
        user = request.user
        addresses = Address.objects.filter(user=user, is_deleted=False)
        # 如果有收货地址什么也不做,没有收货地址把变量设置为None
        addresses = addresses if addresses.exists() else None
        # 创建redis连接
        redis_coon = get_redis_connection('carts')
        # 获取hash所有数据{sku_id: count}
        redis_cart = redis_coon.hgetall('carts_%s' % user.id)
        # 获取set集合数据{sku_id}
        cart_selected = redis_coon.smembers('selected_%s' % user.id)
        # 准备一个字典,用来装勾选商品id及count  {1: 2}
        cart_dict = {}
        # 遍历set集合
        # 将勾选的商品sku_id 和count装入字典,并都转换为int类型
        for sku_id_bytes in cart_selected:
            cart_dict[int(sku_id_bytes)] = int(redis_cart[sku_id_bytes])

        # 通过set集合中的sku_id查询到对应的所有sku模型
        sku_qs = SKU.objects.filter(id__in=cart_dict.keys())
        # 记录总数量
        total_count = 0
        # 商品总价
        total_amount = Decimal('0.00')
        # 遍历sku_qs查询集给每个sku模型多定义count和amount属性
        for sku in sku_qs:
            # 获取当前商品的购买数量
            count = cart_dict[sku.id]
            # 把当前商品购物车数据绑定到sku模型对象上
            sku.count = count
            sku.amount = sku.price * count
            # 累加购买商品总数量
            total_count += count
            # 累加商品总价
            total_amount += sku.amount
        # 运费
        freight = Decimal('10.00')
        # 渲染数据
        '''
            'addresses': addresses,  # 用户收货地址
            'skus': sku_qs,  # 勾选的购物车商品数据
            'total_count': total_count,  # 勾选商品总数量
            'total_amount': total_amount,  # 勾选商品总价
            'freight': freight,  # 运费
            'payment_amount': total_amount + freight  # 实付款
        '''

        context = {

            'addresses': addresses,
            'skus': sku_qs,
            'total_count': total_count,
            'total_amount': total_amount,
            'freight': freight,
            'payment_amount': total_amount + freight

        }
        return render(request, 'place_order.html', context)


class OrderCommitView(LoginRequiredView):
    '''订单提交'''

    def post(self, request):
        """保存订单信息和订单商品信息"""

        # 获取当前要保存的订单信息
        user = request.user
        json_dict = json.loads(request.body.decode())
        address_id = json_dict.get('address_id')
        pay_method = json_dict.get('pay_method')
        # 校验
        if all([address_id, pay_method]) is False:
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return http.HttpResponseForbidden('address不存在')

        if int(pay_method) not in OrderInfo.PAY_METHODS_ENUM.values():
            return http.HttpResponseForbidden('付款方式有误')

        # 生成订单编号 年月日时分秒+user.id
        order_id = timezone.now().strftime('%Y%m%d%H%M%S') + ('%09d' % user.id)

        # 订单状态
        status = OrderInfo.ORDER_STATUS_ENUM['UNPAID'] \
                if pay_method == OrderInfo.PAY_METHODS_ENUM['ALIPAY'] \
                else OrderInfo.ORDER_STATUS_ENUM['UNCOMMENT']

        # 开启事物
        with transaction.atomic():
            # 创建保存点
            save_id = transaction.savepoint()
            # 暴力回滚
            try:
                # 保存生成订单

                order = OrderInfo.objects.create(

                    user = user,
                    order_id = order_id,
                    address = address,
                    total_count = 0,
                    total_amount = Decimal('0.00'),
                    freight = Decimal('10.00'),
                    pay_method = pay_method,
                    status=status
                )
                # 连接redis服务器
                redis_coon = get_redis_connection('carts')

                # 获取hash 和 set 中所有数据
                redis_cart = redis_coon.hgetall('carts_%s' % user.id)

                cart_selected = redis_coon.smembers('selected_%s' % user.id)

                cart_dict = {}
                # 遍历set把要购买的sku_id和count包装到一个新字典中 组建新的已勾选{sku_id：count} 字典
                for sku_id_bytes in cart_selected:

                    cart_dict[int(sku_id_bytes)] = int(redis_cart[sku_id_bytes])
                # 遍历用来包装所有要购买商品的字典
                for sku_id in cart_dict.keys():
                    while True:
                    # 通过sku_id获取到sku模型
                        sku = SKU.objects.get(id=sku_id)
                        # 获取当前商品要购买的数量
                        buy_count = cart_dict[sku_id]
                        # 获取当前商品的库存和销量
                        origin_stock = sku.stock
                        origin_sales = sku.sales

                        # 判断库存
                        if buy_count > origin_stock:
                            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '库存不足'})

                        # 对数据库中库存和销量进行计算 并修改
                        new_stock = origin_stock - buy_count
                        new_sales = origin_sales + buy_count
                        # sku.stock = new_stock
                        # sku.sales = new_sales
                        # sku.save()
                        result = SKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                        # 如果下单失败，但是库存足够时，继续下单，直到下单成功或者库存不足为止
                        if result == 0:
                            continue

                        sku.spu.sales += buy_count
                        sku.spu.save()

                        # 存储订单商品记录
                        OrderGoods.objects.create(

                            order = order,
                            sku = sku,
                            count = buy_count,
                            price = sku.price
                        )
                        order.total_count += buy_count
                        order.total_amount += (order.total_count * sku.price)
                        # 下单成功或失败跳出循环
                        break
                order.total_amount += order.freight
                order.save()
            except Exception as e:
                # 报错即回滚
                transaction.rollback(save_id)

                # 订单提交成功，提交事物
                transaction.savepoint_commit(save_id)
                # 删除已购买数据
            pl = redis_coon.pipeline()

            pl.hdel('carts_%s' % user.id,*cart_selected)
            pl.delete('selected_%s' % user.id)
            pl.execute()
            # 响应
            return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'order_id': order_id})


class OrderSuccessView(View):
    '''支付成功展示'''

    def get(self, request):

        order_id = request.GET.get('order_id')
        payment_amount = request.GET.get('payment_amount')
        pay_method = int(request.GET.get('pay_method'))


        try:
            order = OrderInfo.objects.get(order_id=order_id, pay_method=pay_method,total_amount=payment_amount)
        except Exception as e:
            print(e)
            return http.HttpResponseForbidden('订单有误')

        context = {

            'order_id': order_id,
            'payment_amount': payment_amount,
            'pay_method': pay_method

        }

        return render(request, 'order_success.html', context)



